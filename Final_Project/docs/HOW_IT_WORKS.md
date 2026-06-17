# CN451 Network Programming Final Project Guide

This project automates a simulated GNS3 network, monitors router CPU, sniffs packets, manages end devices, and runs a TCP chat application across the lab hosts.

The main entry point is `guide.py`, a Rich interactive launcher that presents a numbered menu for all tasks.

## Topology

The topology follows `topology.md`:

| Role | IP address | Notes |
| --- | --- | --- |
| VyOS router | 192.168.1.254 | Routes LAN 1 (`eth1`) and LAN 2 (`eth2`) |
| Arista switch | 192.168.1.250 | LAN 1 switch |
| MikroTik switch | 192.168.2.250 | LAN 2 switch |
| Server (Alpine) | 192.168.2.100 | Chat server host |
| PC1 (Alpine) | 192.168.1.10 | LAN 1 chat client |
| PC2 (Alpine) | 192.168.1.11 | LAN 1 chat client |
| PC3 (Alpine) | 192.168.2.10 | LAN 2 chat client |

## Files

| File | Purpose |
| --- | --- |
| `guide.py` | Rich interactive launcher (entry point for all tasks) |
| `config/devices.txt` | Network device inventory: name, IP, and Netmiko device type |
| `config/login.txt` | SSH/Telnet credentials per device |
| `config/commands.txt` | Per-device configuration commands |
| `config/end_devices.txt` | Alpine end device definitions (name, IP, password) |
| `src/validator.py` | Validates `devices.txt`, `login.txt`, and `commands.txt` |
| `src/network.py` | ICMP ping, SSH-first/Telnet-fallback profiles, command dispatch per device type |
| `src/automate.py` | Task 1–2: network automation runner with Rich status output |
| `src/cpu_monitor.py` | Task 3: VyOS CPU polling via `top`, logging, and Matplotlib graph |
| `src/packet_sniffer.py` | Task 4: Scapy live packet capture with Rich table |
| `src/end_device_manager.py` | Task 5: SSH management of Alpine end devices (6 sub-actions) |
| `src/chat/server.py` | Task 6: threaded TCP chat server |
| `src/chat/client.py` | Task 6: TCP chat client |
| `src/menu.py` | Legacy arrow-key launcher (↑/↓ navigate, Enter select) |

## Setup

Create or activate a Python environment, then install dependencies:

```bash
pip install -r requirements.txt
```

For packet sniffing, run the sniffer as root or with the needed capture permissions.

## How to launch

```bash
python guide.py
```

Select a numbered option to run any task. After the module exits, control returns to the guide. Alternatively, run a task directly:

```bash
python -m src.automate                  # Task 1–2: automation
python -m src.cpu_monitor               # Task 3: CPU monitoring
sudo python -m src.packet_sniffer -i eth0 -c 20   # Task 4: packet sniffing
python -m src.end_device_manager        # Task 5: end device manager
python -m src.chat.server --host 0.0.0.0 --port 5050   # Task 6: server
python -m src.chat.client               # Task 6: client
```

## Task 1: Simulated Network

Build the topology in GNS3 using the provided project file at `GNS3_FINAL_TOPOLOGY/GNS3_FINAL_TOPOLOGY.gns3`:

- 1 VyOS router
- 1 Arista vEOS switch
- 1 MikroTik RouterOS switch
- 3 Alpine client hosts
- 1 Alpine server host

Configure the router interfaces:

- `eth1`: `192.168.1.254/24`
- `eth2`: `192.168.2.254/24`

The server uses `192.168.2.100/24`. The clients use:

- `192.168.2.10/24` (default gateway `192.168.2.254`)
- `192.168.1.11/24` (default gateway `192.168.1.254`)
- `192.168.1.10/24` (default gateway `192.168.1.254`)

## Task 2: Network Automation

Run:

```bash
python -m src.automate
```

What it does:

1. Reads `config/devices.txt`, `config/login.txt`, and `config/commands.txt` via `src/validator.py`.
2. Validates file structure, IPv4 addresses, and device types (`vyos`, `arista_eos`, `mikrotik_routeros`).
3. Pings each device before attempting automation.
4. Connects with SSH first.
5. If SSH times out or fails during handshake, tries Telnet when Netmiko has a matching Telnet driver.
6. Applies each device's commands — Arista enters enable/config mode then `write memory`; VyOS uses `send_config_set` then `commit` + `save`; MikroTik uses direct `send_command`.
7. Shows a Rich summary table with reachability, transport, and result per device.

Handled failures:

- Missing input files
- Malformed inventory, login, or command lines
- Invalid IP addresses
- ICMP unreachable devices (skipped)
- SSH/Telnet timeout or handshake failure
- Authentication failure
- Socket and protocol failures

## Task 3: CPU Monitoring

Run:

```bash
python -m src.cpu_monitor
```

Optional flags:

```bash
python -m src.cpu_monitor -n 12 -i 3    # 12 samples, 3-second interval
```

