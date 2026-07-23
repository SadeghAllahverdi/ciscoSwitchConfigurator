import re
import ipaddress
from ciscoconfparse2 import CiscoConfParse
from back.data_models import switch_device, vlan, svi, interface, port_channel, static_route, back_up, conf

# values the schema accepts. anything else coming from a real config gets
# sanitized here so an insert never dies on a CHECK constraint.
ALLOWED_SPEEDS = {"auto", "10", "100", "1000", "2500", "5000", "10000", "25000", "40000", "100000"}
ALLOWED_DUPLEX = {"auto", "half", "full"}
ALLOWED_LACP_MODES = {"active", "passive", "on"}
ALLOWED_STP_TYPES = {"edge", "network", "normal"}


def _parse_vlan_id(text: str):
    # returns a valid vlan id (1-4094) or None
    try:
        vid = int(text)
    except ValueError:
        return None
    if 1 <= vid <= 4094:
        return vid
    return None


def _normalize_stp_port_type(line: str):
    # "spanning-tree port type edge trunk" -> "edge"  (nxos edge trunk ports)
    rest = line.removeprefix("spanning-tree port type ").strip()
    first = rest.split()[0] if rest.split() else ""
    if first in ALLOWED_STP_TYPES:
        return first
    return None


def _merge_allowed_vlans(current: str, line: str):
    # handles plain / add / none forms of "switchport trunk allowed vlan ..."
    rest = line.removeprefix("switchport trunk allowed vlan ").strip()
    if rest.startswith("add "):
        extra = rest.removeprefix("add ").strip()
        return f"{current},{extra}" if current else extra
    if rest == "none":
        return ""
    if rest.startswith(("remove ", "except ")):
        # cannot represent subtraction in a plain list, keep what we have
        print(f"unsupported allowed vlan form: {line}. keeping previous list")
        return current
    return rest


def _looks_like_dotted_quad(text: str):
    return re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", text) is not None


def _parse_route_tokens(tokens: list[str], vrf: str = ""):
    # tokens = everything after "ip route". returns a static_route or None.
    i = 0
    # ios: "ip route vrf NAME dest mask next-hop ..."
    if len(tokens) >= 2 and tokens[0] == "vrf":
        vrf = tokens[1]
        i = 2

    if len(tokens) - i < 2:
        return None

    dest = tokens[i]
    i += 1

    # ios style destination + netmask -> convert to prefix notation
    if "/" not in dest and _looks_like_dotted_quad(dest) and i < len(tokens) and _looks_like_dotted_quad(tokens[i]):
        try:
            net = ipaddress.ip_network(f"{dest}/{tokens[i]}", strict=False)
            dest = str(net)
            i += 1
        except ValueError:
            pass

    if i >= len(tokens):
        return None

    next_hop = tokens[i]
    i += 1

    new_route = static_route(destination_network=dest, next_hop=next_hop, vrf=vrf)

    rest = tokens[i:]
    j = 0
    while j < len(rest):
        tok = rest[j]
        if tok == "track" and j + 1 < len(rest) and rest[j + 1].isdigit():
            track = int(rest[j + 1])
            if 1 <= track <= 500:
                new_route.track = track
            j += 2
        elif tok in ("name", "tag"):
            # "name FOO" / "tag 5" carry a value token we must not misread
            j += 2
        elif tok.isdigit() and new_route.admin_distance is None:
            ad = int(tok)
            if 1 <= ad <= 254:
                new_route.admin_distance = ad
            j += 1
        else:
            j += 1

    return new_route


