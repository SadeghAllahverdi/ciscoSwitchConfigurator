# SwitchConfigurator

SwitchConfigurator is a Python desktop application for managing Cisco switch configurations from a local database. It provides a PyQt6 interface for registering switches, editing VLANs, SVIs, interfaces, port-channels, and static routes, comparing saved configs against live or saved references, and pushing generated configuration commands to real switches.

The main application entry point is `front/main.py`.

## Features

- Manage a local inventory of switches.
- Store switch metadata such as name, hostname, platform, IP address, management VRF, location, and notes.
- Edit switch configuration sections in dedicated tabs:
  - VLANs
  - SVIs
  - Interfaces
  - Port-channels
  - Static routes
- Validate configuration data before saving.
- Parse Cisco running-config text into structured database records.
- Generate Cisco-style configuration commands from saved database records.
- Compare the current editor state against:
  - another saved switch
  - a live switch configuration
- Pull a compared reference into the editor without saving until confirmed.
- Push generated commands to a live switch over SSH with Netmiko.
- Preview commands before pushing.
- Create pre-push and post-push backups.
- Save manual backups of the current database-generated configuration.
- Package the app with PyInstaller.

## Tech Stack

- Python
- PyQt6
- SQLite
- Netmiko
- ciscoconfparse2
- PyInstaller

## Requirements

- Windows
- Python 3.13 or a compatible Python 3 version
- Network access to switches when using live pull/push features
- Cisco switch credentials for live operations

This project currently does not include a `requirements.txt`, so install dependencies manually:

```powershell
pip install PyQt6 netmiko ciscoconfparse2 pyinstaller
```

## Getting Started

Open the inner project folder:

```powershell
cd C:\Users\Allahverdi\source\repos\switchConfigurator\switchConfigurator
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install PyQt6 netmiko ciscoconfparse2 pyinstaller
```

Run the application:

```powershell
$env:PYTHONPATH="$PWD;$PWD\front"
python front\main.py
```

You can also open `switchConfigurator.slnx` in Visual Studio. The Python project is configured to start from `front\main.py`.

## Basic Workflow

1. Start the app.
2. Add a switch with `+ Add`.
3. Enter switch metadata such as name, platform, IP address, location, and notes.
4. Optionally generate default switch ports during creation.
5. Open the switch from the switch list.
6. Edit configuration data in the tabs:
   - Metadata
   - VLANs
   - SVIs
   - Interfaces
   - Port-Channels
   - Static Routes
7. Save changes to the local SQLite database.
8. Use the comparison panel to compare against a saved switch or live switch.
9. Pull reference data into the editor if needed.
10. Push generated commands to the live switch after reviewing the command preview.

## Live Switch Operations

Live switch features use Netmiko.

The app can:

- Connect to a switch with a username, password, and optional enable secret.
- Pull `show running-config`.
- Parse the running configuration into structured data.
- Compare live data against the current editor data.
- Push generated configuration commands.
- Optionally save the running config to startup config.
- Create backups before and after a push.

Before pushing, the app shows a confirmation dialog with the full command list.

## Data Storage

The app stores its local database in the project folder:

```text
switches.sqlite
```

This database is ignored by Git.

Backups are written under:

```text
back/back_ups/
```

Backup files are also ignored by Git because they can contain real switch configuration data.

## Database Contents

The SQLite schema stores:

- switches
- VLANs
- SVIs
- interfaces
- port-channels
- static routes
- backups
- app metadata

The schema is defined in:

```text
back/schema.sql
```

## Validation

Before saving or pushing, the app checks for common configuration problems such as:

- duplicate VLAN IDs
- duplicate SVIs
- duplicate interface names
- duplicate port-channels
- duplicate static routes
- SVI references to missing VLANs
- interface VLAN references to missing VLANs
- invalid allowed VLAN lists
- port-channel references that do not exist
- invalid MTU or VLAN ranges

Validation logic lives in:

```text
back/validate_conf.py
```

## Configuration Conversion

