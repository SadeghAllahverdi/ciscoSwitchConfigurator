import os
print(f"working dir: {os.getcwd()}")
print(f"schema exists here: {os.path.exists('schema.sql')}")

import tempfile
from back.data_base import DataBase
from back.data_models import switch_device, vlan, svi, interface, port_channel, static_route, back_up, conf



def main():
    # Create a temporary file for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        test_db_path = os.path.join(temp_dir, "test_switch.db")
        print(f"created test database {test_db_path}")
        # testing database creation
        db = DataBase(test_db_path)
        try:
            print("created test database from schema")
            # testing adding switch to db
            switch = switch_device(
                name="core-01",
                hostname="DC1-CORE-01",
                location="DC1 rack A3",
                mgmt_vrf="management",
                platform="cisco_nxos",
                note="Primary core"
            )
            switch_id = db.add_switch_to_db(switch= switch)
            print(f"added switch to db with id {switch_id}")
            # writing switch conf to db
            switch_conf = conf(
                switch= db.get_switch_from_db(switch_id),
                vlans=[vlan(vlan_id= 55, name="VLAN55", state = "suspend", shutdown=True, note="Test VLAN 1"),
                       vlan(vlan_id= 22, name="VLAN22", shutdown=True, note="Test VLAN 2")],
                svis=[svi(vlan_ref_id= 55, description="VLAN55 SVI", primary_ip_address="192.168.1.1", secondary_ip_address="192.168.1.2")],
                interfaces=[interface(name="Ethernet1", description="Uplink", shutdown=True),
                            interface(name="Ethernet2", description="Downlink", shutdown=False),
                            interface(name="Ethernet3")],
                port_channels=[port_channel(po_number=10, description="Peer", mode="trunk", vpc_peer_link=True)],
                static_routes=[static_route(destination_network="0.0.0.0/0", next_hop="192.168.1.254")],
            )
            saved_id = db.save_switch_conf_in_db(switch_conf)
            print(f"saved switch conf to db with id {saved_id}")

            # testing back up
            backup = back_up(switch_id=saved_id, file_path="/tmp/fake_backup.txt", reason="manual", bytes=1024)
            backup_id = db.add_switch_backup_conf_to_db(backup)
            backups = db.get_all_switch_backup_confs_from_db(saved_id)
            assert len(backups) == 1
            print("Backup test passed")

            # testing retrieving switch conf from db
            loaded_switch_conf = db.load_switch_conf_from_db(switch_id= switch_id)
            assert loaded_switch_conf is not None, "Failed to load switch conf from db"
            assert loaded_switch_conf.switch.name == switch_conf.switch.name, "Switch name mismatch"
            assert len(loaded_switch_conf.vlans) == len(switch_conf.vlans), "VLAN count mismatch"
            assert loaded_switch_conf.vlans[0].vlan_id == switch_conf.vlans[0].vlan_id, "VLAN ID mismatch"
            assert loaded_switch_conf.svis[0].primary_ip_address == switch_conf.svis[0].primary_ip_address, "SVI primary IP mismatch"
            assert loaded_switch_conf.interfaces[0].name == switch_conf.interfaces[0].name, "Interface name mismatch"
            assert loaded_switch_conf.interfaces[2].shutdown == switch_conf.interfaces[2].shutdown, "Interface shutdown state mismatch"
            assert loaded_switch_conf.port_channels[0].po_number == switch_conf.port_channels[0].po_number, "Port channel number mismatch"
            print("Successfully loaded switch conf from db and partially verified its integrity")

            # testing the flag funtions
            db.flag_last_push_in_progress(switch_id= switch_id)
            sw = db.get_switch_from_db(switch_id= switch_id)
            assert sw.last_push_status == "in_progress", "Failed to set push in progress flag"
            db.flag_last_push(switch_id= switch_id, success= True)
            sw = db.get_switch_from_db(switch_id= switch_id)
            assert sw.last_push_status == "success", "Failed to set push success flag"
            print("Successfully tested push status flag functions")

            # testing constraints
            try:
                db.add_switch_to_db( switch= switch_device(name= "core-01"))
                print("Error: duplicate name should have failed")

            except Exception as e:
                print(f"Successfully caught duplicate name error: {e}")

            try:
                db.add_switch_to_db( switch= switch_device(name= "wierd switch", platform="wierd platform"))
                print("Error: bad platform should have failed")
        
            except Exception as e:
                print(f"Successfully caught bad platform error: {e}")

            # testing cascade delete
            db.delete_switch_from_db(switch_id= switch_id)
            assert db.get_switch_from_db(switch_id=switch_id) is None , "Failed to delete switch from db"
            assert db.get_all_switch_vlans_from_db(switch_id= switch_id) == [], "Failed to cascade delete vlans"
            assert db.get_all_switch_interfaces_from_db(switch_id= switch_id) == [], "Failed to cascade delete interfaces"
            print("Successfully tested some cascade delete cases")

            print("All tests completed successfully")
        finally:
            db.close()
            del db

if __name__ == "__main__":
    main()