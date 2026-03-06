import argparse
import curses
from queue import Queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import urllib.request
import urllib.error
import ssl
import subprocess
import platform
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import socket
import re
import html
import locales
from urllib.parse import urlparse, parse_qs
import os

CLI_MODE = False

MTPRO_API_URL = 'https://mtpro.xyz/api/?type=mtprotoS'
VANCED_URL = 'https://vanced.to/telegram'

CONFIG_FILE = 'config.json'

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://mtpro.xyz/mtproto-ru',
    'Accept': 'application/json'
}

try:
    SSL_CONTEXT = ssl.create_default_context()
except ssl.SSLError:
    SSL_CONTEXT = None

SSL_CONTEXT_UNVERIFIED = ssl._create_unverified_context()


class CountryData:
    def __init__(self):
        self.countries = {}
        try:
            countries_file = os.path.join(os.path.dirname(__file__), 'countries_data.json')
            with open(countries_file, 'r', encoding='utf-8') as f:
                self.countries = json.load(f)
        except Exception as e:
            if not CLI_MODE:
                print(f"error loading countries_data.json: {e}")
    
    def get_by_alpha2(self, alpha2_code):
        return self.countries.get(alpha2_code.upper())
    
    def get_by_alpha3(self, alpha3_code):
        for alpha2, data in self.countries.items():
            if data.get('alpha_3') == alpha3_code.upper():
                return alpha2
        return None
    
    def search_by_name(self, name):
        name_lower = name.lower().strip()
        
        for alpha2, data in self.countries.items():
            if data['name'].lower() == name_lower:
                return alpha2
        
        for alpha2, data in self.countries.items():
            if name_lower in data['name'].lower() or data['name'].lower().startswith(name_lower):
                return alpha2
        
        return None
    
    def get_borders(self, alpha2_code):
        country = self.countries.get(alpha2_code.upper())
        if country:
            return country.get('borders', [])
        return []


country_data = CountryData()


def create_proxy_dict(host, port, secret, country='N/A', provider='unknown', uptime='N/A'):
    return {
        'host': host,
        'port': int(port),
        'secret': secret,
        'country': country,
        'provider': provider,
        'uptime': uptime,
        'measured_ping': None
    }


def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'language': 'en',
            'DEFAULT_PING_COUNT': 3,
            'PING_TIMEOUT': 5,
            'REQUEST_TIMEOUT': 10,
            'mouse_enabled': True
        }

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except (IOError, OSError):
        pass

config = load_config()
DEFAULT_PING_COUNT = config.get('DEFAULT_PING_COUNT', 3)
PING_TIMEOUT = config.get('PING_TIMEOUT', 5)
REQUEST_TIMEOUT = config.get('REQUEST_TIMEOUT', 10)


def ping_host(host):
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    cmd = ['ping', param, str(DEFAULT_PING_COUNT)]
    
    sys = platform.system().lower()
    if sys == 'darwin':
        cmd.extend(['-t', str(PING_TIMEOUT)])
    elif sys == 'linux':
        cmd.extend(['-W', str(PING_TIMEOUT)])
    elif sys == 'windows':
        cmd.extend(['-w', str(PING_TIMEOUT * 1000)])
    
    cmd.append(host)
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            return -1
        
        out = res.stdout
        if sys in ['darwin', 'linux']:
            for line in out.splitlines():
                if 'round-trip' in line or 'rtt' in line or 'avg' in line:
                    parts = line.split('=')
                    if len(parts) > 1:
                        vals = parts[1].strip().split('/')
                        if len(vals) >= 2:
                            return float(vals[1])
        else:
            for line in out.splitlines():
                if 'Average' in line or 'Среднее' in line:
                    parts = line.split('=')
                    if len(parts) > 1:
                        avg = parts[1].strip().replace('ms', '').strip()
                        return float(avg)
        return -1
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        return -1


def sort_proxies_by_ping(proxies):
    alive = [p for p in proxies if isinstance(p.get('measured_ping'), (int, float)) and p['measured_ping'] > 0]
    dead = [p for p in proxies if isinstance(p.get('measured_ping'), (int, float)) and p['measured_ping'] <= 0]
    unk = [p for p in proxies if p.get('measured_ping') is None]
    alive.sort(key=lambda x: x['measured_ping'])
    return alive + unk + dead


def save_proxies_to_json(proxies, filename='proxy_results.json'):
    proxies_with_uri = []
    for proxy in proxies:
        proxy_copy = proxy.copy()
        host = proxy.get('host', '')
        port = proxy.get('port', '')
        secret = proxy.get('secret', '')
        
        if host and port and secret:
            proxy_copy['uri'] = f"tg://proxy?server={host}&port={port}&secret={secret}"
        else:
            proxy_copy['uri'] = None
        proxies_with_uri.append(proxy_copy)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(proxies_with_uri, f, indent=2, ensure_ascii=False)


def _fetch_url(url, headers, timeout=REQUEST_TIMEOUT):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as response:
            return response.read().decode()
    except (urllib.error.URLError, ssl.SSLError):
        if not CLI_MODE:
            print(f"connecting to {url} without SSL verification")
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT_UNVERIFIED) as response:
            return response.read().decode()


def _get_country_code(html_content, href_raw):
    country_code = 'N/A'
    
    link_pos = html_content.find(href_raw)
    if link_pos <= 0:
        return country_code
    
    start = max(0, link_pos - 2500)
    context = html_content[start:link_pos]
    
    img_pattern = re.compile(r'<img[^>]*(?:alt|title)=["\']([^"\']*flag[^"\']*)["\']', re.IGNORECASE)
    img_match = img_pattern.search(context)
    
    if img_match:
        flag_text = img_match.group(1)
        country_name = flag_text.replace(' flag', '').replace('flag', '').strip()
        
        try:
            country_code = country_data.search_by_name(country_name)
            if not country_code:
                country_code = country_name[:2].upper() if country_name else 'N/A'
        except (KeyError, AttributeError):
            country_code = country_name[:2].upper() if country_name else 'N/A'
    
    if country_code == 'N/A':
        flag_url_pattern = re.compile(r'flag-icons/[^/]+/flags/[^/]+/([a-z]{2})\.svg', re.IGNORECASE)
        flag_url_match = flag_url_pattern.search(context)
        if flag_url_match:
            country_code = flag_url_match.group(1).upper()
    
    return country_code


def parse_mtpro_proxies():
    try:
        content = _fetch_url(MTPRO_API_URL, BROWSER_HEADERS)
        proxies_data = json.loads(content)
        
        if not isinstance(proxies_data, list):
            if not CLI_MODE:
                print("unexpected data format from mtpro.xyz API")
            return []
        
        proxies = [
            create_proxy_dict(
                host=item.get('host', ''),
                port=item.get('port', 0),
                secret=item.get('secret', ''),
                country=item.get('country', 'N/A'),
                provider='mtpro.xyz'
            )
            for item in proxies_data
            if item.get('host') and item.get('port') and item.get('secret')
        ]
        
        if not CLI_MODE:
            print(f"lodaded {len(proxies)} from mtpro.xyz")
        return proxies
        
    except Exception as e:
        if not CLI_MODE:
            print(f"error to parse from mtpro.xyz: {e}")
        return []


