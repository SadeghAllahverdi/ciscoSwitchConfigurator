from dataclasses import dataclass, field

@dataclass
class switch_device:
    id: int | None = None
    name: str = ""
    hostname: str = ""
    location: str = ""
    ip: str = ""
    mgmt_vrf: str = ""
    platform: str = "cisco_nxos"        # cisco_nxos, cisco_ios, cisco_iosxe
    last_pulled_at: str | None = None
    last_pushed_at: str | None = None
    last_push_status: str = "never"     # never , in_progress, success, failure
    last_push_error: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    note: str = ""

@dataclass
class vlan:
    id: int | None = None
    switch_id: int | None = None
    vlan_id: int = 0
    name: str = ""
    state: str = "active"       # active, suspend
    shutdown: bool = False
    note: str = ""

@dataclass
class svi:
    id: int | None = None
    switch_id: int | None = None
    vlan_ref_id: int = 0
    description: str = ""
    primary_ip_address: str = ""
    secondary_ip_address: str = ""
    hsrp_group: int | None = None
    hsrp_virtual_ip: str = ""
    vrf: str = ""
    mtu: int = 1500
    shutdown: bool = False
    note: str = ""

@dataclass
class interface:
    id: int | None = None
    switch_id: int | None = None
    name: str = ""
    description: str = ""
    mode: str = "unused"       # unused, access, trunk, routed
    access_vlan_id: int | None = None
    voice_vlan_id: int | None = None
    allowed_vlan_ids: str = ""
    native_vlan_id: int | None = None
    port_channel: int | None = None
    lacp_mode: str | None = None
    stp_port_type: str | None = None
    speed: str = "auto"       # auto, 10, 100, 1000, 10000
    duplex: str = ""          # '',  auto, half, full
    mtu: int = 1500
    shutdown: bool = False
    note: str = ""

@dataclass
class port_channel:
    id: int | None = None
    switch_id: int | None = None
    po_number: int = 0
    description: str = ""
    mode: str = "trunk"       # access, trunk, routed
    allowed_vlan_ids: str = ""
    native_vlan_id: int | None = None
    stp_port_type: str = ""   # '', edge, network, normal
    vpc_id: int | None = None
    vpc_peer_link: bool = False
    shutdown: bool = False
    note: str = ""

@dataclass
class static_route:
    id: int | None = None
    switch_id: int | None = None
    destination_network: str = ""
    next_hop: str = ""
    vrf: str = ""
    admin_distance:int | None = None
    track: int | None = None    # track id from 1 to 500
    note: str = ""

@dataclass
class back_up:
    id: int | None = None
    switch_id: int | None = None
    file_path: str = ""
    reason: str = "manual"  # pre-push, post-push, manual, scheduled
    bytes: int = 0
    created_at: str | None = None

@dataclass
class conf: 
    switch: switch_device = field(default_factory=switch_device)
    vlans: list[vlan] = field(default_factory=list)
    svis: list[svi] = field(default_factory=list)
    interfaces: list[interface] = field(default_factory=list)
    port_channels: list[port_channel] = field(default_factory=list)
    static_routes: list[static_route] = field(default_factory=list)

@dataclass
class connection_info:
    ip: str = ""
    username: str = ""
    password: str = ""
    platform: str = "cisco_nxos"  
    secret: str = ""               
    port: int = 22
    timeout: int = 20

@dataclass
class push_result:
    success: bool = False
    error_message: str = ""
    output: str = ""               
    pushed_at: str | None = None   

@dataclass
class pull_result:
    success: bool = False
    error_message: str = ""
    output: str = ""           