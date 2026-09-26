# Quick Start — AURA/AME v3.0 (5-10 minutes)

## 1. Clone (1 min)
```bash
git clone https://github.com/raidenia3-oss/AURA-server.01.git
cd frontend
npm install
```

## 2. Run (1 min)
```bash
npm run dev
# Open http://localhost:3000
```

## 3. Explore (3 min)
- **Integrations:** http://localhost:3000/integrations
  - See all 5 integrations (Slack, Discord, Telegram, Teams, Webhooks)
  - Click buttons to install/configure

- **Analytics:** http://localhost:3000/analytics
  - View real-time events
  - Check integration status
  - Track errors

- **API Health:** http://localhost:3000/api/health
  - Should return `{"ok":true,...}`

## 4. Configure (3 min)
```bash
cp .env.example .env.local
# Edit .env.local with your API keys (optional)
```

## 5. Deploy (1 min)
```bash
git push origin main
# Auto-deploys to Vercel
# Check: https://aura-web-chi-seven.vercel.app
```

---

**That's it! You now have a working AURA/AME instance.**

For more details, see:
- README.md (full documentation)
- ARCHITECTURE.md (system design)
- EXAMPLES.md (integration examples)