SwitchConfigurator supports two important conversion directions:

```text
Cisco running-config -> database model
database model -> Cisco config commands
```

Parsing is handled by:

```text
back/cisco_to_db.py
```

Command generation is handled by:

```text
back/db_to_cisco.py
```

The generated command list includes VLANs, port-channels, interfaces, SVIs, and static routes.

## Packaging

A PyInstaller spec file is included:

```text
SwitchConfigurator.spec
```

Build the distributable app from the inner project folder:

```powershell
pyinstaller SwitchConfigurator.spec
```

The generated output is written to:

```text
dist/SwitchConfigurator/
```

Build output is ignored by Git.

## Portable Build

The project already includes the pieces needed for a portable PyInstaller build:

- `SwitchConfigurator.spec` packages the app from `front/main.py`.
- `front/style.qss` and `back/schema.sql` are included as data files.
- `hooks/` is registered in the spec with `hookspath=['hooks']`.
- `hooks/hook-ciscoconfparse2.py` helps PyInstaller include `ciscoconfparse2` correctly.

Build the portable folder app from the inner project folder:

```powershell
cd C:\Users\Allahverdi\source\repos\switchConfigurator\switchConfigurator
.\.venv\Scripts\Activate.ps1
pyinstaller --clean SwitchConfigurator.spec
```

After the build finishes, copy this whole folder to another Windows machine:

```text
dist/SwitchConfigurator/
```

Run the app with:

```text
dist/SwitchConfigurator/SwitchConfigurator.exe
```

Keep the whole `SwitchConfigurator` folder together. Do not move only the `.exe`, because the portable build also needs its bundled Python libraries, schema file, stylesheet, and PyInstaller runtime files.

Runtime data such as `switches.sqlite` and `back/back_ups/` is created locally by the app and should stay with the portable folder if you want to carry the same switch database and backups between machines.

## Tests

Some test scripts are included as runnable Python files.

From the inner project folder:

```powershell
$env:PYTHONPATH="$PWD;$PWD\front"

python back\test_db.py
python back\test_d2c_and_c2d.py
```

There are also small UI test/demo scripts under `front/`:

```powershell
python front\test_ui_switch_list.py
python front\test_ui_switch_metadata.py
python front\test_ui_worker.py
```

These open PyQt windows and are intended for manual UI checks.

## Project Layout

```text
switchConfigurator/
  back/
    back_up.py              # Backup file writing/reading
    cisco_to_db.py          # Parse Cisco config into app models
    connect_to_switch.py    # Netmiko pull/push functions
    data_base.py            # SQLite database wrapper
    data_models.py          # Dataclasses for switch config objects
    db_to_cisco.py          # Generate Cisco commands from models
    schema.sql              # SQLite schema
    validate_conf.py        # Cross-reference and range validation

  front/
    main.py                 # Main PyQt app entry point
    style.qss               # Application stylesheet
    ui_switch_list.py       # Switch inventory screen
    ui_switch_detail.py     # Main switch editor dialog
    ui_compare_panel.py     # Saved/live config comparison and push/pull
    ui_add_switch_dialog.py
    ui_credential_dialog.py
    ui_push_confirm_dialog.py
    ui_switch_metadata.py
    ui_switch_vlans.py
    ui_switch_svis.py
    ui_switch_interfaces.py
    ui_switch_port_channels.py
    ui_switch_static_routes.py
    ui_worker.py            # Background worker helper

  hooks/
    hook-ciscoconfparse2.py # PyInstaller hook

  SwitchConfigurator.spec   # PyInstaller packaging config
  switchConfigurator.pyproj # Visual Studio Python project
```

## Notes

- The application is designed for Cisco platforms listed in the UI: `cisco_nxos`, `cisco_ios`, and `cisco_iosxe`.
- Real switch data is intentionally ignored by Git through `*.sqlite` and `back/back_ups/`.
- The app generates configuration commands from the saved database state, so save editor changes before pushing if you want those changes included.