What it does:

1. Loads the VyOS router credentials from `config/devices.txt` and `config/login.txt`.
2. Connects through SSH first, then Telnet if SSH fails.
3. Runs `top -b -n 2 -d 1` (with `sudo` fallback) on the VyOS router.
4. Parses the output with regex to extract the idle CPU percentage, computing load as `100 - idle`. Multiple regex fallbacks handle different `top` output formats.
5. Writes each timestamped sample to `data/cpu_log.txt`.
6. After all samples, renders a Matplotlib line graph to `assets/cpu_progress.png`.

If the router output does not contain a CPU value, the script warns and keeps polling. If no samples are collected, it does not create a misleading graph.

## Task 4: Packet Sniffing

**Note:** Packet capture requires root privileges. Run with `sudo` or the sniffer will prompt to re-execute with elevated permissions.

Run on a host where Scapy can capture traffic:

Inside a VM:

```bash
sudo python -m src.packet_sniffer -i eth0 -c 20
```

From the Fedora host machine (capturing VM traffic):

```bash
sudo python -m src.packet_sniffer -i virbr0 -c 20
```

Optional BPF filter example for the chat app:

```bash
sudo python -m src.packet_sniffer -i eth0 -c 20 -f "tcp port 5050"
```

The sniffer displays a live Rich table with time, source, destination, protocol, and packet length, clearing and redrawing on each new packet.

## Task 5: End Device Manager

Run:

```bash
python -m src.end_device_manager
```

This opens an interactive sub-menu with 6 actions for managing Alpine end devices (defined in `config/end_devices.txt`):

| Option | Action | Description |
| --- | --- | --- |
| 1 | List devices | Shows name, IP, and ICMP reachability per device |
| 2 | Execute command | Runs a shell command in parallel across selected devices using threading + Paramiko |
| 3 | Change hostname | Auto-detects OS (VyOS, Ubuntu/Debian, CentOS/Fedora, generic) and applies the correct command |
| 4 | SCP file | Copies a local file to remote devices in parallel using `scp.SCPClient` |
| 5 | Interactive shell | Full raw terminal SSH session with arrow-key support |
| 6 | Start chat server | SSHs into the Server device, optionally uploads `server.py` via SCP, and launches it in background (`nohup`) or foreground |

Handled failures:

- Missing `config/end_devices.txt`
- Authentication failure on SSH
- Unreachable devices
- Missing local file for SCP
- Timeout during parallel execution

## Task 6: Chat System

### Run the server

On the server host (192.168.2.100):

```bash
python -m src.chat.server --host 0.0.0.0 --port 5050
```

Without flags, the server interactively prompts for a bind interface and port. The server supports:

- Broadcast chat to all connected users
- `/pm` private messages
- `/users` — list online users
- `/rps` — Rock Paper Scissors (first to 3 wins or 5 rounds)
- `/files` — list uploaded files
- `/download` — send a file as hex-encoded JSON

Files are stored in `storage/uploads/` (max 150 KB).

You can also deploy the server automatically from Task 5 (option 6 in the End Device Manager), which SSHs into the Server, uploads `server.py` if needed, and starts it.

### Run each client

On each client host:

```bash
python -m src.chat.client
```

The client defaults to `192.168.2.100:5050`. You can also pass the server explicitly:

```bash
python -m src.chat.client 192.168.2.100 5050
```

Chat commands:

| Command | Description |
| --- | --- |
| `/help` | Show commands |
| `/users` | List online users |
| `/pm <username> <message>` | Send a private message |
| `/rps <username>` | Start rock-paper-scissors |
| `rock`, `paper`, `scissors` | Send an RPS move |
| `/files` | List uploaded server files |
| `/upload <path>` | Upload a file under 150 KB |
| `/download <filename>` | Download a file |
| `/quit` | Disconnect safely |

Downloads are saved to `storage/downloads/`.

Handled chat failures:

- Invalid or duplicate username
- Broken JSON payloads
- Oversized protocol messages
- Oversized uploads (over 150 KB)
- Missing upload/download files
- Client disconnect during a game (opponent is notified)
- Server disconnect while a client is running
- Bad command syntax

## Troubleshooting Notes

If `sudo python -m src.packet_sniffer` says Scapy is not installed while `pip install scapy` says it is installed, `sudo` is probably using the system Python instead of the project venv Python. The sniffer now detects that and retries with `venv/bin/python` when available.

If Arista fails with `Pattern not detected`, the device prompt probably changed during automation or an interactive command did not return to the prompt. The command file avoids the interactive EOS banner command, and the automation applies hostname commands last with a generic `#` prompt terminator.

If CPU monitoring says no CPU value was found, the VyOS `top` output did not match any of the four regex fallback patterns (`%cpu(s): idle`, `% idle`, `cpu states: % user`, or `%cpu(s): us`). The monitor tries two commands (`top -b -n 2 -d 1` then `sudo top -b -n 2 -d 1`) and logs a preview of the unexpected output for debugging.
