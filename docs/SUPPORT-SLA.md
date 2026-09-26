# AURA OS v2.1 — Support & Response SLAs

Community support levels and response time expectations.

## Response Time Guarantees

| Issue Type | Priority | Response Time | Resolution Target |
|---|---|---|---|
| **Critical Bug** | P1 | <30 minutes | <24 hours |
| **Major Bug** | P2 | <2 hours | <48 hours |
| **Minor Bug** | P3 | <8 hours | <1 week |
| **Feature Request** | P4 | <24 hours | Roadmap |
| **Question/Help** | P5 | <24 hours | <2 days |

## Issue Classification

### Critical (P1) — Response: <30min

**When to use P1:**
- API completely down (500 errors)
- Security vulnerability discovered
- Data loss potential
- Complete feature broken for all users

**Example:**
- "Backend throwing 500 on all endpoints"
- "SQL injection vulnerability found in auth"
- "Database connection lost, all data inaccessible"

### Major (P2) — Response: <2h

**When to use P2:**
- Feature partially broken
- High-impact data corruption
- Performance severely degraded (>5s latency)
- Multi-provider routing failing

**Example:**
- "Chat endpoint returning 400 errors 50% of the time"
- "Memory usage climbing indefinitely"
- "C2 framework not accepting new agents"

### Minor (P3) — Response: <8h

**When to use P3:**
- Non-critical feature broken
- UI/UX issue
- Performance issue (<5s, tolerable)
- Documentation error

**Example:**
- "Dashboard doesn't load on Safari"
- "Help text formatting broken"
- "Getting 2s latency (usually <500ms)"

### Feature Request (P4) — Response: <24h

**When to use P4:**
- New capability request
- Enhancement to existing feature
- Quality of life improvement

**Example:**
- "Would love GraphQL API support"
- "Can we add webhook notifications?"
- "Dark mode for dashboard?"

### Question/Help (P5) — Response: <24h

**When to use P5:**
- How to use a feature
- Deployment question
- Integration help

**Example:**
- "How do I enable local models?"
- "What's the recommended deployment for production?"
- "Can I use AURA OS with Kubernetes?"

## Support Channels

### GitHub Issues ⭐ (Primary)
- **Response Time:** Within SLA above
- **Best for:** Bug reports, feature requests
- **Use template:** bug.md or feature.md
- **Search first:** Avoid duplicates

### GitHub Discussions 💬 (Secondary)
- **Response Time:** <24 hours
- **Best for:** Questions, help, ideas
- **No template needed:** Informal discussion
- **Self-help:** Community can answer

### Discord (Tertiary, if available)
- **Response Time:** Best-effort
- **Best for:** Quick questions, community chat
- **Not monitored 24/7:** Use GitHub for guarantees

## Priority Assignment Process

When you open an issue:

1. **Self-assess priority:**
   ```
   - Am I blocked completely? → P1
   - Can I work around this? → P2/P3
   - Is this a request? → P4
   - Am I asking for help? → P5
   ```

2. **Add priority label:**
   The maintainer will adjust if needed.

3. **Provide reproduction steps:**
   Include: exact commands, expected output, actual output, environment.

4. **P1 issues get immediate attention:**
   Maintainers are alerted via Discord webhook.

## Support Availability

| Time | Coverage |
|---|---|
| Weekdays 9AM-9PM UTC | Full support |
| Weekends 10AM-6PM UTC | Best-effort |
| Outside hours | Critical issues only (P1) |
| Holidays | Minimum coverage |

## SLA Exclusions

The following are NOT eligible for SLA responses:
- Feature requests marked P4 that are "nice to have"
- Issues without reproduction steps
- Duplicate issues
- Issues in archived/experimental repos
- Support for self-modified forks

## Community Support

- **Documentation:** Check docs/ first
- **GitHub Search:** Search existing issues before creating new ones
- **Community Discord:** For informal chat and peer support
- **Stack Overflow:** Tag `aura-os` for Q&A

## Escalation

If your issue isn't getting attention within the SLA:

1. Comment "@maintainer" on the issue
2. Message in Discord #support channel
3. Email: support@aura-os.dev (P1 issues only)

---

**Last Updated:** September 2, 2026  
**Version:** v2.1.0 SLAs apply to releases on the `master` branch only.
