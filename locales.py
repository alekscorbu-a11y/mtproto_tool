# -*- coding: utf-8 -*-
# Localization strings

LANGUAGES = {
    'ru': {
        'app_title': 'MTProto Proxy Checker',
        'btn_load': 'Получить список',
        'btn_check': 'Начать проверку',
        'btn_stop': 'Остановить',
        'btn_save': 'Сохранить',
        'label_batch': 'Порция:',
        'label_interface': 'Интерфейс:',
        'interface_auto': 'Авто',
        'status_waiting': 'Ожидание...',
        'status_loading': 'Загружаю...',
        'status_loaded': 'Загружено %d прокси',
        'status_checking': 'Проверяю %d/%d...',
        'status_stopping': 'Останавливаю...',
        'status_stopped': 'Остановлено',
        'status_done': 'Готово',
        'btn_filters': 'Фильтры',
        'btn_neighbors': 'Соседи',
        'btn_only_alive': 'Только живые',
        'btn_show_all': 'Показать все',
        'label_search': 'Поиск:',
        'filter_title': 'Фильтры',
        'label_countries': 'Страны:',
        'label_exclude': 'Исключить:',
        'label_port': 'Порт:',
        'label_exclude_ports': 'Исключить порты:',
        'hint_comma': '(через запятую)',
        'neighbors_title': 'Соседи',
        'label_country_code': 'Код страны:',
        'btn_find': 'Найти',
        
        # Tree columns
        'col_num': '№',
        'col_status': 'Статус',
        'col_ping': 'Ping',
        'col_host': 'Host',
        'col_port': 'Port',
        'col_country': 'Country',
        'col_provider': 'Provider',
        'col_uptime': 'Uptime',
        
        # Status values
        'status_unknown': '?',
        'status_ok': 'OK',
        'status_dead': 'X',
        'ping_not_checked': 'не проверен',
        'ping_dead': 'мертв',
        
        # Messages
        'msg_error': 'Ошибка',
        'msg_country_code_error': 'Нужен 2-буквенный код (RU, US, etc)',
        'msg_fetch_error': 'Не смог получить данные',
        'msg_neighbors_result': 'Результат',
        'msg_no_neighbors': 'Не нашел соседей',
        'msg_load_error': 'Не загрузил прокси:\n%s',
        'msg_all_checked': 'Все уже проверены',
        'msg_done_title': 'Готово',
        'msg_stats_alive': 'Живых: %d из %d',
        'msg_stats_full': 'Всего: %d | Проверено: %d | Живых: %d',
        'msg_stats_done': '%s: %d/%d | Живых: %d',
        'msg_no_qr_data': 'Нет данных для QR',
        'msg_qr_error': 'QR не создался:\n%s',
        'msg_ok': 'OK',
        'msg_uri_copied': 'URI в буфере',
        'msg_saved': 'Сохранено в proxy_results.json',
        'msg_save_error': 'Не сохранилось: %s',
        
        # QR window
        'qr_title': 'QR Код',
        'qr_country': 'Страна:',
        'qr_provider': 'Провайдер:',
        'qr_uptime': 'Uptime:',
        'qr_ping_api': 'Ping (API):',
        'qr_ping_your': 'Ping (ваш):',
        'qr_not_checked': 'не проверен',
        'btn_copy_uri': 'Копировать URI',
        
        # Language
        'label_language': 'Язык:',
    },
    
    'en': {
        'app_title': 'MTProto Proxy Checker',
        'btn_load': 'Load List',
        'btn_check': 'Start Check',
        'btn_stop': 'Stop',
        'btn_save': 'Save',
        'label_batch': 'Batch:',
        'label_interface': 'Interface:',
        'interface_auto': 'Auto',
        'status_waiting': 'Waiting...',
        'status_loading': 'Loading...',
        'status_loaded': 'Loaded %d proxies',
        'status_checking': 'Checking %d/%d...',
        'status_stopping': 'Stopping...',
        'status_stopped': 'Stopped',
        'status_done': 'Done',
        'btn_filters': 'Filters',
        'btn_neighbors': 'Neighbors',
        'btn_only_alive': 'Only Alive',
        'btn_show_all': 'Show All',
        'label_search': 'Search:',
        'filter_title': 'Filters',
        'label_countries': 'Countries:',
        'label_exclude': 'Exclude:',
        'label_port': 'Port:',
        'label_exclude_ports': 'Exclude ports:',
        'hint_comma': '(comma separated)',
        'neighbors_title': 'Neighbors',
        'label_country_code': 'Country code:',
        'btn_find': 'Find',
        
        # Tree columns
        'col_num': '#',
        'col_status': 'Status',
        'col_ping': 'Ping',
        'col_host': 'Host',
        'col_port': 'Port',
        'col_country': 'Country',
        'col_provider': 'Provider',
        'col_uptime': 'Uptime',
        
        # Status values
        'status_unknown': '?',
        'status_ok': 'OK',
        'status_dead': 'X',
        'ping_not_checked': 'not checked',
        'ping_dead': 'dead',
        
        # Messages
        'msg_error': 'Error',
        'msg_country_code_error': 'Need 2-letter code (RU, US, etc)',
        'msg_fetch_error': 'Failed to fetch data',
        'msg_neighbors_result': 'Result',
        'msg_no_neighbors': 'No neighbors found',
        'msg_load_error': 'Failed to load proxies:\n%s',
        'msg_all_checked': 'All already checked',
        'msg_done_title': 'Done',
        'msg_stats_alive': 'Alive: %d of %d',
        'msg_stats_full': 'Total: %d | Checked: %d | Alive: %d',
        'msg_stats_done': '%s: %d/%d | Alive: %d',
        'msg_no_qr_data': 'No data for QR',
        'msg_qr_error': 'Failed to create QR:\n%s',
        'msg_ok': 'OK',
        'msg_uri_copied': 'URI copied to clipboard',
        'msg_saved': 'Saved to proxy_results.json',
        'msg_save_error': 'Failed to save: %s',
        
        # QR window
        'qr_title': 'QR Code',
        'qr_country': 'Country:',
        'qr_provider': 'Provider:',
        'qr_uptime': 'Uptime:',
        'qr_ping_api': 'Ping (API):',
        'qr_ping_your': 'Ping (yours):',
        'qr_not_checked': 'not checked',
        'btn_copy_uri': 'Copy URI',
        
        # Language
        'label_language': 'Language:',
    }
}

# TODO: add more languages (DE, FR, ES, etc)

def get_text(lang, key):
    """Get localized text"""
    if lang not in LANGUAGES:
        lang = 'en'  # fallback
    return LANGUAGES[lang].get(key, key)
