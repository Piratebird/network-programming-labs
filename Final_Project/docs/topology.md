                                    [ Fedora Host Machine ]
                                 (Network Automation Engine)
                                              |
                                              | 192.168.122.1 (virbr0)
                                              |
                                     [ Mgmt / WAN Cloud ]
                                              |
                                              | eth0: 192.168.122.147/24 (DHCP)
                                    +-------------------+
                                    |    VyOS Router    |
                                    +-------------------+
             eth1: 192.168.1.254/24 /                   \ eth2: 192.168.2.254/24
                                   /                     \
                -------------------                       -------------------
               /    LAN 1 Subnet   \                     /    LAN 2 Subnet   \
               ---------------------                     ---------------------
                         |                                         |
               +-------------------+                     +-------------------+
               |   Arista Switch   |                     |  MikroTik Switch  |
               |  (192.168.1.250)  |                     |  (192.168.2.250)  |
               +-------------------+                     +-------------------+
                 |               |                         |               |
                 |               |                         |               |
            [ Alpine PC 1 ] [ Alpine PC 2 ]           [ Alpine PC 3 ] [ App Server ]
           (192.168.1.10)  (192.168.1.11)            (192.168.2.10)  (192.168.2.100)

Task 6 chat application placement:

- Run `Chat-System/server.py` on the App Server at `192.168.2.100`.
- Run `Chat-System/client.py` on `192.168.1.10`, `192.168.1.11`, and `192.168.2.10`.
- The chat clients default to `192.168.2.100:5050`.
