import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import subprocess
import platform
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import json
import netifaces
import re
import pycountry
from countryinfo import CountryInfo
import locales
# import sys

# TODO: load from config file
API_URL = 'https://mtpro.xyz/api/?type=mtproto'
DEFAULT_PING_COUNT = 3
PING_TIMEOUT = 5
REQUEST_TIMEOUT = 10

CONFIG_FILE = 'config.json'


def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'language': 'ru'}  # default

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except:
        pass


class ProxyCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.current_lang = self.config.get('language', 'ru')
        self.root.title(locales.get_text(self.current_lang, 'app_title'))
        self.root.geometry("1200x700")
        
        self.proxies = []
        self.filtered_proxies = []
        self.checking_list = []  #  список после фильтрации
        self.is_checking = False
        self.stop_checking = False
        self.check_batch_size = 20
        self.current_batch_index = 0
        self.selected_interface = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # top controls
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
        
        self.label_interface = ttk.Label(top, text=locales.get_text(self.current_lang, 'label_interface'))
        self.label_interface.pack(side=tk.LEFT, padx=(10, 5))
        self.interface_var = tk.StringVar(value=locales.get_text(self.current_lang, 'interface_auto'))
        self.interface_combo = ttk.Combobox(top, textvariable=self.interface_var, width=15, state='readonly')
        self.interface_combo['values'] = self.get_interfaces()
        self.interface_combo.pack(side=tk.LEFT, padx=5)
        self.interface_combo.bind('<<ComboboxSelected>>', self.on_iface_change)
        
        self.label_language = ttk.Label(top, text=locales.get_text(self.current_lang, 'label_language'))
        self.label_language.pack(side=tk.LEFT, padx=(20, 5))
        lang_display = 'English' if self.current_lang == 'en' else 'Русский'
        self.lang_var = tk.StringVar(value=lang_display)
        self.lang_combo = ttk.Combobox(top, textvariable=self.lang_var, width=10, state='readonly')
        self.lang_combo['values'] = ['Русский', 'English']
        self.lang_combo.pack(side=tk.LEFT, padx=5)
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_lang_change)
        
        stats = ttk.Frame(self.root, padding="10")
        stats.pack(fill=tk.X)
        
        self.stats_label = ttk.Label(stats, text=locales.get_text(self.current_lang, 'status_waiting'), 
                                     font=("Arial", 10))
        self.stats_label.pack(side=tk.LEFT)
        
        self.progress = ttk.Progressbar(stats, mode='determinate', length=300)
        self.progress.pack(side=tk.LEFT, padx=20)
        
        self.progress_label = ttk.Label(stats, text="0/0")
        self.progress_label.pack(side=tk.LEFT)
        
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
        
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)
        self.label_search = ttk.Label(search_frame, text=locales.get_text(self.current_lang, 'label_search'))
        self.label_search.pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(search_frame, textvariable=self.filter_var, width=30)
        filter_entry.pack(side=tk.LEFT, padx=5)
        filter_entry.bind('<KeyRelease>', lambda e: self.apply_filter())
        
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
        
        # neighbors panel
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
            country = CountryInfo(code)
            alpha3_borders = country.borders()
            
            if not alpha3_borders:
                messagebox.showinfo(locales.get_text(self.current_lang, 'msg_neighbors_result'), 
                                   locales.get_text(self.current_lang, 'msg_no_land_borders'))
                return
            
            alpha2_borders = []
            for alpha3_code in alpha3_borders:
                try:
                    country_obj = pycountry.countries.get(alpha_3=alpha3_code)
                    if country_obj:
                        alpha2_borders.append(country_obj.alpha_2)
                except:
                    pass  # Skip invalid codes
            
            if alpha2_borders:
                alpha2_borders = sorted(set(alpha2_borders))
                self.include_countries_var.set(",".join(alpha2_borders))
                self.apply_filter()
            else:
                messagebox.showinfo(locales.get_text(self.current_lang, 'msg_neighbors_result'), 
                                   locales.get_text(self.current_lang, 'msg_no_neighbors'))
        except KeyError:
            # Country not found in CountryInfo database
            messagebox.showerror(locales.get_text(self.current_lang, 'msg_error'), 
                                locales.get_text(self.current_lang, 'msg_country_not_found'))
        except Exception as e:
            # General error with CountryInfo
            messagebox.showerror(locales.get_text(self.current_lang, 'msg_error'), 
                                locales.get_text(self.current_lang, 'msg_countryinfo_error'))
    
    def start_loading(self):
        self.start_btn.config(state=tk.DISABLED)
        self.stats_label.config(text=locales.get_text(self.current_lang, 'status_loading'))
        t = threading.Thread(target=self.load_proxies)
        t.daemon = True
        t.start()

    def on_iface_change(self, event):
        sel = self.interface_var.get()
        auto_text = locales.get_text(self.current_lang, 'interface_auto')
        if sel == auto_text or sel == 'Авто' or sel == 'Auto':
            self.selected_interface = None
        else:
            self.selected_interface = sel.split(' ')[0]
    
    def refresh_ui_texts(self):
        self.root.title(locales.get_text(self.current_lang, 'app_title'))
        
        self.start_btn.config(text=locales.get_text(self.current_lang, 'btn_load'))
        if self.is_checking:
            self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_stop'))
        else:
            self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_check'))
        self.save_btn.config(text=locales.get_text(self.current_lang, 'btn_save'))
        self.label_batch.config(text=locales.get_text(self.current_lang, 'label_batch'))

        self.label_interface.config(text=locales.get_text(self.current_lang, 'label_interface'))
        self.label_language.config(text=locales.get_text(self.current_lang, 'label_language'))
        
        current_selection = self.interface_combo.current()
        interfaces = self.get_interfaces()
        self.interface_combo['values'] = interfaces
        if current_selection >= 0:
            self.interface_combo.current(current_selection)
        
        if self.filter_visible.get():
            self.toggle_filter_btn.config(text="▼ " + locales.get_text(self.current_lang, 'btn_filters'))
        else:
            self.toggle_filter_btn.config(text="▶ " + locales.get_text(self.current_lang, 'btn_filters'))
        
        if self.neighbors_visible.get():
            self.toggle_neighbors_btn.config(text="▼ " + locales.get_text(self.current_lang, 'btn_neighbors'))
        else:
            self.toggle_neighbors_btn.config(text="▶ " + locales.get_text(self.current_lang, 'btn_neighbors'))
        
        self.btn_only_alive.config(text=locales.get_text(self.current_lang, 'btn_only_alive'))
        self.btn_show_all.config(text=locales.get_text(self.current_lang, 'btn_show_all'))
        
        self.label_search.config(text=locales.get_text(self.current_lang, 'label_search'))
        
        self.filter_container.config(text=locales.get_text(self.current_lang, 'filter_title'))
        self.label_countries.config(text=locales.get_text(self.current_lang, 'label_countries'))
        self.label_exclude_countries.config(text=locales.get_text(self.current_lang, 'label_exclude'))
        self.label_port.config(text=locales.get_text(self.current_lang, 'label_port'))
        self.label_exclude_ports.config(text=locales.get_text(self.current_lang, 'label_exclude_ports'))
        self.label_hint_comma.config(text=locales.get_text(self.current_lang, 'hint_comma'))
        
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
        
        self.neighbors_container.config(text=locales.get_text(self.current_lang, 'neighbors_title'))
        self.label_country_code.config(text=locales.get_text(self.current_lang, 'label_country_code'))
        self.btn_find_neighbors.config(text=locales.get_text(self.current_lang, 'btn_find'))
        
        self.tree.heading("num", text=locales.get_text(self.current_lang, 'col_num'))
        self.tree.heading("status", text=locales.get_text(self.current_lang, 'col_status'))
        self.tree.heading("ping", text=locales.get_text(self.current_lang, 'col_ping'))
        self.tree.heading("host", text=locales.get_text(self.current_lang, 'col_host'))
        self.tree.heading("port", text=locales.get_text(self.current_lang, 'col_port'))
        self.tree.heading("country", text=locales.get_text(self.current_lang, 'col_country'))
        self.tree.heading("provider", text=locales.get_text(self.current_lang, 'col_provider'))
        self.tree.heading("uptime", text=locales.get_text(self.current_lang, 'col_uptime'))
        
        if hasattr(self, 'filtered_proxies'):
            self.display_proxies(self.filtered_proxies)
    
    def on_lang_change(self, event):
        sel = self.lang_var.get()
        if sel == 'English':
            self.current_lang = 'en'
        else:
            self.current_lang = 'ru'
        
        self.config['language'] = self.current_lang
        save_config(self.config)
        
        self.refresh_ui_texts()

    def get_interfaces(self):
        ifaces = [locales.get_text(self.current_lang, 'interface_auto')]
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    ip = addrs[netifaces.AF_INET][0]['addr']
                    ifaces.append(f"{iface} ({ip})")
        except:
            pass  
        return ifaces

    def load_proxies(self):
        try:
            r = requests.get(API_URL, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            self.proxies = r.json()
            
            for p in self.proxies:
                p['measured_ping'] = None
            
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
        for p in self.proxies:
            ports.append(str(p.get('port', 'N/A')))
        ports = sorted(set(ports))
        
        self.port_combo['values'] = ['Все'] + ports
        self.port_var.set('Все')
        
        self.apply_filter()
    
    def display_proxies(self, plist):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # print(f"DEBUG: displaying {len(plist)} proxies")  
        
        for num, p in enumerate(plist, 1):
            ping = p.get('measured_ping')
            
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
            
            real_idx = self.proxies.index(p)
            
            vals = (num, status, ping_str, p.get('host', 'N/A'), p.get('port', 'N/A'),
                   p.get('country', 'N/A'), p.get('provider', 'N/A'), p.get('uptime', 'N/A'), real_idx)
            
            self.tree.insert('', tk.END, values=vals, tags=(tag,))
    
    def start_checking_all(self):
        if self.is_checking:
            self.stop_checking = True
            self.check_btn.config(text=locales.get_text(self.current_lang, 'btn_check'), state=tk.DISABLED)
            self.stats_label.config(text=locales.get_text(self.current_lang, 'status_stopping'))
            return
        
        self.apply_filter()
        
        unchecked = []
        for p in self.filtered_proxies:
            if p.get('measured_ping') is None:
                unchecked.append(p)
        
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
        except:
            workers = 50
        
        total = len(self.checking_list)
        
        if total == 0:
            self.root.after(0, self.on_check_done)
            return
        
        self.root.after(0, lambda: self.progress.config(maximum=total, value=0))
        
        done = 0
        last_update = 0
        
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
        
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(check_one, p) for p in self.checking_list]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    print("Проверка упала: %s" % e)
                
                if self.stop_checking:
                    for fut in futures:
                        fut.cancel()
                    break
        
        self.root.after(0, self.on_check_done)
    
    def on_check_done(self):
        alive = 0
        checked = 0
        
        for p in self.proxies:
            ping = p.get('measured_ping')
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
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        
        cmd = ['ping', param, str(DEFAULT_PING_COUNT)]
        
        sys = platform.system().lower()
        if sys == 'darwin':
            cmd.extend(['-t', str(PING_TIMEOUT)])
        elif sys == 'linux':
            cmd.extend(['-W', str(PING_TIMEOUT)])
        elif sys == 'windows':
            cmd.extend(['-w', str(PING_TIMEOUT * 1000)])
        
        if self.selected_interface:
            if sys == 'darwin':
                cmd.extend(['-b', self.selected_interface])
            elif sys == 'linux':
                cmd.extend(['-I', self.selected_interface])
        
        cmd.append(host)
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return -1
            
            out = res.stdout
            
            # parse output
            if sys in ['darwin', 'linux']:
                for line in out.splitlines():
                    if 'round-trip' in line or 'rtt' in line or 'avg' in line:
                        parts = line.split('=')
                        if len(parts) > 1:
                            vals = parts[1].strip().split('/')
                            if len(vals) >= 2:
                                return float(vals[1])
            else:
                # windows
                for line in out.splitlines():
                    if 'Average' in line or 'Среднее' in line:
                        parts = line.split('=')
                        if len(parts) > 1:
                            avg = parts[1].strip().replace('ms', '').strip()
                            return float(avg)
            
            return -1
        except:
            return -1
    
    def sort_by_ping(self):
        alive = []
        dead = []
        unk = []
        
        for p in self.proxies:
            ping = p.get('measured_ping')
            if ping is None:
                unk.append(p)
            elif ping > 0:
                alive.append(p)
            else:
                dead.append(p)
        
        alive.sort(key=lambda x: x['measured_ping'])
        self.proxies = alive + unk + dead
    
    def apply_filter(self):
        txt = self.filter_var.get().lower()
        
        inc_c = []
        for c in self.include_countries_var.get().split(','):
            c = c.strip().upper()
            if c:
                inc_c.append(c)
        
        port = self.port_var.get()
        
        exc_c = []
        for c in self.exclude_countries_var.get().split(','):
            c = c.strip().upper()
            if c:
                exc_c.append(c)
        
        exc_p = []
        for p in self.exclude_ports_var.get().split(','):
            p = p.strip()
            if p:
                exc_p.append(p)
        
        filtered = []
        
        for p in self.proxies:
            if txt:
                if txt not in p.get('host', '').lower() and \
                   txt not in p.get('country', '').lower() and \
                   txt not in p.get('provider', '').lower():
                    continue
            
            if inc_c:
                if p.get('country', '').upper() not in inc_c:
                    continue
            
            port_all_ru = locales.get_text('ru', 'port_all')
            port_all_en = locales.get_text('en', 'port_all')
            if port and port != port_all_ru and port != port_all_en:
                if str(p.get('port', '')) != port:
                    continue
            
            if exc_c:
                if p.get('country', '').upper() in exc_c:
                    continue
            
            if exc_p:
                if str(p.get('port', '')).strip() in exc_p:
                    continue
            
            filtered.append(p)
        
        self.filtered_proxies = filtered
        self.display_proxies(filtered)
    
    def show_available_only(self):
        self.apply_filter()
        
        alive = []
        for p in self.filtered_proxies:
            ping = p.get('measured_ping')
            if isinstance(ping, (int, float)) and ping > 0:
                alive.append(p)
        
        self.display_proxies(alive)
        self.stats_label.config(text=locales.get_text(self.current_lang, 'msg_stats_alive') % (len(alive), len(self.filtered_proxies)))
    
    def show_all(self):
        self.apply_filter()
        
        alive = 0
        checked = 0
        
        for p in self.filtered_proxies:
            ping = p.get('measured_ping')
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
        
        p = self.proxies[idx]
        h = p.get('host', '')
        port = p.get('port', '')
        secret = p.get('secret', '')
        
        if not h or not port or not secret:
            messagebox.showwarning(locales.get_text(self.current_lang, 'msg_error'), 
                                  locales.get_text(self.current_lang, 'msg_no_qr_data'))
            return
        
        uri = "tg://proxy?server={}&port={}&secret={}".format(h, port, secret)
        
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
            
            country = pycountry.countries.get(alpha_2=p.get('country', ''))
            country_name = country.name if country else 'N/A'
            
            ping_val = p.get('measured_ping', locales.get_text(self.current_lang, 'qr_not_checked'))
            if ping_val is None:
                ping_val = locales.get_text(self.current_lang, 'qr_not_checked')
            
            info = """
{} {} / {}
{} {}
{} {}%
{} {} ms
{} {}
""".format(locales.get_text(self.current_lang, 'qr_country'), p.get('country', 'N/A'), country_name,
           locales.get_text(self.current_lang, 'qr_provider'), p.get('provider', 'N/A'),
           locales.get_text(self.current_lang, 'qr_uptime'), p.get('uptime', 'N/A'),
           locales.get_text(self.current_lang, 'qr_ping_api'), p.get('ping', 'N/A'),
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
            # Добавляем ури для прокси в self.proxies
            proxies_with_uri = []
            for p in self.proxies:
                proxy_copy = p.copy()
                
                # tg://proxy?server=&port=&secret=
                h = p.get('host', '')
                port = p.get('port', '')
                secret = p.get('secret', '')
                
                if h and port and secret:
                    proxy_copy['uri'] = f"tg://proxy?server={h}&port={port}&secret={secret}"
                else:
                    proxy_copy['uri'] = None
                
                proxies_with_uri.append(proxy_copy)
            
            with open('proxy_results.json', 'w', encoding='utf-8') as f:
                json.dump(proxies_with_uri, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo(locales.get_text(self.current_lang, 'msg_ok'), locales.get_text(self.current_lang, 'msg_saved'))
        except Exception as e:
            messagebox.showerror(locales.get_text(self.current_lang, 'msg_error'), locales.get_text(self.current_lang, 'msg_save_error') % e)


def main():
    root = tk.Tk()
    app = ProxyCheckerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
