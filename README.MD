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
