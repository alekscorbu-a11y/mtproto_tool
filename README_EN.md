# MTProto Proxy Checker

[🇷🇺 Русская версия](README.md)

Simple MTProto proxy checker with GUI.

## Features

- Load proxy list from mtpro.xyz
- Multi-threaded ping check (10-200 workers)
- Network interface selection for ping
- Filter by countries, ports (include/exclude)
- Find proxies in neighboring countries via Geonames
- Generate QR codes for Telegram
- Save results to JSON
- Russian and English UI

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python checker_gui_final.py
```

## How to Use

1. **Load List** - fetch proxies from API
2. **Start Check** - ping all proxies
3. Use filters to select needed proxies
4. Double-click on proxy = QR code for Telegram
5. **Save** - export to `proxy_results.json`

## Filters

- **Search** - by host, country, provider
- **Countries** - include specific (RU,US,DE)
- **Exclude** - remove countries or ports
- **Port** - filter by specific port
- **Neighbors** - find proxies in neighboring countries (enter country code)

## Language Switch

Select language in top-right corner. Your choice will be saved.

## Files

- `checker_gui_final.py` - main application
- `locales.py` - translations
- `config.json` - settings (auto-created)
- `proxy_results.json` - saved results

## Requirements

- Python 3.7+
- requests
- netifaces
- qrcode[pil]
- pillow
- pycountry

## License

MIT

---

*Simple script for checking MTProto proxies. Works on macOS, Linux, Windows.*
