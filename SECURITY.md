# Security Policy

## 🚨 Critical Security Incident - November 22, 2025

**Issue**: Discord bot token and OpenRouter API key were accidentally committed to git history.

**Resolution**: 
- ✅ All secrets removed from git history using BFG (Big File Git Cleaner)
- ✅ Commits rewritten and force-pushed to GitHub
- ✅ `.gitignore` enhanced to prevent future incidents
- ✅ Both credentials have been **REVOKED** and regenerated

**What was exposed:**
- Discord bot token (in `.env.minimal` - blob id: `142ee54b178f8f9a6ad2b838266a57754057d447`)
- OpenRouter API key (same file)

**Impact**: Minimal - tokens were revoked immediately upon detection via GitHub Push Protection

---

## Environment Variable Security

### ✅ What You MUST DO

1. **NEVER commit `.env` files** - They contain secrets and credentials
2. **Use `.env.example` for documentation** - Only include placeholder values
3. **Generate `.env.template` for reference** - No real secrets
4. **Add to `.gitignore`:**
   ```
   # Environment (CRITICAL: Never commit secrets!)
   .env
   .env.local
   .env.*.local
   .env.*
   !.env.example
   !.env.template
   ```

### ❌ What NEVER to Do

- ❌ **Never commit real Discord tokens**
- ❌ **Never commit real API keys**
- ❌ **Never commit database passwords**
- ❌ **Never commit `.env.{botname}` files** with real secrets
- ❌ **Never use `git add -f .env*`** - This forces gitignored files into git
- ❌ **Never commit credentials, even if "temporary"**

### 📋 Current `.gitignore` Protection

The repository now includes comprehensive protection:
```
# Environment (CRITICAL: Never commit secrets!)
.env                          # Main .env file
.env.local                    # Local overrides
.env.*.local                  # Bot-specific local overrides
.env.*                        # ALL .env.* files (catches bots, services, etc)
!.env.example                 # Exception: Example template with placeholders
!.env.template                # Exception: Template with defaults
```

This pattern ensures:
- ✅ All real environment files are ignored
- ✅ Example/template files CAN be committed for reference
- ✅ No accidental secret commits

---

## Credential Management

### For Local Development

1. **Copy from template:**
   ```bash
   cp .env.example .env
   cp .env.template .env.{botname}
   ```

2. **Edit locally only:**
   ```bash
   # Edit locally with YOUR credentials
   nano .env.elena
   
   # Verify it's not staged
   git status  # Should NOT show .env.elena
   ```

3. **Never stage .env files:**
   ```bash
   # ✅ Correct: Only stage source code
   git add src_v2/
   
   # ❌ Wrong: Never do this
   git add .env*
   git add -f .env.elena  # Force-add is dangerous!
   ```

### For GitHub Actions / CI/CD

Use GitHub Secrets instead:
```yaml
env:
  DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
  OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

### For Docker Deployment

Use environment variable files or secrets management:
```bash
# ✅ Use --env-file with local .env
docker compose --env-file .env.elena up

# ✅ Or set via command line
docker compose -e DISCORD_BOT_TOKEN=$token up
```

---

## Git History Cleanup (What Happened)

If you ever need to remove secrets from git history:

### Quick Reference
```bash
# 1. Create file with secrets to remove
cat > /tmp/secrets.txt << 'EOF'
your-secret-here
another-secret-here
EOF

# 2. Run BFG to clean history
bfg --no-blob-protection --replace-text /tmp/secrets.txt .

# 3. Cleanup and force push
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force-with-lease origin main
```

⚠️ **Force push rewrites history** - Only do this for security incidents with team coordination

---

## Detection & Monitoring

### GitHub Push Protection

WhisperEngine uses GitHub's Secret Scanning with Push Protection:
- 🛡️ **Enabled**: Prevents pushing commits containing known secret patterns
- 🔔 **Alerts**: Notifies on detection
- 📋 **Review**: Requires explicit approval to allow secrets (not recommended)

### Local Pre-Commit Checking

Consider using pre-commit hooks to prevent accidental commits:
```bash
# Install pre-commit framework
pip install pre-commit

# Create .pre-commit-config.yaml with secret detection
# Then: pre-commit install
```

---

## Timeline of Incident

| Date | Time | Event |
|------|------|-------|
| Nov 22, 2025 | 05:55 UTC | Commit with `.env.minimal` containing secrets |
| Nov 22, 2025 | ~06:00 UTC | GitHub Push Protection blocked push |
| Nov 22, 2025 | ~06:00 UTC | BFG used to remove secrets from history |
| Nov 22, 2025 | ~06:05 UTC | Force-pushed clean history to GitHub |
| Nov 22, 2025 | ~06:05 UTC | All credentials revoked and regenerated |

---

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** create a public GitHub issue
2. **DO** email maintainers privately with:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

3. **DO** allow reasonable time for remediation before disclosure

---

## Credentials Currently Revoked ❌

The following credentials were exposed and have been **PERMANENTLY REVOKED**:

- Discord Bot Token (REVOKED) - 1278 commits cleaned via BFG
- OpenRouter API Key (REVOKED) - 1278 commits cleaned via BFG

**Do NOT attempt to use these credentials** - they have been permanently disabled and no longer grant access to any resources. All services have been secured with new credentials.

---

## Best Practices Checklist

- [ ] `.env` files are in `.gitignore`
- [ ] `.env.example` exists with placeholder values only
- [ ] No real secrets in version control history
- [ ] Environment variables loaded from `.env` files (not committed)
- [ ] GitHub Push Protection enabled for this repository
- [ ] Team educated on secret management practices
- [ ] Pre-commit hooks configured (optional but recommended)

---

*Last Updated: November 22, 2025*
*Security Incident: Resolved*
