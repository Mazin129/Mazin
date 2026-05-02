# FGT-HQ Full Lab Configuration

## 1. System Baseline

```bash
config system global
    set hostname FGT-HQ
    set admintimeout 60
    set admin-sport 443
    set timezone 04                   # Adjust to your region
    set dst enable
end

config system ntp
    set ntpsyn enable
    set type custom
    config ntpserver
        edit 1
            set server "pool.ntp.org"
        next
    end
end

config system dns
    set primary 10.99.0.10            # Win-DC-01 (internal DNS)
    set secondary 8.8.8.8
end
```

---

## 2. Interfaces

```bash
config system interface
    # WAN1 (ISP-1)
    edit "port1"
        set alias "WAN1-ISP1"
        set mode static
        set ip 203.0.113.2/30
        set allowaccess ping
        set description "ISP1 Uplink"
    next
    # WAN2 (ISP-2)
    edit "port2"
        set alias "WAN2-ISP2"
        set mode static
        set ip 198.51.100.2/30
        set allowaccess ping
        set description "ISP2 Uplink"
    next
    # FortiLink (FortiSwitch)
    edit "port3"
        set alias "FortiLink"
        set type fortilink
        set fortilink-split-interface disable
        set allowaccess ping
    next
    # DMZ
    edit "port4"
        set alias "DMZ"
        set ip 10.10.10.1/24
        set allowaccess ping https ssh
    next
    # HA Heartbeat
    edit "port5"
        set alias "HA-Heartbeat"
        set allowaccess ping
    next
    # Management
    edit "port6"
        set alias "Management"
        set ip 10.99.0.1/24
        set allowaccess https ssh ping snmp
    next
    # VLAN 10 — Data (created on FortiLink)
    edit "vlan10"
        set vdom "root"
        set ip 10.10.0.1/24
        set interface "port3"
        set vlanid 10
        set allowaccess ping
    next
    # VLAN 20 — Voice
    edit "vlan20"
        set vdom "root"
        set ip 10.20.0.1/24
        set interface "port3"
        set vlanid 20
        set allowaccess ping
    next
    # VLAN 30 — Wireless
    edit "vlan30"
        set vdom "root"
        set ip 10.30.0.1/24
        set interface "port3"
        set vlanid 30
        set allowaccess ping
    next
    # VLAN 40 — Guest
    edit "vlan40"
        set vdom "root"
        set ip 10.40.0.1/24
        set interface "port3"
        set vlanid 40
        set allowaccess ping
    next
    # VLAN 50 — IoT
    edit "vlan50"
        set vdom "root"
        set ip 10.50.0.1/24
        set interface "port3"
        set vlanid 50
        set allowaccess ping
    next
    # VLAN 99 — Management (switch devices)
    edit "vlan99"
        set vdom "root"
        set ip 10.99.1.1/24
        set interface "port3"
        set vlanid 99
        set allowaccess ping https ssh
    next
    # VLAN 100 — Quarantine
    edit "vlan100"
        set vdom "root"
        set ip 10.100.0.1/24
        set interface "port3"
        set vlanid 100
        set allowaccess ping
    next
end
```

---

## 3. SD-WAN

```bash
config system sdwan
    set status enable
    config members
        edit 1
            set interface "port1"
            set gateway 203.0.113.1
            set priority 1
        next
        edit 2
            set interface "port2"
            set gateway 198.51.100.1
            set priority 2
        next
    end
    config health-check
        edit "ISP-Health"
            set server "8.8.8.8" "1.1.1.1"
            set interval 1000
            set failtime 3
            set recoverytime 5
            set probe-timeout 500
            set members 1 2
        next
    end
    config service
        edit 1
            set name "VoIP-Steering"
            set mode sla
            set dst "all"
            set src "VLAN20-Voice"
            config sla
                edit 1
                    set health-check "ISP-Health"
                    set latency-threshold 150
                    set jitter-threshold 30
                    set packetloss-threshold 1
                next
            end
            config priority-members
                edit 1
                    set member 1
                next
                edit 2
                    set member 2
                next
            end
        next
        edit 2
            set name "Default-LoadBalance"
            set mode load-balance
            set load-balance-mode src-dst-ip-based
            config priority-members
                edit 1
                    set member 1
                next
                edit 2
                    set member 2
                next
            end
        next
    end
end
```

---

## 4. DHCP Servers

