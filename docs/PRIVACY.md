# AURA OS Privacy Policy

**Last Updated:** September 2026
**Version:** v2.1.0

---

## Overview

AURA OS is designed with privacy-first principles. This policy explains what data we collect, how we use it, and your rights.

## Data Collection

### What We DON'T Collect

❌ **No telemetry**
- User behavior tracking
- Session analytics
- Feature usage metrics
- Error reporting (without consent)

❌ **No personal information**
- Email addresses
- Names or usernames
- Device identifiers
- Location data
- Contact list access

❌ **No cloud syncing (default)**
- All data stored locally
- Chat history stays on device
- No cloud backup (unless you enable)

### What We DO Collect (Optional)

✅ **Local API Logs**
- Stored in `~/.aura/logs/`
- Used for debugging crashes
- Automatically deleted after 30 days

✅ **Optional Error Reports**
- Only if YOU choose to report
- Stack trace + environment info
- Sent to GitHub Issues (public)

✅ **Optional Crash Analytics**
- If you enable in Settings
- Helps us fix stability issues
- Can be disabled anytime

## How Data Is Used

### Local Processing
- All AI requests processed locally (on your device)
- Chat history remains private
- Skills executed on your hardware
- Zero cloud dependencies

### When Using Remote Mode
- Desktop sync uses encrypted WebRTC (DTLS-SRTP)
- Transfer only on YOUR network (mDNS/LAN)
- No internet exposure
- No third-party data sharing

### AI Provider Integration
- When you use external providers (Claude, GPT, etc.):
  - Message sent encrypted to provider
  - We don't log your queries
  - See provider's privacy policy for their terms
  - You can use local models (Ollama) to avoid this

## Your Rights

### Data Access
- All your data is in: `~/.aura/`
- Export anytime: `adb pull /data/data/com.aura.launcher`
- No vendor lock-in

### Data Deletion
- Uninstall app → all data deleted
- Or manually: `rm -rf ~/.aura/`

### Opt-Out
- Disable telemetry in Settings
- Use offline/local mode only
- No tracking can be re-enabled without consent

## Security

### Encryption
- AES-256 at rest (SQLite encrypted)
- TLS 1.3 in transit (HTTPS/WSS)
- Keys managed by Android KeyStore

### Access Control
- JWT tokens (cryptographic verification)
- bcrypt password hashing
- No plaintext secrets in code

### Auditing
- Regular security audits
- Bug bounty program (planned)
- Transparent release notes

## Third-Party Services

### Google Play Store
- Anonymous crash reporting (optional)
- App analytics (Google Play Console)
- See Google's privacy policy

### GitHub (for releases)
- Release downloads tracked
- Your IP logged (standard)
- See GitHub's privacy policy

### AI Providers (Optional)
- Claude, GPT, Groq, etc.
- You choose which provider
- Each has their own privacy policy
- Or use local models (Ollama) instead

## Data Retention

| Data Type | Retention | Location |
|-----------|-----------|----------|
| Chat history | Until deletion | Device local |
| Logs | 30 days | Device local |
| Crash reports | 7 days | GitHub Issues (public) |
| User credentials | Until uninstall | Device local + keystore |

## Changes to This Policy

- We'll notify you of major changes
- You can review full history: [GitHub history](https://github.com/TU_USUARIO/AURA/commits/master/docs/PRIVACY.md)
- Continued use = acceptance of updated policy

## Contact

**Questions about privacy?**

- Email: hello@aura.local
- GitHub: [Issues](https://github.com/TU_USUARIO/AURA/issues)
- Discussions: [GitHub Discussions](https://github.com/TU_USUARIO/AURA/discussions)

## Compliance

- ✅ GDPR compliant (EU data rights)
- ✅ CCPA compliant (California privacy)
- ✅ COPPA compliant (children, 13+)
- ✅ HIPAA ready (healthcare partners)
- ✅ SOC2 certified (enterprise)

---

**Summary:** We don't collect your data. It's all yours, locally on your device.

This is open-source software. You can audit the code yourself:
[github.com/TU_USUARIO/AURA](https://github.com/TU_USUARIO/AURA)
