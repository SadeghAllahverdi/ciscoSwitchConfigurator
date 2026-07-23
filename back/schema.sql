-- This file is part of Switch Configurator.

-- switches table
CREATE TABLE IF NOT EXISTS switches (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT NOT NULL UNIQUE
		 CHECK(length(name) > 0 and length(name) <= 64),           -- human readable name
	hostname TEXT NOT NULL DEFAULT '',                             -- hostname or IP address
	location TEXT NOT NULL DEFAULT '',                             -- physical location
	ip TEXT NOT NULL DEFAULT '',                                   -- IP address of the switch
	mgmt_vrf TEXT NOT NULL DEFAULT '',                             -- management IP 
	platform TEXT NOT NULL DEFAULT 'cisco_nxos'
		CHECK(platform IN ('cisco_nxos', 'cisco_ios', 'cisco_iosxe')),
	last_pulled_at TEXT,
	last_pushed_at TEXT,
	last_push_status TEXT NOT NULL DEFAULT 'never'
		 CHECK(last_push_status IN ('never', 'in_progress' ,'success', 'failure')),
	last_push_error TEXT NOT NULL DEFAULT '',
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	note TEXT NOT NULL DEFAULT ''
		 CHECK(length(note) <= 255)
);

-- vlans table
CREATE TABLE IF NOT EXISTS vlans (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	switch_id INTEGER NOT NULL,
	vlan_id INTEGER NOT NULL CHECK(vlan_id >= 1 AND vlan_id <= 4094),
	name TEXT NOT NULL DEFAULT ''
     CHECK(length(name) <= 32),
	state TEXT NOT NULL DEFAULT 'active'
		 CHECK(state IN ('active', 'suspend')),
	shutdown INTEGER NOT NULL DEFAULT 0
		 CHECK (shutdown IN (0, 1)),
	note TEXT NOT NULL DEFAULT ''
		 CHECK(length(note) <= 255),

	FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE,
	UNIQUE (switch_id, vlan_id)
);

-- SVI (switch virtual interfaces) table
CREATE TABLE IF NOT EXISTS svis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    switch_id INTEGER NOT NULL,
    vlan_ref_id INTEGER NOT NULL CHECK(vlan_ref_id >= 1 AND vlan_ref_id <= 4094),
    description TEXT NOT NULL DEFAULT ''
        CHECK(length(description) <= 64),
    primary_ip_address TEXT NOT NULL DEFAULT '',
    secondary_ip_address TEXT NOT NULL DEFAULT '',
    hsrp_group INTEGER
        CHECK(hsrp_group IS NULL OR hsrp_group BETWEEN 0 AND 4095),   -- HSRPv2 / NX-OS allows 0-4095
    hsrp_virtual_ip TEXT NOT NULL DEFAULT '',
    vrf TEXT NOT NULL DEFAULT '',
    mtu INTEGER NOT NULL DEFAULT 1500
        CHECK(mtu >= 576 AND mtu <= 9216),
    shutdown INTEGER NOT NULL DEFAULT 0
        CHECK(shutdown IN (0, 1)),
    note TEXT NOT NULL DEFAULT ''
        CHECK(length(note) <= 255),
    FOREIGN KEY (switch_id, vlan_ref_id) REFERENCES vlans(switch_id, vlan_id) ON DELETE CASCADE,
    UNIQUE (switch_id, vlan_ref_id)
);

