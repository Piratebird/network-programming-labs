# Network Programming Course

This repository contains coursework for the Network Programming class.

## Project 1: Device Inventory Audit

Project 1 reads a network inventory file, parses device records, analyzes them, and generates a simple audit report.

### What it does

- Reads `inventory.txt`
- Splits raw text into device records
- Parses records into `Device` objects
- Counts hosts, switches, and routers
- Lists devices that need attention
- Lists inactive switches
- Writes `network_audit.txt` when report generation is selected

### Project structure

- [project1/__main__.py](</home/piratebird/Documents/Network Programming /project1/__main__.py:1>): menu and program entry point
- [project1/reader.py](</home/piratebird/Documents/Network Programming /project1/reader.py:1>): reads and splits inventory data into records
- [project1/parser.py](</home/piratebird/Documents/Network Programming /project1/parser.py:1>): converts records into `Device` objects
- [project1/analyzer.py](</home/piratebird/Documents/Network Programming /project1/analyzer.py:1>): counts device types and finds attention items
- [project1/writer.py](</home/piratebird/Documents/Network Programming /project1/writer.py:1>): writes the audit report
- [project1/device.py](</home/piratebird/Documents/Network Programming /project1/device.py:1>): device model
- [project1/inventory.txt](</home/piratebird/Documents/Network Programming /project1/inventory.txt:1>): input data

### How it works internally

**`__main__.py` — entry point and menu:**
- `__main__.py:16-37` — `main()` orchestrates the full pipeline: calls `reader.read_file()` to load inventory, `parser.parse_devices()` to build `Device` objects, and `analyze()` to count types and find items needing attention.
- `__main__.py:41-69` — The menu loop offers three options:
  1. **Check CLI output** — calls `main()` and prints results to the terminal.
  2. **Check inventory file** — runs the full pipeline and calls `writer.write_report()` to produce `network_audit.txt`.
  3. **Exit** — breaks the loop.

**`reader.py:9-35` — `read_file()`:**
Joins all non-empty lines into a single string, then splits into records using regex `\s+(?=(?:HOST|SWITCH|ROUTER),)` — the positive lookahead keeps the device type as the start of each record. Each record is split on commas with whitespace stripped (spaces removed from fields with `.replace(" ", "")`). Returns a list of field lists like `[["HOST","192.168.1.180","Active"], ...]`.

**`parser.py:5-47` — `parse_devices()`:**
Iterates the field-list records. Normalizes device type with `.strip().upper()`, then dispatches by type:
- **HOST** (3 fields): creates `Device("HOST", ip, ip, status)`
- **SWITCH** (4 fields): creates `Device("SWITCH", name, None, status, vlan)`
- **ROUTER** (4 fields): creates `Device("ROUTER", name, ip, status)`
Returns a list of `Device` objects.

**`device.py:1-42` — `Device` class:**
- `needs_attention()` (`device.py:17-18`) — returns `True` if status is `"inactive"` or `"maintenance"`.
- `get_device_info()` (`device.py:20-42`) — formats output differently per type (host shows IP, switch shows name+VLAN, router shows name+IP).

**`analyzer.py:1-24` — `analyze()`:**
Iterates the device list, counts hosts/switches/routers, collects devices matching `needs_attention()`, and separately tracks inactive switches. Returns `(host_count, switch_count, router_count, needs_attention_list, inactive_switches_list)`.

**`writer.py:4-15` — `write_report()`:**
Writes the formatted audit report to `project1/network_audit.txt` with device counts and the attention list.

### Input format

The inventory contains records such as:

```text
HOST,192.168.1.180,Active
SWITCH,SW-Floor-4-22,Inactive,VLAN32
ROUTER,Router-Core-19,Active,10.0.0.5
```

`reader.py` converts the file into a list of records like:

```python
[
    ["HOST", "192.168.1.180", "Active"],
    ["SWITCH", "SW-Floor-4-22", "Inactive", "VLAN32"],
    ["ROUTER", "Router-Core-19", "Active", "10.0.0.5"],
]
```

