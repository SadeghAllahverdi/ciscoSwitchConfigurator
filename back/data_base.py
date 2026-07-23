import os
import sqlite3
from back.data_models import switch_device, vlan, svi, interface, port_channel, static_route, back_up, conf

current_dir = os.path.dirname(os.path.abspath(__file__))
db_schema_file_path = os.path.join(current_dir, "schema.sql")

def boolean_to_int(b: bool):
    return 1 if b else 0

def int_to_boolean(i: int):
    return True if i == 1 else False

def tb_row_to_switch_device(row: sqlite3.Row):
    return switch_device(
        id= row["id"],
        name= row["name"],
        hostname= row["hostname"],
        location= row["location"],
        ip= row["ip"],
        mgmt_vrf= row["mgmt_vrf"],
        platform= row["platform"],
        last_pulled_at= row["last_pulled_at"],
        last_pushed_at= row["last_pushed_at"],
        last_push_status= row["last_push_status"],
        last_push_error= row["last_push_error"],
        created_at= row["created_at"],
        updated_at= row["updated_at"],
        note= row["note"]
    )

# db class
class DataBase:
    def __init__(self, path: str):
        self.path = path # path to .db file
        try:
            self.con = sqlite3.connect(self.path)
            self.con.row_factory = sqlite3.Row
            self.cur = self.con.cursor()
            self.cur.execute("PRAGMA foreign_keys = ON")
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Error connecting to database: {e}")

        try:
            with open(db_schema_file_path, "r") as f:
                schema = f.read()
            self.cur.executescript(schema)
            self._migrate_old_tables(schema)
        except FileNotFoundError:
            raise RuntimeError(f"Database schema file not found at path: {db_schema_file_path}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Error executing database schema: {e}")

    def _table_sql(self, table_name: str):
        row = self.cur.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,)
        ).fetchone()
        return row["sql"] if row else ""

    def _migrate_old_tables(self, schema: str):
        # existing databases were created with stricter CHECK constraints
        # (hsrp_group max 255, short speed list). CREATE TABLE IF NOT EXISTS
        # keeps the old definition, so rebuild those tables with the new one.
        to_rebuild = []
        if "BETWEEN 0 AND 255" in self._table_sql("svis"):
            to_rebuild.append("svis")
        if "'100000'" not in self._table_sql("interfaces"):
            to_rebuild.append("interfaces")
        if not to_rebuild:
            return

        self.cur.execute("PRAGMA foreign_keys = OFF")
        try:
            for table in to_rebuild:
                self.cur.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
            # recreates the renamed tables with the new definitions
            self.cur.executescript(schema)
            for table in to_rebuild:
                self.cur.execute(f"INSERT INTO {table} SELECT * FROM {table}_old")
                self.cur.execute(f"DROP TABLE {table}_old")
            # dropping the old tables removed their indexes, recreate them
            self.cur.executescript(schema)
            self.con.commit()
        except sqlite3.Error as e:
            self.con.rollback()
            raise RuntimeError(f"Error migrating database tables {to_rebuild}: {e}")
        finally:
            self.cur.execute("PRAGMA foreign_keys = ON")

    def close(self):
        self.cur.close()
        self.con.close()

    def add_switch_to_db(self, switch: switch_device):
        try:
            self.cur.execute(
                """
                INSERT INTO switches (name, hostname, location, ip, mgmt_vrf, platform, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, 
                (switch.name, switch.hostname, switch.location, switch.ip, switch.mgmt_vrf, switch.platform, switch.note)
                )
            self.con.commit()
            return self.cur.lastrowid
        except sqlite3.Error as e:
            raise RuntimeError(f"Error adding switch to database: {e}")

    def delete_switch_from_db(self, switch_id: int):
        try:
            self.cur.execute(
                """
                DELETE FROM switches
                WHERE id = ?
                """, 
                (switch_id,)
                )
            self.con.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Error deleting switch from database: {e}")

    def update_switch(self, switch: switch_device):
        if switch.id is None:
            raise ValueError("def update_switch() called with a switch that has no id! something went wrong!")

        try:
            self.cur.execute(
                """
                UPDATE switches
                SET name = ?, hostname = ?, location = ?, ip = ?, mgmt_vrf = ?, platform = ?, updated_at = CURRENT_TIMESTAMP, note = ?
                WHERE id = ?
                """,
                (switch.name, switch.hostname, switch.location, switch.ip, switch.mgmt_vrf, switch.platform, switch.note, switch.id)
                )
            self.con.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Error updating switch in database: {e}")

    def get_switch_from_db(self, switch_id: int):
        try:
            self.cur.execute(
                """
                SELECT * FROM switches
                WHERE id = ?
                """,
                (switch_id,)
            )
            row = self.cur.fetchone()
            if row is None:
                return None
            return tb_row_to_switch_device(row)
        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving switch from database: {e}")

    def get_all_switches_from_db(self):
        try:
            self.cur.execute(
                """
                SELECT * FROM switches
                """
                )
            rows = self.cur.fetchall()
            return [tb_row_to_switch_device(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving all switches from database: {e}")

    def flag_last_push_in_progress(self, switch_id: int):   # sets last_push_status to in_progress
        try:
            self.cur.execute(
                """
                UPDATE switches
                SET last_push_status = 'in_progress'
                WHERE id = ?
                """,
                (switch_id,)
                )
            self.con.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Error flagging last push to last_push_status to in_progress for the switch in database: {e}")

    def flag_last_push(self, switch_id: int, success: bool, error: str = ""):   # sets last_push_status, last_push_error and last_pushed_at
        try:
            status = "success" if success else "failure"
            self.cur.execute(
                """
                UPDATE switches
                SET last_push_status = ?, last_push_error = ?, last_pushed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, error, switch_id)
                )
            self.con.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Error flagging last_push_status and last_push_error for the switch in database: {e}")

    def flag_last_pulled_at(self, switch_id: int):
        try:
            self.cur.execute(
                """
                UPDATE switches
                SET last_pulled_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (switch_id,)
                )
            self.con.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Error flagging last_pulled_at for the switch in database: {e}")

    # note: the overwrite_* methods do not commit on their own. the caller
    # (save_switch_conf_in_db) commits once at the end so a failure half way
    # through never leaves a switch with deleted or partial sections.
    def overwrite_switch_vlans_in_db(self, switch_id: int, vlans: list[vlan]):
        try:
            self.cur.execute(
                """
                DELETE FROM vlans
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            for vlan in vlans:
                self.cur.execute(
                    """
                    INSERT INTO vlans (switch_id, vlan_id, name, state, shutdown, note)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (switch_id, vlan.vlan_id, vlan.name, vlan.state, boolean_to_int(vlan.shutdown), vlan.note)
                )
        except sqlite3.Error as e:
            raise RuntimeError(f"Error overwriting switch vlans in database: {e}")

    def get_all_switch_vlans_from_db(self, switch_id: int):
        try:
            self.cur.execute(
                """
                SELECT * FROM vlans
                WHERE switch_id = ?
                """,
                (switch_id,)
            )
            rows = self.cur.fetchall()
            vlans = []
            for row in rows:
                v = vlan(
                    id= row["id"],
                    switch_id= row["switch_id"],
                    vlan_id= row["vlan_id"],
                    name= row["name"],
                    state= row["state"],
                    shutdown= int_to_boolean(row["shutdown"]),
                    note= row["note"]
                )
                vlans.append(v)
            return vlans

        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving all vlans for the switch from database: {e}")

    def overwrite_switch_svis_in_db(self, switch_id: int, svis: list[svi]):
        try:
            self.cur.execute(
                """
                DELETE FROM svis
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            for svi in svis:
                self.cur.execute(
                    """
                    INSERT INTO svis (switch_id, vlan_ref_id, description, primary_ip_address, secondary_ip_address, hsrp_group, hsrp_virtual_ip, vrf, mtu, shutdown, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (switch_id, svi.vlan_ref_id, svi.description, svi.primary_ip_address, svi.secondary_ip_address, svi.hsrp_group, svi.hsrp_virtual_ip, svi.vrf, svi.mtu, boolean_to_int(svi.shutdown), svi.note)
                )
        except sqlite3.Error as e:
            raise RuntimeError(f"Error overwriting switch svis in database: {e}")

    def get_all_switch_svis_from_db(self, switch_id: int):
        try:
            self.cur.execute(
                """
                SELECT * FROM svis
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            rows = self.cur.fetchall()
            svis = []
            for row in rows:
                s = svi(
                    id= row["id"],
                    switch_id= row["switch_id"],
                    vlan_ref_id= row["vlan_ref_id"],
                    description= row["description"],
                    primary_ip_address= row["primary_ip_address"],
                    secondary_ip_address= row["secondary_ip_address"],
                    hsrp_group= row["hsrp_group"],
                    hsrp_virtual_ip= row["hsrp_virtual_ip"],
                    vrf= row["vrf"],
                    mtu= row["mtu"],
                    shutdown= int_to_boolean(row["shutdown"]),
                    note= row["note"]
                )
                svis.append(s)
            return svis

        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving all svis for the switch from database: {e}")

    def overwrite_switch_interfaces_in_db(self, switch_id: int, interfaces: list[interface]):
        try:
            self.cur.execute(
                """
                DELETE FROM interfaces
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            for interface in interfaces:
                self.cur.execute(
                    """
                    INSERT INTO interfaces (switch_id, name, description, mode, access_vlan_id, voice_vlan_id, allowed_vlan_ids, native_vlan_id, port_channel, lacp_mode, stp_port_type, speed, duplex, mtu, shutdown, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (switch_id, interface.name, interface.description, interface.mode, interface.access_vlan_id, interface.voice_vlan_id, interface.allowed_vlan_ids, interface.native_vlan_id, interface.port_channel, interface.lacp_mode, interface.stp_port_type, interface.speed, interface.duplex, interface.mtu, boolean_to_int(interface.shutdown), interface.note)
                    )
        except sqlite3.Error as e:
            raise RuntimeError(f"Error overwriting switch interfaces in database: {e}")

    def get_all_switch_interfaces_from_db(self, switch_id: int):
        try:
            self.cur.execute(
                """
                SELECT * FROM interfaces
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            rows = self.cur.fetchall()
            interfaces = []
            for row in rows:
                i = interface(
                    id= row["id"],
                    switch_id= row["switch_id"],
                    name= row["name"],
                    description= row["description"],
                    mode= row["mode"],
                    access_vlan_id= row["access_vlan_id"],
                    voice_vlan_id= row["voice_vlan_id"],
                    allowed_vlan_ids= row["allowed_vlan_ids"],
                    native_vlan_id= row["native_vlan_id"],
                    port_channel= row["port_channel"],
                    lacp_mode= row["lacp_mode"],
                    stp_port_type= row["stp_port_type"],
                    speed= row["speed"],
                    duplex= row["duplex"],
                    mtu= row["mtu"],
                    shutdown= int_to_boolean(row["shutdown"]),
                    note= row["note"]
                )
                interfaces.append(i)
            return interfaces

        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving all interfaces for the switch from database: {e}")

    def overwrite_switch_port_channels_in_db(self, switch_id: int, port_channels: list[port_channel]):
        try:
            self.cur.execute(
                """
                DELETE FROM port_channels
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            for port_channel in port_channels:
                self.cur.execute(
                    """
                    INSERT INTO port_channels (switch_id, po_number, description, mode, allowed_vlan_ids, native_vlan_id, stp_port_type, vpc_id, vpc_peer_link, shutdown, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (switch_id, port_channel.po_number, port_channel.description, port_channel.mode, port_channel.allowed_vlan_ids, port_channel.native_vlan_id, port_channel.stp_port_type, port_channel.vpc_id, port_channel.vpc_peer_link, boolean_to_int(port_channel.shutdown), port_channel.note)
                    )
        except sqlite3.Error as e:
            raise RuntimeError(f"Error overwriting switch port channels in database: {e}")

    def get_all_switch_port_channels_from_db(self, switch_id: int):
        try: 
            self.cur.execute(
                """
                SELECT * FROM port_channels
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            rows = self.cur.fetchall()
            port_channels = []
            for row in rows:
                pc = port_channel(
                    id= row["id"],
                    switch_id= row["switch_id"],
                    po_number= row["po_number"],
                    description= row["description"],
                    mode= row["mode"],
                    allowed_vlan_ids= row["allowed_vlan_ids"],
                    native_vlan_id= row["native_vlan_id"],
                    stp_port_type= row["stp_port_type"],
                    vpc_id= row["vpc_id"],
                    vpc_peer_link= int_to_boolean(row["vpc_peer_link"]),
                    shutdown= int_to_boolean(row["shutdown"]),
                    note= row["note"]
                )
                port_channels.append(pc)
            return port_channels

        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving all port channels for the switch from database: {e}")

    def overwrite_switch_static_routes_in_db(self, switch_id: int, static_routes: list[static_route]):
        try:
            self.cur.execute(
                """
                DELETE FROM static_routes
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            for static_route in static_routes:
                self.cur.execute(
                    """
                    INSERT INTO static_routes (switch_id, destination_network, next_hop, vrf, admin_distance, track, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (switch_id, static_route.destination_network, static_route.next_hop, static_route.vrf, static_route.admin_distance, static_route.track, static_route.note)
                    )
        except sqlite3.Error as e:
            raise RuntimeError(f"Error overwriting switch static routes in database: {e}")

    def get_all_switch_static_routes_from_db(self, switch_id: int):
        try:
            self.cur.execute(
                """
                SELECT * FROM static_routes
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            rows = self.cur.fetchall()
            static_routes = []
            for row in rows:
                sr = static_route(
                    id= row["id"],
                    switch_id= row["switch_id"],
                    destination_network= row["destination_network"],
                    next_hop= row["next_hop"],
                    vrf= row["vrf"],
                    admin_distance= row["admin_distance"],
                    track= row["track"],
                    note= row["note"]
                )
                static_routes.append(sr)
            return static_routes

        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving all static routes for the switch from database: {e}")

    def add_switch_backup_conf_to_db(self, backup_conf: back_up):
        try:
            self.cur.execute(
                """
                INSERT INTO backups (switch_id, file_path, reason, bytes)
                VALUES (?, ?, ?, ?)
                """,
                (backup_conf.switch_id, backup_conf.file_path, backup_conf.reason, backup_conf.bytes)
                )
            self.con.commit()
            return self.cur.lastrowid
        except sqlite3.Error as e:
            raise RuntimeError(f"Error adding switch backup conf to database: {e}")

    def get_all_switch_backup_confs_from_db(self, switch_id: int):
        try:
            self.cur.execute(
                """
                SELECT * FROM backups
                WHERE switch_id = ?
                """,
                (switch_id,)
                )
            rows = self.cur.fetchall()
            backups = []
            for row in rows:
                b = back_up(
                    id= row["id"],
                    switch_id= row["switch_id"],
                    file_path= row["file_path"],
                    reason= row["reason"],
                    bytes= row["bytes"],
                    created_at= row["created_at"]
                )
                backups.append(b)
            return backups
        except sqlite3.Error as e:
            raise RuntimeError(f"Error retrieving all backup confs for the switch from database: {e}")

    def load_switch_conf_from_db(self, switch_id: int):
        switch = self.get_switch_from_db(switch_id)
        if switch is None:
            raise ValueError(f"Switch with id {switch_id} not found in database")
        vlans = self.get_all_switch_vlans_from_db(switch_id)
        svis = self.get_all_switch_svis_from_db(switch_id)
        interfaces = self.get_all_switch_interfaces_from_db(switch_id)
        port_channels = self.get_all_switch_port_channels_from_db(switch_id)
        static_routes = self.get_all_switch_static_routes_from_db(switch_id)
        c = conf(
            switch= switch,
            vlans= vlans,
            svis= svis,
            interfaces= interfaces,
            port_channels= port_channels,
            static_routes= static_routes
        )
        return c

    def save_switch_conf_in_db(self, conf: conf):
        try:
            if conf.switch.id is None:
                switch_id = self.add_switch_to_db(conf.switch)

            else:
                switch_id = conf.switch.id
                self.update_switch(conf.switch)

            self.overwrite_switch_vlans_in_db(switch_id, conf.vlans)
            self.overwrite_switch_svis_in_db(switch_id, conf.svis)
            self.overwrite_switch_interfaces_in_db(switch_id, conf.interfaces)
            self.overwrite_switch_port_channels_in_db(switch_id, conf.port_channels)
            self.overwrite_switch_static_routes_in_db(switch_id, conf.static_routes)

            self.con.commit()
            return switch_id
        except Exception:
            # keep the previously saved config instead of a half written one
            self.con.rollback()
            raise