from back.cisco_to_db import parse_conf
from back.db_to_cisco import generate_conf
from back.data_models import switch_device

test_configuration = """
hostname test_switch
snmp-server location my test location
vlan 1,55,200,400
vlan 55
  name UPD_MGMT
vlan 200
  name BigLeaf_WAN
vlan 400
  name QNAP_LACP
ip route 0.0.0.0/0 192.168.3.1
ip route 10.99.0.0/16 192.168.3.9 200 track 5
vrf context management
  ip route 0.0.0.0/0 192.168.3.1
interface Vlan1
interface Vlan55
  description MGMT SVI
  ip address 192.168.55.2/24
  ip address 192.168.56.2/24 secondary
  hsrp 300
    ip 192.168.55.1
  no shutdown
interface Vlan700
  description SVI without a declared vlan
  ip address 10.70.0.2/24
interface port-channel10
  description PO-Peer
  switchport
  switchport mode trunk
  spanning-tree port type network
  vpc peer-link
interface port-channel12
  description PO-NetGate
  switchport
  switchport mode trunk
  switchport trunk allowed vlan 55,400
  spanning-tree port type edge
  vpc 12
interface Ethernet1/3
  description NetGate_Uplink
  switchport
  switchport mode trunk
  switchport trunk allowed vlan 55,400
  channel-group 12 mode active
  no shutdown
interface Ethernet1/25
  description U_W_A | Po15
  switchport
  switchport mode trunk
  switchport trunk native vlan 602
  switchport trunk allowed vlan 55
  switchport trunk allowed vlan add 602
  channel-group 15 mode active
  no shutdown
interface Ethernet1/40
  description edge trunk port
  switchport mode trunk
  spanning-tree port type edge trunk
  speed 40000
  no shutdown
"""

ios_test_configuration = """
hostname ios_switch
vlan 10
 name USERS
interface Vlan10
 description users svi
 ip address 10.10.0.2 255.255.255.0
 standby 10 ip 10.10.0.1
interface GigabitEthernet0/1
 switchport mode dynamic desirable
 switchport access vlan 10
ip route 10.50.0.0 255.255.0.0 10.10.0.254
ip route vrf mgmt 0.0.0.0 0.0.0.0 10.99.0.1 name backup
"""