`parser.py` then turns those records into `Device` objects.

### How to run

From the repository root:

```bash
python3 project1/__main__.py
```

### Menu options

1. `Check CLI output`
   Prints the counts and device attention list in the terminal.

2. `Check inventory file`
   Reads the inventory, analyzes it, and writes `project1/network_audit.txt`.

3. `Exit`
   Closes the program.

### Verified parsing result

With the current `inventory.txt`, the parser reads:

- `550` records
- `442` hosts
- `78` switches
- `30` routers

### Important implementation note

A previous bug happened because the parser expected a flat list of tokens, while the reader was already returning a list of records. The parser now correctly processes one record at a time and normalizes device types with `.strip().upper()`.

### Future improvements

- Add unit tests for `reader.py` and `parser.py`
- Avoid removing internal spaces from all fields unless needed
- Improve handling for malformed records
- Add clearer report formatting

## Project 2: Multi-Client Chat Server

Project 2 is a TCP socket chat application. It has one server that accepts multiple clients, lets users chat in a shared room, send private messages, upload/download small files, and play Rock Paper Scissors.

### What it does

- Starts a threaded TCP server on port `5050`
- Allows multiple clients to connect at the same time
- Registers each client with a unique username
- Broadcasts normal chat messages to all connected users
- Supports private messages between users
- Lists active users
- Uploads files to the server, up to `150 KB`
- Lists and downloads files stored on the server
- Supports a two-player Rock Paper Scissors game

### Project structure

- [project2/server.py](</home/piratebird/Documents/Network Programming /project2/server.py:1>): server socket, client threads, shared state, chat commands, file storage, and RPS game logic
- [project2/client.py](</home/piratebird/Documents/Network Programming /project2/client.py:1>): client connection, user input, command handling, uploads, downloads, and message display
- `project2/uploads/`: created by the server when files are uploaded
- `project2/downloads/`: created by the client when files are downloaded

### How it works internally

**Server (`server.py`):**
- `server.py:427-447` — `start_server()` creates a TCP socket with `SO_REUSEADDR`, binds to `0.0.0.0:5050`, listens, and accepts connections. Each accepted client socket gets a daemon thread running `handle_client()`.
- `server.py:369-424` — `handle_client()` calls `register_client()` to validate and store the new user, then enters a receive loop. Incoming JSON payloads are dispatched by key: `message` (broadcast or `/command`), `rps_choice`, or `file_upload`.
- `server.py:164-184` — `register_client()` reads a JSON `{"username": ...}` packet, checks for duplicates, creates a `Client` object, and stores it in `clients_by_name` and `clients_by_socket` under `state_lock`.
- `server.py:99-115` — Protocol layer: `receive_exact()` loops until exactly 64 header bytes are read. `receive_json()` (`server.py:118-137`) decodes the header to get the payload length, reads exactly that many bytes, and runs `json.loads()`.
- `server.py:140-146` — `send_json_to_sock()` serializes the payload, prepends a 64-byte space-padded length header, and sends both via `sock.sendall()`.
- `server.py:339-363` — `handle_command()` routes: `/help` → help text, `/users` → online list, `/pm` → private message, `/rps` → start game, `/files` → list uploads, `/download` → send file as hex, `/quit` → raise `ConnectionError`.
- `server.py:32-87` — `RPS` class: `add_choice()` registers each player's choice, applies the `beats` dict (`rock→scissors`, `paper→rock`, `scissors→paper`), and ends the game when a player reaches 3 wins or after 5 scored rounds.
- `server.py:187-214` — `unregister_client()` removes the client from global state under `state_lock`, notifies the RPS opponent if a game was in progress, and closes the socket.
- `server.py:220-226` — `broadcast_message()` iterates all connected clients and sends the chat payload to everyone except the sender.
- `server.py:388-412` — File upload: receives hex-encoded content, validates the 150 KB limit, and writes to `uploads/<filename>`.
- `server.py:324-336` — `handle_download()` reads a file from `uploads/`, hex-encodes it, and sends as `{"file": {"name": ..., "content": hex}}`.