def parse_conf(raw_switch_config: str, switch: switch_device):
    parsed_switch_conf = CiscoConfParse(config=raw_switch_config)
    switch_conf = conf(switch=switch)

    # switch
    hostname = parsed_switch_conf.re_match_iter_typed(regexspec=r"^hostname\s+(\S+)", group=1, result_type=str, default="")
    if not hostname:
        # nxos often uses "switchname" instead of "hostname"
        hostname = parsed_switch_conf.re_match_iter_typed(regexspec=r"^switchname\s+(\S+)", group=1, result_type=str, default="UNKNOWN_HOSTNAME")
    switch_conf.switch.hostname = hostname
    switch_conf.switch.location = parsed_switch_conf.re_match_iter_typed(regexspec=r"^snmp-server\s+location\s+(.+)", group=1, result_type=str, default="UNKNOWN_LOCATION")

    # vlans
    vlans: dict[int, vlan] = {}
    for obj in parsed_switch_conf.find_objects(r"^vlan\s+"):
        vlan_line = obj.text.strip()
        id_part = vlan_line.split(sep=" ", maxsplit=1)[1].strip()
        # nxos list/range line, e.g. "vlan 1,55,200-205"
        if not obj.children:
            for vlan_id in id_part.split(sep=","):
                vlan_id = vlan_id.strip()

                if "-" in vlan_id:
                    a, b = vlan_id.split(sep="-", maxsplit=1)
                    try:
                        for vid in range(int(a), int(b) + 1):
                            if _parse_vlan_id(str(vid)) is not None:
                                vlans.setdefault(vid, vlan(vlan_id=vid))
                    except ValueError:
                        print(f"weird vlan range: {vlan_id}. dropping it")
                else:
                    vid = _parse_vlan_id(vlan_id)
                    if vid is not None:
                        vlans.setdefault(vid, vlan(vlan_id=vid))
                    else:
                        print(f"weird vlan id: {vlan_id}. dropping it")
            continue
        # block with children (name / state / shutdown)
        vid = _parse_vlan_id(id_part.split()[0])
        if vid is None:
            print(f"weird vlan line's id part: {id_part}. dropping it")
            continue
        v = vlans.setdefault(vid, vlan(vlan_id=vid))
        # adding vlan info
        for child in obj.children:
            line = child.text.strip()
            if line.startswith("name "):
                v.name = line.removeprefix("name ").strip()
            elif line == "state suspend":
                v.state = "suspend"
            elif line == "shutdown":
                v.shutdown = True

    # interfaces, virtual interfaces, port channels
    switch_conf.svis = []
    switch_conf.interfaces = []
    switch_conf.port_channels = []

    for obj in parsed_switch_conf.find_objects(r"^interface\s+"):
        interface_line = obj.text.strip()
        interface_name = interface_line.split(sep=None, maxsplit=1)[1]

        # virtual interface
        if interface_name.lower().startswith("vlan"):
            match = re.search(r"(\d+)\s*$", interface_name)
            if not match:
                print(f"weird virtual interface: {interface_name}. dropping it")
                continue
            vlan_id = _parse_vlan_id(match.group(1))
            if vlan_id is None:
                print(f"weird virtual interface vlan id: {interface_name}. dropping it")
                continue

            new_svi = svi(vlan_ref_id=vlan_id)
            # adding vi info
            for child in obj.children:
                line = child.text.strip()
                if line.startswith("description "):
                    new_svi.description = line.removeprefix("description ").strip()
                elif line.startswith("vrf member "):
                    new_svi.vrf = line.removeprefix("vrf member ").strip()
                elif line.startswith("vrf forwarding "):
                    new_svi.vrf = line.removeprefix("vrf forwarding ").strip()
                elif line.startswith("ip vrf forwarding "):
                    new_svi.vrf = line.removeprefix("ip vrf forwarding ").strip()
                elif line.startswith("ip address "):
                    rest = line.removeprefix("ip address ").strip()
                    if rest.endswith(" secondary"):
                        new_svi.secondary_ip_address = rest.removesuffix(" secondary").strip()
                    else:
                        new_svi.primary_ip_address = rest
                elif re.fullmatch(r"hsrp\s+\d+", line):
                    # nxos: "hsrp 10" block with "ip <vip>" inside
                    group = int(line.split()[1])
                    if 0 <= group <= 4095:
                        new_svi.hsrp_group = group
                        for sub in child.children:
                            sub_line = sub.text.strip()
                            m = re.fullmatch(r"ip\s+(\d{1,3}(?:\.\d{1,3}){3})", sub_line)
                            if m:
                                new_svi.hsrp_virtual_ip = m.group(1)
                elif line.startswith("standby "):
                    # ios: "standby 10 ip 192.168.1.254"
                    parts = line.split()
                    if len(parts) >= 4 and parts[1].isdigit() and parts[2] == "ip":
                        group = int(parts[1])
                        if 0 <= group <= 4095:
                            new_svi.hsrp_group = group
                            new_svi.hsrp_virtual_ip = parts[3]
                elif line.startswith("mtu "):
                    try:
                        mtu = int(line.split()[1])
                        if 576 <= mtu <= 9216:
                            new_svi.mtu = mtu
                        else:
                            print(f"svi mtu out of supported range: {line}. keeping default")
                    except (ValueError, IndexError):
                        print(f"weird svi mtu: {line}. dropping it")
                elif line == "shutdown":
                    new_svi.shutdown = True
                elif line == "no shutdown":
                    new_svi.shutdown = False

            switch_conf.svis.append(new_svi)

        # Port-channel (a name with "." is a routed subinterface -> treat as normal interface)
        elif interface_name.lower().startswith("port-channel") and "." not in interface_name:
            match = re.search(r"(\d+)\s*$", interface_name)
            if not match:
                print(f"weird port-channel: {interface_name}. dropping it")
                continue

            new_port_channel = port_channel(po_number=int(match.group(1)))

            # flags to remember what we saw, so we can decide mode at the end
            seen_no_switchport = False
            explicit_mode = None

            # getting port channel data
            for child in obj.children:
                line = child.text.strip()
                if line.startswith("description "):
                    new_port_channel.description = line.removeprefix("description ").strip()
                elif line == "no switchport":
                    seen_no_switchport = True
                elif line.startswith("switchport mode "):
                    mode = line.removeprefix("switchport mode ").strip()
                    if mode in ("access", "trunk"):
                        explicit_mode = mode
                    else:
                        print(f"unsupported port-channel mode: {line}. ignoring it")
                elif line.startswith("switchport trunk allowed vlan "):
                    new_port_channel.allowed_vlan_ids = _merge_allowed_vlans(new_port_channel.allowed_vlan_ids, line)
                elif line.startswith("switchport trunk native vlan "):
                    vid = _parse_vlan_id(line.split()[-1])
                    if vid is not None:
                        new_port_channel.native_vlan_id = vid
                    else:
                        print(f"weird native vlan: {line}. dropping it")
                elif line.startswith("spanning-tree port type "):
                    stp = _normalize_stp_port_type(line)
                    if stp is not None:
                        new_port_channel.stp_port_type = stp
                elif line == "vpc peer-link":
                    new_port_channel.vpc_peer_link = True
                elif line.startswith("vpc "):
                    parts = line.split()
                    if len(parts) > 1 and parts[1].isdigit():
                        new_port_channel.vpc_id = int(parts[1])
                elif line == "shutdown":
                    new_port_channel.shutdown = True
                elif line == "no shutdown":
                    new_port_channel.shutdown = False

            # decide the mode after seeing everything
            # 'no switchport' wins over 'switchport mode X' if both appear
            if seen_no_switchport:
                new_port_channel.mode = "routed"
            elif explicit_mode:
                new_port_channel.mode = explicit_mode

            switch_conf.port_channels.append(new_port_channel)

        # interface
        else:
            new_interface = interface(name=interface_name)

            # flags to remember what we saw across the whole interface block
            seen_no_switchport = False
            explicit_mode = None

            for child in obj.children:
                line = child.text.strip()
                if line.startswith("description "):
                    new_interface.description = line.removeprefix("description ").strip()
                elif line == "no switchport":
                    seen_no_switchport = True
                elif line.startswith("switchport mode "):
                    mode = line.removeprefix("switchport mode ").strip()
                    if mode in ("access", "trunk"):
                        explicit_mode = mode
                    else:
                        # dynamic / dot1q-tunnel / fex-fabric / private-vlan ... cannot be stored
                        print(f"unsupported interface mode: {line}. ignoring it")
                elif line.startswith("switchport access vlan "):
                    vid = _parse_vlan_id(line.split()[-1])
                    if vid is not None:
                        new_interface.access_vlan_id = vid
                    else:
                        print(f"weird access vlan: {line}")
                elif line.startswith("switchport voice vlan "):
                    vid = _parse_vlan_id(line.split()[-1])
                    if vid is not None:
                        new_interface.voice_vlan_id = vid
                    else:
                        print(f"weird voice vlan: {line}")
                elif line.startswith("switchport trunk allowed vlan "):
                    new_interface.allowed_vlan_ids = _merge_allowed_vlans(new_interface.allowed_vlan_ids, line)
                elif line.startswith("switchport trunk native vlan "):
                    vid = _parse_vlan_id(line.split()[-1])
                    if vid is not None:
                        new_interface.native_vlan_id = vid
                    else:
                        print(f"weird native vlan: {line}")
                elif line.startswith("channel-group "):
                    parts = line.split()
                    try:
                        po = int(parts[1])
                        if 1 <= po <= 4096:
                            new_interface.port_channel = po
                    except (ValueError, IndexError):
                        print(f"weird channel-group: {line}")
                    if "mode" in parts:
                        try:
                            lacp = parts[parts.index("mode") + 1]
                            if lacp in ALLOWED_LACP_MODES:
                                new_interface.lacp_mode = lacp
                        except IndexError:
                            print(f"weird lacp mode: {line}")
                elif line.startswith("spanning-tree port type "):
                    stp = _normalize_stp_port_type(line)
                    if stp is not None:
                        new_interface.stp_port_type = stp
                elif line.startswith("speed "):
                    tok = line.split()[-1]
                    if tok in ALLOWED_SPEEDS:
                        new_interface.speed = tok
                    else:
                        print(f"unsupported speed: {line}. keeping auto")
                elif line.startswith("duplex "):
                    tok = line.split()[-1]
                    if tok in ALLOWED_DUPLEX:
                        new_interface.duplex = tok
                elif line.startswith("mtu "):
                    try:
                        mtu = int(line.split()[1])
                        if 576 <= mtu <= 9216:
                            new_interface.mtu = mtu
                        else:
                            print(f"mtu out of supported range: {line}. keeping default")
                    except (ValueError, IndexError):
                        print(f"weird mtu: {line}")
                elif line == "shutdown":
                    new_interface.shutdown = True
                elif line == "no shutdown":
                    new_interface.shutdown = False

            # decide the mode after seeing everything in the block.
            # an explicit "switchport mode X" wins over guesses from other lines.
            if explicit_mode:
                new_interface.mode = explicit_mode
            elif seen_no_switchport:
                new_interface.mode = "routed"
            elif new_interface.access_vlan_id is not None:
                new_interface.mode = "access"
            elif new_interface.allowed_vlan_ids or new_interface.native_vlan_id is not None:
                new_interface.mode = "trunk"

            switch_conf.interfaces.append(new_interface)

    # static routes
    switch_conf.static_routes = []
    for obj in parsed_switch_conf.find_objects(r"^ip route\s+"):
        if obj.indent > 0:
            continue
        line = obj.text.strip()
        new_route = _parse_route_tokens(line.split()[2:])
        if new_route is None:
            print(f"weird ip route: {line}. dropping it")
            continue
        switch_conf.static_routes.append(new_route)

    # inside "vrf context X" blocks (nxos)
    for vrf_obj in parsed_switch_conf.find_objects(r"^vrf context\s+"):
        vrf_name = vrf_obj.text.strip().removeprefix("vrf context ").strip()
        for child in vrf_obj.children:
            line = child.text.strip()
            if not line.startswith("ip route "):
                continue
            new_route = _parse_route_tokens(line.split()[2:], vrf=vrf_name)
            if new_route is None:
                print(f"weird ip route in vrf {vrf_name}: {line}. dropping it")
                continue
            switch_conf.static_routes.append(new_route)

    # an SVI can only exist if its VLAN exists on the device, so make sure the
    # vlan table has every SVI vlan even when the config did not declare it.
    for s in switch_conf.svis:
        if s.vlan_ref_id not in vlans:
            vlans[s.vlan_ref_id] = vlan(vlan_id=s.vlan_ref_id, note="auto-added: SVI exists for this VLAN")

    switch_conf.vlans = [vlans[k] for k in sorted(vlans.keys())]

    return switch_conf
