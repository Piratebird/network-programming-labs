#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import paramiko
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.panel import Panel
from scp import SCPClient

console = Console()

END_DEVICES_FILE = Path(__file__).resolve().parent.parent / "config" / "end_devices.txt"
SSH_USER = os.environ.get("SSH_USER", "")


def load_end_devices():
    devices = {}
    if not END_DEVICES_FILE.exists():
        console.print(f"[bold red]Missing:[/] {END_DEVICES_FILE}")
        return devices

    with END_DEVICES_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.match(
                r"^(.+?):\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\s*\(Password:\s*(.+)\)$",
                line,
            )
            if m:
                name = m.group(1).strip()
                ip = m.group(2).strip()
                password = m.group(3).strip()
                devices[name] = {"ip": ip, "password": password}
    return devices


def set_ssh_user():
    global SSH_USER
    if not SSH_USER:
        SSH_USER = Prompt.ask("[cyan]SSH username for end devices[/]", default="root")


def ssh_connect(info):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            info["ip"],
            username=SSH_USER,
            password=info["password"],
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
            banner_timeout=15,
        )
        return client, None
    except paramiko.AuthenticationException:
        return None, "Authentication failed — wrong username or password"
    except paramiko.SSHException as e:
        return None, f"SSH negotiation failed: {e}"
    except OSError as e:
        return None, f"Network error: {e}"
    except Exception as e:
        return None, str(e)


def exec_ssh(client, command, timeout=20):
    try:
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        return out, err
    except Exception as e:
        return "", str(e)


def ping_device(ip, timeout=2):
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except (OSError, ValueError):
        return False


def list_devices_action(devices):
    table = Table(title="End Devices", show_lines=True)
    table.add_column("Name", style="bold")
    table.add_column("IP")
    table.add_column("Reachable")
    for name, info in devices.items():
        reachable = ping_device(info["ip"])
        status = "[green]YES[/]" if reachable else "[red]NO[/]"
        table.add_row(name, info["ip"], status)
    console.print(table)


def _execute_all(devices, target_names, action_fn, join_timeout=30):
    results = {}
    threads = []
    lock = threading.Lock()

    targets = {n: d for n, d in devices.items() if target_names is None or n in target_names}
    if not targets:
        console.print("[yellow]No devices selected.[/]")
        return results

    for name, info in targets.items():
        t = threading.Thread(target=action_fn, args=(name, info, results, lock), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=join_timeout)

    return results, targets


def exec_cmd_on_device(name, info, results, lock):
    client, err = ssh_connect(info)
    if err:
        with lock:
            results[name] = ("", err)
        return
    try:
        out, err = exec_ssh(client, info.get("_command", "echo OK"))
        with lock:
            results[name] = (out, err)
    finally:
        client.close()


def exec_on_devices(devices, command, target_names=None):
    for info in devices.values():
        info["_command"] = command

    results, targets = _execute_all(devices, target_names, exec_cmd_on_device, join_timeout=30)

    table = Table(title="Command Results", show_lines=True)
    table.add_column("Device")
    table.add_column("Output")
    table.add_column("Error")
    for name in targets:
        out, err = results.get(name, ("", "Timed out"))
        table.add_row(name, out[:300] if out else "-", err[:300] if err else "-")
    console.print(table)
    return results


def change_hostname_on_device(name, info, results, lock):
    client, err_msg = ssh_connect(info)
    if err_msg:
        with lock:
            results[name] = err_msg
        return
    try:
        distro_check, _ = exec_ssh(
            client, "cat /etc/os-release 2>/dev/null || cat /etc/*release 2>/dev/null || echo unknown"
        )
        lower = distro_check.lower()
        new_hostname = info.get("_hostname", "device")

        if "vyos" in lower:
            cmd = f"/configure set system host-name {new_hostname} && /configure commit && /configure save"
        elif "ubuntu" in lower or "debian" in lower or "raspbian" in lower:
            cmd = f"hostnamectl set-hostname {new_hostname} && sed -i 's/^127.0.1.1.*/127.0.1.1 {new_hostname}/' /etc/hosts"
        elif "centos" in lower or "fedora" or "rhel" in lower:
            cmd = f"hostnamectl set-hostname {new_hostname}"
        else:
            cmd = f"hostname {new_hostname} && echo '{new_hostname}' > /etc/hostname"

        out, err = exec_ssh(client, cmd, timeout=30)
        with lock:
            results[name] = out or err or "Done"
    finally:
        client.close()


def change_hostname_action(devices, new_hostname, target_names=None):
    for info in devices.values():
        info["_hostname"] = new_hostname

    results, targets = _execute_all(devices, target_names, change_hostname_on_device, join_timeout=30)

    table = Table(title="Hostname Change Results", show_lines=True)
    table.add_column("Device")
    table.add_column("Result")
    for name in targets:
        table.add_row(name, results.get(name, "Timed out"))
    console.print(table)


