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
vrf context management
  ip route 0.0.0.0/0 192.168.3.1
interface Vlan1
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
  switchport trunk allowed vlan 55,602
  channel-group 15 mode active
  no shutdown
"""

def main():
    sw = switch_device(name="test_device", platform="cisco_nxos")
    # 1. parser check
    cfg = parse_conf(raw_switch_config=test_configuration, switch=sw)
    # metadata check
    assert cfg.switch.hostname == "test_switch" , "hostname mismatch"
    assert cfg.switch.location == "my test location", "location mismatch"
    print("successfully parsed meta data")
    # vlans check
    assert len(cfg.vlans) == 4, "mismatch in number of vlans detected"
    parsed_vlans = {v.vlan_id: v.name for v in cfg.vlans}
    expected_vlans = {1: "", 55: "UPD_MGMT", 200: "BigLeaf_WAN", 400: "QNAP_LACP"}
    assert parsed_vlans == expected_vlans, f"vlan mismatch: got {parsed_vlans}, expected {expected_vlans}"
    print("successfully vlans data")
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
    # one interfacen through check
    e_1_3 = next((i for i in cfg.interfaces if i.name == "Ethernet1/3"), None)
    assert e_1_3 is not None, "interface Ethernet1/3 was not parsed!"
    assert e_1_3.mode == "trunk", "in"
    assert e_1_3.port_channel == 12
    assert e_1_3.lacp_mode == "active"
    for i in cfg.interfaces:
        print(i.name, i.mode)
        assert len(cfg.interfaces) == 2, "mismatch in number of interfaces detected"
    
    # static routes 
    for sr in cfg.static_routes:
        print(f"route: dest={sr.destination_network}, vrf={sr.vrf!r}, next_hop={sr.next_hop}")
    assert any(sr.vrf == "" for sr in cfg.static_routes), "no default vrf route found"
    assert any(sr.vrf == "management" for sr in cfg.static_routes), "no managment vrf route found"
    print("\parser checks pass.")
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
    print("\ngenerator checks pass.")


if __name__ == "__main__":
    main()