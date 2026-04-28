import reader
import parser
import writer
from analyzer import analyze

logo = r"""
_   _ _____ _______        _____  ____  _  __    _   _   _ ____ ___ _____ 
| \ | | ____|_   _\ \      / / _ \|  _ \| |/ /   / \ | | | |  _ \_ _|_   _|
|  \| |  _|   | |  \ \ /\ / / | | | |_) | ' /   / _ \| | | | | | | |  | |  
| |\  | |___  | |   \ V  V /| |_| |  _ <| . \  / ___ \ |_| | |_| | |  | |  
|_| \_|_____| |_|    \_/\_/  \___/|_| \_\_|\_\/_/   \_\___/|____/___| |_|      """

print(logo)


def main(file_path="inventory.txt"):

    # read the file and parse the devices
    device_info = reader.read_file(file_path)
    devices = parser.parse_devices(device_info)
    host, switch, router, needs_attention, inactive_switches = analyze(devices)

    # print the results

    print(f"Hosts: {host}")
    print(f"Switches: {switch}")
    print(f"Routers: {router}")

    print(f"\nDevices needing attention:")
    for i, device in enumerate(needs_attention, start=1):
        print(f" - {i}, {device.get_device_info()}")

    print(f"\nInactive switches: {len(inactive_switches)}")
    for s in inactive_switches:
        print(f" - {s.name}, {s.vlan}")

    return host, switch, router, needs_attention


if __name__ == "__main__":
    while True:
        try:
            choice = input(
                "What would you like to do?\n1.Check CLI output\n2.Check inventory file\n3.Exit\n"
            )

            if choice == "1":
                print("Checking CLI output...")
                host, switch, router, needs_attention = main()

            elif choice == "2":
                print("Checking inventory file...")

                device_info = reader.read_file("inventory.txt")
                devices = parser.parse_devices(device_info)

                host, switch, router, needs_attention, inactive_switches = analyze(
                    devices
                )

                writer.write_report(host, switch, router, needs_attention)
                print("Report created: network_audit.txt")

            elif choice == "3":
                print("Exiting...")
                break
        except KeyboardInterrupt as e:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
