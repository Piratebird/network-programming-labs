#!/usr/bin/env python3

from . import validator, network
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.traceback import install

install(show_locals=False)
console = Console()


def _build_profile(dev_name, info, creds):
    return {
        "device_type": info["type"],
        "host": info["ip"],
        "username": creds[dev_name]["username"],
        "password": creds[dev_name]["password"],
        "secret": creds[dev_name]["password"],
        "global_delay_factor": 2,
        "fast_cli": False,
        "conn_timeout": 12,
        "auth_timeout": 12,
        "banner_timeout": 15,
        "timeout": 20,
    }


def _summary_table(rows):
    table = Table(title="Automation Summary", show_lines=True)
    table.add_column("Device", style="bold")
    table.add_column("IP")
    table.add_column("Reachable")
    table.add_column("Transport")
    table.add_column("Result")

    for row in rows:
        table.add_row(
            row["name"],
            row["ip"],
            row["reachable"],
            row["transport"],
            row["result"],
        )
    return table


def main():
    console.print(
        Panel.fit(
            Text("CN451 Network Configuration Automation", justify="center"),
            subtitle="SSH first, Telnet fallback, validated inputs",
            border_style="cyan",
        )
    )

    try:
        devices = validator.load_and_validate_devices("config/devices.txt")
        creds = validator.load_credentials("config/login.txt")
        commands = validator.load_commands("config/commands.txt")
    except Exception as e:
        console.print(f"[bold red]CRITICAL:[/] Data ingestion error: {e}")
        return

    results = []

    for dev_name, info in devices.items():
        ip = info["ip"]
        console.rule(f"[bold]Processing {dev_name} ({ip})")

        with console.status(f"Checking ICMP reachability for {ip}...", spinner="dots"):
            is_alive = network.check_reachability(ip)

        if not is_alive:
            console.print(f"[yellow]WARNING:[/] Host {ip} is unreachable via ICMP.")
            results.append(
                {
                    "name": dev_name,
                    "ip": ip,
                    "reachable": "no",
                    "transport": "-",
                    "result": "skipped",
                }
            )
            continue
        console.print(f"[green]OK:[/] Host {ip} responded to ping.")

        if dev_name not in creds or dev_name not in commands:
            console.print(
                f"[yellow]INFO:[/] No command map or credential entry found for {dev_name}."
            )
            results.append(
                {
                    "name": dev_name,
                    "ip": ip,
                    "reachable": "yes",
                    "transport": "-",
                    "result": "missing input",
                }
            )
            continue

        device_conn_profile = _build_profile(dev_name, info, creds)

        result = network.push_configurations(
            device_conn_profile,
            commands[dev_name],
            status_callback=lambda message: console.log(message),
        )
        if result.ok:
            console.print(
                Panel(
                    result.output[-1200:] if result.output else "Commands completed.",
                    title=f"{dev_name} execution log ({result.transport.upper()})",
                    border_style="green",
                )
            )
            results.append(
                {
                    "name": dev_name,
                    "ip": ip,
                    "reachable": "yes",
                    "transport": result.transport,
                    "result": "configured",
                }
            )
        else:
            console.print(f"[bold red]ERROR:[/] {result.error}")
            results.append(
                {
                    "name": dev_name,
                    "ip": ip,
                    "reachable": "yes",
                    "transport": result.transport,
                    "result": "failed",
                }
            )

    console.print(_summary_table(results))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")
