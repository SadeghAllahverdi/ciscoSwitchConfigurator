from data_models import switch_device, vlan, svi, interface, port_channel, static_route, back_up, conf

def generate_conf(switch_conf: conf):
    
    output: list[str] = []
    output.append(f"! Config for {switch_conf.switch.name} (platform: {switch_conf.switch.platform})")
    output.append(f"configure terminal")
    # vlans
    for v in switch_conf.vlans:
        output.append(f"vlan {v.vlan_id}")
        if v.name:
            output.append(f"  name {v.name}")
        if v.state == "suspend":
            output.append("  state suspend")
        if v.shutdown:
            output.append("  shutdown")
    # port channels
    for p in switch_conf.port_channels:
        output.append(f"interface port-channel{p.po_number}")
        if p.description:
            output.append(f"  description {p.description}")
        if p.mode == "access":
            output.append("  switchport mode access")
        elif p.mode == "trunk":
            output.append("  switchport mode trunk")
            if p.native_vlan_id is not None:
                output.append(f"  switchport trunk native vlan {p.native_vlan_id}")
            if p.allowed_vlan_ids:
                output.append(f"  switchport trunk allowed vlan {p.allowed_vlan_ids.strip()}")
        elif p.mode == "routed":
            output.append("  no switchport")
        if p.stp_port_type:
            output.append(f"  spanning-tree port type {p.stp_port_type}")
        # nexos specifc
        if switch_conf.switch.platform == "cisco_nxos":
            if p.vpc_peer_link:
                output.append("  vpc peer-link")
            elif p.vpc_id is not None:
                output.append(f"  vpc {p.vpc_id}")
        if p.shutdown:
            output.append("  shutdown")
        else:
            output.append("  no shutdown")
    # interfaces
    for i in switch_conf.interfaces:
        output.append(f"interface {i.name}")
        if i.description:
            output.append(f"  description {i.description}")
        if i.speed and i.speed != "auto":
            output.append(f"  speed {i.speed}")
        if i.duplex and i.duplex != "auto":
            output.append(f"  duplex {i.duplex}")
        if i.mtu is not None:
            output.append(f"  mtu {i.mtu}")
        if i.mode == "access":
            output.append("  switchport")
            output.append("  switchport mode access")
            if i.access_vlan_id is not None:
                output.append(f"  switchport access vlan {i.access_vlan_id}")
            if i.voice_vlan_id is not None:
                output.append(f"  switchport voice vlan {i.voice_vlan_id}")
        elif i.mode == "trunk":
            output.append("  switchport")
            output.append("  switchport mode trunk")
            if i.native_vlan_id is not None:
                output.append(f"  switchport trunk native vlan {i.native_vlan_id}")
            if i.allowed_vlan_ids:
                output.append(f"  switchport trunk allowed vlan {i.allowed_vlan_ids.strip()}")

        elif i.mode == "routed":
            output.append("  no switchport")
        # mode "unused" -> no L2 confi

        if i.stp_port_type:
            output.append(f"  spanning-tree port type {i.stp_port_type}")
        if i.port_channel is not None:
            mode = i.lacp_mode or "active"
            output.append(f"  channel-group {i.port_channel} mode {mode}")
        if i.shutdown:
            output.append("  shutdown")
        else:
            output.append("  no shutdown")
    # virtual interfaces
    for vi in switch_conf.svis:
        output.append(f"interface Vlan{vi.vlan_ref_id}")
        if vi.description:
            output.append(f"  description {vi.description}")
        if vi.vrf:
            # nxos: vrf member X
            if switch_conf.switch.platform == "cisco_nxos":
                output.append(f"  vrf member {vi.vrf}")
            # ios: vrf forwarding X
            else:
                output.append(f"  vrf forwarding {vi.vrf}")
        if vi.primary_ip_address:
            output.append(f"  ip address {vi.primary_ip_address}")
        if vi.secondary_ip_address:
            output.append(f"  ip address {vi.secondary_ip_address} secondary")
        if vi.mtu is not None:
            output.append(f"  mtu {vi.mtu}")
        if vi.hsrp_group is not None and vi.hsrp_virtual_ip:
            output.append(f"  hsrp {vi.hsrp_group}")
            output.append(f"    ip {vi.hsrp_virtual_ip}")
        if vi.shutdown:
            output.append("  shutdown")
        else:
            output.append("  no shutdown")
    # static routes
    for sr in switch_conf.static_routes:
        # nxos
        command_parts = ["ip route"]
        # ios
        if sr.vrf and switch_conf.switch.platform != "cisco_nxos":
            command_parts = ["ip route", f"vrf {sr.vrf}"]
        command_parts.append(sr.destination_network)
        command_parts.append(sr.next_hop)
        if sr.admin_distance is not None:
            command_parts.append(str(sr.admin_distance))
        if sr.track is not None:
            command_parts.append(f"track {sr.track}")
        command = " ".join(command_parts)
        #nxos
        if sr.vrf and switch_conf.switch.platform == "cisco_nxos":
            output.append(f"vrf context {sr.vrf}")
            output.append(f"  {command}")
            output.append("exit")
        #ios
        else:
            output.append(command)

    output.append("end")
    return output