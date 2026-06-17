#!/usr/bin/env python3

# ------IMPORTS----------#
import argparse
import sys
import time
import re
import matplotlib.pyplot as plt
from netmiko import ConnectHandler
from . import validator, network
from rich.console import Console
from rich.progress import track
from rich.prompt import Prompt

# ------VARIABLES----------#
console = Console()
CPU_COMMANDS = [
    "top -b -n 2 -d 1",
    "sudo top -b -n 2 -d 1",
]


# ------FUNCTIONS----------#
def parse_cpu_percent(output):

    lowered = output.lower()

    # Drop the [:10] limit! We need to search the entire output to find the 2nd iteration.
    # %cpu(s): is unique to headers, so it won't accidentally match process tables.

    #  Match Linux standard 'top' idle metric (Grabbing the LAST occurrence)
    matches_id = list(re.finditer(r"%cpu\(s\):.*?([0-9.]+)\s*id", lowered))
    if matches_id:
        return max(0.0, round(100.0 - float(matches_id[-1].group(1)), 2))

    #  Match alternative "% idle" format
    matches_idle = list(re.finditer(r"([0-9.]+)%\s*idle", lowered))
    if matches_idle:
        return max(0.0, round(100.0 - float(matches_idle[-1].group(1)), 2))

    #  Fallback to older VyOS legacy "show system cpu"
    matches_user = list(re.finditer(r"cpu states:\s*([0-9.]+)%\s*user", lowered))
    if matches_user:
        return min(100.0, float(matches_user[-1].group(1)))

    #  Final fallback to explicit 'us' metric
    matches_us = list(re.finditer(r"%cpu\(s\):\s*([0-9.]+)\s*us", lowered))
    if matches_us:
        return min(100.0, float(matches_us[-1].group(1)))

    # If no match, return None
    return None


def read_cpu_percent(net_connect):
    """Reads the CPU usage from the device."""
    last_output = ""
    # Try each command
    for command in CPU_COMMANDS:
        try:
            output = net_connect.send_command(command, read_timeout=30)
        except Exception:
            continue

        last_output = output
        cpu_pct = parse_cpu_percent(output)
        if cpu_pct is not None:
            return round(cpu_pct, 2), command, output

    return None, None, last_output


def monitor_system(iterations=8, interval=4):
    # Run the monitor
    """Collects CPU metrics using a persistent SSH connection."""
    try:
        devices = validator.load_and_validate_devices("config/devices.txt")
        creds = validator.load_credentials("config/login.txt")
    except Exception as exc:
        # Handle the exception
        console.print(f"[bold red]CRITICAL:[/] Could not load inputs: {exc}")
        return

    if "vyos_router" not in devices:
        console.print("[bold red]CRITICAL:[/] VyOS Router entry missing!")
        return
    if "vyos_router" not in creds:
        console.print("[bold red]CRITICAL:[/] VyOS Router credentials missing!")
        return

    profile = {
        "device_type": devices["vyos_router"]["type"],
        "host": devices["vyos_router"]["ip"],
        "username": creds["vyos_router"]["username"],
        "password": creds["vyos_router"]["password"],
        "conn_timeout": 12,
        "auth_timeout": 12,
        "banner_timeout": 15,
        "timeout": 20,
    }

    cpu_values = []
    timestamps = []

    console.rule("[bold cyan]Task 3: Real-Time CPU Profiling")

    for transport, conn_profile in network.build_connection_profiles(profile):
        try:
            console.print(f"Connecting to VyOS using {transport.upper()}...")
            with ConnectHandler(**conn_profile) as net_connect:
                console.print("[green]SUCCESS:[/] Connected. Starting CPU stream.\n")

                with open("data/cpu_log.txt", "w", encoding="utf-8") as log_file:
                    log_file.write("Timestamp,CPU_Utilization\n")

                    for idx in track(
                        range(iterations), description="Polling router CPU"
                    ):
                        current_time = time.strftime("%H:%M:%S")

                        cpu_pct, command_used, output = read_cpu_percent(net_connect)

                        if cpu_pct is not None:
                            cpu_values.append(cpu_pct)
                            timestamps.append(current_time)

                            console.print(
                                f"Sample {idx + 1}/{iterations} | {current_time} | "
                                f"VyOS CPU Load: {cpu_pct}% | command: {command_used}"
                            )
                            log_file.write(f"{current_time},{cpu_pct}\n")
                            log_file.flush()
                        else:
                            preview = (
                                " ".join(output.split())[:160]
                                if output
                                else "no command output"
                            )
                            console.print(
                                "[yellow]WARNING:[/] CPU value not found in router output. "
                                f"Last output preview: {preview}"
                            )

                        time.sleep(interval)
                break

        except Exception as e:
            console.print(
                f"[yellow]WARNING:[/] {transport.upper()} polling failed: {e}"
            )
    else:
        console.print("[bold red]ERROR:[/] Failed to poll CPU over SSH and Telnet.")
        return

    if not cpu_values:
        console.print(
            "[bold red]ERROR:[/] No CPU samples collected; graph was not created."
        )
        return

    console.print("\n[cyan]Compiling analytics and rendering trend graph...[/]")
    plt.figure(figsize=(9, 4.5))
    plt.plot(
        timestamps,
        cpu_values,
        marker="o",
        color="#1f77b4",
        linestyle="-",
        linewidth=2.5,
    )

    plt.title(
        "VyOS Edge Router - CPU Real-Time Utilization", fontsize=12, fontweight="bold"
    )
    plt.xlabel("Polling Time", fontsize=10)
    plt.ylabel("System Resource Load (%)", fontsize=10)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.ylim(0, max(max(cpu_values) + 10, 25))

    output_image = "assets/cpu_progress.png"
    plt.savefig(output_image)
    console.print(
        f"[green]SUCCESS:[/] Real-time files saved: data/cpu_log.txt and {output_image}"
    )


# Prompt functions
def prompt_iterations(default=8):
    """Prompts the user for the number of CPU samples to collect."""
    try:
        while True:
            raw = Prompt.ask("[cyan]Number of CPU samples[/]", default=str(default))
            try:
                val = int(raw)
                if val > 0:
                    return val
                console.print("[red]Must be greater than zero.[/]")
            except ValueError:
                console.print("[red]Enter a valid number.[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")
        sys.exit(0)


def prompt_interval(default=4):
    """Prompts the user for the interval between CPU samples."""
    try:
        while True:
            raw = Prompt.ask(
                "[cyan]Interval between samples (seconds)[/]", default=str(default)
            )
            try:
                val = float(raw)
                if val > 0:
                    return val
                console.print("[red]Must be greater than zero.[/]")
            except ValueError:
                console.print("[red]Enter a valid number.[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")
        sys.exit(0)


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Task 3 VyOS CPU monitor")
    parser.add_argument(
        "-n", "--iterations", type=int, default=None, help="Number of CPU samples"
    )
    # Add optional interval argument
    parser.add_argument(
        "-i", "--interval", type=float, default=None, help="Seconds between samples"
    )
    args = parser.parse_args()

    try:
        iters = args.iterations if args.iterations else prompt_iterations()
        interval = args.interval if args.interval else prompt_interval()
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")
        sys.exit(0)

    # Run the monitor
    try:
        monitor_system(iterations=iters, interval=interval)
    # Handle KeyboardInterrupt
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")
