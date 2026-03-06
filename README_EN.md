# MTProto Proxy Checker

[🇷🇺 Русская версия](README.md)

Simple MTProto proxy checker with GUI and CLI interfaces.

## Features

- **Two operation modes**: GUI (tkinter) and CLI (curses for terminal)
- Load proxy list from two sources (mtpro.xyz and vanced.to)
- Multi-threaded ping check (10-200 workers)
- Filter by countries, ports (include/exclude)
- Find proxies in neighboring countries
- Generate QR codes for Telegram (graphical in GUI, ASCII in CLI)
- Save results to JSON
- Russian and English UI
- Minimal dependencies (only qrcode)

## Installation

### Dependencies

**Required:**
- Python 3.7+
- tkinter (for GUI mode)
- qrcode (for QR code generation)

**Optional:**
- pyperclip (for clipboard support in CLI mode)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Platform-specific requirements

**macOS**: if tkinter is not installed:
```bash
brew install python-tk@3.12
```

**Linux**: tkinter is usually included with Python, but if needed:
```bash
sudo apt-get install python3-tk  # Debian/Ubuntu
sudo dnf install python3-tkinter  # Fedora
```

**Windows**: tkinter is included in standard Python installation

## Usage

### GUI mode (default)

```bash
python mtprotool.py
```

### CLI mode (curses interface)

```bash
python mtprotool.py --cli
# or
python mtprotool.py -c
```

**CLI mode:**
- Text-based terminal interface
- Works without GUI (tkinter)
- ASCII QR codes
- Navigation: arrows/vim keys (hjkl), Page Up/Down, Home/End
- Hotkeys:
  - F1: help
  - F2: load proxies
  - F3: start/stop checking
  - F4: save results
  - F5: filters
  - F6: show only alive
  - F7: show all
  - F10/q: quit
  - Enter: show QR code
  - /: search
  - l: change language
  - +/-: adjust batch size

## How to Use

1. **Load List** - fetch proxies from two sources (mtpro.xyz and vanced.to)
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

- `mtprotool.py` - main application
- `locales.py` - translations
- `countries_data.json` - countries database and borders
- `config.json` - settings (auto-created)
- `proxy_results.json` - saved results

## Requirements

- Python 3.7+
- tkinter (see Installation section)
- Python standard library only

## 🔒 Security

For detailed security policy, see [SECURITY_EN.md](SECURITY_EN.md)

## License

MIT

---

*Simple script for checking MTProto proxies. Works on macOS, Linux, Windows.*
