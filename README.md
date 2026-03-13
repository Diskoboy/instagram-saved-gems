# Instagram Saved Gems

Два независимых инструмента в одном репозитории:

Вытаскивает сохранённые посты из Instagram и помогает понять, зачем ты их сохранял — что в них важного и ценного.

1. **Instagram Archive** — архивирует сохранённые посты из Instagram-экспорта: скачивает медиа, генерирует превью, категоризирует через Claude AI, строит веб-галерею и экспортирует в Obsidian.
2. **Video Analysis** — анализирует видео из любого источника: транскрибирует аудио (faster-whisper), извлекает текст с экрана (ollama vision), строит HTML-отчёт по инструментам и смыслу контента.

## Как это работает

### Instagram Archive Pipeline

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

### Video Analysis Pipeline

```
URL / mp4-файлы / posts.json
       │
       ▼
 fetcher.py  ──►  content_analysis/<id>/video.mp4  +  data/analysis.json
       │
       ▼
transcriber.py ──►  data/analysis.json (+ transcription: text, language)
       │
       ▼
   ocr.py   ──►  data/analysis.json (+ screen_text: combined)
       │
       ▼
reporter.py  ──►  html/analysis.html
```

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

## Video Analysis Pipeline

Анализирует видео из любого источника — не только Instagram. Извлекает смысл: о чём говорится, какие инструменты упоминаются, что написано на экране.

### Требования

- [ffmpeg](https://ffmpeg.org/) — для извлечения кадров (уже нужен для основного pipeline)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — транскрипция аудио локально
- [ollama](https://ollama.com/) + vision-модель — OCR текста с экрана и анализ

```bash
# Установить faster-whisper
pip install -r requirements_analysis.txt

# Установить ollama (Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Скачать vision-модель (поддерживает работу с изображениями)
ollama pull gemma3:4b
```

> **Windows:** ollama — установщик с [ollama.com/download](https://ollama.com/download). ffmpeg — скачай с [github.com/BtbN/FFmpeg-Builds/releases](https://github.com/BtbN/FFmpeg-Builds/releases), распакуй `ffmpeg.exe` и `ffprobe.exe` в папку `bin/` проекта — скрипт найдёт автоматически.

> **Важно:** для OCR нужна vision-capable модель: `gemma3:4b`, `llava:7b`, `moondream`. Текстовые модели (`gemma2`, `llama3`) не поддерживают изображения.

### Запуск

```bash
# Полный pipeline: скачать → транскрибировать → OCR → отчёт
python run_analysis.py --from-posts data/posts.json   # из Instagram-архива
python run_analysis.py --urls-file urls.txt           # из текстового файла с URL
python run_analysis.py --local-dir /path/to/videos    # из локальной папки

# Отдельные шаги
python run_analysis.py --only fetch       # только скачать видео
python run_analysis.py --only transcribe  # только транскрипция
python run_analysis.py --only ocr         # только OCR экрана
python run_analysis.py --only report      # только собрать отчёт

# Без LLM-анализа (просто сырые данные в HTML)
python run_analysis.py --only report --no-llm

# Выбор моделей
python run_analysis.py --model-whisper small --model-ollama llava:7b
```

После запуска открой `html/analysis.html` в браузере.

### Конфигурация Video Analysis

| Переменная | Описание | По умолчанию |
|---|---|---|
| `OLLAMA_URL` | URL ollama сервера | `http://localhost:11434` |
| `OLLAMA_MODEL` | Vision-модель для OCR и анализа | `gemma3:4b` |
| `WHISPER_MODEL` | Размер модели: `tiny` / `base` / `small` / `medium` / `large-v3` | `base` |
| `WHISPER_DEVICE` | Устройство: `auto` / `cpu` / `cuda` | `auto` |
| `WHISPER_COMPUTE_TYPE` | Точность: `int8` (CPU) / `float16` (GPU) | `int8` |
| `FFMPEG_PATH` | Путь к ffmpeg (если не в PATH и не в `bin/`) | — |

## Конфигурация Instagram Archive

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
instagram-post-analyzer/
├── scripts/
│   ├── parser.py           # парсит HTML-экспорт Instagram → links.json
│   ├── fetch.py            # скачивает медиа через yt-dlp + Instagram API
│   ├── thumbnailer.py      # генерирует превью (ffmpeg + Instagram API)
│   ├── categorizer.py      # категоризирует через Claude AI
│   ├── builder.py          # строит html/index.html галерею
│   ├── obsidian_export.py  # экспортирует в Obsidian markdown
│   └── analysis/
│       ├── fetcher.py      # скачивает видео из URL / локальных файлов / posts.json
│       ├── transcriber.py  # транскрибирует аудио через faster-whisper
│       ├── ocr.py          # извлекает текст с экрана через ollama vision
│       └── reporter.py     # строит html/analysis.html отчёт
├── data/
│   ├── links.json          # спарсенные ссылки (генерируется)
│   ├── posts.json          # данные постов с категориями (генерируется)
│   ├── categories.json     # индекс категорий (генерируется)
│   └── analysis.json       # результаты анализа видео (генерируется)
├── content/                # скачанные медиафайлы Instagram (генерируется, не в git)
├── content_analysis/       # скачанные видео для анализа (генерируется, не в git)
├── html/
│   ├── index.html          # веб-галерея Instagram (генерируется)
│   ├── analysis.html       # отчёт по видео (генерируется)
│   └── data/posts.js       # данные для галереи (генерируется, не в git)
├── obsidian/               # Obsidian-заметки (генерируется, не в git)
├── bin/                    # локальные бинарники (не в git)
│   └── ffmpeg.exe          # Windows: положить руками
├── run.py                  # оркестратор Instagram pipeline
├── run_analysis.py         # оркестратор Video Analysis pipeline
├── requirements.txt        # зависимости Instagram pipeline
├── requirements_analysis.txt  # зависимости Video Analysis pipeline
├── setup.sh                # скрипт установки (Linux/macOS)
├── .env.example            # шаблон конфигурации
└── saved_posts.html        # экспорт из Instagram (не в git)
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
