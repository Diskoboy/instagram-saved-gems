# Instagram Saved Gems

Скачивает все посты из Instagram, которые ты сохранил. Каждый пост — отдельная папка с медиа. Опционально: AI-анализ — транскрипция, OCR, категоризация — и веб-галерея с фильтрами.

## Как это работает

### Уровень 1 — скачать

```
saved_posts.html
    → parser.py  → data/links.json
    → fetch.py   → content/{id}/   (фото, видео, reels)
                   data/posts/{id}/meta.json
```

Всё. Больше ничего не нужно — медиа лежат по папкам.

### Уровень 2 — понять (опционально, нужен LLM)

```
content/{id}/
    → thumbnailer.py    → content/{id}/thumbnail.jpg
    → transcriber.py    → data/posts/{id}/transcription.json  (видео → текст)
    → ocr.py            → data/posts/{id}/ocr.json            (текст с экрана)
    → enricher.py       → data/posts/{id}/enriched.json       (категория / инсайт / шаги)
    → builder.py        → html/index.html  (галерея с фильтрами)
    → obsidian_export.py → obsidian/*.md
```

## Требования

**Уровень 1:** Python 3.11+, yt-dlp, Firefox или Chrome с залогиненным Instagram

**Уровень 2:** + ffmpeg; LLM: Ollama (локально) **ИЛИ** OpenRouter API key **ИЛИ** Anthropic API key

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
# Просто скачать все сохранённые посты:
python run.py --only extract     # HTML → links.json
python run.py --only fetch       # скачать медиа → content/{id}/

# Полный pipeline с AI-анализом и галереей:
python run.py                    # extract → fetch → thumbnails → enrich → build → obsidian

# Отдельные шаги:
python run.py --only thumbnails  # превью из видео
python run.py --only enrich      # AI-анализ (нужен LLM_PROVIDER)
python run.py --only build       # собрать html/index.html
python run.py --only obsidian    # экспорт в Obsidian

.venv/bin/python scripts/fetch.py --retry-errors   # повторить ошибки
.venv/bin/python scripts/enricher.py --force        # пересчитать анализ
```

После запуска открой `html/index.html` в браузере.

## Конфигурация LLM

Нужна только для шага `enrich`. Выбери одного провайдера:

| Переменная | Описание | По умолчанию |
|---|---|---|
| `LLM_PROVIDER` | Провайдер: `ollama` / `openrouter` / `claude` | `ollama` |
| `OLLAMA_URL` | URL ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Модель ollama (нужна vision для OCR) | `gemma3:4b` |
| `OPENROUTER_API_KEY` | API-ключ OpenRouter | — |
| `OPENROUTER_MODEL` | Модель OpenRouter | `openai/gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | API-ключ Anthropic | — |
| `ANTHROPIC_MODEL` | Модель Claude | `claude-haiku-4-5-20251001` |

> Для OCR нужна vision-capable модель: `gemma3:4b`, `llava:7b`, `moondream`. Текстовые модели не поддерживают изображения.

## Конфигурация Instagram

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
instagram-saved-gems/
├── scripts/
│   ├── parser.py           # парсит HTML-экспорт Instagram → links.json
│   ├── fetch.py            # скачивает медиа через yt-dlp + Instagram API
│   ├── thumbnailer.py      # генерирует превью (ffmpeg + Instagram API)
│   ├── transcriber.py      # транскрибирует аудио → transcription.json
│   ├── ocr.py              # извлекает текст с экрана → ocr.json
│   ├── enricher.py         # AI-анализ → enriched.json (категория / инсайт / шаги)
│   ├── store.py            # хранилище данных per-post
│   ├── builder.py          # строит html/index.html галерею
│   └── obsidian_export.py  # экспортирует в Obsidian markdown
├── data/
│   ├── links.json          # спарсенные ссылки (генерируется)
│   └── posts/
│       └── {id}/
│           ├── meta.json           # fetch.py
│           ├── transcription.json  # transcriber.py
│           ├── ocr.json            # ocr.py
│           └── enriched.json       # enricher.py
├── content/                # скачанные медиафайлы Instagram (генерируется, не в git)
├── html/
│   ├── index.html          # веб-галерея (генерируется)
│   └── data/posts.js       # данные для галереи (генерируется, не в git)
├── obsidian/               # Obsidian-заметки (генерируется, не в git)
├── bin/                    # локальные бинарники (не в git)
│   └── ffmpeg.exe          # Windows: положить руками
├── run.py                  # оркестратор pipeline
├── requirements.txt        # зависимости
├── setup.sh                # скрипт установки (Linux/macOS)
├── .env.example            # шаблон конфигурации
└── saved_posts.html        # экспорт из Instagram (не в git)
```

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

**AI-анализ не запускается / нужно пересчитать:**
```bash
.venv/bin/python scripts/enricher.py --force
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
