# Instagram Saved Gems — документация на русском

Два независимых инструмента для работы с контентом Instagram.

📖 [English documentation](README.md)

---

## Модуль 1 — Instagram Archive

Архивирует сохранённые посты из официального экспорта Instagram:
скачивает все медиа, генерирует превью, категоризирует через AI,
и даёт три формата выгрузки для дальнейшей работы.

**Что получаешь:**
- `html/index.html` — поисковая веб-галерея с AI-категориями, дайджестом инструментов и вкладкой Workflow
- `tmp/media/` — плоский экспорт: все фото и видео в одной папке, с именами `{postId}_filename.jpg/mp4`
- `obsidian/` — Markdown-заметки на каждый пост, готовые к добавлению в Obsidian vault

**Пайплайн:**

```
saved_posts.html  →  parser.py   →  data/links.json
links.json        →  fetch.py    →  content/{id}/        (скачивание медиа)
content/{id}/     →  thumbnailer →  превью
content/{id}/     →  transcriber →  transcription.json   (аудио → текст)
content/{id}/     →  ocr.py      →  ocr.json             (текст с экрана)
data/posts/{id}/  →  enricher.py →  enriched.json        (AI-категории)
data/posts/{id}/  →  builder.py  →  html/index.html      (веб-галерея)
data/posts/{id}/  →  obsidian    →  obsidian/*.md
content/{id}/     →  export_flat →  tmp/media/           (плоская копия)
```

---

## Модуль 2 — Video Analysis

Анализирует видео из любого источника (не только Instagram):
транскрибирует аудио через faster-whisper, извлекает текст с экрана через LLM vision,
строит HTML-отчёт по инструментам и ценности контента.

```
urls.txt / .mp4  →  fetcher.py   →  content_analysis/{id}/video.mp4
video.mp4        →  transcriber  →  транскрипция
video.mp4        →  ocr.py       →  текст с экрана
analysis.json    →  reporter.py  →  html/analysis.html
```

---

## Установка

```bash
git clone https://github.com/Diskoboy/instagram-saved-gems.git
cd instagram-saved-gems
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # отредактируй .env под себя
```

Для модуля 2 (Video Analysis):
```bash
pip install -r requirements_analysis.txt
```

---

## Конфигурация

Скопируй `.env.example` в `.env` и измени нужные переменные.

### LLM-провайдер

| Провайдер | Настройка | Примечание |
|-----------|-----------|-----------|
| Ollama (локально) | `LLM_PROVIDER=ollama` | По умолчанию. [ollama.com](https://ollama.com/download) → `ollama pull gemma3:4b` |
| OpenRouter | `LLM_PROVIDER=openrouter` | Указать `OPENROUTER_API_KEY` |
| Anthropic Claude | `LLM_PROVIDER=claude` | Указать `ANTHROPIC_API_KEY` |

Для OCR нужна vision-совместимая модель: `gemma3:4b`, `llava:7b`, `moondream`.

### Аутентификация через браузер

yt-dlp читает Instagram-куки напрямую из браузера (нужно быть залогиненным):

```env
BROWSER=firefox
FIREFOX_PROFILE=~/snap/firefox/common/.mozilla/firefox
```

Найти путь к профилю Firefox:
```bash
ls ~/snap/firefox/common/.mozilla/firefox/   # Snap-версия
ls ~/.mozilla/firefox/                        # Обычная установка
```

### Настройка задержек (защита от бана)

Все задержки настраиваются в `.env`:

```env
FETCH_SLEEP_MIN=3          # минимальная задержка между запросами (секунды)
FETCH_SLEEP_MAX=10         # максимальная случайная задержка (секунды)
FETCH_SOCKET_TIMEOUT=60    # таймаут сокета
FETCH_RETRIES=5            # повторные попытки при ошибке
FETCH_EXTRACTOR_RETRIES=3  # повторы на уровне экстрактора
FETCH_PROCESS_TIMEOUT=120  # жёсткий таймаут подпроцесса
FETCH_API_TIMEOUT=20       # таймаут Instagram API (fallback)
```

---

## Модуль 1 — Использование

### 1. Получи экспорт Instagram

Инстаграм → Настройки → Ваша активность → Загрузить свою информацию.
Выбери формат **HTML**. Распакуй архив, положи `saved_posts.html` (и `saved_collections.html`) в корень проекта.

Или создай текстовый файл с ссылками по одной в строке:
```
https://www.instagram.com/p/ABC123/
https://www.instagram.com/reel/XYZ456/
```

### 2. Запуск пайплайна

```bash
# Полный пайплайн
python run.py

# Отдельные шаги
python run.py --only extract     # парсинг HTML → links.json
python run.py --only fetch       # скачивание медиа из Instagram
python run.py --only thumbnails  # превью
python run.py --only transcribe  # транскрипция аудио (faster-whisper)
python run.py --only ocr         # текст с экрана (ollama vision)
python run.py --only enrich      # AI-категоризация
python run.py --only build       # сборка веб-галереи
python run.py --only obsidian    # экспорт в Obsidian
python run.py --only export      # плоская копия в tmp/media/
```

Все шаги **инкрементальные** — уже обработанные посты пропускаются автоматически.

### 3. Открыть галерею

```bash
xdg-open html/index.html   # Linux
open html/index.html        # macOS
# Windows: двойной клик по html/index.html
```

### Плоский экспорт

Все медиафайлы в одной папке — удобно для сортировки или импорта в фотоприложения:
```bash
python scripts/export_flat.py
# → tmp/media/{postId}_media_001.jpg
# → tmp/media/{postId}_media_001.mp4
```

### Экспорт в Obsidian

```bash
python run.py --only obsidian
# → obsidian/{postId}.md
```

---

## Модуль 2 — Использование

```bash
# Из файла с URL
python scripts/analysis/fetcher.py --urls-file urls.txt

# Из локальных видеофайлов
python scripts/analysis/fetcher.py --local-dir /path/to/videos

# Транскрипция + OCR
python scripts/analysis/transcriber.py
python scripts/analysis/ocr.py

# Сборка HTML-отчёта
python scripts/analysis/reporter.py
xdg-open html/analysis.html
```

---

## Устранение проблем

**yt-dlp не работает / Instagram блокирует:**
- Убедись, что залогинен в Instagram в Firefox/Chrome
- Увеличь задержки: `FETCH_SLEEP_MIN=5`, `FETCH_SLEEP_MAX=20`

**LLM не успевает ответить:**
Увеличь `LLM_TIMEOUT=240` в `.env`.

**ffmpeg не найден (Windows):**
Скачай с [github.com/BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases),
скопируй `ffmpeg.exe` и `ffprobe.exe` в папку `bin/` в корне проекта.

**OCR возвращает JSON вместо текста:**
Уже обработано — `clean_ocr_text()` автоматически извлекает plain text из любого JSON-ответа.

---

## run.py vs run_analysis.py

| | `run.py` | `run_analysis.py` |
|---|---|---|
| **Модуль** | 1 — Instagram Archive | 2 — Video Analysis |
| **Источник** | `saved_posts.html` / список URL | любые видео: URL, локальные файлы, mp4 |
| **Шаги** | extract → fetch → thumbnails → transcribe → ocr → enrich → build → obsidian → export | fetch → transcribe → ocr → report |
| **Выход** | `html/index.html` (галерея постов) | `html/analysis.html` (отчёт по видео) |
| **Флаги** | `--only <step>` | `--only`, `--skip`, `--from-posts`, `--urls-file`, `--local-dir`, `--no-llm` |

`run.py` — для архива сохранённых постов Instagram.
`run_analysis.py` — для анализа произвольных видео из любого источника.
