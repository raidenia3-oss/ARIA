# AURA Ruby Tools

Advanced scripting toolkit for AURA OS in Ruby.

## Features

- **Network Scanner** — Ping, port scanning, network enumeration
- **DNS Resolver** — Lookup, reverse lookup, WHOIS, subdomain enumeration
- **Hash Tools** — MD5, SHA1, SHA256, SHA512, bcrypt, base64
- **System Tools** — CPU, memory, processes, uptime

## Installation

```bash
cd aura-os/ruby-tools
bundle install
```

## Usage

### CLI

```bash
# Network
./bin/aura-ruby network ping google.com
./bin/aura-ruby network scan 192.168.1.0/24
./bin/aura-ruby network ports 192.168.1.1

# DNS
./bin/aura-ruby dns lookup example.com
./bin/aura-ruby dns whois 8.8.8.8
./bin/aura-ruby dns subdomains example.com

# Hash
./bin/aura-ruby hash sha256 "hello world"
./bin/aura-ruby hash bcrypt "mypassword"

# System
./bin/aura-ruby system cpu
./bin/aura-ruby system processes
./bin/aura-ruby system uptime
```

### Programmatic

```ruby
require_relative 'lib/aura_tools'

# Network scanning
scanner = AuraTools::NetworkScanner.new
result = scanner.ping("8.8.8.8")
puts result.inspect

# DNS lookup
resolver = AuraTools::DNSResolver.new
ips = resolver.lookup("google.com")
puts ips.inspect

# Hashing
hash = AuraTools::HashTools.sha256("secret")
puts hash

# System info
cpu = AuraTools::SystemTools.cpu_usage
puts cpu.inspect
```

## Requirements

- Ruby 2.7+
- Bundler
- nmap (for port scanning)
- dnsmasq or bind-tools (for DNS)

## License

MIT