**Client (`client.py`):**
- `client.py:189-247` — `main()` parses `sys.argv` for `host` and `port` (defaults `127.0.0.1:5050`), calls `connect_and_register()`, prints the help menu, spawns a background `receive_loop` thread, then enters an input loop. `/upload` is intercepted to call `send_upload()`, RPS choices (`rock`/`paper`/`scissors`) are sent as `{"rps_choice": ...}`, and `/quit` sets `running = False`.
- `client.py:40-76` — `receive_loop()` runs in a daemon thread: reads the 64-byte length header, reads the exact payload, and dispatches to `print_message()` or `handle_incoming_file()`.
- `client.py:82-90` — `connect_and_register()` creates a TCP socket, connects, prompts for a username, and sends `{"username": ...}`.
- `client.py:142-168` — `print_message()` decodes structured JSON payloads (`system`, `error`, `chat`, `private_message`, `users`, `files`) and displays them with a `\r\033[K` prefix to cleanly overwrite any existing prompt text.
- `client.py:93-118` — `send_upload()` reads a local file, validates the 150 KB size limit, hex-encodes the bytes, and sends as `{"file_upload": {"name": ..., "content": hex}}`.
- `client.py:22-37` — `send_json()` serializes with a padded 64-byte length header and sends via `sock.sendall()`.

### How to run

Open one terminal for the server:

```bash
cd project2
python3 server.py
```

Open another terminal for each client:

```bash
cd project2
python3 client.py
```

The client connects to `127.0.0.1:5050` by default. To connect to a different server host or port:

```bash
python3 client.py <host> <port>
```

Example:

```bash
python3 client.py 192.168.1.10 5050
```

### Client commands

- `/help`: shows the command menu
- `/quit`: disconnects from the server
- `/users`: lists online users
- `/pm <username> <message>`: sends a private message
- `/rps <username>`: starts a Rock Paper Scissors game with another user
- `/files`: lists files stored on the server
- `/upload <filepath>`: uploads a local file smaller than `150 KB`
- `/download <filename>`: downloads a file from the server

Anything that does not start with `/` is sent as a public chat message.

### Rock Paper Scissors

Start a game with:

```text
/rps <username>
```

After the game starts, each player types one of:

```text
rock
paper
scissors
```

The server compares both choices, updates the score, and sends the result to both players. The game ends when one player reaches `3` wins or after `5` scored rounds.

### File sharing

Upload a file:

```text
/upload notes.txt
```

List server files:

```text
/files
```

Download a file:

```text
/download notes.txt
```

Uploaded files are saved in `project2/uploads/`. Downloaded files are saved in `project2/downloads/`.

### Important implementation notes

- The server uses one thread per connected client.
- Shared dictionaries store connected users and active RPS games.
- Locks are used around shared state and socket sends to reduce race conditions.
- Files are sent as hex strings inside JSON messages.
- The server strips uploaded file paths down to the filename to avoid basic path traversal issues.
- The file size limit is `150 KB`.

### Future improvements

- Add passwords or account-based login
- Add timestamps to chat messages
- Add better validation for empty command arguments
- Add unit tests for the JSON send/receive helpers
- Store chat history while the server is running

## Final Project: Network Automation Lab

