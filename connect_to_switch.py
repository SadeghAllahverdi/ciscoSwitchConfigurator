from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
from data_models import connection_info, push_result, pull_result

def push_config_to_switch(ci: connection_info, commands: list[str], save_to_startup: bool = False):
    filtered_commands = []
    for c in commands:
        c = c.rstrip()
        if not c: # empty command
            continue
        if c.startswith("!"): # comment command
            continue
        if c.strip() in ("configure terminal", "end"): # netmiko does these
            continue
        if c.startswith("copy running-config"): # incase some how someone managed to inject this to the db
            continue
        filtered_commands.append(c)
    
    # netmiko input
    device_dict = {
        "device_type": ci.platform,
        "host": ci.host,
        "username": ci.username,
        "password": ci.password,
        "fast_cli": False,         
        "session_log": None,
    }
    if ci.secret:
        device_dict["secret"] = ci.secret

    try:
        with ConnectHandler(**device_dict) as conn:
            if ci.secret:
                conn.enable()

            push_output = conn.send_config_set(filtered_commands, read_timeout=120, exit_config_mode=True)

            save_output = ""
            if save_to_startup:
                save_output = conn.save_config()

            push_text = push_output if push_output else ""
            save_text = save_output if save_output else ""

            result = push_result(success=True, output=push_text + "\n" + save_text)

            return result 

    except NetmikoAuthenticationException as e:
        return push_result(success=False, error_message=f"auth failed: {e}")
    except NetmikoTimeoutException as e:
        return push_result(success=False, error_message=f"connection timed out: {e}")
    except Exception as e:
        return push_result(success=False, error_message=f"something went wrong: {e}")


def pull_config_from_switch(ci: connection_info):
    # netmiko input
    device_dict = {
        "device_type": ci.platform,
        "host": ci.host,
        "username": ci.username,
        "password": ci.password,
        "fast_cli": False,         
        "session_log": None,
    }
    if ci.secret:
        device_dict["secret"] = ci.secret
    try:
        with ConnectHandler(**device_dict) as conn:
            if ci.secret:
                conn.enable()
            config_output = conn.send_command("show running-config", read_timeout=120)
            config_text = config_output if config_output else ""
            result = pull_result(success=True, output=config_text)
            return result 
    except NetmikoAuthenticationException as e:
        return pull_result(success=False, error_message=f"auth failed: {e}")
    except NetmikoTimeoutException as e:
        return pull_result(success=False, error_message=f"connection timed out: {e}")
    except Exception as e:
        return pull_result(success=False, error_message=f"something went wrong: {e}")