```bash
config system dhcp server
    # VLAN 10 — Data
    edit 10
        set interface "vlan10"
        set default-gateway 10.10.0.1
        set netmask 255.255.255.0
        set dns-server1 10.99.0.10
        set dns-server2 8.8.8.8
        set ip-range
            edit 1
                set start-ip 10.10.0.100
                set end-ip 10.10.0.200
            next
        end
    next
    # VLAN 20 — Voice
    edit 20
        set interface "vlan20"
        set default-gateway 10.20.0.1
        set netmask 255.255.255.0
        set dns-server1 8.8.8.8
        set ip-range
            edit 1
                set start-ip 10.20.0.100
                set end-ip 10.20.0.200
            next
        end
        # Option 150 for Cisco/IP phone TFTP
        config options
            edit 1
                set code 150
                set type ip
                set value 10.20.0.1
            next
        end
    next
    # VLAN 30 — Wireless
    edit 30
        set interface "vlan30"
        set default-gateway 10.30.0.1
        set netmask 255.255.255.0
        set dns-server1 10.99.0.10
        set ip-range
            edit 1
                set start-ip 10.30.0.50
                set end-ip 10.30.0.200
            next
        end
    next
    # VLAN 40 — Guest
    edit 40
        set interface "vlan40"
        set default-gateway 10.40.0.1
        set netmask 255.255.255.0
        set dns-server1 8.8.8.8
        set ip-range
            edit 1
                set start-ip 10.40.0.100
                set end-ip 10.40.0.250
            next
        end
        set lease-time 3600
    next
end
```

---

## 5. FortiAnalyzer Logging

```bash
config log fortianalyzer setting
    set status enable
    set server "10.99.0.60"
    set source-ip "10.99.0.1"
    set reliable enable
    set hmac-algorithm sha256
end

config log fortianalyzer filter
    set severity information
    set forward-traffic enable
    set local-traffic enable
    set sniffer-traffic disable
    set anomaly enable
    set voip disable
end
```

---

## 6. Firewall Addresses & Groups

```bash
config firewall address
    edit "VLAN10-Data"
        set subnet 10.10.0.0/24
    next
    edit "VLAN20-Voice"
        set subnet 10.20.0.0/24
    next
    edit "VLAN30-Wireless"
        set subnet 10.30.0.0/24
    next
    edit "VLAN40-Guest"
        set subnet 10.40.0.0/24
    next
    edit "VLAN50-IoT"
        set subnet 10.50.0.0/24
    next
    edit "DMZ-Servers"
        set subnet 10.10.10.0/24
    next
    edit "Branch-Site"
        set subnet 172.16.1.0/24
    next
    edit "Web-Server-01"
        set type iprange
        set start-ip 10.10.10.10
        set end-ip 10.10.10.10
    next
    edit "AD-Server"
        set fqdn "dc01.corp.local"
        set type fqdn
    next
end

config firewall addrgrp
    edit "Internal-Subnets"
        set member "VLAN10-Data" "VLAN20-Voice" "VLAN30-Wireless"
    next
    edit "Corp-Subnets"
        set member "VLAN10-Data" "VLAN20-Voice" "VLAN30-Wireless" "Branch-Site"
    next
end
```

---

## 7. Firewall Policies

```bash
config firewall policy
    # Internal → Internet
    edit 1
        set name "Internal-to-Internet"
        set srcintf "vlan10" "vlan20" "vlan30"
        set dstintf "virtual-wan-link"
        set srcaddr "Internal-Subnets"
        set dstaddr "all"
        set action accept
        set nat enable
        set schedule "always"
        set service "ALL"
        set utm-status enable
        set ssl-ssh-profile "Corp-Deep-Inspect"
        set av-profile "Corp-AV"
        set ips-sensor "Enterprise-IPS"
        set application-list "Corp-AppCtrl"
        set webfilter-profile "Corp-WebFilter"
        set logtraffic all
    next
    # Guest → Internet only (captive portal)
    edit 2
        set name "Guest-to-Internet"
        set srcintf "vlan40"
        set dstintf "virtual-wan-link"
        set srcaddr "VLAN40-Guest"
        set dstaddr "all"
        set action accept
        set nat enable
        set schedule "always"
        set service "HTTP" "HTTPS" "DNS"
        set logtraffic all
        set groups "Guest-Users"
    next
    # IoT — restricted
    edit 3
        set name "IoT-Restricted"
        set srcintf "vlan50"
        set dstintf "vlan10"
        set srcaddr "VLAN50-IoT"
        set dstaddr "VLAN10-Data"
        set action deny
        set logtraffic all
    next
    # DMZ → Internal (deny by default)
    edit 4
        set name "DMZ-to-Internal-Deny"
        set srcintf "port4"
        set dstintf "vlan10"
        set srcaddr "DMZ-Servers"
        set dstaddr "Internal-Subnets"
        set action deny
        set logtraffic all
    next
    # VPN — Branch to HQ
    edit 5
        set name "Branch-to-HQ"
        set srcintf "HQ-to-BR1"
        set dstintf "vlan10"
        set srcaddr "Branch-Site"
        set dstaddr "VLAN10-Data"
        set action accept
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next
    # HQ to Branch
    edit 6
        set name "HQ-to-Branch"
        set srcintf "vlan10"
        set dstintf "HQ-to-BR1"
        set srcaddr "VLAN10-Data"
        set dstaddr "Branch-Site"
        set action accept
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next
    # Inbound DNAT — Web server VIP
    edit 7
        set name "Internet-to-WebServer"
        set srcintf "virtual-wan-link"
        set dstintf "port4"
        set srcaddr "all"
        set dstaddr "VIP-WebServer"
        set action accept
        set schedule "always"
        set service "HTTP" "HTTPS"
        set utm-status enable
        set ips-sensor "Enterprise-IPS"
        set logtraffic all
    next
end
```

