def _find_duplicates(values):
    seen = set()
    duplicates = set()

    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)

    return sorted(duplicates)


def _parse_vlan_list(text):
    text = (text or "").strip()

    if not text:
        return set(), []

    if text.lower() == "all":
        return set(), []

    vlan_ids = set()
    errors = []

    for part in text.split(","):
        part = part.strip()

        if not part:
            continue

        if "-" in part:
            start_text, end_text = part.split("-", 1)

            if not start_text.strip().isdigit() or not end_text.strip().isdigit():
                errors.append(f"Invalid VLAN range '{part}'.")
                continue

            start = int(start_text)
            end = int(end_text)

            if start > end:
                errors.append(f"Invalid VLAN range '{part}'.")
                continue

            if start < 1 or end > 4094:
                errors.append(f"VLAN range '{part}' must be between 1 and 4094.")
                continue

            vlan_ids.update(range(start, end + 1))
            continue

        if not part.isdigit():
            errors.append(f"Invalid VLAN ID '{part}'.")
            continue

        vlan_id = int(part)

        if vlan_id < 1 or vlan_id > 4094:
            errors.append(f"VLAN ID '{part}' must be between 1 and 4094.")
            continue

        vlan_ids.add(vlan_id)

    return vlan_ids, errors


def validate_switch_conf(cfg):
    errors = []

    vlan_ids = [v.vlan_id for v in cfg.vlans]
    vlan_id_set = set(vlan_ids)

    for vlan_id in _find_duplicates(vlan_ids):
        errors.append(f"Duplicate VLAN ID {vlan_id}.")

    svi_vlan_ids = [s.vlan_ref_id for s in cfg.svis]
    for vlan_id in _find_duplicates(svi_vlan_ids):
        errors.append(f"Duplicate SVI for VLAN {vlan_id}.")

    interface_names = [i.name for i in cfg.interfaces]
    for name in _find_duplicates(interface_names):
        errors.append(f"Duplicate interface name '{name}'.")

    po_numbers = [pc.po_number for pc in cfg.port_channels]

    for po_number in _find_duplicates(po_numbers):
        errors.append(f"Duplicate port-channel {po_number}.")

    route_keys = [
        (r.destination_network, r.next_hop, r.vrf or "")
        for r in cfg.static_routes
    ]

    for destination, next_hop, vrf in _find_duplicates(route_keys):
        vrf_label = vrf or "default"
        errors.append(
            f"Duplicate static route {destination} via {next_hop} in VRF {vrf_label}."
        )

    # SVIs are the only place a missing VLAN is a hard error: the database
    # enforces it with a foreign key, and a real switch cannot have an SVI
    # without the VLAN either.
    for s in cfg.svis:
        if s.vlan_ref_id not in vlan_id_set:
            errors.append(f"SVI VLAN {s.vlan_ref_id} does not exist in VLANs.")

    # access/voice/native/allowed VLANs pointing at undeclared VLANs and
    # channel-groups pointing at not-yet-created port-channels are all legal
    # on real switches, so only the list syntax is checked here.
    for i in cfg.interfaces:
        _, parse_errors = _parse_vlan_list(i.allowed_vlan_ids)

        for parse_error in parse_errors:
            errors.append(f"Interface {i.name}: {parse_error}")

    for pc in cfg.port_channels:
        _, parse_errors = _parse_vlan_list(pc.allowed_vlan_ids)

        for parse_error in parse_errors:
            errors.append(f"Port-channel {pc.po_number}: {parse_error}")

    return errors
