def analyze(devices):
    host = 0
    switch = 0
    router = 0

    needs_attention = []
    inactive_switches = []

    for d in devices:
        if d.device_type == "HOST":
            host += 1
        elif d.device_type == "SWITCH":
            switch += 1
            if d.status.lower().strip() == "inactive":
                inactive_switches.append(d)
        elif d.device_type == "ROUTER":
            router += 1
        else:
            print(f"Unknown device type: {d.device_type}")

        if d.needs_attention():
            needs_attention.append(d)

    return host, switch, router, needs_attention, inactive_switches