def scp_to_device(name, info, results, lock):
    client, err_msg = ssh_connect(info)
    if err_msg:
        with lock:
            results[name] = err_msg
        return
    try:
        with SCPClient(client.get_transport(), socket_timeout=30) as scp:
            scp.put(str(info["_local"]), info["_remote"])
        with lock:
            results[name] = f"Copied to {info['_remote']}"
    except Exception as e:
        with lock:
            results[name] = str(e)
    finally:
        client.close()


def scp_file_action(devices, local_path, remote_path, target_names=None):
    local = Path(local_path).expanduser()
    if not local.exists():
        console.print(f"[bold red]Local file not found:[/] {local}")
        return

    for info in devices.values():
        info["_local"] = local
        info["_remote"] = remote_path

    console.print(f"[cyan]Copying [bold]{local}[/bold] to {len(targets := {n: d for n, d in devices.items() if target_names is None or n in target_names})} device(s)...[/]")

    results, targets = _execute_all(devices, target_names, scp_to_device, join_timeout=60)

    table = Table(title="SCP Results", show_lines=True)
    table.add_column("Device")
    table.add_column("Result")
    for name in targets:
        table.add_row(name, results.get(name, "Timed out"))
    console.print(table)


def interactive_shell(devices, target_name):
    if target_name not in devices:
        console.print(f"[bold red]Device '{target_name}' not found.[/]")
        return

    info = devices[target_name]
    client, err_msg = ssh_connect(info)
    if err_msg:
        console.print(f"[bold red]SSH connection to {target_name} failed:[/] {err_msg}")
        return

    console.print(f"[green]Connected to {target_name} ({info['ip']}). Type 'exit' to quit.[/]")
    channel = client.invoke_shell(term="vt220")
    channel.settimeout(0)

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)

    running = True

    def read_output():
        nonlocal running
        parts = []
        while running:
            try:
                if channel.recv_ready():
                    data = channel.recv(4096)
                    parts.append(data)
                    continue
                if parts:
                    raw = b"".join(parts)
                    parts.clear()
                    cleaned = re.sub(rb"\x1b\[[0-9;]*[R]", b"", raw)
                    sys.stdout.buffer.write(cleaned)
                    sys.stdout.flush()
                if channel.recv_stderr_ready():
                    data = channel.recv_stderr(4096)
                    sys.stdout.buffer.write(data)
                    sys.stdout.flush()
                if channel.exit_status_ready():
                    running = False
                time.sleep(0.02)
            except OSError:
                running = False

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    try:
        while running:
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                char = sys.stdin.buffer.read(1)
                if not char or char == b"\x04":
                    break
                if char == b"\x03":
                    raise KeyboardInterrupt()
                if char == b"\x1b":
                    seq = char
                    while True:
                        n = sys.stdin.buffer.read(1)
                        if not n:
                            break
                        seq += n
                        if n == b"R":
                            break
                        if n in b"ABCDHPQ~":
                            break
                        if n.isalpha():
                            break
                        if n == b"\x1b":
                            seq = n
                            break
                    continue
                channel.send(char)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        running = False
        time.sleep(0.1)
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        channel.close()
        client.close()
        console.print("\n[yellow]see you later alligator[/]")


def start_chat_server_on_device(devices):
    if "Server" not in devices:
        console.print("[bold red]No 'Server' device found in end_devices.txt[/]")
        return

    info = devices["Server"]
    client, err_msg = ssh_connect(info)
    if err_msg:
        console.print(f"[bold red]Could not connect to Server:[/] {err_msg}")
        return

    console.print(f"[green]Connected to Server ({info['ip']}). Starting chat server...[/]")

    server_path = "/root/Chat-System/server.py"
    check, _ = exec_ssh(client, f"test -f {server_path} && echo exists || echo missing")
    if "missing" in check:
        console.print(f"[yellow]Chat-System not found at {server_path}. Uploading...[/]")
        local_server = Path(__file__).resolve().parent / "chat" / "server.py"
        if local_server.exists():
            with SCPClient(client.get_transport()) as scp:
                scp.put(str(local_server), "/root/")
            exec_ssh(client, "mkdir -p /root/Chat-System && mv /root/server.py /root/Chat-System/server.py")
        else:
            console.print("[red]server.py not found locally.[/]")
            client.close()
            return

    transport = Prompt.ask(
        "[cyan]Run with[/]",
        choices=["nohup (background)", "foreground"],
        default="nohup (background)",
    )
    if "nohup" in transport:
        exec_ssh(
            client,
            f"cd /root/Chat-System && nohup python3 server.py --host 0.0.0.0 --port 5050 "
            f"> server.log 2>&1 &",
        )
        console.print("[green]Chat server started in background on Server device.[/]")
    else:
        console.print("[yellow]Starting chat server in foreground. Ctrl+C to stop.[/]")
        channel = client.invoke_shell()
        channel.send("cd /root/Chat-System && python3 server.py --host 0.0.0.0 --port 5050\n")
        try:
            while True:
                if channel.recv_ready():
                    data = channel.recv(4096).decode("utf-8", errors="replace")
                    print(data, end="", flush=True)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]see you later alligator[/]")
        channel.close()
    client.close()


