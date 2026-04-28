import os


def write_report(host, switch, router, needs_attention):
    output_path = os.path.join(os.path.dirname(__file__), "network_audit.txt")

    with open(output_path, "w") as file:
        file.write("--- Enterprise Network Audit ---\n\n")
        file.write(f"Hosts: {host}\n")
        file.write(f"Switches: {switch}\n")
        file.write(f"Routers: {router}\n\n")

        file.write("Devices needing attention:\n")
        for i, device in enumerate(needs_attention, start=1):
            file.write(f" - {i}, {device.get_device_info()}\n")
