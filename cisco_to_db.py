import re
from ciscoconfparse2 import CiscoConfParse
from data_models import switch_device, vlan, svi, interface, port_channel, static_route, back_up, conf

def parse_conf(raw_switch_config: str, switch: switch_device):
    parsed_switch_conf = CiscoConfParse(config=raw_switch_config)
    switch_conf = conf()

    # switch
    switch_conf.switch.hostname = parsed_switch_conf.re_match_iter_typed(regexspec=r"^hostname\s+(\S+)",group=1,result_type=str, default="UNKNOWN_HOSTNAME")
    switch_conf.switch.location = parsed_switch_conf.re_match_iter_typed(regexspec=r"^snmp-server\s+location\s+(.+)",group=1, result_type=str,default="UNKNOWN_LOCATION")
    # vlans
    vlans: dict[int, vlan] = {}
    for obj in parsed_switch_conf.find_objects(r"^vlan\s+"):
        vlan_line = obj.text.strip()
        id_part = vlan_line.split(sep=" ", maxsplit=1)[1].strip()
        # nxos
        if not obj.children:
            for vlan_id in id_part.split(sep=","):
                vlan_id = vlan_id.strip()

                if "-" in vlan_id:
                    a, b = vlan_id.split(sep="-", maxsplit=1)
                    try:
                        for vid in range(int(a), int(b) + 1):
                            vlans.setdefault(vid, vlan(vlan_id=vid))
                    except ValueError:
                        print(f"weird vlan range: {vlan_id}. dropping it")
                else:
                    try:
                        vid = int(vlan_id)
                        vlans.setdefault(vid, vlan(vlan_id=vid))
                    except ValueError:
                        print(f"weird vlan id: {vlan_id}. dropping it")
            continue
        # ios
        try:
            vid = int(id_part.split()[0])
        except ValueError:
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

    switch_conf.vlans = [vlans[k] for k in sorted(vlans.keys())]

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
            vlan_id = int(match.group(1))

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
                elif line.startswith("ip address "):
                    new_svi.primary_ip_address = line.removeprefix("ip address ").strip()
                elif line.startswith("mtu "):
                    try:
                        new_svi.mtu = int(line.split()[1])
                    except (ValueError, IndexError):
                        print(f"weird svi mtu: {line}. dropping it")
                elif line == "shutdown":
                    new_svi.shutdown = True
                elif line == "no shutdown":
                    new_svi.shutdown = False

            switch_conf.svis.append(new_svi)

        # Port-channel
        elif "port-channel" in interface_name.lower():
            match = re.search(r"(\d+)\s*$", interface_name)
            if not match:
                print(f"weird port-channel: {interface_name}. dropping it")
                continue

            new_port_channel = port_channel(po_number=int(match.group(1)))

            # flags to remember what we saw, so we can decide mode at the end
            seen_no_switchport = False

            # getting port channel data
            for child in obj.children:
                line = child.text.strip()
                if line.startswith("description "):
                    new_port_channel.description = line.removeprefix("description ").strip()
                elif line == "no switchport":
                    seen_no_switchport = True
                elif line.startswith("switchport mode "):
                    mode = line.split()[-1]
                    if mode in ("access", "trunk"):
                        new_port_channel.mode = mode
                elif line.startswith("switchport trunk allowed vlan "):
                    new_port_channel.allowed_vlan_ids = line.removeprefix("switchport trunk allowed vlan ").strip()
                elif line.startswith("switchport trunk native vlan "):
                    try:
                        new_port_channel.native_vlan_id = int(line.split()[-1])
                    except ValueError:
                        print(f"weird native vlan: {line}. dropping it")
                elif line.startswith("spanning-tree port type "):
                    new_port_channel.stp_port_type = line.split()[-1]
                elif line == "vpc peer-link":
                    new_port_channel.vpc_peer_link = True
                elif line.startswith("vpc "):
                    parts = line.split()
                    if len(parts) > 1 and parts[1].isdigit():
                        new_port_channel.vpc_id = int(parts[1])
                elif line == "shutdown":
                    new_port_channel.shutdown = True

            # decide the mode after seeing everything
            # 'no switchport' wins over 'switchport mode X' if both appear
            if seen_no_switchport:
                new_port_channel.mode = "routed"

            switch_conf.port_channels.append(new_port_channel)

        # interface
        else:
            new_interface = interface(name=interface_name)

            # flags to remember what we saw across the whole interface block
            seen_no_switchport = False

            for child in obj.children:
                line = child.text.strip()
                if line.startswith("description "):
                    new_interface.description = line.removeprefix("description ").strip()
                elif line == "no switchport":
                    seen_no_switchport = True
                elif line.startswith("switchport mode "):
                    new_interface.mode = line.split()[-1]
                elif line.startswith("switchport access vlan "):
                    new_interface.mode = "access"
                    try:
                        new_interface.access_vlan = int(line.split()[-1])
                    except ValueError:
                        print(f"weird access vlan: {line}")

                elif line.startswith("switchport voice vlan "):
                    try:
                        new_interface.voice_vlan = int(line.split()[-1])
                    except ValueError:
                        print(f"weird voice vlan: {line}")

                elif line.startswith("switchport trunk allowed vlan "):
                    new_interface.mode = "trunk"
                    new_interface.allowed_vlan_ids = line.removeprefix(
                        "switchport trunk allowed vlan "
                    ).strip()
                elif line.startswith("switchport trunk native vlan "):
                    try:
                        new_interface.native_vlan_id = int(line.split()[-1])
                    except ValueError:
                        print(f"weird native vlan: {line}")
                elif line.startswith("channel-group "):
                    parts = line.split()
                    try:
                        new_interface.port_channel = int(parts[1])
                    except (ValueError, IndexError):
                        print(f"weird channel-group: {line}")
                    if "mode" in parts:
                        try:
                            new_interface.lacp_mode = parts[parts.index("mode") + 1]
                        except IndexError:
                            print(f"weird lacp mode: {line}")
                elif line.startswith("spanning-tree port type "):
                    new_interface.stp_port_type = line.split()[-1]
                elif line.startswith("speed "):
                    new_interface.speed = line.split()[-1]
                elif line.startswith("duplex "):
                    new_interface.duplex = line.split()[-1]
                elif line.startswith("mtu "):
                    try:
                        new_interface.mtu = int(line.split()[1])
                    except (ValueError, IndexError):
                        print(f"weird mtu: {line}")
                elif line == "shutdown":
                    new_interface.shutdown = True
                elif line == "no shutdown":
                    new_interface.shutdown = False

            # decide the mode after seeing everything in the block
            if new_interface.mode == "unused" and seen_no_switchport:
                new_interface.mode = "routed"

            switch_conf.interfaces.append(new_interface)

    # static routes
    switch_conf.static_routes = []
    for obj in parsed_switch_conf.find_objects(r"^ip route\s+"):
        if obj.indent > 0:
            continue
        line = obj.text.strip()
        parts = line.split()
        if len(parts) < 4:
            print(f"weird ip route: {line}. dropping it")
            continue

        new_route = static_route(
            destination_network=parts[2],
            next_hop=parts[3],
            vrf="",
        )
        rest = parts[4:]
        for i, tok in enumerate(rest):
            if tok.isdigit() and new_route.admin_distance is None:
                new_route.admin_distance = int(tok)
            elif tok == "track" and i + 1 < len(rest) and rest[i + 1].isdigit():
                new_route.track = int(rest[i + 1])

        switch_conf.static_routes.append(new_route)

    # inside "vrf context X" blocks
    for vrf_obj in parsed_switch_conf.find_objects(r"^vrf context\s+"):
        vrf_name = vrf_obj.text.strip().removeprefix("vrf context ").strip()
        for child in vrf_obj.children:
            line = child.text.strip()
            if not line.startswith("ip route "):
                continue

            parts = line.split()
            if len(parts) < 4:
                print(f"weird ip route in vrf {vrf_name}: {line}. dropping it")
                continue

            new_route = static_route(
                destination_network=parts[2],
                next_hop=parts[3],
                vrf=vrf_name,
            )

            rest = parts[4:]
            for i, tok in enumerate(rest):
                if tok.isdigit() and new_route.admin_distance is None:
                    new_route.admin_distance = int(tok)
                elif tok == "track" and i + 1 < len(rest) and rest[i + 1].isdigit():
                    new_route.track = int(rest[i + 1])

            switch_conf.static_routes.append(new_route)

    return switch_conf