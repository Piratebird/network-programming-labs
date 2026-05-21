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

### How the data flows

```text
inventory.txt -> reader.py -> parser.py -> analyzer.py -> console/report output
```

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

### How it works

The server listens for incoming TCP connections. Each connected client runs in its own thread, so one user can send messages without blocking everyone else.

Every message uses a simple JSON protocol:

```text
64-byte message length header -> JSON message body
```

For example, when a client sends a chat message, the client first sends a fixed-size length header. The server reads that header, then reads exactly that many bytes for the JSON payload. This prevents partial socket reads from breaking the message.

### Data flow

```text
client.py -> JSON over TCP -> server.py -> command handler -> other clients/files/game state
```

Normal chat messages are broadcast to all connected users. Commands like `/users`, `/pm`, `/files`, `/download`, and `/rps` are handled by the server.

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
