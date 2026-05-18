# DNS & Domain — Cloudflare

## Domain

- **Domain:** `babook.co.il`
- **Registrar:** LiveDNS.co.il
- **DNS hosting:** Cloudflare (free plan)
- **Nameservers:** `anna.ns.cloudflare.com` / `zahir.ns.cloudflare.com`

## Why Cloudflare

Migrated from LiveDNS.co.il because their DNS panel cannot set MX records on
subdomains (only 3 fields: Mail Server, MX priority, TTL). Cloudflare gives full
control over all record types needed for email authentication.

## DNS records

| Name | Type | Value | Purpose |
|------|------|-------|---------|
| `babook.co.il` | A | (Render IP) | Main site |
| `www.babook.co.il` | CNAME | `mysite-0tu0.onrender.com` | www redirect |
| `resend._domainkey.babook.co.il` | CNAME | (Resend-provided) | DKIM for email |
| `babook.co.il` | TXT | `v=spf1 include:amazonses.com ~all` | SPF for Resend |
| `_dmarc.babook.co.il` | TXT | `v=DMARC1; p=none;` | DMARC policy |

## SSL/TLS

- Cloudflare SSL mode: **Full (strict)**
- Render provides its own SSL cert for `babook.co.il`
- Cloudflare proxies traffic (orange cloud) with its edge cert

## Render custom domain

- Render service: `mysite` (ID: `srv-d6ttohq4d50c73chm4tg`)
- Custom domain `babook.co.il` added in Render dashboard
- Render auto-provisions Let's Encrypt cert

## Changing DNS records

1. Log into Cloudflare → `babook.co.il` zone
2. Add/edit records in DNS tab
3. Propagation: usually < 5 minutes (Cloudflare is fast)

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Site not resolving | Check nameservers point to Cloudflare; verify A/CNAME |
| SSL error | Ensure Cloudflare SSL mode is Full (strict) |
| Email DKIM fail | Verify `resend._domainkey` CNAME exists and is proxied=off (DNS only) |
| "Too many redirects" | SSL mode must be Full, not Flexible |
