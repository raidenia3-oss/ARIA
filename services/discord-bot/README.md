# Discord Bot

AURA's primary operations interface via Discord. Replaces Telegram as the main interaction channel.

## Stack
- Ruby 3.3+
- discordrb ~> 3.4
- Redis ~> 5.0
- dotenv ~> 2.8
- httparty ~> 0.21

## Setup

### 1. Create Discord Application
1. Go to https://discord.com/developers/applications
2. Create new application → "AURA Bot"
3. Go to "Bot" settings → Create bot → Copy token
4. Go to "OAuth2" → "URL Generator" → Select scopes:
   - `bot`
   - `applications.commands`
5. Copy invite URL, open in browser, add to your server
6. Enable **Message Content Intent** in Bot settings

### 2. Get Guild ID
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click your server → Copy ID

### 3. Configure Environment
```bash
cd services/discord-bot
cp .env.example .env.local
```

Edit `.env.local`:
```env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CLIENT_ID=your_application_id_here
DISCORD_GUILD_ID=your_guild_id_here
DISCORD_NOTIFY_CHANNEL=ops
AURA_BACKEND_URL=http://localhost:8000
REDIS_URL=redis://localhost:6379/0
```

### 4. Install Dependencies
```bash
gem install bundler
bundle install
```

### 5. Run
```bash
ruby bot.rb
```

For development with auto-reload:
```bash
gem install rerun
rerun ruby bot.rb
```

## Slash Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/status` | Show AURA services status | `/status` or `/status backend` |
| `/logs` | Get recent logs from a service | `/logs service:backend lines:50` |
| `/restart` | Restart an AURA service | `/restart service:backend` |
| `/deploy` | Deploy an AURA service | `/deploy service:hf-space` |
| `/esoteric` | Generate esoteric code challenge | `/esoteric language:brainfuck` |
| `/rules` | List automation rules | `/rules action:list` |

## Integration with AURA Backend

The bot calls the AURA backend API:
- `GET /api/status` — Service health
- `GET /api/logs` — Recent logs
- `POST /api/restart` — Restart service
- `POST /api/deploy` — Deploy service

Make sure the backend is running on `AURA_BACKEND_URL`.

## Redis Events

The bot publishes events to Redis:
- `aura:events` — List of all events (messages, voice states)
- `aura:rules` — Set of automation rules

## Docker
```bash
docker build -t aura-discord-bot services/discord-bot
docker run --env-file services/discord-bot/.env.local aura-discord-bot
```

## Testing
```bash
bundle exec rspec
```

## Production
Use a process manager like systemd or Docker Compose. See `docker/docker-compose.multi.yml`.
