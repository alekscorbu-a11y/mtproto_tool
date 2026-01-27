# 🔒 Security Policy

[🇷🇺 Русская версия](SECURITY.md)

## Supported Versions

Currently, only the latest version of the project is supported.

| Version | Support            |
| ------- | ------------------ |
| latest  | ✅ Supported       |
| older   | ❌ Not supported   |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do not create public issues** for critical security problems
2. Send vulnerability description directly to the project author
3. Include as much detail as possible:
   - Vulnerability description
   - Steps to reproduce
   - Potential impact
   - Suggested fixes (if any)

### What to Expect

- **Acknowledgment**: within 48 hours
- **Updates**: regular progress updates
- **Fix**: patch within 7-14 days (depending on complexity)
- **Disclosure**: coordinated disclosure after fix

## Security Guidelines

### For Users

- ✅ Always use the latest version
- ✅ Install dependencies only from `requirements.txt`
- ✅ Verify proxy servers before use
- ⚠️ Don't use proxies from untrusted sources
- ⚠️ Be careful with `config.json` - it may contain personal settings

### Application Features

**Network Activity:**
- Application sends requests to mtpro.xyz API to fetch proxy list
- Application performs ping requests to proxy servers for availability check
- Application may send requests to Geonames.org for neighboring countries search

**Local Data:**
- `config.json` - stores selected language
- `proxy_results.json` - saved proxy check results

**What the Application DOES NOT do:**
- Does not collect personal data
- Does not send analytics
- Does not connect to proxies for actual use (ping only)
- Does not modify system settings

### Dependency Security

Used libraries are regularly checked for vulnerabilities:

- `requests` - HTTP client
- `netifaces` - network interface information
- `qrcode[pil]` - QR code generation
- `pillow` - image processing
- `pycountry` - country database
- `countryinfo` - country information

**Recommendation**: periodically update dependencies via `pip install -r requirements.txt --upgrade`

## Known Limitations

1. **Ping on Windows**: requires administrator rights for ICMP ping
2. **mtpro.xyz API**: application depends on external API availability
3. **Rate limiting**: frequent API requests may be throttled

## License and Liability

This software is provided "as is" under the MIT license. Authors are not responsible for application use or proxy servers.

---

*Last updated: January 27, 2026*
