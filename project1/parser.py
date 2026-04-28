# device -> the file where the Device class is defined
from device import Device


def parse_devices(device_info):
    devices = []
    for record in device_info:
        try:
            if not record:
                continue

            device_type = record[0].strip().upper()

            # host (3 fields: type, ip, status)
            if device_type == "HOST":
                if len(record) < 3:
                    raise ValueError("Insufficient data for host.")

                ip = record[1]
                status = record[2]
                devices.append(Device("HOST", ip, ip, status))

            # switch (4 fields: type, name, status, vlan)
            elif device_type == "SWITCH":
                if len(record) < 4:
                    raise ValueError("Insufficient data for switch.")

                name = record[1]
                status = record[2]
                vlan = record[3]
                devices.append(Device("SWITCH", name, None, status, vlan))

            # router (4 fields: type, name, status, ip)
            elif device_type == "ROUTER":
                if len(record) < 4:
                    raise ValueError("Insufficient data for router.")

                name = record[1]
                status = record[2]
                ip = record[3]
                devices.append(Device("ROUTER", name, ip, status))
            else:
                print(f"Skipping unknown device type: {record[0]}")
        except Exception as e:
            print("Skipping bad data:", e)

    return devices
