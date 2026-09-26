# AURA Backend - API Documentation

**Base URL:** `http://localhost:8000`  
**Protocol:** HTTP/REST + WebSocket  
**Authentication:** JWT (optional)  
**Version:** 1.0

---

## 📋 Table of Contents

1. [Health Check](#health-check)
2. [Chat / AI](#chat--ai)
3. [Tools](#tools)
4. [WebSocket](#websocket)
5. [System](#system)
6. [Examples](#examples)

---

## 🏥 Health Check

### `GET /health`

Check if backend is running.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-01-29T00:00:00Z"
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

---

## 🤖 Chat / AI

### `POST /api/chat`

Send a message to AURA AI assistant.

**Request:**
```json
{
  "message": "Hello AURA, how are you?"
}
```

**Response:**
```json
{
  "response": "I'm doing great! How can I help you today?",
  "timestamp": "2026-01-29T00:00:00Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello AURA"}'
```

---

## 🔧 Tools

### `POST /api/tools/scan`

Port scan on a target host.

**Request:**
```json
{
  "target": "192.168.1.1"
}
```

**Response:**
```json
{
  "open_ports": [22, 80, 443],
  "results": [
    {"port": 22, "service": "SSH", "status": "open"},
    {"port": 80, "service": "HTTP", "status": "open"},
    {"port": 443, "service": "HTTPS", "status": "open"}
  ]
}
```

---

### `POST /api/tools/whois`

WHOIS lookup for a domain.

**Request:**
```json
{
  "domain": "example.com"
}
```

**Response:**
```json
{
  "domain": "example.com",
  "registrar": "Example Registrar",
  "created": "2020-01-01",
  "expires": "2025-01-01"
}
```

---

### `POST /api/tools/ping`

Ping a host.

**Request:**
```json
{
  "host": "8.8.8.8",
  "count": 4
}
```

**Response:**
```json
{
  "host": "8.8.8.8",
  "packets_sent": 4,
  "packets_received": 4,
  "loss": "0%",
  "avg_time": "12.5ms"
}
```

---

### `POST /api/tools/http`

HTTP headers and info.

**Request:**
```json
{
  "url": "https://example.com"
}
```

**Response:**
```json
{
  "url": "https://example.com",
  "status": 200,
  "headers": {
    "content-type": "text/html",
    "server": "nginx"
  },
  "title": "Example Domain"
}
```

---

### `POST /api/tools/geo`

GeoIP lookup.

**Request:**
```json
{
  "ip": "8.8.8.8"
}
```

**Response:**
```json
{
  "ip": "8.8.8.8",
  "country": "United States",
  "region": "California",
  "city": "Mountain View",
  "isp": "Google LLC"
}
```

---

### `POST /api/tools/hash`

Generate hashes.

**Request:**
```json
{
  "text": "password123"
}
```

**Response:**
```json
{
  "md5": "482c811da5d5b4ef6dbe2c7b2c3f1a2b",
  "sha1": "ba4b5ce6c0a7b4a4c8e3d2f1a9b8c7d6e5f4a3b2",
  "sha256": "ef92b778bafe771e89245b89ecbc4a3c8d..."
}
```

---

### `POST /api/tools/dns`

DNS lookup.

**Request:**
```json
{
  "domain": "example.com"
}
```

**Response:**
```json
{
  "a_records": ["93.184.216.34"],
  "mx_records": ["mail.example.com"],
  "ns_records": ["ns1.example.com"]
}
```

---

### `POST /api/tools/ssl`

SSL/TLS certificate info.

**Request:**
```json
{
  "host": "example.com",
  "port": 443
}
```

**Response:**
```json
{
  "subject": "example.com",
  "issuer": "Let's Encrypt",
  "valid_from": "2024-01-01",
  "valid_to": "2025-01-01",
  "version": 3
}
```

---

### `POST /api/tools/passgen`

Generate secure password.

**Request:**
```json
{
  "length": 16
}
```

**Response:**
```json
{
  "password": "aB3$xY9!pQ2@rT5#",
  "length": 16
}
```

---

## 🔌 WebSocket

### `WS /ws/telemetry`

Real-time telemetry stream.

**Connect:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/telemetry');
```

**Messages received:**
```json
{
  "type": "telemetry",
  "data": {
    "cpu": 45,
    "memory": 62,
    "network": 120,
    "timestamp": "2026-01-29T00:00:00Z"
  }
}
```

**Send:**
```json
{
  "type": "subscribe",
  "channels": ["cpu", "memory", "network"]
}
```

---

## 💻 System

### `GET /api/system/info`

Get system information.

**Response:**
```json
{
  "hostname": "aura-os",
  "os": "Alpine Linux",
  "kernel": "6.6.0",
  "uptime": 3600,
  "cpu": "4 cores",
  "memory": "8GB"
}
```

---

### `GET /api/system/status`

Get system status.

**Response:**
```json
{
  "backend": "running",
  "redis": "running",
  "postgresql": "running",
  "disk_usage": "45%",
  "memory_usage": "62%"
}
```

---

## 📊 Examples

### Python
```python
import requests

# Chat
response = requests.post('http://localhost:8000/api/chat', json={
    'message': 'Hello AURA'
})
print(response.json()['response'])

# Port scan
response = requests.post('http://localhost:8000/api/tools/scan', json={
    'target': '192.168.1.1'
})
print(response.json())
```

### JavaScript
```javascript
// Chat
const response = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Hello AURA' })
});
const data = await response.json();
console.log(data.response);
```

### Ruby
```ruby
require 'net/http'
require 'json'

uri = URI('http://localhost:8000/api/chat')
req = Net::HTTP::Post.new(uri, 'Content-Type' => 'application/json')
req.body = { message: 'Hello AURA' }.to_json

res = Net::HTTP.start(uri.hostname, uri.port) { |http| http.request(req) }
puts JSON.parse(res.body)['response']
```

### Bash
```bash
# Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello AURA"}'

# Health
curl http://localhost:8000/health

# Port scan
curl -X POST http://localhost:8000/api/tools/scan \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.1"}'
```

---

## 🚀 Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/chat` | POST | Chat with AURA |
| `/api/tools/scan` | POST | Port scan |
| `/api/tools/whois` | POST | WHOIS lookup |
| `/api/tools/ping` | POST | Ping host |
| `/api/tools/http` | POST | HTTP headers |
| `/api/tools/geo` | POST | GeoIP lookup |
| `/api/tools/hash` | POST | Generate hashes |
| `/api/tools/dns` | POST | DNS lookup |
| `/api/tools/ssl` | POST | SSL/TLS info |
| `/api/tools/passgen` | POST | Password generator |
| `/api/system/info` | GET | System info |
| `/api/system/status` | GET | System status |
| `/ws/telemetry` | WS | Real-time telemetry |

---

## 🔒 Security Notes

- Backend binds to `0.0.0.0` (all interfaces)
- No authentication by default (add JWT for production)
- CORS enabled for `localhost`
- Rate limiting: 1000 requests/minute

---

**Last updated:** 2026-01-29  
**Maintainer:** AURA OS Team