def main():
    global SSH_USER
    parser = argparse.ArgumentParser(description="End Device Manager")
    parser.add_argument("--host", help="Target hostname or IP")
    args = parser.parse_args()

    devices = load_end_devices()
    if not devices:
        console.print("[bold red]No end devices loaded. Check end_devices.txt[/]")
        return

    set_ssh_user()

    try:
        while True:
            console.clear()
            console.print(
                Panel.fit(
                    "[bold cyan]End Device Manager[/]",
                    border_style="cyan",
                )
            )
            console.print(f"  SSH user: [green]{SSH_USER}[/]")
            console.print()
            console.print("  1. List devices")
            console.print("  2. Execute command on devices")
            console.print("  3. Change hostname(s)")
            console.print("  4. SCP file to devices")
            console.print("  5. Interactive SSH shell")
            console.print("  6. Start chat server on Server device")
            console.print("  7. Exit")

            choice = Prompt.ask(
                "[cyan]Select option[/]",
                choices=["1", "2", "3", "4", "5", "6", "7"],
                default="1",
            )

            if choice == "1":
                list_devices_action(devices)
                input("\nPress Enter to continue...")

            elif choice == "2":
                names = list(devices.keys())
                console.print("[cyan]Available devices:[/]")
                for i, n in enumerate(names, 1):
                    console.print(f"  {i}. {n}")
                console.print("  a. All devices")
                raw = Prompt.ask("[cyan]Select device(s)[/]", default="a")
                target_names = None
                if raw.lower() != "a":
                    try:
                        idx = int(raw) - 1
                        target_names = [names[idx]]
                    except (ValueError, IndexError):
                        console.print("[red]Invalid selection.[/]")
                        continue

                command = Prompt.ask("[cyan]Command to execute[/]")
                if command:
                    exec_on_devices(devices, command, target_names)
                    input("\nPress Enter to continue...")

            elif choice == "3":
                names = list(devices.keys())
                console.print("[cyan]Available devices:[/]")
                for i, n in enumerate(names, 1):
                    console.print(f"  {i}. {n}")
                console.print("  a. All devices")
                raw = Prompt.ask("[cyan]Select device(s)[/]", default="a")
                target_names = None
                if raw.lower() != "a":
                    try:
                        idx = int(raw) - 1
                        target_names = [names[idx]]
                    except (ValueError, IndexError):
                        console.print("[red]Invalid selection.[/]")
                        continue

                new_hostname = Prompt.ask("[cyan]New hostname[/]")
                if new_hostname:
                    change_hostname_action(devices, new_hostname, target_names)
                    input("\nPress Enter to continue...")

            elif choice == "4":
                names = list(devices.keys())
                console.print("[cyan]Available devices:[/]")
                for i, n in enumerate(names, 1):
                    console.print(f"  {i}. {n}")
                console.print("  a. All devices")
                raw = Prompt.ask("[cyan]Select device(s)[/]", default="a")
                target_names = None
                if raw.lower() != "a":
                    try:
                        idx = int(raw) - 1
                        target_names = [names[idx]]
                    except (ValueError, IndexError):
                        console.print("[red]Invalid selection.[/]")
                        continue

                local_path = Prompt.ask("[cyan]Local file path[/]")
                remote_path = Prompt.ask("[cyan]Remote destination path[/]", default="/root/")
                if local_path:
                    scp_file_action(devices, local_path, remote_path, target_names)
                    input("\nPress Enter to continue...")

            elif choice == "5":
                names = list(devices.keys())
                console.print("[cyan]Available devices:[/]")
                for i, n in enumerate(names, 1):
                    console.print(f"  {i}. {n}")
                raw = Prompt.ask("[cyan]Select device for shell[/]", default="1")
                try:
                    idx = int(raw) - 1
                    target_name = names[idx]
                    interactive_shell(devices, target_name)
                except (ValueError, IndexError):
                    console.print("[red]Invalid selection.[/]")
                input("\nPress Enter to continue...")

            elif choice == "6":
                start_chat_server_on_device(devices)
                input("\nPress Enter to continue...")

            elif choice == "7":
                break
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")


if __name__ == "__main__":
    main()