---

## 8. IPsec VPN — HQ Side

```bash
config vpn ipsec phase1-interface
    edit "HQ-to-BR1"
        set interface "port1"
        set ike-version 2
        set peertype one
        set remote-gw 198.51.100.5          # Branch WAN IP
        set proposal aes256gcm-prfsha256
        set dhgrp 19
        set psksecret Fortinet123!
        set dpd on-idle
        set dpd-retryinterval 20
        set net-device enable
        set auto-discovery-sender enable
    next
end

config vpn ipsec phase2-interface
    edit "HQ-to-BR1-P2"
        set phase1name "HQ-to-BR1"
        set proposal aes256gcm
        set pfs enable
        set dhgrp 19
        set auto-negotiate enable
        set keylifeseconds 3600
    next
end

config system interface
    edit "HQ-to-BR1"
        set ip 169.254.0.1/30
        set remote-ip 169.254.0.2
    next
end

config router static
    edit 10
        set dst 172.16.1.0/24
        set device "HQ-to-BR1"
    next
end
```

---

## 9. RADIUS Authentication (FortiAuthenticator)

```bash
config user radius
    edit "FortiAuth-RADIUS"
        set server "10.99.0.50"
        set secret Fortinet123!
        set auth-type auto
        set radius-coa enable
        set radius-port 1812
        set acct-server "10.99.0.50"
        set acct-port 1813
        set acct-secret Fortinet123!
    next
end

config user group
    edit "Corp-Dot1X-Users"
        set member "FortiAuth-RADIUS"
    next
    edit "Guest-Users"
        set member "FortiAuth-RADIUS"
    next
end
```

---

## 10. High Availability

```bash
config system ha
    set mode a-p
    set group-id 1
    set group-name "FCSS-HA"
    set password Fortinet123!
    set priority 200
    set override enable
    set hbdev "port5" 50
    set session-sync-dev "port5"
    set monitor "port1" "port2" "port3"
    set unicast-hb enable
    set unicast-hb-peerip 10.0.5.2     # Secondary HA port5 IP
    set ha-mgmt-status enable
    config ha-mgmt-interfaces
        edit 1
            set interface "port6"
            set gateway 10.99.0.254
        next
    end
end
```

---

## 11. Security Fabric

```bash
config system csf
    set status enable
    set group-name "FCSS-Fabric"
    set group-password Fortinet123!
    set upstream-ip 0.0.0.0            # This is root
    set fabric-object-unification default
    config trusted-list
        edit 1
            set authorization-type serial
            set serial "FGT60F-BR1SERIAL"
        next
    end
end

config log fortianalyzer setting
    set status enable
    set server "10.99.0.60"
end
```

---

## 12. SSL Inspection Profile

```bash
config firewall ssl-ssh-profile
    edit "Corp-Deep-Inspect"
        set caname "Fortinet_CA_SSL"
        set untrusted-caname "Fortinet_CA_Untrusted"
        config https
            set ports 443
            set status deep-inspection
        end
        config ssl-exempt
            edit 1
                set type category
                set category 6          # Finance
            next
            edit 2
                set type category
                set category 61         # Health and medicine
            next
        end
    next
end
```
