#!/usr/bin/env python3

import subprocess
from dataclasses import dataclass

from netmiko import (
    ConnectHandler,
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)

TELNET_DEVICE_TYPES = {
    "vyos": "vyos_telnet",
    "arista_eos": "arista_eos_telnet",
    "mikrotik_routeros": "mikrotik_routeros_telnet",
}


@dataclass
class ConnectionResult:
    ok: bool
    output: str
    transport: str = "none"
    error: str = ""


def check_reachability(ip_address, timeout=2):
    """Performs a single-packet OS ICMP ping to verify real-time reachability."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip_address],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except (OSError, ValueError):
        return False


def build_connection_profiles(base_profile):
    """Returns SSH first, then Telnet fallback profile if Netmiko supports that driver."""
    profiles = [("ssh", dict(base_profile))]
    telnet_type = TELNET_DEVICE_TYPES.get(base_profile["device_type"])
    if telnet_type:
        telnet_profile = dict(base_profile)
        telnet_profile["device_type"] = telnet_type
        telnet_profile["port"] = 23
        profiles.append(("telnet", telnet_profile))
    return profiles


def _send_commands(net_connect, device_type, commands):
    normalized_type = device_type.replace("_telnet", "")

    if normalized_type == "arista_eos":
        # Escalate privileges from User EXEC (>) to Privileged EXEC (#)
        output = "\nEntering enable mode...\n"
        net_connect.enable()

        # Enter configuration mode
        output += "Entering config mode...\n"
        output += net_connect.config_mode()

        for cmd in commands:
            output += f"\nExecuting: {cmd}\n"
            output += net_connect.send_command_timing(cmd)

            # Resync Netmiko's internal prompt expectation immediately after the hostname changes
            if cmd.strip().lower().startswith("hostname "):
                net_connect.set_base_prompt()

        output += "\nExiting config mode...\n"
        output += net_connect.exit_config_mode()

        # Save the Arista config to memory
        output += "\nSaving configuration...\n"
        output += net_connect.send_command("write memory")

        return output

    if normalized_type == "vyos":
        output = net_connect.send_config_set(
            commands, read_timeout=45, cmd_verify=False
        )
        output += "\n" + net_connect.send_command("commit", read_timeout=45)
        output += "\n" + net_connect.send_command("save", read_timeout=45)
        return output

    # Fallback for MikroTik or other device types
    output = ""
    for cmd in commands:
        output += f"\nExecuting: {cmd}\n"
        output += net_connect.send_command(cmd, read_timeout=30)
    return output


def push_configurations(device_info, commands, status_callback=None):
    """Applies commands with SSH first and Telnet fallback for lab devices."""
    errors = []

    for transport, profile in build_connection_profiles(device_info):
        if status_callback:
            status_callback(
                f"Connecting to {profile['host']} using {transport.upper()}"
            )

        try:
            with ConnectHandler(**profile) as net_connect:
                output = _send_commands(net_connect, profile["device_type"], commands)
                return ConnectionResult(ok=True, output=output, transport=transport)
        except NetmikoAuthenticationException as exc:
            return ConnectionResult(
                ok=False,
                output="",
                transport=transport,
                error=f"Authentication failed on {transport.upper()}: {exc}",
            )
        except NetmikoTimeoutException as exc:
            errors.append(f"{transport.upper()} timeout/handshake failed: {exc}")
        except (EOFError, OSError, ValueError) as exc:
            errors.append(f"{transport.upper()} socket/protocol failure: {exc}")
        except Exception as exc:
            errors.append(f"{transport.upper()} unexpected failure: {exc}")

    return ConnectionResult(ok=False, output="", error=" | ".join(errors))
