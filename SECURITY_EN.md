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

### Dependencies

**Required:**
- `qrcode` - QR code generation (uses qrcode 7.x+)

**Optional:**
- `pyperclip` - clipboard operations (used only in CLI mode)

**System:**
- tkinter - GUI library (included in standard Python installation)
- curses - CLI interface (included in standard Python installation, except Windows)

All dependencies are specified in `requirements.txt`. Recommended to install via pip.

**Operation modes:**
- GUI mode (default): requires tkinter
- CLI mode (`--cli`): requires curses, runs in terminal

### For Users

- ✅ Always use the latest version
- ✅ Install dependencies only from official sources
- ✅ Verify proxy servers before use

### Application Features

**Network Activity:**
- Application sends requests to two sources for proxy list:
  - mtpro.xyz API
  - vanced.to
- Application performs ping requests to proxy servers for availability check
- All requests use Python standard libraries (urllib)

**Local Data:**
- `config.json` - stores settings (language, ping parameters and timeouts)
- `proxy_results.json` - saved proxy check results
- `countries_data.json` - built-in countries database and their borders

**What the Application DOES NOT do:**
- Does not collect personal data
- Does not send analytics
- Does not connect to proxies for actual use (ping only)
- Does not modify system settings

### Code Security

The application uses only Python standard library, which minimizes security risks:

- No external dependencies that may contain vulnerabilities
- All code can be audited in the source file
- SSL/TLS certificate verification by default (with fallback on errors)

**Recommendation**: periodically update Python to the latest stable version

## Known Limitations

1. **Ping on Windows**: requires administrator rights for ICMP ping
2. **Data sources**: application depends on external sources availability (mtpro.xyz, vanced.to)
3. **Rate limiting**: frequent requests may be throttled by sources
4. **SSL fallback**: on SSL certificate errors, the application may disable verification

## License and Liability

This software is provided "as is" under the MIT license. Authors are not responsible for application use or proxy servers.

---

*Last updated: March 7, 2026*
