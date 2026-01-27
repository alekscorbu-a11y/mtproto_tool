# Система локализации / Localization System

## Файлы / Files

- `locales.py` - файл с переводами
- `mtprotool.py` - основное приложение с поддержкой локализации

## Поддерживаемые языки / Supported Languages

- 🇷🇺 Русский (ru) - по умолчанию
- 🇬🇧 English (en)

## Как добавить новый язык / How to Add New Language

1. Откройте `locales.py`
2. Скопируйте словарь `'ru'` или `'en'`
3. Создайте новый словарь с кодом языка (например, `'de'` для немецкого)
4. Переведите все строки
5. Добавьте язык в выпадающий список в `mtprotool.py`:

```python
self.lang_combo['values'] = ['Русский', 'English', 'Deutsch']  # пример. Немецкий в планах.
```

И в метод `on_lang_change`:

```python
def on_lang_change(self, event):
    sel = self.lang_var.get()
    if sel == 'English':
        self.current_lang = 'en'
    elif sel == 'Deutsch':
        self.current_lang = 'de'
    else:
        self.current_lang = 'ru'
    # ...
```

## Использование / Usage

Запустите приложение:
```bash
python mtprotool.py
```

В правом верхнем углу выберите язык из выпадающего списка.

**Примечание**: Язык переключается мгновенно без перезапуска приложения.

## Структура переводов / Translation Structure

Все переводы хранятся в словаре `LANGUAGES` в файле `locales.py`:

```python
LANGUAGES = {
    'ru': {
        'app_title': 'MTProto Proxy Checker',
        'btn_load': 'Получить список',
        # ...
    },
    'en': {
        'app_title': 'MTProto Proxy Checker',
        'btn_load': 'Load List',
        # ...
    }
}
```

Функция `get_text(lang, key)` возвращает переведенную строку:

```python
locales.get_text('ru', 'btn_load')  # вернет 'Получить список'
locales.get_text('en', 'btn_load')  # вернет 'Load List'
```

## TODO

- [ ] Полная перезагрузка UI при смене языка (сейчас требуется перезапуск)
- [ ] Добавить немецкий язык (DE)
- [ ] Добавить французский язык (FR)
- [ ] Добавить испанский язык (ES)
- [ ] Сохранять выбранный язык в настройках
