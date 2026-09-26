# Task: Integrate Security Assessment Module into AURA OS

**Status**: PENDING  
**Assigned to**: AURA OS autonomous agent  
**Priority**: Medium  
**Created**: 2026-09-02  

## Context

A standalone defensive security assessment module was created at `tools/security_assessment/` as a separate package (28 tests, all passing). It was NOT integrated with the core backend (`backend/main.py`) and should remain separate until AURA OS autonomously merges it.

## What NOT to Integrate

The Copilot investigation of `Mikacr1138/claude-bug-bounty` found these items that should **NEVER** be integrated:

- [ ] `h1_idor_scanner.py` — Active IDOR scanning against HackerOne
- [ ] `h1_race.py` — Race condition testing
- [ ] `zero_day_fuzzer.py` — Fuzzer (untested payloads)
- [ ] Any code with `subprocess.run(..., shell=True)` — Shell injection risk
- [ ] Payloads targeting external domains (HackerOne, Bugcrowd, etc.)
- [ ] RCE/SSRF payloads in exploit.py
- [ ] The `.zip`/`.exe` installer linked in the original repo

## What CAN be Integrated (Defensive Concepts Only)

The `tools/security_assessment/` module contains:
- `scope.py` — Allowlist-based scope validation
- `evidence.py` — Evidence anonymization (IPs hashed, secrets redacted)
- `passive_recon.py` — Read-only HTTP/DNS/SSL checks only
- `triage.py` — AI classification using Omniroute (with local fallback)
- `policy.py` — Dry-run mode, rate limits, exploit blocking, Discord approval
- `report.py` — JSON + Markdown reports with evidence hashes

## Integration Steps (for AURA OS to execute)

1. **Verify module isolation** (no shared state with main backend):
   ```bash
   python -m pytest tools/security_assessment/tests/ -v
   # Expected: 28 passed
   ```

2. **Integrate scope validation with main.py routes** (optional):
   - Add `POST /api/security/assess` endpoint that accepts target URLs
   - Validate scope via `PolicyEnforcer.validate()` before processing
   - Return 403 if target is external or not in allowlist

3. **Integrate triage with omniroute**:
   - Use existing `/api/chat/omniroute` endpoint for AI classification
   - If no providers available, fall back to local rules
   - Store findings in the existing telemetry system

4. **Connect audit log to existing logging**:
   - Pipe `PolicyEnforcer.get_audit_log()` to `backend/logging/config.py`
   - Add `audit=True` flag to security-related routes

5. **Connect to Discord bot**:
   - Use `services/discord-bot/bot.rb` for approval notifications
   - Add `!security approve` and `!security reject` commands
   - Send findings to `#security` channel

6. **Run in dry-run mode by default**:
   - All `PolicyEnforcer` instances start with `dry_run=True`
   - `SECURITY_DRY_RUN=false` must be explicitly set to enable execution

## Safety Requirements

- [ ] No `shell=True` in any subprocess calls
- [ ] No external network requests (except to localhost/allowlist)
- [ ] All evidence anonymized before storage
- [ ] All actions logged with hash references (not raw data)
- [ ] Exploit classification blocked unconditionally
- [ ] Rate limit: 60 requests/minute per target
- [ ] All reports reference hashed evidence, never raw IPs/hostnames

## Verification

After integration:
```bash
python -c "from tools.security_assessment import default_policy, PolicyEnforcer; print('Integration OK')"
bash -n scripts/security-audit.sh
```

## Notes

- The module was designed to be defensive-only from inception
- No code from the BountyBot repo was copied
- All patterns and logic are original to this project
- The module uses the existing AURA backend's omniroute integration for AI triage