> **Final Project** — For less technical details, check [HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

The final project automates a simulated GNS3 network, monitors router CPU, sniffs packets, manages end devices, and runs a TCP chat application across the lab hosts.

### What it does

- Simulated network with VyOS router, Arista/MikroTik switches, and Alpine hosts
- Automates device configuration via SSH (with Telnet fallback) using Netmiko with Rich status display
- Monitors VyOS CPU load in real time and generates Matplotlib trend graphs
- Sniffs network traffic using Scapy with a live-updating Rich table
- Manages Alpine end devices: parallel SSH commands, hostname changes, SCP file distribution, interactive shell, remote chat server deployment
- Multi-client TCP chat with file upload/download, private messages, and Rock Paper Scissors

### Project structure

- [Final_Project/guide.py](</home/piratebird/Documents/Network Programming /Final_Project/guide.py:1>): Rich interactive launcher menu (entry point)
- [Final_Project/src/automate.py](</home/piratebird/Documents/Network Programming /Final_Project/src/automate.py:1>): Task 1–2 — network device automation
- [Final_Project/src/cpu_monitor.py](</home/piratebird/Documents/Network Programming /Final_Project/src/cpu_monitor.py:1>): Task 3 — VyOS CPU profiling
- [Final_Project/src/packet_sniffer.py](</home/piratebird/Documents/Network Programming /Final_Project/src/packet_sniffer.py:1>): Task 4 — Scapy packet capture
- [Final_Project/src/end_device_manager.py](</home/piratebird/Documents/Network Programming /Final_Project/src/end_device_manager.py:1>): Task 5 — end device SSH management
- [Final_Project/src/chat/server.py](</home/piratebird/Documents/Network Programming /Final_Project/src/chat/server.py:1>): Task 6 — TCP chat server
- [Final_Project/src/chat/client.py](</home/piratebird/Documents/Network Programming /Final_Project/src/chat/client.py:1>): Task 6 — TCP chat client
- [Final_Project/src/validator.py](</home/piratebird/Documents/Network Programming /Final_Project/src/validator.py:1>): input file validation
- [Final_Project/src/network.py](</home/piratebird/Documents/Network Programming /Final_Project/src/network.py:1>): Netmiko profiles, ping, command dispatch
- [Final_Project/src/menu.py](</home/piratebird/Documents/Network Programming /Final_Project/src/menu.py:1>): legacy arrow-key launcher
- `Final_Project/config/`: device inventory, credentials, commands, end devices
- `Final_Project/data/`: runtime logs (e.g. `cpu_log.txt`)
- `Final_Project/assets/`: generated graphs (e.g. `cpu_progress.png`)

### Tasks and modules

Each task maps to a Python module under `Final_Project/src/`. The project is launched via `guide.py`, a Rich interactive launcher.

#### Task 1–2: Network Automation (`src/automate.py`)

Reads device inventory (`config/devices.txt`), login credentials (`config/login.txt`), and per-device commands (`config/commands.txt`). For each device:
1. Validates all input files via `src/validator.py`
2. Pings the device (ICMP reachability via `src/network.py`)
3. Connects over SSH first; falls back to Telnet if SSH is unavailable
4. Pushes configuration commands — Arista enters enable/config mode and saves; VyOS uses `send_config_set` then `commit` + `save`; MikroTik uses direct `send_command`
5. Displays a Rich summary table showing reachability, transport used, and result per device

**How it works internally:**
- `automate.py:50` — `main()` loads devices, credentials, and commands through `validator.py`, which strips comments, checks IPv4 validity via `ipaddress.IPv4Address`, and validates device types against `{"vyos", "arista_eos", "mikrotik_routeros"}`.
- `automate.py:72-86` — Each device is first ICMP-pinged via `network.check_reachability()`. Unreachable hosts are skipped and recorded as `"skipped"`.
- `automate.py:106-110` — `network.push_configurations()` iterates over `build_connection_profiles()` which yields SSH first, then a Telnet fallback profile (mapping device type to its `_telnet` variant, e.g. `vyos` → `vyos_telnet`).
- `network.py:108-126` — Within `push_configurations()`, `ConnectHandler` is opened inside a `with` block. On success, `_send_commands()` dispatches by device type:
  - **Arista** (`network.py:56-80`): calls `enable()`, enters `config_mode()`, runs commands with `send_command_timing()`, resyncs prompt after `hostname` changes, then `write memory`.
  - **VyOS** (`network.py:82-88`): uses `send_config_set()`, then `commit` + `save`.
  - **MikroTik** (`network.py:90-95`): iterates with `send_command()`.
- On failure (NetmikoTimeoutException, authentication error, etc.), the next transport profile is tried. If all fail, the error list is joined and returned as a `ConnectionResult(ok=False)`.

#### Task 3: CPU Monitor (`src/cpu_monitor.py`)

SSHs into the VyOS router and polls CPU utilization:
1. Connects using credentials from `config/login.txt`
2. Runs `top -b -n 2 -d 1` (with `sudo` fallback via `CPU_COMMANDS` list at line 17)
3. Parses the output using regex to extract the idle percentage, computing CPU load as `100 - idle`
4. Logs each sample with a timestamp to `data/cpu_log.txt`
5. After all samples, renders a Matplotlib line graph saved to `assets/cpu_progress.png`
6. Sample count and interval are configurable via CLI flags (`-n`, `-i`) or interactive prompts

**How it works internally:**
- `cpu_monitor.py:73-103` — `monitor_system()` loads the VyOS device entry and credentials via `validator.py`, then builds a Netmiko profile. It iterates transport profiles (SSH, then Telnet) from `network.build_connection_profiles()`.
- `cpu_monitor.py:107-144` — After connecting, it opens `data/cpu_log.txt` and writes a CSV header. A progress-loop polls CPU via `read_cpu_percent()` at the configured interval.
- `cpu_monitor.py:55-70` — `read_cpu_percent()` tries each command in `CPU_COMMANDS` (`top -b -n 2 -d 1`, then `sudo top -b -n 2 -d 1`), calls `parse_cpu_percent()`, and returns the first successful parse.
- `cpu_monitor.py:24-52` — `parse_cpu_percent()` applies regex fallbacks in order:
  1. `%cpu(s):` lines — extracts the `id` (idle) field from the last occurrence.
  2. `X% idle` — alternative format.
  3. `cpu states: X% user` — legacy VyOS `show system cpu` format.
  4. `%cpu(s): X us` — direct user percentage.
- If no pattern matches, `None` is returned and the sample is skipped with a warning.
- `cpu_monitor.py:161-183` — After collection, a Matplotlib figure is plotted (timestamps on x-axis, CPU % on y-axis, grid enabled) and saved to `assets/cpu_progress.png`.

#### Task 4: Packet Sniffer (`src/packet_sniffer.py`)

**Note:** Packet capture requires root privileges. Run with `sudo` or the sniffer will prompt to re-execute with elevated permissions.

Scapy-based live packet capture:
1. Lists available network interfaces (Linux `sys/class/net` or Windows `ipconfig`)
2. Prompts for interface selection, packet count, and optional BPF filter
3. Captures packets with `scapy.all.sniff()` and displays each in a live Rich table (timestamp, source, destination, protocol, length)
4. Auto-re-executes with `sudo` if insufficient permissions

**How it works internally:**
- `packet_sniffer.py:19-35` — `load_scapy_sniff()` lazily imports `scapy.all.sniff`. If Scapy is unavailable in the current interpreter, it re-executes using the project venv's Python via `os.execv()`.
- `packet_sniffer.py:59-106` — `sniff_packets()` creates a Rich `Table` with columns (Time, Source, Destination, Protocol, Length). The `handle_packet()` callback extracts `packet.src`, `packet.dst`, `packet.lastlayer().name` for protocol, and `len(packet)` for length. On each packet the console is cleared and the table is re-rendered.
- `packet_sniffer.py:108-123` — `list_interfaces()` reads `/sys/class/net` entries on Linux (filtering out `lo`), or parses `ipconfig` output on Windows.
- `packet_sniffer.py:38-56` — `prompt_sudo_reexec()` asks the user if they want to re-run with `sudo` when a `PermissionError` occurs, then calls `os.execv()` on the `sudo` binary.
- CLI supports `-i <interface>`, `-c <count>`, and `-f <BPF filter>`. Missing flags trigger interactive prompts via `Prompt.ask()`.

#### Task 5: End Device Manager (`src/end_device_manager.py`)

SSH-based management of Alpine end devices and the App Server (read from `config/end_devices.txt`):
1. **List devices** — shows name, IP, and ICMP reachability
2. **Execute command** — runs a shell command in parallel across selected devices using threading + Paramiko
3. **Change hostname** — auto-detects OS (VyOS, Ubuntu/Debian, CentOS/Fedora, or generic) and applies the appropriate command
4. **SCP file** — copies a local file to remote devices in parallel using `scp.SCPClient`
5. **Interactive shell** — full raw terminal SSH session with arrow-key support
6. **Start chat server** — SSHs into the Server device, optionally uploads `server.py`, and launches it in background or foreground

**How it works internally:**
- `end_device_manager.py:26-46` — `load_end_devices()` parses `config/end_devices.txt` using regex `name: ip (Password: pass)` and returns a dict of device entries.
- `end_device_manager.py:114-132` — `_execute_all()` is the parallel execution engine: it creates a thread per target device, each running a given `action_fn`, with a shared lock for safe result collection. Threads join with a configurable timeout.
- `end_device_manager.py:149-163` — `exec_on_devices()` sets `_command` on each device info dict, calls `_execute_all()` with `exec_cmd_on_device()`, and renders a Rich results table.
- `end_device_manager.py:166-192` — `change_hostname_on_device()` runs `cat /etc/os-release` to detect OS, then applies:
  - **VyOS**: `/configure set system host-name ... && /configure commit && /configure save`
  - **Ubuntu/Debian**: `hostnamectl set-hostname ...` + `/etc/hosts` update
  - **CentOS/Fedora**: `hostnamectl set-hostname ...`
  - **Generic/other**: `hostname ...` + write to `/etc/hostname`
- `end_device_manager.py:209-224` — `scp_to_device()` uses `scp.SCPClient` over an existing Paramiko transport to copy files with a 30-second socket timeout.
- `end_device_manager.py:249-337` — `interactive_shell()` opens a raw Paramiko `invoke_shell()` channel, sets the terminal to raw mode via `tty.setraw()`, runs a background reader thread that strips ANSI cursor-position reports (`\x1b[...R`), and forwards stdin to the channel byte-by-byte with arrow-key passthrough.
- `end_device_manager.py:340-391` — `start_chat_server_on_device()` connects to the `Server` device, optionally uploads `src/chat/server.py` via SCP if not already present, then starts the server either as a background `nohup` process or in interactive foreground mode.

#### Task 6: Chat Server (`src/chat/server.py`)

Threaded TCP chat server:
- Binds to a user-selected interface and port (default `0.0.0.0:5050`)
- Each client gets a dedicated thread
- JSON protocol: 64-byte padded length header + JSON payload
- Features: broadcast chat, `/pm` private messages, `/users`, `/rps` (Rock Paper Scissors — first to 3 wins or 5 rounds), `/files`, `/download`
- File uploads stored in `storage/uploads/` (max 150 KB)
- Client disconnect cleanup (notifies opponent if mid-game)

**How it works internally:**
- `server.py:578-598` — `start_server()` creates a TCP socket with `SO_REUSEADDR`, binds, listens, and accepts connections in a loop. Each accepted socket gets a daemon thread running `handle_client()`.
- `server.py:518-575` — `handle_client()` calls `register_client()` to validate the username (24-char max, no duplicates), then enters a receive loop calling `receive_json()`.
- `server.py:225-264` — The protocol layer: `receive_exact()` loops until exactly `HEADER_SIZE` (64) bytes are read; `receive_json()` decodes the header to get the payload length, then reads exactly that many bytes and runs `json.loads()`.
- `server.py:267-276` — `send_json_to_sock()` serializes the payload, prepends a 64-byte space-padded length header, and sends both halves via `sock.sendall()`.
- `server.py:488-512` — `handle_command()` routes incoming client messages: `/users` lists online users, `/pm` sends private messages, `/rps` starts a game, `/files` lists uploads, `/download` sends a file as hex, `/quit` raises `ConnectionError`.
- `server.py:158-213` — The `RPS` class manages game state: `add_choice()` compares choices, applies the `beats` dict (`rock→scissors`, `paper→rock`, `scissors→paper`), updates scores, and ends when a player reaches 3 wins or after 5 scored rounds.
- `server.py:318-352` — `unregister_client()` safely removes the client from global state dicts and notifies their RPS opponent if a game was in progress.

#### Task 6: Chat Client (`src/chat/client.py`)

TCP chat client that connects to the server:
- Prompts for server IP and port (default `192.168.2.100:5050`)
- Registers with a username, then runs a background receive thread for non-blocking message display
- Commands: `/help`, `/quit`, `/users`, `/pm`, `/rps`, `/files`, `/upload`, `/download`
- During RPS, typing `rock`, `paper`, or `scissors` sends the choice directly
- Downloads saved to `storage/downloads/`

**How it works internally:**
- `client.py:107-118` — `connect_and_register()` creates a TCP socket, connects with a 15-second timeout, sends a JSON `{"username": ...}` packet, then sets the socket to blocking mode.
- `client.py:67-101` — `receive_loop()` runs in a background daemon thread. It reads the 64-byte header, extracts the JSON payload length, reads the exact payload bytes, and dispatches to `print_message()` or `handle_incoming_file()`.
- `client.py:168-194` — `print_message()` decodes structured JSON: `system` messages, `error`, `chat` (broadcast), `private_message`, `users` lists, `files` lists. Each is displayed with a `\r\033[K` prefix to overwrite any prior prompt text.
- `client.py:121-147` — `send_upload()` reads a local file, checks it is under 150 KB, hex-encodes the bytes, and sends as `{"file_upload": {"name": ..., "content": hex}}`.
- `client.py:248-312` — `main()` connects, prints the help table, spawns the receiver thread, then enters an input loop. `/upload` is intercepted to call `send_upload()`, RPS choices (`rock`/`paper`/`scissors`) are sent as `{"rps_choice": ...}`, and `/quit` sets `running = False` and breaks.

### Supporting modules

- **`src/validator.py`** — loads and validates `devices.txt`, `login.txt`, and `commands.txt`:
  - `load_and_validate_devices()` (`validator.py:22`) — iterates comma-separated lines, validates IPv4 via `ipaddress.IPv4Address`, checks device type against `VALID_DEVICE_TYPES`, skips malformed lines with warnings
  - `load_credentials()` (`validator.py:51`) — parses `name,username,password` triplets, returns a `{name: {username, password}}` dict
  - `load_commands()` (`validator.py:71`) — parses `name: cmd1 | cmd2 | cmd3` lines, splits on `|`, returns `{name: [cmd, ...]}`
- **`src/network.py`** — ICMP reachability check, builds SSH-first/Telnet-fallback Netmiko profiles, executes commands per device type:
  - `check_reachability()` (`network.py:27`) — runs a single `ping -c 1` with a 2-second timeout
  - `build_connection_profiles()` (`network.py:41`) — returns `[("ssh", profile), ("telnet", telnet_profile)]` where the Telnet variant is looked up in `TELNET_DEVICE_TYPES`
  - `_send_commands()` (`network.py:53`) — dispatches by device type: Arista enters `enable()`/`config_mode()` then `write memory`; VyOS runs `send_config_set()` then `commit` + `save`; MikroTik uses direct `send_command()`
  - `push_configurations()` (`network.py:98`) — iterates transport profiles, catches `NetmikoTimeoutException`/`NetmikoAuthenticationException`/`EOFError`, returns a `ConnectionResult` dataclass
  - `ConnectionResult` (`network.py:19`) — dataclass with `ok: bool`, `output: str`, `transport: str`, `error: str`
- **`src/menu.py`** — legacy arrow-key launcher (↑/↓ to navigate, Enter to select, Ctrl+C to quit):
  - `menu.py:16-27` — `_getch()` reads a single raw keystroke using `termios`/`tty`, decodes arrow escape sequences (`\x1b[A` / `\x1b[B`)
  - `menu.py:41-55` — `draw(sel)` clears the console and renders a Rich panel with a highlighted selection
  - `menu.py:57-88` — `main()` runs the input loop, mapping ↑/↓ to index changes, Enter to `subprocess.run()` of the selected module, and Ctrl+C to exit

### Guide launcher (`guide.py`)

`guide.py` is the main entry point for the final project, located at `Final_Project/guide.py`. It presents a Rich interactive menu with numbered options:

| Key | Module | Tasks | Description |
|-----|--------|-------|-------------|
| 1 | Network Automation | 1–2 | Push configuration commands to network devices |
| 2 | CPU Monitor | 3 | Real-time VyOS CPU profiling with trend graph |
| 3 | Packet Sniffer | 4 | Scapy live packet capture with protocol inspection |
| 4 | End Device Manager | 5 | SSH management, hostname changes, SCP, shell |
| 5 | Chat Server | 6 | Multi-client TCP chat server |
| 6 | Chat Client | 6 | Connect to the chat server |
| 7 | Legacy Menu | — | Original arrow-key launcher |
| 8 | Exit | — | Leave the guide |

**How it works internally:**
- `guide.py:16-72` — The `MODULES` list defines each entry with a `key`, `name`, `tasks`, dotted `module` path (e.g. `"src.automate"`), and `description`. Option 8 (Exit) has `module: None`.
- `guide.py:75-106` — `draw_welcome()` clears the console, renders a `Panel` title with subtitle, then builds a Rich `Table` with columns Key/Module/Tasks/Description using the `MODULES` list (skipping the Exit entry).
- `guide.py:109-133` — `launch_module(module_name)` runs the module as a child process via `subprocess.run([sys.executable, "-m", module_name], cwd=BASE)`. It catches `FileNotFoundError` (module missing), `OSError`, `KeyboardInterrupt`, and general exceptions. After the subprocess exits, it waits for the user to press Enter before returning to the menu.
- `guide.py:136-167` — `main()` loops: calls `draw_welcome()`, reads user input with `input()`, matches against the `MODULES` list by key. If the choice is `"8"` or `KeyboardInterrupt` is caught, the loop breaks. Invalid choices show an error and re-prompt. On launch, `launch_module()` is called with the matched module's dotted path.

### Topology

```
[ Fedora Host Machine ]
        |
  [ Mgmt / WAN Cloud ]
        |
  [ VyOS Router ]  (192.168.1.254, 192.168.2.254)
     /       \
[ Arista ]  [ MikroTik ]
192.168.1.250  192.168.2.250
   |    \        |      \
Alpine  Alpine  Alpine  App Server
1.10    1.11    2.10    2.100
```

The chat server runs on `192.168.2.100:5050`. Clients connect from the three Alpine hosts.

### How to run

```bash
cd Final_Project
pip install -r requirements.txt
python guide.py                                    # Interactive launcher (all tasks)
python -m src.automate                             # Task 1–2: automation
python -m src.cpu_monitor                          # Task 3: CPU monitoring
sudo python -m src.packet_sniffer -i eth0 -c 20   # Task 4: packet sniffing
python -m src.end_device_manager                   # Task 5: end device manager
python -m src.chat.server --host 0.0.0.0 --port 5050  # Task 6: chat server
python -m src.chat.client                          # Task 6: chat client
```

### Handling failures

- Missing or malformed input files
- Invalid IPv4 addresses
- ICMP unreachable devices
- SSH/Telnet timeout or handshake failure
- Authentication failure
- Broken JSON payloads and oversized messages
- Client disconnect during active game
