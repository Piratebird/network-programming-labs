class Device:
    def __init__(self, device_type, name, ip, status, vlan=None):
        self.device_type = device_type.strip().upper()
        self.name = name
        self.ip = ip
        self.status = status
        self.vlan = vlan

    def device_type_info(self):
        device_labels = {
            "HOST": "Host",
            "SWITCH": "Switch",
            "ROUTER": "Router",
        }
        return device_labels.get(self.device_type, "Unknown device type")

    def needs_attention(self):
        return self.status.lower().strip() in ["inactive", "maintenance"]

    def get_device_info(self):
        device_class = self.device_type_info()

        if self.device_type == "HOST":
            return f"Device Class: {device_class}, IP: {self.ip}, Status: {self.status}"

        if self.device_type == "SWITCH":

            return (
                f"Device Class: {device_class}, Name: {self.name}, "
                f"Status: {self.status}, VLAN: {self.vlan}"
            )

        if self.device_type == "ROUTER":
            return (
                f"Device Class: {device_class}, Name: {self.name}, "
                f"IP: {self.ip}, Status: {self.status}"
            )

        return (
            f"Device Class: {device_class}, Name: {self.name}, "
            f"IP: {self.ip}, Status: {self.status}"
        )
