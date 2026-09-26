#!/usr/bin/env ruby
# AURA OS — Ruby Tooling

Ruby scripts para herramientas de sistema de AURA OS:
- Network scanning avanzado
- WHOIS/DNS queries
- Hash & encoding utilities
- System automation

## Instalación

```bash
cd aura-os/ruby
bundle install
```

## Uso

```bash
# Network scanning
ruby network_scanner.rb --scan 192.168.1.0/24 --ports 1-1000

# WHOIS / DNS
ruby whois_dns.rb --whois example.com
ruby whois_dns.rb --dns example.com

# Hash utilities
ruby hash_utils.rb --hash sha256 "hello world"
ruby hash_utils.rb --encode base64 "hello world"

# System automation
ruby system_automation.rb --scan-network
ruby system_automation.rb --health-check
```
