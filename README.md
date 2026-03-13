# Save-Inst

Инструмент для архивирования сохранённых постов Instagram. Скачивает медиа, генерирует превью, категоризирует через Claude AI, строит интерактивную веб-галерею и экспортирует в Obsidian.

## Как это работает

```
saved_posts.html
       │
       ▼
   parser.py  ──►  data/links.json
       │
       ▼
   fetch.py   ──►  content/<id>/  +  data/posts.json
       │
       ▼
 thumbnailer.py ──►  content/<id>/thumbnail.jpg
       │
       ▼
 categorizer.py ──►  data/posts.json (с категориями)
       │
       ▼
  builder.py  ──►  html/index.html  +  html/data/posts.js
       │
       ▼
obsidian_export.py ──►  obsidian/*.md
```

**thumbnailer.py** — отдельный шаг после `fetch`: извлекает первый кадр из видео (ffmpeg) или скачивает превью через Instagram API, если yt-dlp не вернул thumbnail. Без этого шага галерея работает, но медленнее (браузер загружает полные видео вместо превью).

## Требования

- Python 3.11+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — устанавливается через `setup.sh`
- [ffmpeg](https://ffmpeg.org/) — для извлечения превью из видео (`thumbnailer`)
- Firefox **или** Chrome с залогиненным Instagram
- [Claude CLI](https://github.com/anthropics/claude-code) (`claude` в PATH) — только для шага `categorize`

### Платформы

| Платформа | Статус | Примечания |
|---|---|---|
| Linux | Полная поддержка | Основная платформа |
| macOS | Полная поддержка | Homebrew ffmpeg, стандартные пути Chrome/Firefox |
| Windows (WSL) | Полная поддержка | Рекомендуется Ubuntu в WSL2 |
| Windows нативно | Ограниченно | `run.py` поддерживает, yt-dlp может не читать Chrome cookies |

## Установка

### Linux / macOS / WSL

```bash
git clone <repo>
cd save-inst
bash setup.sh
```

`setup.sh` создаёт `.venv`, устанавливает зависимости, копирует `.env.example → .env`.

Отредактируй `.env` под свою систему (см. раздел **Конфигурация**).

### Windows нативно (без WSL)

```powershell
git clone <repo>
cd save-inst
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Отредактируй `.env`, укажи `BROWSER=chrome` и путь к профилю Chrome.

## Получение HTML-экспорта Instagram

1. Открой Instagram → **Настройки → Центр аккаунтов → Ваша информация и разрешения → Скачать ваши данные**
2. Выбери **"Скачать или перенести информацию"**
3. Формат: **HTML**, диапазон: **Всё время**
4. Дождись письма на почту (обычно несколько часов — до нескольких дней)
5. В архиве найди:
   - `saved_posts/saved_posts.html`
   - `saved_posts/saved_collections.html` (если есть коллекции)
6. Скопируй файлы в корень проекта

## Куки и авторизация

yt-dlp (скачивание видео/reels) и Instagram API (fallback для картинок) требуют авторизации через куки. Выбери удобный способ.

### Способ 1 — Firefox (рекомендуется на Linux/macOS)

Ничего настраивать не нужно — yt-dlp сам читает куки из SQLite-базы Firefox.

1. Убедись, что в Firefox открыт и залогинен instagram.com
2. Укажи путь к профилю в `.env`:
   ```
   BROWSER=firefox
   FIREFOX_PROFILE=~/snap/firefox/common/.mozilla/firefox  # Ubuntu/snap
   # FIREFOX_PROFILE=~/.mozilla/firefox                    # обычный Firefox
   ```
3. Запускай скрипты от того же пользователя, под которым запущен Firefox

Найти путь к профилю:
```bash
ls ~/snap/firefox/common/.mozilla/firefox/   # Ubuntu с snap
ls ~/.mozilla/firefox/                        # стандартный Firefox
```

### Способ 2 — Chrome (рекомендуется на Windows/macOS)

1. Убедись, что в Chrome открыт и залогинен instagram.com
2. Укажи в `.env`:
   ```
   BROWSER=chrome
   # Windows:
   CHROME_PROFILE=C:\Users\<Name>\AppData\Local\Google\Chrome\User Data
   # Linux (обычно автоопределяется):
   # CHROME_PROFILE=~/.config/google-chrome
   # macOS (обычно автоопределяется):
   # CHROME_PROFILE=~/Library/Application Support/Google/Chrome
   ```

> На Windows yt-dlp может потребовать закрыть Chrome перед запуском (база куки залочена).

### Способ 3 — cookies.txt (универсальный, для headless/CI)

Если yt-dlp не может читать куки браузера:

1. Установи расширение **"Get cookies.txt LOCALLY"** (Chrome/Firefox)
2. Открой instagram.com, экспортируй куки в `cookies.txt` (Netscape-формат)
3. Положи `cookies.txt` в корень проекта
4. В `scripts/fetch.py` замени строку `--cookies-from-browser` на `--cookies cookies.txt`

### Способ 4 — instaloader session-file (рекомендуется как дополнение)

instaloader используется как fallback для картинок, когда yt-dlp не справляется.

```bash
# Войти один раз — instaloader сохранит сессию в ~/.config/instaloader/
.venv/bin/instaloader --login YOUR_USERNAME

# Сессия подхватывается автоматически при запуске fetch.py
```

### Способ 5 — логин через .env (для CI / headless)

```
INSTA_USER=your_username
INSTA_PASS=your_password
```

> Прямой логин через пароль чаще вызывает капчу. Предпочтительнее session-file.

### Про Instagram API

Официального API для сохранённых постов **не существует**:
- `Instagram Basic Display API` — закрыт 4 декабря 2024
- `Instagram Graph API` — только для бизнес-аккаунтов, эндпоинта для saved posts нет

Проект использует приватный API Instagram (тот же, что мобильное приложение) с куками браузера.

## Запуск

```bash
# Полный pipeline (все шаги)
python run.py

# Отдельные шаги
python run.py --only extract     # HTML → data/links.json
python run.py --only fetch       # скачать медиа → content/ + data/posts.json
python run.py --only thumbnails  # сгенерировать превью → content/<id>/thumbnail.jpg
python run.py --only categorize  # категоризировать через Claude AI
python run.py --only build       # собрать html/index.html
python run.py --only obsidian    # экспорт в obsidian/

# Повторный прогон только ошибочных постов
.venv/bin/python scripts/fetch.py --retry-errors

# Пересчитать категории заново
.venv/bin/python scripts/categorizer.py --force
```

После запуска открой `html/index.html` в браузере.

## Конфигурация

Скопируй `.env.example` в `.env` и заполни нужные поля:

| Переменная | Описание | По умолчанию |
|---|---|---|
| `BROWSER` | Браузер для куки: `firefox` или `chrome` | `firefox` |
| `FIREFOX_PROFILE` | Путь к профилю Firefox | `~/snap/firefox/common/.mozilla/firefox` |
| `CHROME_PROFILE` | Путь к профилю Chrome (нужен если `BROWSER=chrome`) | автоопределение |
| `INSTA_USER` | Логин Instagram (для instaloader) | — |
| `INSTA_PASS` | Пароль Instagram (для instaloader) | — |

## Структура проекта

```
save-inst/
├── scripts/
│   ├── parser.py          # парсит HTML-экспорт Instagram → links.json
│   ├── fetch.py           # скачивает медиа через yt-dlp + Instagram API
│   ├── thumbnailer.py     # генерирует превью (ffmpeg + Instagram API)
│   ├── categorizer.py     # категоризирует через Claude AI
│   ├── builder.py         # строит html/index.html галерею
│   └── obsidian_export.py # экспортирует в Obsidian markdown
├── data/
│   ├── links.json         # спарсенные ссылки (генерируется)
│   ├── posts.json         # данные постов с категориями (генерируется)
│   └── categories.json    # индекс категорий (генерируется)
├── content/               # скачанные медиафайлы (генерируется, не в git)
├── html/
│   ├── index.html         # веб-галерея (генерируется)
│   └── data/posts.js      # данные для галереи (генерируется, не в git)
├── obsidian/              # Obsidian-заметки (генерируется, не в git)
├── run.py                 # оркестратор pipeline
├── requirements.txt
├── setup.sh               # скрипт установки
├── .env.example           # шаблон конфигурации
└── saved_posts.html       # экспорт из Instagram (не в git)
```

## Оптимизации (для контрибьюторов)

- **Параллельное скачивание** — `fetch.py` сейчас последовательный; `asyncio` + `ThreadPoolExecutor` ускорит в N раз
- **Кэш Instagram API** — повторные запросы к одному посту можно кэшировать в `data/api_cache.json`
- **Инкрементальный thumbnailer** — сейчас пропускает уже готовые превью, но не проверяет их валидность (размер > 0)
- **Веб-интерфейс** — `html/index.html` — статика; можно добавить локальный HTTP-сервер для корректной работы путей
- **Категоризация батчами** — сейчас один пост = один вызов Claude; можно группировать по 10-20 для ускорения
- **Windows-поддержка yt-dlp** — Chrome cookies на Windows могут быть зашифрованы DPAPI; нужен тест на нативном Windows

## Troubleshooting

**yt-dlp падает с ошибкой cookies:**
- Убедись что `BROWSER` и путь к профилю в `.env` верны
- Firefox: попробуй запустить с открытым и закрытым браузером
- Chrome на Windows: закрой браузер перед запуском (база куки залочена)
- Альтернатива: используй `cookies.txt` (Способ 3)

**instaloader не скачивает картинки:**
- Создай session-file (Способ 4)
- Без авторизации instaloader не достаёт приватные/старые посты

**Посты с `fetch_error: true`:**
```bash
.venv/bin/python scripts/fetch.py --retry-errors
```

**Категории слетели / нужно пересчитать:**
```bash
.venv/bin/python scripts/categorizer.py --force
```

**Превью не отображаются:**
```bash
python run.py --only thumbnails
```

**Пути к медиа не работают в браузере:**
- Открывай именно `html/index.html`, не отдельные файлы из `html/data/`
- Пути вида `../content/...` работают только относительно `html/`

**Python не найден (Windows нативно):**
- Убедись что Python 3.11+ в PATH
- Используй `python` вместо `python3`