def parse_vanced_proxies():
    try:
        html_content = _fetch_url(VANCED_URL, {'User-Agent': BROWSER_HEADERS['User-Agent']})
        
        proxies = []
        
        link_pattern = re.compile(r'href=["\']?(tg://proxy\?[^"\'>\s]+)["\']?', re.IGNORECASE)
        links = link_pattern.findall(html_content)
        
        for href_raw in links:
            href = html.unescape(href_raw)
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            
            if 'server' not in params or 'port' not in params or 'secret' not in params:
                continue
            
            server = params['server'][0]
            port = params['port'][0]
            secret = params['secret'][0]
            
            country_code = _get_country_code(html_content, href_raw)
            
            proxy_dict = create_proxy_dict(
                host=server,
                port=port,
                secret=secret,
                country=country_code,
                provider='vanced.to'
            )
            
            proxies.append(proxy_dict)
        
        if not CLI_MODE:
            print(f"loaded {len(proxies)} from vanced.to")
        return proxies
        
    except Exception as e:
        if not CLI_MODE:
            print(f"error to parse from vanced.to: {e}")
        return []


def generate_ascii_qr(uri):
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=1
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        matrix = qr.get_matrix()
        ascii_art = []
        for row in matrix:
            line = ''.join(['██' if cell else '  ' for cell in row])
            ascii_art.append(line)
        
        return '\n'.join(ascii_art)
    except ImportError:
        return "[QR code generation requires 'qrcode' package]\n" + uri
    except Exception as e:
        return f"[QR generation error: {e}]\n" + uri


def parse_cli_args():
    parser = argparse.ArgumentParser(
        description='MTProto Proxy Checker',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--cli', '-c',
        action='store_true',
        help='Force CLI/curses interface (no GUI)'
    )
    return parser.parse_args()


class ProxyCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.current_lang = self.config.get('language', 'ru')
        self.root.title(locales.get_text(self.current_lang, 'app_title'))
        self.root.geometry("1200x700")
        
        self.proxies = []
        self.filtered_proxies = []
        self.checking_list = []
        self.is_checking = False
        self.stop_checking = False
        self.check_batch_size = 20
        self.current_batch_index = 0
        
        self.setup_ui()
    
    def setup_ui(self):
        self._setup_top_panel()
        self._setup_stats_panel()
        self._setup_toggle_panel()
        self._setup_search_panel()
        self._setup_filter_panel()
        self._setup_neighbors_panel()
        self._setup_tree()
    
    def _setup_top_panel(self):
        top = ttk.Frame(self.root, padding="10")
        top.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(top, text=locales.get_text(self.current_lang, 'btn_load'), 
                                     command=self.start_loading, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.check_btn = ttk.Button(top, text=locales.get_text(self.current_lang, 'btn_check'), 
                                     command=self.start_checking_all,
                                     state=tk.DISABLED, width=15)
        self.check_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = ttk.Button(
            top,
            text=locales.get_text(self.current_lang, 'btn_save'),
            command=self.save_results,
            state=tk.DISABLED,
            width=10
        )
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.label_batch = ttk.Label(top, text=locales.get_text(self.current_lang, 'label_batch'))
        self.label_batch.pack(side=tk.LEFT, padx=(10, 5))
        self.batch_size_var = tk.StringVar(value="20")
        ttk.Spinbox(top, from_=10, to=200, textvariable=self.batch_size_var, width=8).pack(side=tk.LEFT)
        
        self.label_language = ttk.Label(top, text=locales.get_text(self.current_lang, 'label_language'))
        self.label_language.pack(side=tk.LEFT, padx=(20, 5))
        lang_display = 'English' if self.current_lang == 'en' else 'Русский'
        self.lang_var = tk.StringVar(value=lang_display)
        self.lang_combo = ttk.Combobox(top, textvariable=self.lang_var, width=10, state='readonly')
        self.lang_combo['values'] = ['Русский', 'English']
        self.lang_combo.pack(side=tk.LEFT, padx=5)
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_lang_change)
    
    def _setup_stats_panel(self):
        stats = ttk.Frame(self.root, padding="10")
        stats.pack(fill=tk.X)
        
        self.stats_label = ttk.Label(stats, text=locales.get_text(self.current_lang, 'status_waiting'), 
                                     font=("Arial", 10))
        self.stats_label.pack(side=tk.LEFT)
        
        self.progress = ttk.Progressbar(stats, mode='determinate', length=300)
        self.progress.pack(side=tk.LEFT, padx=20)
        
        self.progress_label = ttk.Label(stats, text="0/0")
        self.progress_label.pack(side=tk.LEFT)
    
    def _setup_toggle_panel(self):
        toggle_frame = ttk.Frame(self.root, padding="10")
        toggle_frame.pack(fill=tk.X)
        
        self.filter_visible = tk.BooleanVar(value=False)
        self.toggle_filter_btn = ttk.Button(toggle_frame, 
                                            text="▶ " + locales.get_text(self.current_lang, 'btn_filters'), 
                                            command=self.toggle_filters, width=15)
        self.toggle_filter_btn.pack(side=tk.LEFT, padx=5)
        
        self.neighbors_visible = tk.BooleanVar(value=False)
        self.toggle_neighbors_btn = ttk.Button(toggle_frame, 
                                               text="▶ " + locales.get_text(self.current_lang, 'btn_neighbors'), 
                                               command=self.toggle_neighbors, width=15)
        self.toggle_neighbors_btn.pack(side=tk.LEFT, padx=5)
        
        self.btn_only_alive = ttk.Button(toggle_frame, text=locales.get_text(self.current_lang, 'btn_only_alive'), 
                  command=self.show_available_only)
        self.btn_only_alive.pack(side=tk.LEFT, padx=5)
        self.btn_show_all = ttk.Button(toggle_frame, text=locales.get_text(self.current_lang, 'btn_show_all'), 
                  command=self.show_all)
        self.btn_show_all.pack(side=tk.LEFT, padx=5)
    
    def _setup_search_panel(self):
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)
        self.label_search = ttk.Label(search_frame, text=locales.get_text(self.current_lang, 'label_search'))
        self.label_search.pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(search_frame, textvariable=self.filter_var, width=30)
        filter_entry.pack(side=tk.LEFT, padx=5)
        filter_entry.bind('<KeyRelease>', lambda e: self.apply_filter())
    
    def _setup_filter_panel(self):
        self.filter_container = ttk.LabelFrame(self.root, 
                                               text=locales.get_text(self.current_lang, 'filter_title'), 
                                               padding="10")
        filter_fr = ttk.Frame(self.filter_container, padding="5")
        filter_fr.pack(fill=tk.X)
        
        self.label_countries = ttk.Label(filter_fr, text=locales.get_text(self.current_lang, 'label_countries'))
        self.label_countries.pack(side=tk.LEFT, padx=(15, 5))
        self.include_countries_var = tk.StringVar()
        inc_entry = ttk.Entry(filter_fr, textvariable=self.include_countries_var, width=20)
        inc_entry.pack(side=tk.LEFT, padx=5)
        inc_entry.bind('<KeyRelease>', lambda e: self.apply_filter())
        
        self.label_exclude_countries = ttk.Label(filter_fr, text=locales.get_text(self.current_lang, 'label_exclude'))
        self.label_exclude_countries.pack(side=tk.LEFT, padx=(10, 5))
        self.exclude_countries_var = tk.StringVar()
        exc_entry = ttk.Entry(filter_fr, textvariable=self.exclude_countries_var, width=20)
        exc_entry.pack(side=tk.LEFT, padx=5)
        exc_entry.bind('<KeyRelease>', lambda e: self.apply_filter())
        
        filter_fr2 = ttk.Frame(self.filter_container, padding="10")
        filter_fr2.pack(fill=tk.X)
        self.label_port = ttk.Label(filter_fr2, text=locales.get_text(self.current_lang, 'label_port'))
        self.label_port.pack(side=tk.LEFT, padx=5)
        self.port_var = tk.StringVar(value=locales.get_text(self.current_lang, 'port_all'))
        self.port_combo = ttk.Combobox(filter_fr2, textvariable=self.port_var, width=10, state='readonly')
        self.port_combo['values'] = [locales.get_text(self.current_lang, 'port_all')]
        self.port_combo.pack(side=tk.LEFT, padx=5)
        self.port_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filter())
        
        self.label_exclude_ports = ttk.Label(filter_fr2, text=locales.get_text(self.current_lang, 'label_exclude_ports'))
        self.label_exclude_ports.pack(side=tk.LEFT, padx=(10, 5))
        self.exclude_ports_var = tk.StringVar()
        exc_ports = ttk.Entry(filter_fr2, textvariable=self.exclude_ports_var, width=20)
        exc_ports.pack(side=tk.LEFT, padx=5)
        exc_ports.bind('<KeyRelease>', lambda e: self.apply_filter())
        self.label_hint_comma = ttk.Label(filter_fr2, text=locales.get_text(self.current_lang, 'hint_comma'))
        self.label_hint_comma.pack(side=tk.LEFT, padx=5)
    
    def _setup_neighbors_panel(self):
        self.neighbors_container = ttk.LabelFrame(self.root, text=locales.get_text(self.current_lang, 'neighbors_title'), padding="10")
        neighbors_fr = ttk.Frame(self.neighbors_container, padding="5")
        neighbors_fr.pack(fill=tk.X)
        self.label_country_code = ttk.Label(neighbors_fr, text=locales.get_text(self.current_lang, 'label_country_code'))
        self.label_country_code.pack(side=tk.LEFT, padx=(15, 5))
        self.neighbors_source_var = tk.StringVar()
        ttk.Entry(neighbors_fr, textvariable=self.neighbors_source_var, width=6).pack(side=tk.LEFT, padx=5)
        self.btn_find_neighbors = ttk.Button(neighbors_fr, text=locales.get_text(self.current_lang, 'btn_find'), 
                  command=self.fetch_neighbors)
        self.btn_find_neighbors.pack(side=tk.LEFT, padx=5)
    
    def _setup_tree(self):
        tree_frame = ttk.Frame(self.root, padding="10")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        cols = ("num", "status", "ping", "host", "port", "country", "provider", "uptime")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.tree.yview)
        
        self.tree.heading("num", text=locales.get_text(self.current_lang, 'col_num'))
        self.tree.heading("status", text=locales.get_text(self.current_lang, 'col_status'))
        self.tree.heading("ping", text=locales.get_text(self.current_lang, 'col_ping'))
        self.tree.heading("host", text=locales.get_text(self.current_lang, 'col_host'))
        self.tree.heading("port", text=locales.get_text(self.current_lang, 'col_port'))
        self.tree.heading("country", text=locales.get_text(self.current_lang, 'col_country'))
        self.tree.heading("provider", text=locales.get_text(self.current_lang, 'col_provider'))
        self.tree.heading("uptime", text=locales.get_text(self.current_lang, 'col_uptime'))
        
        self.tree.column("num", width=50, anchor=tk.CENTER, stretch=False)
        self.tree.column("status", width=70, anchor=tk.CENTER, stretch=False)
        self.tree.column("ping", width=100, anchor=tk.CENTER, stretch=False)
        self.tree.column("host", width=300, stretch=True)
        self.tree.column("port", width=70, anchor=tk.CENTER, stretch=False)
        self.tree.column("country", width=70, anchor=tk.CENTER, stretch=False)
        self.tree.column("provider", width=200, stretch=True)
        self.tree.column("uptime", width=90, anchor=tk.CENTER, stretch=False)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind('<Double-1>', self.show_details)
        
        self.tree.tag_configure('available', background='#d4edda')
        self.tree.tag_configure('unavailable', background='#f8d7da')
        self.tree.tag_configure('unchecked', background='#fff3cd')
    
    def toggle_filters(self):
        if self.filter_visible.get():
            self.filter_container.pack_forget()
            self.toggle_filter_btn.config(text="▶ " + locales.get_text(self.current_lang, 'btn_filters'))
            self.filter_visible.set(False)
        else:
            self.filter_container.pack(fill=tk.X, before=self.tree.master)
            self.toggle_filter_btn.config(text="▼ " + locales.get_text(self.current_lang, 'btn_filters'))
            self.filter_visible.set(True)

    def toggle_neighbors(self):
        if self.neighbors_visible.get():
            self.neighbors_container.pack_forget()
            self.toggle_neighbors_btn.config(text="▶ " + locales.get_text(self.current_lang, 'btn_neighbors'))
            self.neighbors_visible.set(False)
        else:
            self.neighbors_container.pack(fill=tk.X, before=self.tree.master)
            self.toggle_neighbors_btn.config(text="▼ " + locales.get_text(self.current_lang, 'btn_neighbors'))
            self.neighbors_visible.set(True)

    def fetch_neighbors(self):
        code = self.neighbors_source_var.get().strip().upper()
        if len(code) != 2:
            messagebox.showwarning(locales.get_text(self.current_lang, 'msg_error'), 
                                  locales.get_text(self.current_lang, 'msg_country_code_error'))
            return
        
        try:
            alpha2_borders = country_data.get_borders(code)
            
            if not alpha2_borders:
                messagebox.showinfo(locales.get_text(self.current_lang, 'msg_neighbors_result'), 
                                   locales.get_text(self.current_lang, 'msg_no_land_borders'))
                return
            
            alpha2_borders = sorted(set(alpha2_borders))
            self.include_countries_var.set(",".join(alpha2_borders))
            self.apply_filter()
        except KeyError:
            messagebox.showerror(locales.get_text(self.current_lang, 'msg_error'), 
                                locales.get_text(self.current_lang, 'msg_country_not_found'))
        except Exception as e:
            messagebox.showerror(locales.get_text(self.current_lang, 'msg_error'), 
                                locales.get_text(self.current_lang, 'msg_countryinfo_error'))
    
    def start_loading(self):
        self.start_btn.config(state=tk.DISABLED)
        self.stats_label.config(text=locales.get_text(self.current_lang, 'status_loading'))
        t = threading.Thread(target=self.load_proxies)
        t.daemon = True
        t.start()
    
    def refresh_ui_texts(self):
        self.root.title(locales.get_text(self.current_lang, 'app_title'))
        self._refresh_ui()
        
        if hasattr(self, 'filtered_proxies'):
            self.display_proxies(self.filtered_proxies)
    
    def _refresh_ui(self):
        self.start_btn.config(text=locales.get_text(self.current_lang, 'btn_load'))
        if self.is_checking:
            self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_stop'))
        else:
            self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_check'))
        self.save_btn.config(text=locales.get_text(self.current_lang, 'btn_save'))
        
        if self.filter_visible.get():
            self.toggle_filter_btn.config(text="▶ " + locales.get_text(self.current_lang, 'btn_filters'))
        else:
            self.toggle_filter_btn.config(text="▼ " + locales.get_text(self.current_lang, 'btn_filters'))
        
        if self.neighbors_visible.get():
            self.toggle_neighbors_btn.config(text="▼ " + locales.get_text(self.current_lang, 'btn_neighbors'))
        else:
            self.toggle_neighbors_btn.config(text="▶ " + locales.get_text(self.current_lang, 'btn_neighbors'))
        
        self.btn_only_alive.config(text=locales.get_text(self.current_lang, 'btn_only_alive'))
        self.btn_show_all.config(text=locales.get_text(self.current_lang, 'btn_show_all'))
        self.btn_find_neighbors.config(text=locales.get_text(self.current_lang, 'btn_find'))
        
        self.label_batch.config(text=locales.get_text(self.current_lang, 'label_batch'))
        self.label_language.config(text=locales.get_text(self.current_lang, 'label_language'))
        self.label_search.config(text=locales.get_text(self.current_lang, 'label_search'))
        
        self.filter_container.config(text=locales.get_text(self.current_lang, 'filter_title'))
        self.label_countries.config(text=locales.get_text(self.current_lang, 'label_countries'))
        self.label_exclude_countries.config(text=locales.get_text(self.current_lang, 'label_exclude'))
        self.label_port.config(text=locales.get_text(self.current_lang, 'label_port'))
        self.label_exclude_ports.config(text=locales.get_text(self.current_lang, 'label_exclude_ports'))
        self.label_hint_comma.config(text=locales.get_text(self.current_lang, 'hint_comma'))
        
        self.neighbors_container.config(text=locales.get_text(self.current_lang, 'neighbors_title'))
        self.label_country_code.config(text=locales.get_text(self.current_lang, 'label_country_code'))
        
        current_port = self.port_var.get()
        port_all_ru = locales.get_text('ru', 'port_all')
        port_all_en = locales.get_text('en', 'port_all')
        port_all_new = locales.get_text(self.current_lang, 'port_all')
        
        current_values = list(self.port_combo['values'])
        new_values = []
        for val in current_values:
            if val == port_all_ru or val == port_all_en:
                new_values.append(port_all_new)
            else:
                new_values.append(val)
        self.port_combo['values'] = new_values
        
        if current_port == port_all_ru or current_port == port_all_en:
            self.port_var.set(port_all_new)
        
        self.tree.heading("num", text=locales.get_text(self.current_lang, 'col_num'))
        self.tree.heading("status", text=locales.get_text(self.current_lang, 'col_status'))
        self.tree.heading("ping", text=locales.get_text(self.current_lang, 'col_ping'))
        self.tree.heading("host", text=locales.get_text(self.current_lang, 'col_host'))
        self.tree.heading("port", text=locales.get_text(self.current_lang, 'col_port'))
        self.tree.heading("country", text=locales.get_text(self.current_lang, 'col_country'))
        self.tree.heading("provider", text=locales.get_text(self.current_lang, 'col_provider'))
        self.tree.heading("uptime", text=locales.get_text(self.current_lang, 'col_uptime'))
    
    def on_lang_change(self, event):
        sel = self.lang_var.get()
        if sel == 'English':
            self.current_lang = 'en'
        else:
            self.current_lang = 'ru'
        
        self.config['language'] = self.current_lang
        save_config(self.config)
        
        self.refresh_ui_texts()

    def load_proxies(self):
        try:
            proxies_from_mtpro = parse_mtpro_proxies()
            
            proxies_from_vanced = parse_vanced_proxies()
            
            self.proxies = proxies_from_mtpro + proxies_from_vanced
            
            for proxy in self.proxies:
                proxy['measured_ping'] = None
            
            self.root.after(0, self.on_proxies_loaded)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                locales.get_text(self.current_lang, 'msg_error'), 
                locales.get_text(self.current_lang, 'msg_load_error') % e))
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
    
    def on_proxies_loaded(self):
        self.stats_label.config(text=locales.get_text(self.current_lang, 'status_loaded') % len(self.proxies))
        self.check_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)
        self.label_batch.config(state=tk.NORMAL)
        self.current_batch_index = 0
        
        ports = []
        for proxy in self.proxies:
            ports.append(str(proxy.get('port', 'N/A')))
        ports = sorted(set(ports))
        
        self.port_combo['values'] = ['Все'] + ports
        self.port_var.set('Все')
        
        self.apply_filter()
    
    def display_proxies(self, plist):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        
        for num, proxy in enumerate(plist, 1):
            ping = proxy.get('measured_ping')
            
            if ping is None:
                status = locales.get_text(self.current_lang, 'status_unknown')
                ping_str = locales.get_text(self.current_lang, 'ping_not_checked')
                tag = 'unchecked'
            elif ping > 0:
                status = locales.get_text(self.current_lang, 'status_ok')
                ping_str = "%.1f" % ping
                tag = 'available'
            else:
                status = locales.get_text(self.current_lang, 'status_dead')
                ping_str = locales.get_text(self.current_lang, 'ping_dead')
                tag = 'unavailable'
            
            real_idx = self.proxies.index(proxy)
            
            vals = (num, status, ping_str, proxy.get('host', 'N/A'), proxy.get('port', 'N/A'),
                   proxy.get('country', 'N/A'), proxy.get('provider', 'N/A'), proxy.get('uptime', 'N/A'), real_idx)
            
            self.tree.insert('', tk.END, values=vals, tags=(tag,))
    
    def start_checking_all(self):
        if self.is_checking:
            self.stop_checking = True
            self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_check'), state=tk.DISABLED)
            self.stats_label.config(text=locales.get_text(self.current_lang, 'status_stopping'))
            return
        
        self.apply_filter()
        
        unchecked = []
        for proxy in self.filtered_proxies:
            if proxy.get('measured_ping') is None:
                unchecked.append(proxy)
        
        if not unchecked:
            messagebox.showinfo(locales.get_text(self.current_lang, 'msg_done_title'), 
                               locales.get_text(self.current_lang, 'msg_all_checked'))
            return
        
        self.checking_list = unchecked.copy()
        
        self.is_checking = True
        self.stop_checking = False
        self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_stop'))
        self.start_btn.config(state=tk.DISABLED)
        
        t = threading.Thread(target=self.check_all_in_batches)
        t.daemon = True
        t.start()
    
    def check_all_in_batches(self):
        try:
            workers = int(self.batch_size_var.get())
        except (ValueError, AttributeError):
            workers = 50
        
        total = len(self.checking_list)
        
        if total == 0:
            self.root.after(0, self.on_check_done)
            return
        
        self.root.after(0, lambda: self.progress.config(maximum=total, value=0))
        
        done = 0
        last_update = 0
        check_one = self._create_proxy_checker(done, last_update, total)
        
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(check_one, proxy) for proxy in self.checking_list]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    if not CLI_MODE:
                        print("Failed: %s" % e)
                
                if self.stop_checking:
                    for fut in futures:
                        fut.cancel()
                    break
        
        self.root.after(0, self.on_check_done)
    
    def _create_proxy_checker(self, done, last_update, total):
        def check_one(proxy):
            nonlocal done, last_update
            
            if self.stop_checking:
                return
            
            ping = self.ping(proxy.get('host', ''))
            proxy['measured_ping'] = ping
            done += 1
            
            self.root.after(0, lambda: self.progress.config(value=done))
            self.root.after(0, lambda: self.progress_label.config(text=f"{done}/{total}"))
            self.root.after(0, lambda: self.stats_label.config(
                text=locales.get_text(self.current_lang, 'status_checking') % (done, total)))
            
            if done - last_update >= 10 or done == total:
                last_update = done
                self.root.after(0, self.sort_by_ping)
                self.root.after(0, self.apply_filter)
        
        return check_one
    
    def on_check_done(self):
        alive = 0
        checked = 0
        
        for proxy in self.proxies:
            ping = proxy.get('measured_ping')
            if ping is not None:
                checked += 1
            if isinstance(ping, (int, float)) and ping > 0:
                alive += 1
        
        msg = locales.get_text(self.current_lang, 'status_stopped') if self.stop_checking else locales.get_text(self.current_lang, 'status_done')
        self.stats_label.config(text=locales.get_text(self.current_lang, 'msg_stats_done') % (msg, checked, len(self.proxies), alive))
        
        self.is_checking = False
        self.stop_checking = False
        self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_check'), state=tk.NORMAL)
        self.start_btn.config(state=tk.NORMAL)
        self.apply_filter()
    
    def ping(self, host):
        return ping_host(host)
    
    def sort_by_ping(self):
        self.proxies = sort_proxies_by_ping(self.proxies)
    
    def apply_filter(self):
        txt = self.filter_var.get().lower()
        
        include_countries = []
        for country_code in self.include_countries_var.get().split(','):
            country_code = country_code.strip().upper()
            if country_code:
                include_countries.append(country_code)
        
        port = self.port_var.get()
        
        exclude_countries = []
        for country_code in self.exclude_countries_var.get().split(','):
            country_code = country_code.strip().upper()
            if country_code:
                exclude_countries.append(country_code)
        
        exclude_ports = []
        for port_str in self.exclude_ports_var.get().split(','):
            port_str = port_str.strip()
            if port_str:
                exclude_ports.append(port_str)
        
        filtered = []
        
        for proxy in self.proxies:
            if txt:
                if txt not in proxy.get('host', '').lower() and \
                   txt not in proxy.get('country', '').lower() and \
                   txt not in proxy.get('provider', '').lower():
                    continue
            
            if include_countries:
                if proxy.get('country', '').upper() not in include_countries:
                    continue
            
            port_all_ru = locales.get_text('ru', 'port_all')
            port_all_en = locales.get_text('en', 'port_all')
            if port and port != port_all_ru and port != port_all_en:
                if str(proxy.get('port', '')) != port:
                    continue
            
            if exclude_countries:
                if proxy.get('country', '').upper() in exclude_countries:
                    continue
            
            if exclude_ports:
                if str(proxy.get('port', '')).strip() in exclude_ports:
                    continue
            
            filtered.append(proxy)
        
        self.filtered_proxies = filtered
        self.display_proxies(filtered)
    
    def show_available_only(self):
        self.apply_filter()
        
        alive = []
        for proxy in self.filtered_proxies:
            ping = proxy.get('measured_ping')
            if isinstance(ping, (int, float)) and ping > 0:
                alive.append(proxy)
        
        self.display_proxies(alive)
        self.stats_label.config(text=locales.get_text(self.current_lang, 'msg_stats_alive') % (len(alive), len(self.filtered_proxies)))
    
    def show_all(self):
        self.apply_filter()
        
        alive = 0
        checked = 0
        
        for proxy in self.filtered_proxies:
            ping = proxy.get('measured_ping')
            if ping is not None:
                checked += 1
            if isinstance(ping, (int, float)) and ping > 0:
                alive += 1
        
        self.stats_label.config(text=locales.get_text(self.current_lang, 'msg_stats_full') % 
                               (len(self.filtered_proxies), checked, alive))
    
    def show_details(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        
        vals = self.tree.item(sel[0])['values']
        if len(vals) < 9:
            return
        
        idx = int(vals[8])
        if idx >= len(self.proxies):
            return
        
        proxy = self.proxies[idx]
        host = proxy.get('host', '')
        port = proxy.get('port', '')
        secret = proxy.get('secret', '')
        
        if not host or not port or not secret:
            messagebox.showwarning(locales.get_text(self.current_lang, 'msg_error'), 
                                  locales.get_text(self.current_lang, 'msg_no_qr_data'))
            return
        
        uri = "tg://proxy?server={}&port={}&secret={}".format(host, port, secret)
        
        win = tk.Toplevel(self.root)
        win.title(locales.get_text(self.current_lang, 'qr_title'))
        win.geometry("500x500")
        
        try:
            import qrcode
            from PIL import Image, ImageTk
            
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L,
                              box_size=10, border=4)
            qr.add_data(uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize((300, 300), Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(img)
            
            lbl = ttk.Label(win, image=img_tk)
            lbl.image = img_tk
            lbl.pack(pady=0)
            
            country = country_data.get_by_alpha2(proxy.get('country', ''))
            country_name = country['name'] if country else 'N/A'
            
            ping_val = proxy.get('measured_ping', locales.get_text(self.current_lang, 'qr_not_checked'))
            if ping_val is None:
                ping_val = locales.get_text(self.current_lang, 'qr_not_checked')
            
            info = """
{} {} / {}
{} {}
{} {}%
{} {} ms
{} {}
""".format(locales.get_text(self.current_lang, 'qr_country'), proxy.get('country', 'N/A'), country_name,
           locales.get_text(self.current_lang, 'qr_provider'), proxy.get('provider', 'N/A'),
           locales.get_text(self.current_lang, 'qr_uptime'), proxy.get('uptime', 'N/A'),
           locales.get_text(self.current_lang, 'qr_ping_api'), proxy.get('ping', 'N/A'),
           locales.get_text(self.current_lang, 'qr_ping_your'), ping_val)
            
            ttk.Label(win, text=info, wraplength=480).pack(pady=0)
            
            def copy():
                win.clipboard_clear()
                win.clipboard_append(uri)
                messagebox.showinfo(locales.get_text(self.current_lang, 'msg_ok'), 
                                   locales.get_text(self.current_lang, 'msg_uri_copied'))
            
            ttk.Button(win, text=locales.get_text(self.current_lang, 'btn_copy_uri'), 
                      command=copy).pack(pady=5)
        
        except Exception as e:
            messagebox.showerror(locales.get_text(self.current_lang, 'msg_error'), 
                                locales.get_text(self.current_lang, 'msg_qr_error') % e)
            win.destroy()
    
    def save_results(self):
        try:
            save_proxies_to_json(self.proxies)
            messagebox.showinfo(locales.get_text(self.current_lang, 'msg_ok'), locales.get_text(self.current_lang, 'msg_saved'))
        except Exception as e:
            messagebox.showerror(locales.get_text(self.current_lang, 'msg_error'), locales.get_text(self.current_lang, 'msg_save_error') % e)


class ProxyCheckerCursesApp:

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.config = load_config()
        self.current_lang = self.config.get('language', 'en')
        self.mouse_enabled = self.config.get('mouse_enabled', True)
        
        self.proxies = []
        self.filtered_proxies = []
        self.selected_row = 0
        self.scroll_offset = 0
        
        self.is_checking = False
        self.stop_checking = False
        self.batch_size = 20
        
        self.filter_visible = False
        self.neighbors_visible = False
        self.search_mode = False
        self.search_text = ""
        
        self.include_countries = ""
        self.exclude_countries = ""
        self.port_filter = "All"
        self.exclude_ports = ""
        
        self.ui_update_queue = Queue()
        
        self.windows = {}
        
        self.setup_curses()
        self.setup_colors()
        self.setup_layout()
    
    def setup_curses(self):
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(100)
        
        if self.mouse_enabled and hasattr(curses, 'mousemask'):
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    
    def setup_colors(self):
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
            curses.init_pair(5, curses.COLOR_BLUE, -1)
            curses.init_pair(6, curses.COLOR_MAGENTA, -1)
            curses.init_pair(7, curses.COLOR_WHITE, -1)
    
    def setup_layout(self):
        max_y, max_x = self.stdscr.getmaxyx()
        
        header_height = 2
        menu_height = 3
        status_height = 1
        table_height = max_y - header_height - menu_height - status_height
        
        self.windows['header'] = curses.newwin(header_height, max_x, 0, 0)
        self.windows['menu'] = curses.newwin(menu_height, max_x, header_height, 0)
        self.windows['table'] = curses.newwin(table_height, max_x, header_height + menu_height, 0)
        self.windows['status'] = curses.newwin(status_height, max_x, max_y - status_height, 0)
        
        self.table_height = table_height
        self.max_x = max_x
    
    def run(self):
        self.draw_all()
        
        while True:
            while not self.ui_update_queue.empty():
                update_func = self.ui_update_queue.get()
                update_func()
            
            try:
                key = self.stdscr.getch()
            except curses.error:
                key = -1
            
            if key == -1:
                continue
            
            if self.handle_keypress(key):
                break
            
            self.draw_all()
    
    def draw_all(self):
        try:
            self.draw_header()
            self.draw_menu()
            self.draw_table()
            self.draw_status_bar()
            self.stdscr.refresh()
        except curses.error:
            pass
    
    def handle_keypress(self, key):
        display_proxies = self.filtered_proxies if self.filtered_proxies else self.proxies
        max_row = len(display_proxies) - 1
        visible_rows = self.table_height - 1
        
        if self.search_mode:
            if key == 27:
                self.search_mode = False
                self.search_text = ""
            elif key == 10 or key == 13:
                self.do_search()
                self.search_mode = False
            elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                self.search_text = self.search_text[:-1]
            elif 32 <= key <= 126:
                self.search_text += chr(key)
            return False
        
        if key == curses.KEY_UP or key == ord('k'):
            if self.selected_row > 0:
                self.selected_row -= 1
                if self.selected_row < self.scroll_offset:
                    self.scroll_offset = self.selected_row
        
        elif key == curses.KEY_DOWN or key == ord('j'):
            if self.selected_row < max_row:
                self.selected_row += 1
                if self.selected_row >= self.scroll_offset + visible_rows:
                    self.scroll_offset = self.selected_row - visible_rows + 1
        
        elif key == curses.KEY_PPAGE:
            self.selected_row = max(0, self.selected_row - visible_rows)
            self.scroll_offset = max(0, self.scroll_offset - visible_rows)
        
        elif key == curses.KEY_NPAGE:
            self.selected_row = min(max_row, self.selected_row + visible_rows)
            self.scroll_offset = min(max(0, max_row - visible_rows + 1), 
                                    self.scroll_offset + visible_rows)
        
        elif key == curses.KEY_HOME or key == ord('g'):
            self.selected_row = 0
            self.scroll_offset = 0
        
        elif key == curses.KEY_END or key == ord('G'):
            self.selected_row = max_row
            self.scroll_offset = max(0, max_row - visible_rows + 1)
        
        elif key == curses.KEY_F1:
            self.show_help()
        
        elif key == curses.KEY_F2:
            self.load_proxies_async()
        
        elif key == curses.KEY_F3:
            if not self.is_checking:
                self.start_checking_async()
            else:
                self.stop_checking = True
        
        elif key == curses.KEY_F4:
            self.save_results()
        
        elif key == curses.KEY_F5:
            self.show_filters()
        
        elif key == curses.KEY_F6:
            self.show_available_only()
        
        elif key == curses.KEY_F7:
            self.show_all()
        
        elif key == curses.KEY_F10 or key == ord('q'):
            return True
        
        elif key == 10 or key == 13:
            if 0 <= self.selected_row < len(display_proxies):
                proxy = display_proxies[self.selected_row]
                self.show_proxy(proxy)
        
        elif key == ord('/'):
            self.search_mode = True
            self.search_text = ""
        
        elif key == ord('l') or key == ord('L'):
            self.change_language('en' if self.current_lang == 'ru' else 'ru')
        
        elif key == ord('+') or key == ord('='):
            self.batch_size = min(200, self.batch_size + 10)
        
        elif key == ord('-') or key == ord('_'):
            self.batch_size = max(10, self.batch_size - 10)
        
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                self.handle_mouse(mx, my, bstate)
            except curses.error:
                pass
        
        return False
    
    def handle_mouse(self, mx, my, bstate):
        header_height = 2
        menu_height = 3
        table_start = header_height + menu_height + 1
        
        if my >= table_start:
            row_in_table = my - table_start
            visible_row = self.scroll_offset + row_in_table
            display_proxies = self.filtered_proxies if self.filtered_proxies else self.proxies
            
            if 0 <= visible_row < len(display_proxies):
                if bstate & curses.BUTTON1_CLICKED:
                    self.selected_row = visible_row
                elif bstate & curses.BUTTON1_DOUBLE_CLICKED:
                    self.selected_row = visible_row
                    proxy = display_proxies[visible_row]
                    self.show_proxy(proxy)
        
        if bstate & curses.BUTTON4_PRESSED:
            if self.scroll_offset > 0:
                self.scroll_offset -= 1
                if self.selected_row >= self.scroll_offset + (self.table_height - 1):
                    self.selected_row = self.scroll_offset + (self.table_height - 2)
        elif bstate & (1 << 21):
            display_proxies = self.filtered_proxies if self.filtered_proxies else self.proxies
            max_offset = max(0, len(display_proxies) - (self.table_height - 1))
            if self.scroll_offset < max_offset:
                self.scroll_offset += 1
                if self.selected_row < self.scroll_offset:
                    self.selected_row = self.scroll_offset
    
    
    def load_proxies_async(self):
        def load_worker():
            try:
                proxies_from_mtpro = parse_mtpro_proxies()
                proxies_from_vanced = parse_vanced_proxies()
                self.proxies = proxies_from_mtpro + proxies_from_vanced
                
                for proxy in self.proxies:
                    proxy['measured_ping'] = None
                
                self.ui_update_queue.put(lambda: self.apply_filters())
            except Exception as e:
                pass
        
        thread = threading.Thread(target=load_worker, daemon=True)
        thread.start()
    
    def start_checking_async(self):
        self.is_checking = True
        self.stop_checking = False
        
        display_proxies = self.filtered_proxies if self.filtered_proxies else self.proxies
        unchecked = [p for p in display_proxies if p.get('measured_ping') is None]
        
        if not unchecked:
            self.is_checking = False
            return
        
        def check_worker():
            done = 0
            total = len(unchecked)
            
            def check_one(proxy):
                nonlocal done
                if self.stop_checking:
                    return
                
                host = proxy.get('host', '')
                ping = self.ping(host)
                proxy['measured_ping'] = ping
                
                done += 1
                if done % 5 == 0 or done == total:
                    self.ui_update_queue.put(lambda: None)
            
            with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                futures = [executor.submit(check_one, p) for p in unchecked]
                for f in as_completed(futures):
                    if self.stop_checking:
                        break
                    try:
                        f.result()
                    except Exception:
                        pass
            
            self.sort_by_ping()
            self.is_checking = False
            self.ui_update_queue.put(lambda: self.apply_filters())
        
        thread = threading.Thread(target=check_worker, daemon=True)
        thread.start()
    
    def ping(self, host):
        return ping_host(host)
    
    def sort_by_ping(self):
        self.proxies = sort_proxies_by_ping(self.proxies)
    
    def apply_filters(self):
        filtered = []
        
        include_countries = [c.strip().upper() for c in self.include_countries.split(',') if c.strip()]
        exclude_countries = [c.strip().upper() for c in self.exclude_countries.split(',') if c.strip()]
        exclude_ports = [p.strip() for p in self.exclude_ports.split(',') if p.strip()]
        
        for proxy in self.proxies:
            if self.search_text:
                search_lower = self.search_text.lower()
                if search_lower not in proxy.get('host', '').lower() and \
                   search_lower not in proxy.get('country', '').lower() and \
                   search_lower not in proxy.get('provider', '').lower():
                    continue
            
            if include_countries and proxy.get('country', '').upper() not in include_countries:
                continue
            if exclude_countries and proxy.get('country', '').upper() in exclude_countries:
                continue
            
            if self.port_filter != "All" and str(proxy.get('port', '')) != self.port_filter:
                continue
            if exclude_ports and str(proxy.get('port', '')).strip() in exclude_ports:
                continue
            
            filtered.append(proxy)
        
        self.filtered_proxies = filtered
        
        if self.selected_row >= len(filtered):
            self.selected_row = max(0, len(filtered) - 1)
        if self.scroll_offset >= len(filtered):
            self.scroll_offset = max(0, len(filtered) - (self.table_height - 1))
    
    def show_available_only(self):
        alive = [p for p in self.proxies if isinstance(p.get('measured_ping'), (int, float)) and p['measured_ping'] > 0]
        self.filtered_proxies = alive
        self.selected_row = 0
        self.scroll_offset = 0
    
    def show_all(self):
        self.filtered_proxies = []
        self.apply_filters()
    
    def do_search(self):
        self.apply_filters()
    
    def save_results(self):
        try:
            save_proxies_to_json(self.proxies)
        except (IOError, OSError):
            pass
    
    def change_language(self, new_lang):
        self.current_lang = new_lang
        self.config['language'] = new_lang
        save_config(self.config)
    
    def show_proxy(self, proxy):
        max_y, max_x = self.stdscr.getmaxyx()
        popup_height = min(50, max_y - 2)
        popup_width = min(100, max_x - 4)
        popup_y = (max_y - popup_height) // 2
        popup_x = (max_x - popup_width) // 2
        
        popup = curses.newwin(popup_height, popup_width, popup_y, popup_x)
        popup.box()
        popup.keypad(True)
        
        try:
            host = proxy.get('host', '')
            port = proxy.get('port', '')
            secret = proxy.get('secret', '')
            country = proxy.get('country', 'N/A')
            provider = proxy.get('provider', 'N/A')
            
            popup.addstr(0, 2, " QR Code ", curses.color_pair(5) | curses.A_BOLD)
            
            info_line = f"{country} | {provider} | {host}:{port}"
            popup.addstr(1, 2, info_line[:popup_width-4], curses.color_pair(7))
            
            if host and port and secret:
                uri = f"tg://proxy?server={host}&port={port}&secret={secret}"
                qr_text = generate_ascii_qr(uri)
                qr_lines = qr_text.split('\n')
                
                max_qr_width = popup_width - 4
                row = 3
                
                for qr_line in qr_lines:
                    if row >= popup_height - 2:
                        break
                    
                    display_line = qr_line[:max_qr_width]
                    popup.addstr(row, 2, display_line)
                    row += 1
            
            popup.addstr(popup_height - 2, 2, "[C]opy URI | [Any key] Close", curses.color_pair(6))
            popup.refresh()
            
            key = popup.getch()
            if key == ord('c') or key == ord('C'):
                try:
                    import pyperclip
                    uri = f"tg://proxy?server={host}&port={port}&secret={secret}"
                    pyperclip.copy(uri)
                except ImportError:
                    pass
        
        except curses.error:
            pass
        finally:
            del popup
    
    def show_help(self):
        max_y, max_x = self.stdscr.getmaxyx()
        popup_height = min(25, max_y - 4)
        popup_width = min(70, max_x - 4)
        popup_y = (max_y - popup_height) // 2
        popup_x = (max_x - popup_width) // 2
        
        popup = curses.newwin(popup_height, popup_width, popup_y, popup_x)
        popup.box()
        popup.keypad(True)
        
        try:
            popup.addstr(0, 2, " Help - Keybindings ", curses.color_pair(5) | curses.A_BOLD)
            
            help_text = [
                "",
                "Navigation:",
                "  ↑/↓, j/k       - Move cursor up/down",
                "  PgUp/PgDn      - Page up/down",
                "  Home/End, g/G  - First/Last item",
                "",
                "Actions:",
                "  F1       - This help",
                "  F2       - Load proxies from API",
                "  F3       - Start/Stop checking",
                "  F4       - Save results to JSON",
                "  F5       - Filters dialog",
                "  F6       - Show only alive proxies",
                "  F7       - Show all proxies",
                "  F10, q   - Quit",
                "",
                "Other:",
                "  Enter    - Show proxy details & QR code",
                "  /        - Search mode",
                "  l        - Change language",
                "  +/-      - Adjust batch size",
                "",
                "Press any key to close"
            ]
            
            for i, line in enumerate(help_text, 1):
                if i < popup_height - 1:
                    popup.addstr(i, 2, line[:popup_width-4])
            
            popup.refresh()
            popup.getch()
        
        except curses.error:
            pass
        finally:
            del popup
    
    def show_filters(self):
        max_y, max_x = self.stdscr.getmaxyx()
        popup_height = min(18, max_y - 4)
        popup_width = min(70, max_x - 4)
        popup_y = (max_y - popup_height) // 2
        popup_x = (max_x - popup_width) // 2
        
        popup = curses.newwin(popup_height, popup_width, popup_y, popup_x)
        popup.box()
        popup.keypad(True)
        curses.curs_set(1)
        
        try:
            popup.addstr(0, 2, " Filters ", curses.color_pair(5) | curses.A_BOLD)
            
            fields = [
                ("Include Countries (comma-separated):", self.include_countries),
                ("Exclude Countries (comma-separated):", self.exclude_countries),
                ("Port (or 'All'):", self.port_filter),
                ("Exclude Ports (comma-separated):", self.exclude_ports)
            ]
            
            current_field = 0
            values = [self.include_countries, self.exclude_countries, self.port_filter, self.exclude_ports]
            
            while True:
                popup.clear()
                popup.box()
                popup.addstr(0, 2, " Filters ", curses.color_pair(5) | curses.A_BOLD)
                
                for idx, (label, _) in enumerate(fields):
                    row = 2 + idx * 3
                    if row < popup_height - 2:
                        popup.addstr(row, 2, label[:popup_width-4])
                        value_row = row + 1
                        if value_row < popup_height - 2:
                            display_value = values[idx][:popup_width-6]
                            color = curses.color_pair(4) if idx == current_field else curses.color_pair(7)
                            popup.addstr(value_row, 2, "> " + display_value + (" " * (popup_width - 6 - len(display_value))), color)
                
                instructions = "Tab:Next | Enter:Apply | Esc:Cancel"
                if popup_height > 2:
                    popup.addstr(popup_height - 2, 2, instructions[:popup_width-4], curses.color_pair(6))
                
                popup.refresh()
                
                key = popup.getch()
                
                if key == 27:
                    break
                elif key == 9:
                    current_field = (current_field + 1) % len(fields)
                elif key == 10 or key == 13:
                    self.include_countries = values[0]
                    self.exclude_countries = values[1]
                    self.port_filter = values[2]
                    self.exclude_ports = values[3]
                    self.apply_filters()
                    break
                elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                    if values[current_field]:
                        values[current_field] = values[current_field][:-1]
                elif 32 <= key <= 126:
                    values[current_field] += chr(key)
                elif key == curses.KEY_UP:
                    current_field = (current_field - 1) % len(fields)
                elif key == curses.KEY_DOWN:
                    current_field = (current_field + 1) % len(fields)
        
        except curses.error:
            pass
        finally:
            curses.curs_set(0)
            del popup
    
    def draw_header(self):
        win = self.windows['header']
        win.clear()
        
        try:
            title = locales.get_text(self.current_lang, 'app_title')
            lang_display = 'RU' if self.current_lang == 'ru' else 'EN'
            win.addstr(0, 0, f"{title} | Language: {lang_display}", curses.color_pair(5) | curses.A_BOLD)
            
            help_text = "F2:Load | F3:Check | F4:Save | F5:Filters | F10:Quit"
            win.addstr(1, 0, help_text, curses.color_pair(7))
            
            win.refresh()
        except curses.error:
            pass
    
    def draw_menu(self):
        win = self.windows['menu']
        win.clear()
        
        try:
            win.addstr(0, 0, f"Batch: {self.batch_size}", curses.color_pair(7))
            
            if self.is_checking:
                win.addstr(1, 0, "Progress: [Checking...]", curses.color_pair(3))
            else:
                win.addstr(1, 0, "Ready", curses.color_pair(7))
            
            total = len(self.proxies)
            filtered = len(self.filtered_proxies)
            alive = sum(1 for p in self.proxies if isinstance(p.get('measured_ping'), (int, float)) and p['measured_ping'] > 0)
            stats = f"Total: {total} | Filtered: {filtered} | Alive: {alive}"
            win.addstr(2, 0, stats, curses.color_pair(7))
            
            win.refresh()
        except curses.error:
            pass
    
    def draw_table(self):
        win = self.windows['table']
        win.clear()
        
        try:
            header = f"{'#':<5} {'St':<4} {'Ping':<10} {'Host':<30} {'Port':<7} {'CC':<4} {'Provider':<15}"
            win.addstr(0, 0, header[:self.max_x-1], curses.color_pair(5) | curses.A_BOLD)
            
            visible_rows = self.table_height - 1
            display_proxies = self.filtered_proxies if self.filtered_proxies else self.proxies
            
            for i in range(visible_rows):
                row_idx = self.scroll_offset + i
                if row_idx >= len(display_proxies):
                    break
                
                proxy = display_proxies[row_idx]
                ping = proxy.get('measured_ping')
                
                if ping is None:
                    status = '?'
                    ping_str = 'not checked'
                    color = curses.color_pair(3)
                elif ping > 0:
                    status = 'OK'
                    ping_str = f'{ping:.1f} ms'
                    color = curses.color_pair(1)
                else:
                    status = 'X'
                    ping_str = 'dead'
                    color = curses.color_pair(2)
                
                if row_idx == self.selected_row:
                    color = color | curses.A_REVERSE
                
                num = row_idx + 1
                host = proxy.get('host', 'N/A')[:30]
                port = str(proxy.get('port', 'N/A'))[:7]
                country = proxy.get('country', 'N/A')[:4]
                provider = proxy.get('provider', 'N/A')[:15]
                
                row_text = f"{num:<5} {status:<4} {ping_str:<10} {host:<30} {port:<7} {country:<4} {provider:<15}"
                win.addstr(i + 1, 0, row_text[:self.max_x-1], color)
            
            win.refresh()
        except curses.error:
            pass
    
    def draw_status_bar(self):
        win = self.windows['status']
        win.clear()
        
        try:
            if self.search_mode:
                status = f"Search: {self.search_text}_"
            else:
                status = "[Normal] ↑↓:Navigate | Enter:Details | /:Search | F10:Quit"
            
            win.addstr(0, 0, status[:self.max_x-1], curses.color_pair(6))
            win.refresh()
        except curses.error:
            pass


def main():
    global CLI_MODE
    args = parse_cli_args()
    
    if args.cli:
        CLI_MODE = True
        try:
            curses.wrapper(run_curses_app)
        except Exception as e:
            print(f"Error running CLI mode: {e}")
            import traceback
            traceback.print_exc()
    else:
        try:
            root = tk.Tk()
            app = ProxyCheckerGUI(root)
            root.mainloop()
        except (ImportError, tk.TclError) as e:
            print(f"GUI not available ({e}), switching to CLI mode...")
            CLI_MODE = True
            try:
                curses.wrapper(run_curses_app)
            except Exception as e2:
                print(f"Error running CLI mode: {e2}")
                import traceback
                traceback.print_exc()


def run_curses_app(stdscr):
    try:
        app = ProxyCheckerCursesApp(stdscr)
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        curses.endwin()
        print(f"Error in curses app: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