def main():
    sw = switch_device(name="test_device", platform="cisco_nxos")
    # 1. parser check
    cfg = parse_conf(raw_switch_config=test_configuration, switch=sw)
    # metadata check
    assert cfg.switch.hostname == "test_switch" , "hostname mismatch"
    assert cfg.switch.location == "my test location", "location mismatch"
    print("successfully parsed meta data")
    # vlans check (700 is auto-added because interface Vlan700 exists)
    assert len(cfg.vlans) == 5, f"mismatch in number of vlans detected: {[v.vlan_id for v in cfg.vlans]}"
    parsed_vlans = {v.vlan_id: v.name for v in cfg.vlans}
    expected_vlans = {1: "", 55: "UPD_MGMT", 200: "BigLeaf_WAN", 400: "QNAP_LACP", 700: ""}
    assert parsed_vlans == expected_vlans, f"vlan mismatch: got {parsed_vlans}, expected {expected_vlans}"
    print("successfully vlans data")
    # svi checks
    svi55 = next((s for s in cfg.svis if s.vlan_ref_id == 55), None)
    assert svi55 is not None, "SVI Vlan55 was not parsed!"
    assert svi55.primary_ip_address == "192.168.55.2/24", f"svi primary ip mismatch: {svi55.primary_ip_address}"
    assert svi55.secondary_ip_address == "192.168.56.2/24", f"svi secondary ip mismatch: {svi55.secondary_ip_address}"
    assert svi55.hsrp_group == 300, f"svi hsrp group mismatch: {svi55.hsrp_group}"
    assert svi55.hsrp_virtual_ip == "192.168.55.1", f"svi hsrp vip mismatch: {svi55.hsrp_virtual_ip}"
    print("successfully svis data")
    # port channels check
    assert len(cfg.port_channels) == 2, "mismatch in number of port channel detected"
    parsed_pos = {p.po_number:
                  {"mode": "trunk", "allowed_vlan_ids": p.allowed_vlan_ids, "vpc_id": p.vpc_id, "vpc_peer_link": p.vpc_peer_link, "stp_port_type": p.stp_port_type}
                 for p in cfg.port_channels
                 }
    expected_pos = {10:
                     {"mode": "trunk", "allowed_vlan_ids": "", "vpc_id": None, "vpc_peer_link": True, "stp_port_type": "network"},
                    12:
                     {"mode": "trunk", "allowed_vlan_ids": "55,400", "vpc_id": 12, "vpc_peer_link": False, "stp_port_type": "edge"}
                    }
    assert parsed_pos == expected_pos, f"port-channel mismatch:\n  got: {parsed_pos}\n  expected: {expected_pos}"
    print("successfully port channels data")
    # interface checks
    assert len(cfg.interfaces) == 3, "mismatch in number of interfaces detected"
    e_1_3 = next((i for i in cfg.interfaces if i.name == "Ethernet1/3"), None)
    assert e_1_3 is not None, "interface Ethernet1/3 was not parsed!"
    assert e_1_3.mode == "trunk", "interface mode mismatch"
    assert e_1_3.port_channel == 12
    assert e_1_3.lacp_mode == "active"
    e_1_25 = next((i for i in cfg.interfaces if i.name == "Ethernet1/25"), None)
    assert e_1_25.allowed_vlan_ids == "55,602", f"allowed vlan add mismatch: {e_1_25.allowed_vlan_ids}"
    e_1_40 = next((i for i in cfg.interfaces if i.name == "Ethernet1/40"), None)
    assert e_1_40.stp_port_type == "edge", f"'edge trunk' should be stored as 'edge': {e_1_40.stp_port_type}"
    assert e_1_40.speed == "40000", f"speed 40000 should be kept: {e_1_40.speed}"
    print("successfully interfaces data")
    # static routes
    for sr in cfg.static_routes:
        print(f"route: dest={sr.destination_network}, vrf={sr.vrf!r}, next_hop={sr.next_hop}, ad={sr.admin_distance}, track={sr.track}")
    assert any(sr.vrf == "" for sr in cfg.static_routes), "no default vrf route found"
    assert any(sr.vrf == "management" for sr in cfg.static_routes), "no managment vrf route found"
    tracked = next((sr for sr in cfg.static_routes if sr.destination_network == "10.99.0.0/16"), None)
    assert tracked is not None, "tracked route was not parsed"
    assert tracked.admin_distance == 200, f"admin distance mismatch: {tracked.admin_distance}"
    assert tracked.track == 5, f"track mismatch: {tracked.track}"
    print("parser checks pass.")
    # 2. generator check
    cmds = generate_conf(cfg)
    print("\ngenerated config:")
    for line in cmds:
        print(line)

    joined = "\n".join(cmds)
    assert "interface Ethernet1/3" in joined , "missing: interface Ethernet1/3"
    assert "switchport trunk allowed vlan 55,400" in joined, "missing: switchport trunk allowed vlan 55,400"
    assert "channel-group 12 mode active" in joined, "missing: channel-group 12 mode active"
    assert "vpc peer-link" in joined, "missing: vpc peer-link"
    assert "vpc 12" in joined, "missing: vpc 12"
    assert "vrf context management" in joined, "missing vrf context managment"
    assert "feature interface-vlan" in joined, "missing: feature interface-vlan"
    assert "feature hsrp" in joined, "missing: feature hsrp"
    assert "hsrp 300" in joined, "missing: hsrp 300"
    assert "ip address 192.168.56.2/24 secondary" in joined, "missing: secondary ip address"
    assert "ip route 10.99.0.0/16 192.168.3.9 200 track 5" in joined, "missing: tracked route"
    print("\ngenerator checks pass.")

    # 3. ios parser + generator check
    ios_sw = switch_device(name="ios_device", platform="cisco_ios")
    ios_cfg = parse_conf(raw_switch_config=ios_test_configuration, switch=ios_sw)

    ios_svi = next((s for s in ios_cfg.svis if s.vlan_ref_id == 10), None)
    assert ios_svi is not None, "ios SVI Vlan10 was not parsed!"
    assert ios_svi.hsrp_group == 10, f"ios standby group mismatch: {ios_svi.hsrp_group}"
    assert ios_svi.hsrp_virtual_ip == "10.10.0.1", f"ios standby vip mismatch: {ios_svi.hsrp_virtual_ip}"

    g0_1 = next((i for i in ios_cfg.interfaces if i.name == "GigabitEthernet0/1"), None)
    assert g0_1 is not None, "ios interface was not parsed!"
    assert g0_1.mode == "access", f"'switchport mode dynamic' must not be stored, access vlan implies access: {g0_1.mode}"
    assert g0_1.access_vlan_id == 10

    ios_routes = {sr.destination_network: sr for sr in ios_cfg.static_routes}
    assert "10.50.0.0/16" in ios_routes, f"ios mask route not converted to prefix: {list(ios_routes)}"
    assert ios_routes["10.50.0.0/16"].next_hop == "10.10.0.254", "ios route next hop mismatch"
    assert "0.0.0.0/0" in ios_routes, "ios vrf route not parsed"
    assert ios_routes["0.0.0.0/0"].vrf == "mgmt", f"ios route vrf mismatch: {ios_routes['0.0.0.0/0'].vrf}"

    ios_cmds = "\n".join(generate_conf(ios_cfg))
    assert "standby 10 ip 10.10.0.1" in ios_cmds, "missing: ios standby command"
    assert "ip route 10.50.0.0 255.255.0.0 10.10.0.254" in ios_cmds, "ios route not generated in mask form"
    assert "ip route vrf mgmt 0.0.0.0 0.0.0.0 10.99.0.1" in ios_cmds, "missing: ios vrf route"
    assert "feature interface-vlan" not in ios_cmds, "nxos feature command must not appear for ios"
    print("\nios checks pass.")


if __name__ == "__main__":
    main()
