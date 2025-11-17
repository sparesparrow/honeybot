# Security Best Practices for SCAIPOT

This document outlines security considerations and best practices for deploying and operating SCAIPOT honeypot systems.

## Production Deployment Security

### Critical Security Checklist

Before deploying to production, ensure:

- [ ] `ENV=production` is set in environment variables
- [ ] Strong `JWT_SECRET` generated and configured
- [ ] Database password changed from default `password`
- [ ] Redis password set to a strong value
- [ ] All API keys (Anthropic, platform tokens) are valid and secured
- [ ] Docker socket access protected via docker-socket-proxy
- [ ] ALLOWED_ORIGINS configured for your domain
- [ ] Logs are monitored and stored securely
- [ ] Network access restricted to necessary ports only

### Generating Secure Secrets

**JWT Secret (Required for Production):**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Database Password:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

**Redis Password:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

Update `.env` or set environment variables directly:
```bash
export JWT_SECRET="YOUR_GENERATED_SECRET_HERE"
export DATABASE_PASSWORD="YOUR_DB_PASSWORD_HERE"
export REDIS_PASSWORD="YOUR_REDIS_PASSWORD_HERE"
```

## Configuration Security

### Environment Variables

**Trusted Values:**
- Environment variables are considered trusted and are not validated for injection
- Only set environment variables from secure sources
- Never allow untrusted users to modify environment variables

**Production Validation:**
When `ENV=production`, SCAIPOT automatically validates:
1. JWT_SECRET is not the default value
2. Database URL doesn't contain default password
3. Anthropic API key is configured
4. Warns if VM spawning is enabled (Docker socket access)

### YAML Loading

Always use `yaml.safe_load()` for configuration files:

```python
# ✅ SAFE - Use this
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# ❌ UNSAFE - Never use this with untrusted input
# with open('config.yaml') as f:
#     config = yaml.load(f, Loader=yaml.Loader)  # Arbitrary code execution risk!
```

## Docker Security

### Docker Socket Protection

**Problem:** Direct Docker socket access (`/var/run/docker.sock`) grants root-equivalent access to the host system.

**Solution:** Use `docker-socket-proxy` to restrict Docker API access:

```yaml
# docker-compose.yml
services:
  docker-proxy:
    image: tecnativa/docker-socket-proxy:latest
    environment:
      # Allow only safe read operations
      CONTAINERS: 1
      IMAGES: 1
      # Deny dangerous operations
      POST: 0
      BUILD: 0
      EXEC: 0
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

**Enabling VM Spawning Feature:**
```bash
# Use Docker Compose profile to enable docker-proxy
docker-compose --profile vm-spawning up -d
```

### Container Security

1. **Run as non-root user** (planned for v0.2.0)
2. **Read-only root filesystem** where possible
3. **Drop unnecessary capabilities**
4. **Use security scanning** (Snyk, Trivy) on container images

## Database Security

### PostgreSQL

1. **Strong Passwords:** Never use default `password`
2. **Connection Encryption:** Use SSL/TLS for database connections
3. **Principle of Least Privilege:** Grant only necessary permissions
4. **Audit Logging:** Enable PostgreSQL audit logging

**Enable SSL (Production):**
```python
DATABASE_URL=postgresql://scaipot:password@postgres:5432/scaipot?sslmode=require
```

### Redis

1. **Authentication:** Always set `REDIS_PASSWORD`
2. **Network Isolation:** Bind Redis to internal network only
3. **Disable Dangerous Commands:**
   ```conf
   rename-command FLUSHDB ""
   rename-command FLUSHALL ""
   rename-command CONFIG ""
   ```

## API Security

### Claude API (Anthropic)

1. **API Key Protection:**
   - Never commit API keys to version control
   - Rotate keys periodically
   - Monitor usage in Anthropic Console

2. **Rate Limiting:**
   - Implement client-side rate limiting
   - Monitor for unusual usage patterns
   - Set budget alerts

### Platform Bots (Telegram, Signal)

1. **Token Security:**
   - Bot tokens are sensitive - treat like passwords
   - Regenerate if compromised
   - Use environment variables, never hardcode

2. **Webhook Security (when implemented):**
   - Use HTTPS only
   - Validate webhook signatures
   - Implement IP allowlisting

## Logging & Monitoring

### Safe Logging Practices

**Don't Log:**
- ❌ Passwords or API keys
- ❌ JWT tokens
- ❌ Database connection strings with credentials
- ❌ Personally Identifiable Information (PII)

**Do Log:**
- ✅ Authentication attempts (success/failure)
- ✅ Configuration changes
- ✅ Error conditions
- ✅ Scammer interaction patterns (anonymized)

### Example - Safe Database Logging

```python
# ❌ UNSAFE - May leak credentials
logger.info(f"Connecting to: {database_url}")

# ✅ SAFE - No credential exposure
logger.info("Initializing database connection")
```

## Vulnerability Reporting

If you discover a security vulnerability in SCAIPOT:

1. **Do NOT** open a public GitHub issue
2. Email: security@sparesparrow.dev
3. Include:
   - Vulnerability description
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and provide a fix timeline.

## Security Updates

- **Monitor:** Watch GitHub releases for security updates
- **Subscribe:** Enable notifications for security advisories
- **Update Promptly:** Apply security patches within 7 days
- **Test:** Always test updates in staging before production

## Compliance & Legal

### GDPR Compliance

SCAIPOT processes scammer data (messages, patterns):

1. **Legitimate Interest:** Fraud prevention (GDPR Art. 6(1)(f))
2. **Data Minimization:** Only collect necessary data
3. **Retention:** Implement data retention policies
4. **Anonymization:** Anonymize data before reporting to threat databases

### Terms of Service

Ensure your deployment complies with:
- Platform ToS (Telegram, Signal, WhatsApp)
- Anthropic Acceptable Use Policy
- Local fraud investigation laws
- Anti-hacking regulations

**Important:** Honeypots must be:
- ✅ Passive (scammers initiate contact)
- ✅ Defensive only (no "hacking back")
- ❌ Not used for entrapment or vigilante justice

## Incident Response

### If Honeypot is Compromised

1. **Isolate:** Disconnect from network immediately
2. **Assess:** Determine scope of compromise
3. **Contain:** Revoke all API keys and credentials
4. **Investigate:** Review logs for indicators of compromise
5. **Remediate:** Patch vulnerabilities, rebuild from clean state
6. **Report:** Notify affected parties if data breach occurred

### Monitoring for Compromise

Watch for:
- Unusual outbound network traffic
- Unexpected Docker container creation
- Failed authentication attempts
- Configuration file modifications
- Resource exhaustion (CPU, memory, disk)

## Security Hardening Roadmap

**Alpha v0.1.0 (Current):**
- [x] Production secret validation
- [x] Docker socket protection
- [x] Safe database logging
- [x] Input validation

**Beta v0.2.0:**
- [ ] Non-root container user
- [ ] Read-only root filesystem
- [ ] Network security policies
- [ ] Automated vulnerability scanning

**v1.0.0 (Production):**
- [ ] Security audit by third party
- [ ] Penetration testing
- [ ] Bug bounty program
- [ ] SOC2 compliance preparation

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [Anthropic Security](https://www.anthropic.com/security)

---

**Last Updated:** 2025-11-17
**Version:** Alpha v0.1.0
**Maintainer:** @sparesparrow
