import os
import re
from datetime import datetime
from data_base import DataBase
from data_models import back_up

back_up_dir = os.path.join(os.path.dirname(__file__), "back_ups")

def safe_file_name(name: str):
    return re.sub(r"[^A-Za-z0-9_\-.]+", "_", name) or "switch"

def write_backup_to_file(db: DataBase, switch_id: int, switch_name: str, raw_conf: str, reason: str):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    folder = os.path.join(back_up_dir, f"{safe_file_name(switch_name)}_{switch_id}")
    os.makedirs(folder, exist_ok=True)

    final_path = os.path.join(folder, f"{timestamp}_{reason}.txt")
    temp_path = os.path.join(folder, f"{timestamp}_{reason}.tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(raw_conf)

    os.replace(temp_path, final_path)

    back_up_size = os.path.getsize(final_path)
    db.add_switch_backup_conf_to_db(back_up(switch_id=switch_id, file_path=final_path, bytes=back_up_size, reason=reason))

    return final_path

def read_backup_from_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
