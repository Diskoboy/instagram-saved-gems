"""
Объединённый энричер: категоризация + анализ видео → data/enriched.json

Читает data/posts.json + data/analysis.json (если есть), джойнит по id.
Один LLM-запрос на пост: description + tags + transcription + screen_text.
Результат: category, tools, insight, steps.

Usage:
  python scripts/enricher.py
  python scripts/enricher.py --limit 5
  python scripts/enricher.py --ids ABC123 DEF456
  python scripts/enricher.py --force
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from llm import ask  # noqa: E402
from store import all_post_ids, load_meta, load_transcription, load_ocr, load_enriched, save_enriched  # noqa: E402

ENRICH_PROMPT = """Предположи, что пользователь сохранил этот пост, потому что в нём есть полезная идея или инструмент.

Твоя задача — проанализировать Instagram-пост и извлечь полезную идею, ради которой человек мог его сохранить.

На вход: описание поста, хэштеги, текст с изображений (OCR), транскрипция речи.

Не пересказывай видео. Объясни практическую идею поста.

Верни ТОЛЬКО валидный JSON:
{{
  "core_idea": "2–4 предложения на русском: главная практическая идея, зачем это могли сохранить",
  "category": "1–2 слова: AI Coding | Automation | Tools | Marketing | Design | Business | Productivity | Other",
  "tools": ["конкретные инструменты, AI-модели, сервисы, упомянутые в посте"],
  "value_type": "тип пользы: ускорение разработки | экономия денег | автоматизация | новый инструмент | workflow | инструкция | идея | техника",
  "topics": ["3–6 ключевых слов темы"],
  "workflow": ["шаг 1", "шаг 2"],
  "ideas": [
    {{"tools": "Инструмент1 + Инструмент2", "description": "Одно предложение — что делает и зачем."}}
  ]
}}

workflow: если пост описывает конкретную последовательность действий — перечисли шаги. Иначе [].
ideas: список конкретных идей из поста. Каждая — связка инструментов и одно предложение практической пользы.
Если инструмент один — просто его название. Если несколько — через " + ".

Представь, что ты пишешь заметки для личной базы знаний инженера.

Пост:
{description}

{transcription_block}{screen_text_block}
Верни только JSON, без объяснений."""


def _default() -> dict:
    return {
        'category': 'Other',
        'tools': [],
        'core_idea': '',
        'value_type': '',
        'topics': [],
        'workflow': [],
        'ideas': [],
    }


def parse_json_response(text: str) -> dict:
    start = text.find('{')
    end = text.rfind('}') + 1
    if start == -1:
        return {}
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return {}


_CODE_RE = re.compile(
    r'import |def |git |docker|npm |pip |apt |http|`|\$\s|\.py|\.sh|\.ts|\.js|={2,}',
    re.I,
)


def is_useful_screen_text(screen_text: str, transcription: str) -> bool:
    """Возвращает True если screen_text содержит полезный контент (код, команды, URL),
    False если это субтитры (дублируют транскрипцию)."""
    if not screen_text.strip():
        return False
    if _CODE_RE.search(screen_text):
        return True
    s_words = set(screen_text.lower().split())
    t_words = set(transcription.lower().split())
    if not s_words:
        return False
    overlap = len(s_words & t_words) / len(s_words)
    return overlap < 0.6


def enrich_post(post: dict, analysis: dict | None, existing_cats: list[str]) -> tuple[dict, str]:
    description = post.get('description', '')[:800]
    hashtags = post.get('hashtags', [])
    if hashtags:
        description += '\nHashtags: ' + ' '.join(hashtags[:20])

    transcription_block = ''
    if analysis:
        transcription = analysis.get('transcription', {}).get('text', '')[:1500]
        if transcription:
            transcription_block = f'Transcription (audio):\n{transcription}\n\n'

    post_type = post.get('type', '')

    screen_text_block = ''
    screen_label = ''
    if analysis:
        transcription_text = analysis.get('transcription', {}).get('text', '')
        screen_raw = analysis.get('screen_text', {}).get('combined', '')
        if screen_raw:
            if post_type in ('image', 'carousel'):
                screen_text_block = f'Image text (OCR):\n{screen_raw[:800]}\n\n'
                screen_label = ' screen:image'
            elif is_useful_screen_text(screen_raw, transcription_text):
                screen_text_block = f'On-screen text:\n{screen_raw[:800]}\n\n'
                screen_label = ' screen:useful'
            else:
                screen_label = ' screen:subtitles(skipped)'

    prompt = ENRICH_PROMPT.format(
        description=description,
        transcription_block=transcription_block,
        screen_text_block=screen_text_block,
    )

    try:
        raw = ask(prompt)
    except RuntimeError as e:
        print(f'  LLM error: {e}', file=sys.stderr)
        return _default(), screen_label

    result = parse_json_response(raw)
    if not result:
        print(f'  failed to parse: {raw[:200]}', file=sys.stderr)
        return _default(), screen_label

    return {
        'category': result.get('category') or 'Other',
        'tools': result.get('tools', []),
        'core_idea': result.get('core_idea', ''),
        'value_type': result.get('value_type', ''),
        'topics': result.get('topics', []),
        'workflow': result.get('workflow') or [],
        'ideas': result.get('ideas', []),
    }, screen_label


def main():
    parser = argparse.ArgumentParser(
        description='Enrich Instagram posts with LLM: category, tools, insight, steps'
    )
    parser.add_argument('--force', action='store_true',
                        help='Re-process already enriched posts')
    parser.add_argument('--limit', type=int, default=0, metavar='N',
                        help='Process only first N posts (0 = all)')
    parser.add_argument('--ids', nargs='+', metavar='ID',
                        help='Process only these post IDs')
    args = parser.parse_args()

    id_filter = set(args.ids) if args.ids else None

    to_process = []
    for pid in all_post_ids():
        meta = load_meta(pid)
        if not meta or meta.get('fetch_error'):
            continue
        if id_filter and pid not in id_filter:
            continue
        if not args.force and load_enriched(pid).get('category'):
            continue
        to_process.append((pid, meta))

    if args.limit and args.limit > 0:
        to_process = to_process[:args.limit]

    if not to_process:
        print('Nothing to process.')
    else:
        print(f'Processing {len(to_process)} posts (LLM_PROVIDER={__import__("os").getenv("LLM_PROVIDER","ollama")})...')

    done_cats: list[str] = []
    for i, (pid, post) in enumerate(to_process, 1):
        existing_cats = list(dict.fromkeys(done_cats))

        analysis = {
            'transcription': load_transcription(pid),
            'screen_text': load_ocr(pid),
        }
        result, screen_label = enrich_post(post, analysis, existing_cats)
        print(f'[{i}/{len(to_process)}] {pid} (cats: {len(existing_cats)}){screen_label}')
        print(f'  [{result.get("category","?")}] {result.get("core_idea","")[:80]}')

        save_enriched(pid, {'id': pid, **result})
        if result.get('category'):
            done_cats.append(result['category'])

        if result.get('workflow'):
            print(f'  steps: {len(result["workflow"])}')

    total = sum(1 for pid in all_post_ids() if load_enriched(pid).get('category'))
    print(f'\nDone. Total enriched: {total}')


if __name__ == '__main__':
    main()