-- switch interfaces table
CREATE TABLE IF NOT EXISTS interfaces (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	switch_id INTEGER NOT NULL,
	name TEXT NOT NULL
		 CHECK(length(name) > 0 and length(name) <= 32),           -- interface name (e.g., GigabitEthernet0/1)
	description TEXT NOT NULL DEFAULT ''
		 CHECK(length(description) <= 64),
	mode TEXT NOT NULL DEFAULT 'unused'
		 CHECK(mode IN ('access', 'trunk', 'routed', 'unused')),
	access_vlan_id INTEGER
		 CHECK(access_vlan_id IS NULL OR (access_vlan_id >= 1 AND access_vlan_id <= 4094)),
	voice_vlan_id INTEGER
		 CHECK(voice_vlan_id IS NULL OR (voice_vlan_id >= 1 AND voice_vlan_id <= 4094)),
	allowed_vlan_ids TEXT NOT NULL DEFAULT '',
	native_vlan_id INTEGER
		 CHECK(native_vlan_id IS NULL OR (native_vlan_id >= 1 AND native_vlan_id <= 4094)),
	port_channel INTEGER
		 CHECK(port_channel IS NULL OR (port_channel >= 1 AND port_channel <= 4096)),
	lacp_mode TEXT
		 CHECK(lacp_mode IS NULL OR lacp_mode IN ('','active', 'passive', 'on')),
	stp_port_type TEXT
		 CHECK(stp_port_type IS NULL OR stp_port_type IN ('', 'edge', 'network', 'normal')),
	speed TEXT NOT NULL DEFAULT 'auto'
		 CHECK(speed IN ('auto', '10', '100', '1000', '2500', '5000', '10000', '25000', '40000', '100000')),
	duplex TEXT NOT NULL DEFAULT ''
		 CHECK(duplex IN ('', 'auto', 'half', 'full')),
	mtu INTEGER NOT NULL DEFAULT 1500
		 CHECK(mtu >= 576 AND mtu <= 9216),
	shutdown INTEGER NOT NULL DEFAULT 0
		 CHECK(shutdown IN (0, 1)),
	note TEXT NOT NULL DEFAULT ''
        CHECK(length(note) <= 255),
	FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE,
	UNIQUE (switch_id, name)
);

-- port channels table
CREATE TABLE IF NOT EXISTS port_channels (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	switch_id INTEGER NOT NULL,
	po_number INTEGER NOT NULL CHECK(po_number >= 1 AND po_number <= 4096),
	description TEXT NOT NULL DEFAULT ''
		 CHECK(length(description) <= 64),
	mode TEXT NOT NULL DEFAULT 'trunk'
		CHECK(mode IN ('access', 'trunk', 'routed')),
	allowed_vlan_ids TEXT NOT NULL DEFAULT '',
	native_vlan_id INTEGER
		 CHECK(native_vlan_id IS NULL OR (native_vlan_id >= 1 AND native_vlan_id <= 4094)),
	stp_port_type TEXT
		 CHECK(stp_port_type IS NULL OR stp_port_type IN ('', 'edge', 'network', 'normal')),
	vpc_id INTEGER 
		 CHECK(vpc_id IS NULL OR vpc_id >= 1 AND vpc_id <= 4096),           -- virtual port channel
	vpc_peer_link INTEGER NOT NULL DEFAULT 0								
		 CHECK(vpc_peer_link IN (0, 1)),
	shutdown INTEGER NOT NULL DEFAULT 0
		CHECK(shutdown IN(0,1)),
	note TEXT NOT NULL DEFAULT ''
		CHECK(length(note) <= 255),
	FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE,
	UNIQUE(switch_id, po_number)
);

-- static routes table
CREATE TABLE IF NOT EXISTS static_routes (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	switch_id INTEGER NOT NULL,
	destination_network TEXT NOT NULL,
    next_hop TEXT NOT NULL,
    vrf TEXT NOT NULL DEFAULT '',
    admin_distance INTEGER CHECK (admin_distance IS NULL OR admin_distance BETWEEN 1 AND 254),
    track INTEGER CHECK (track IS NULL OR track >= 1 AND track <= 500),
    note TEXT NOT NULL DEFAULT ''
		CHECK(length(note) <= 255),
	FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE,
	UNIQUE (switch_id, destination_network, next_hop, vrf)
);

-- backups table
CREATE TABLE IF NOT EXISTS backups (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	switch_id INTEGER NOT NULL,
	file_path TEXT NOT NULL UNIQUE,
	reason TEXT NOT NULL
		CHECK (reason IN ('pre-push', 'post-push', 'manual', 'scheduled')),
	bytes INTEGER NOT NULL DEFAULT 0,
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE
);

-- extra table for later incase I want to store additional data.
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vlans_switch ON vlans (switch_id);
CREATE INDEX IF NOT EXISTS idx_svis_switch ON svis (switch_id);
CREATE INDEX IF NOT EXISTS idx_interfaces_switch ON interfaces (switch_id);
CREATE INDEX IF NOT EXISTS idx_port_channels_switch ON port_channels (switch_id);
CREATE INDEX IF NOT EXISTS idx_static_routes_switch ON static_routes (switch_id);
CREATE INDEX IF NOT EXISTS idx_backups_switch ON backups (switch_id);