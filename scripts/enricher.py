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

ENRICH_PROMPT = """Analyze this Instagram post and return ONLY valid JSON.

Post description and hashtags:
{description}

{transcription_block}{screen_text_block}
Return:
{{
  "category": "short English label 1-3 words describing the main topic",
  "tools": ["tool1", "tool2"],
  "insight": "one sentence summary in Russian",
  "steps": ["step1", "step2"]
}}

tools: specific software/services/AI models/libraries mentioned (empty [] if none)
insight: key takeaway in Russian, one sentence
steps: if the post describes a process with concrete actions/commands — list them sequentially.
       Include exact commands, URLs, settings. Empty [] if no actionable steps.

Return only the JSON, no explanation."""


def _default() -> dict:
    return {
        'category': 'Other',
        'tools': [],
        'insight': '',
        'steps': [],
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

    screen_text_block = ''
    screen_label = ''
    if analysis:
        transcription_text = analysis.get('transcription', {}).get('text', '')
        screen_raw = analysis.get('screen_text', {}).get('combined', '')
        if screen_raw:
            if is_useful_screen_text(screen_raw, transcription_text):
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
        'insight': result.get('insight', ''),
        'steps': result.get('steps', []),
    }, screen_label


def main():
    parser = argparse.ArgumentParser(
        description='Enrich Instagram posts with LLM: category, tools, insight, steps'
    )
    parser.add_argument('--input', default='data/posts.json', metavar='FILE')
    parser.add_argument('--analysis', default='data/analysis.json', metavar='FILE',
                        help='Video analysis file (transcription + screen_text). Optional.')
    parser.add_argument('--output', default='data/enriched.json', metavar='FILE')
    parser.add_argument('--force', action='store_true',
                        help='Re-process already enriched posts')
    parser.add_argument('--limit', type=int, default=0, metavar='N',
                        help='Process only first N posts (0 = all)')
    parser.add_argument('--ids', nargs='+', metavar='ID',
                        help='Process only these post IDs')
    args = parser.parse_args()

    posts_path = Path(args.input)
    if not posts_path.exists():
        print(f'{args.input} not found. Run fetch.py first.', file=sys.stderr)
        sys.exit(1)

    posts: list[dict] = json.loads(posts_path.read_text(encoding='utf-8'))

    # Load analysis if available
    analysis_by_id: dict[str, dict] = {}
    analysis_path = Path(args.analysis)
    if analysis_path.exists():
        analysis_list: list[dict] = json.loads(analysis_path.read_text(encoding='utf-8'))
        analysis_by_id = {r['id']: r for r in analysis_list}

    # Load existing enriched data
    output_path = Path(args.output)
    enriched_by_id: dict[str, dict] = {}
    if output_path.exists() and not args.force:
        existing: list[dict] = json.loads(output_path.read_text(encoding='utf-8'))
        enriched_by_id = {r['id']: r for r in existing}

    # Filter posts to process
    id_filter = set(args.ids) if args.ids else None

    to_process = []
    for post in posts:
        if post.get('fetch_error'):
            continue
        pid = post['id']
        if id_filter and pid not in id_filter:
            continue
        if pid in enriched_by_id and not args.force:
            continue
        to_process.append(post)

    if args.limit and args.limit > 0:
        to_process = to_process[:args.limit]

    if not to_process:
        print('Nothing to process.')
    else:
        print(f'Processing {len(to_process)} posts (LLM_PROVIDER={__import__("os").getenv("LLM_PROVIDER","ollama")})...')

    for i, post in enumerate(to_process, 1):
        pid = post['id']
        existing_cats = list(dict.fromkeys(
            r['category'] for r in enriched_by_id.values()
            if r.get('category')
        ))

        analysis = analysis_by_id.get(pid)
        result, screen_label = enrich_post(post, analysis, existing_cats)
        print(f'[{i}/{len(to_process)}] {pid} (cats: {len(existing_cats)}){screen_label}')

        enriched_by_id[pid] = {'id': pid, **result}

        # Save after each post
        output_path.parent.mkdir(parents=True, exist_ok=True)
        enriched_list = list(enriched_by_id.values())
        output_path.write_text(json.dumps(enriched_list, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f'  [{result["category"]}] {result["insight"][:60]}')
        if result['steps']:
            print(f'  steps: {len(result["steps"])}')

    total = len(enriched_by_id)
    with_steps = sum(1 for r in enriched_by_id.values() if r.get('steps'))
    cats = list(dict.fromkeys(r['category'] for r in enriched_by_id.values()))
    print(f'\nDone. Total enriched: {total}. With steps: {with_steps}. Categories: {cats}')


if __name__ == '__main__':
    main()
