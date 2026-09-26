# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in AURA, please report it responsibly.

**Do not** open a public GitHub issue for security vulnerabilities.

### Reporting Process

1. Email: security@aura.example.com
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **24 hours:** Initial response acknowledging receipt
- **7 days:** Detailed analysis and triage
- **30 days:** Fix and coordinated disclosure

### Security Best Practices

When deploying AURA:

1. **Secrets Management**
   - Never commit `.env` files to version control
   - Use Kubernetes Secrets or external secret managers
   - Rotate credentials regularly

2. **Network Security**
   - Enable HTTPS/TLS in production
   - Use VPN or private networking for admin access
   - Restrict database access to application tier only

3. **Authentication**
   - Use strong JWT secrets (32+ random characters)
   - Enable token expiration and refresh
   - Implement rate limiting on auth endpoints

4. **Monitoring**
   - Enable audit logging
   - Monitor failed authentication attempts
   - Set up alerts for unusual activity

## Known Security Considerations

- JWT tokens are stateless; revocation requires blacklisting
- Redis Pub/Sub channels should be authenticated in production
- Kubernetes secrets should be encrypted at rest
- Database backups should be encrypted

## Security Audit Results

**Last Audit:** 2026-08-27
**Score:** 17/17 checks passed
**Status:** ✅ Production Ready

### Audit Coverage

- ✅ JWT authentication
- ✅ Password hashing (bcrypt)
- ✅ Rate limiting
- ✅ CORS configuration
- ✅ Security headers (HSTS, X-Frame-Options, etc.)
- ✅ Input validation
- ✅ SQL injection prevention
- ✅ XSS protection
- ✅ CSRF protection
- ✅ Encryption at rest
- ✅ Encryption in transit
- ✅ Secrets management
- ✅ Audit logging
- ✅ Dependency scanning
- ✅ Database permissions
- ✅ Error handling
- ✅ Health check security

---

For more information, see [SECURITY.md](./SECURITY.md).
