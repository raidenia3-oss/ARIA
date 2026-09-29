# Discord Bot Setup Guide for ARIA v6.0

## Bot Identity
- **Bot Name**: ARIA
- **Discord Tag**: ARIA#4852
- **Application ID**: Create at https://discord.com/developers/applications

---

## 1. Create Discord Application

1. Go to https://discord.com/developers/applications
2. Click **New Application** → Name: `ARIA`
3. Go to **Bot** tab → Click **Add Bot** → Confirm
4. Copy **Token** → Save as `DISCORD_BOT_TOKEN` in `.env`
5. Enable **Message Content Intent** and **Server Members Intent**
6. Go to **OAuth2** → **URL Generator** → Scopes: `bot`, `applications.commands`
7. Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Use Slash Commands`
8. Copy generated URL, open in browser, add bot to your server

---

## 2. Channel Configuration

Create these channels in your Discord server:

| Channel | Purpose | Webhook Name |
|---------|---------|--------------|
| `#aria-status` | System online/offline, health checks | ARIA Status |
| `#aria-tasks` | Task assignments, completions, failures | ARIA Tasks |
| `#aria-improvements` | Auto-commits, GitHub issues, code changes | ARIA Improvements |
| `#aria-logs` | Debug logs, errors, verbose output | ARIA Logs |

### Create Webhooks for Each Channel

For each channel:
1. Right-click channel → **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**
2. Name: `ARIA [Channel]` (e.g., `ARIA Status`)
3. Copy **Webhook URL** → Add to `.env`

### Environment Variables

```env
# .env (git-ignored)
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_WEBHOOK_STATUS=https://discord.com/api/webhooks/xxx/yyy
DISCORD_WEBHOOK_TASKS=https://discord.com/api/webhooks/xxx/yyy
DISCORD_WEBHOOK_IMPROVEMENTS=https://discord.com/api/webhooks/xxx/yyy
DISCORD_WEBHOOK_LOGS=https://discord.com/api/webhooks/xxx/yyy

# Single webhook fallback (used by USB agent & autonomous)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy

# GitHub integration (for autonomous controller)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=yourusername/aria-repo

# ARIA config
ARIA_BASE_URL=http://127.0.0.1:8002
ARIA_REPO_ROOT=C:/Users/User/Downloads/AURA
ARIA_BRANCH=feature/v6.0-axum-migration
ARIA_IDLE_THRESHOLD=60
ARIA_POLL_INTERVAL=30
ARIA_HEARTBEAT_INTERVAL=30
ARIA_AUTONOMOUS_INTERVAL=300
```

---

## 3. Webhook Integration

### Python (stdlib only - urllib)

```python
import json
import urllib.request

def discord_notify(webhook_url: str, content: str, username: str = "ARIA") -> bool:
    payload = json.dumps({"content": content, "username": username}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 204
    except Exception:
        return False

# Usage
discord_notify(WEBHOOK_STATUS, "🟢 **Backend Online**\nPort: 8002")
discord_notify(WEBHOOK_TASKS, "📋 Task `abc123` assigned to USB-ARIA")
discord_notify(WEBHOOK_IMPROVEMENTS, "✅ Auto-committed 3 improvements")
discord_notify(WEBHOOK_LOGS, "⚠️ Error: Connection timeout")
```

### Embed Example (Rich Formatting)

```python
def discord_embed(webhook_url: str, title: str, description: str, color: int = 0x00ffff, fields: list = None):
    embed = {"title": title, "description": description, "color": color}
    if fields:
        embed["fields"] = [{"name": k, "value": v, "inline": True} for k, v in fields]
    payload = json.dumps({"embeds": [embed], "username": "ARIA"}).encode()
    # ... same urllib request as above
```

### Color Codes
- `0x00ffff` - Cyan (info)
- `0x00ff00` - Green (success)
- `0xffaa00` - Orange (warning)
- `0xff0000` - Red (error)
- `0x8000ff` - Purple (autonomous)

---

## 4. Bot Commands (Optional)

If using slash commands via `discord.py` or similar:

| Command | Description |
|---------|-------------|
| `/aria status` | Show backend health, agent status |
| `/aria tasks` | List pending/completed tasks |
| `/aria logs [lines]` | Show recent logs |
| `/aria restart [component]` | Restart backend/agent/autonomous |
| `/aria config` | Show current configuration |

---

## 5. Testing Webhooks

```bash
# Test each webhook
curl -X POST "$DISCORD_WEBHOOK_STATUS" \
  -H "Content-Type: application/json" \
  -d '{"content": "🟢 Test from ARIA Status webhook", "username": "ARIA"}'

curl -X POST "$DISCORD_WEBHOOK_TASKS" \
  -H "Content-Type: application/json" \
  -d '{"content": "📋 Test from ARIA Tasks webhook", "username": "ARIA"}'

curl -X POST "$DISCORD_WEBHOOK_IMPROVEMENTS" \
  -H "Content-Type: application/json" \
  -d '{"content": "✅ Test from ARIA Improvements webhook", "username": "ARIA"}'

curl -X POST "$DISCORD_WEBHOOK_LOGS" \
  -H "Content-Type: application/json" \
  -d '{"content": "📝 Test from ARIA Logs webhook", "username": "ARIA"}'
```

---

## 6. Security Notes

- **Never commit `.env`** - Already in `.gitignore`
- Rotate tokens if exposed: Discord Developer Portal → Bot → Reset Token
- Use separate webhooks per channel for granular permissions
- Webhook URLs are secrets - treat like passwords
- For production, consider Discord Bot (not just webhooks) for interactive commands

---

## 7. Troubleshooting

| Issue | Solution |
|-------|----------|
| Webhook returns 404 | URL incorrect or webhook deleted |
| Webhook returns 401 | Token invalid, regenerate webhook |
| No messages in channel | Check channel permissions, webhook channel match |
| Rate limited (429) | Add delay, Discord limits: 30 req/min per webhook |
| Bot not responding | Check intents enabled, bot online in server |

---

## 8. Files Using Discord Integration

| File | Webhooks Used |
|------|---------------|
| `v6/aria_usb_agent.py` | `DISCORD_WEBHOOK_URL` (fallback) |
| `v6/aria_autonomous.py` | `DISCORD_WEBHOOK_URL` (fallback) |
| Future: `aria_discord_bot.py` | All four webhooks + bot token |

---

## Quick Start Checklist

- [ ] Create Discord Application
- [ ] Create Bot user, copy token
- [ ] Enable Message Content Intent
- [ ] Generate OAuth2 URL, add to server
- [ ] Create 4 channels: `#aria-status`, `#aria-tasks`, `#aria-improvements`, `#aria-logs`
- [ ] Create webhook in each channel, copy URLs
- [ ] Add all variables to `.env`
- [ ] Test each webhook with curl
- [ ] Run `start_all.bat` and verify notifications appear