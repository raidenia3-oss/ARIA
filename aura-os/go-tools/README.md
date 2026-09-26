# AURA Go Tools

High-performance networking tools written in Go for AURA OS.

## Features

- **aura-scanner** — Ultra-fast concurrent port scanner (65535 ports in <30s)
- **aura-resolver** — DNS resolver with DoH support
- **aura-enum** — Parallel subdomain enumerator
- Static binaries (no dependencies, works everywhere)
- JSON/Text output formats
- Goroutine-based parallelism

## Installation

### From Source

```bash
cd aura-os/go-tools
make build
make install
```

### Docker

```bash
docker build -t aura-go-tools .
docker run -it aura-go-tools aura-scanner -h localhost -p 1 -e 1000
```

## Usage

### Port Scanner

Scan a single host:

```bash
aura-scanner -h 192.168.1.1 -p 1 -e 65535 -w 100
```

Parameters:
- `-h` — Target host
- `-p` — Start port (default: 1)
- `-e` — End port (default: 1000)
- `-w` — Workers/goroutines (default: 100)
- `-t` — Timeout (default: 3s)
- `-f` — Format: text/json (default: text)
- `-o` — Output file

Output:

```
[*] Starting scan of 192.168.1.1 (ports 1-65535, 100 workers)
[+] Port 22/tcp (SSH) - OPEN
[+] Port 80/tcp (HTTP) - OPEN
[+] Port 443/tcp (HTTPS) - OPEN
[*] Scan completed in 24.35 seconds
[*] Found 3 open ports
```

### DNS Resolver

Resolve domain:

```bash
aura-resolver -d google.com -t A
```

Bulk resolve:

```bash
aura-resolver -d google.com -b A,AAAA,MX,NS
```

Parameters:
- `-d` — Domain
- `-t` — Record type: A, AAAA, MX, NS, TXT, CNAME
- `-b` — Bulk (comma-separated types)
- `-o` — Format: text/json

### Subdomain Enumerator

Enumerate subdomains:

```bash
aura-enum -d example.com -w wordlist.txt -j 10
```

Parameters:
- `-d` — Domain
- `-w` — Wordlist file
- `-j` — Workers (default: 10)
- `-o` — Format: text/json

## Performance Targets

| Tool | Target |
|------|--------|
| aura-scanner | 65535 ports in <30s |
| aura-resolver | 10k+ queries/sec |
| aura-enum | 1000+ subdomains/min |

## Building Static Binaries

All binaries are built with:

```
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w"
```

This produces fully static executables with zero dependencies.

## Integration with AURA

These tools can be called from AURA skills:

```python
# backend/skills/custom/go_scan.py

import subprocess
import json

def scan_ports(host: str, start_port: int = 1, end_port: int = 1000):
    """Execute aura-scanner"""
    result = subprocess.run(
        ["aura-scanner", "-h", host, "-p", str(start_port), "-e", str(end_port), "-f", "json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)
```

## Requirements

- Go 1.21+
- Linux/macOS/Windows (binaries built for Linux by default)
- net, flag, encoding/json (stdlib only)

## License

MIT
