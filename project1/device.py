import reader as r


class Device:
    def __init__(self, device_type, name, ip, status, vlan=None):
        self.device_type = device_type
        self.name = name
        self.ip = ip
        self.status = status
        self.vlan = vlan

    def device_type_info(self):
        if self.device_type.lower().strip() == "router":
            self.name = "Router"
            pass
        elif self.device_type.lower().strip() == "switch":
            pass
        elif self.device_type.lower().strip() == "host":
            pass
        else:
            return "Unknown device type."

    def needs_attention(self):
        return self.status.lower() in ["inactive", "maintenance"]

    def get_device_info(self):
        if self.device_type == "SWITCH":
            return f"Device Type: {self.device_type}, Name: {self.name}, Status: {self.status}, VLAN: {self.vlan}"
        return f"Device Type: {self.device_type}, Name: {self.name}, IP: {self.ip}, Status: {self.status}"
