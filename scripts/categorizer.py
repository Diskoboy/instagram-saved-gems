"""
Читает data/posts.json, категоризирует каждый пост через Claude CLI,
дописывает category, tools, value_type, workflow, insight → data/posts.json,
data/categories.json, data/tools.json, data/values.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_PROMPT = """Given an Instagram post, return ONLY valid JSON.

Existing categories ({cat_count}/10): {existing_cats_json}

Rules for category:
- If post fits an existing category → use that exact name
- If no fit AND count < 10 → suggest new short name (1-3 words, English)
- If no fit AND count >= 10 → use the closest existing category

Return:
{{
  "category": "...",
  "tools": ["tool1", "tool2"],
  "value_type": "one of: ускорение разработки / автоматизация / workflow / гайд / новый инструмент / экономия денег / другое",
  "workflow": ["step1", "step2"],
  "insight": "one sentence in Russian"
}}

tools: specific software/services/AI models/libraries mentioned (empty [] if none)
workflow: sequential steps if post describes a process, else []
insight: key takeaway in Russian

Post text:
{post_text}
"""


def categorize_post(post_text: str, existing_cats: list[str]) -> dict:
    prompt = SKILL_PROMPT.format(
        cat_count=len(existing_cats),
        existing_cats_json=json.dumps(existing_cats, ensure_ascii=False),
        post_text=post_text,
    )

    env = {k: v for k, v in os.environ.items() if k != 'CLAUDECODE'}
    result = subprocess.run(
        ['claude', '-p', prompt, '--output-format', 'json'],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )

    if result.returncode != 0:
        print(f'  claude error: {result.stderr[-200:]}', file=sys.stderr)
        return _default()

    try:
        outer = json.loads(result.stdout)
        raw = outer.get('result', result.stdout)
    except json.JSONDecodeError:
        raw = result.stdout

    try:
        if isinstance(raw, str):
            start = raw.find('{')
            end = raw.rfind('}') + 1
            return json.loads(raw[start:end])
        return raw
    except (json.JSONDecodeError, ValueError):
        print(f'  failed to parse: {raw[:200]}', file=sys.stderr)
        return _default()


def _default() -> dict:
    return {
        'category': 'Other',
        'tools': [],
        'value_type': 'другое',
        'workflow': [],
        'insight': '',
    }


def main():
    posts_path = Path('data/posts.json')
    if not posts_path.exists():
        print('data/posts.json not found. Run fetch.py first.')
        sys.exit(1)

    force = '--force' in sys.argv
    posts: list[dict] = json.loads(posts_path.read_text(encoding='utf-8'))

    if force:
        print('--force: resetting all enrichment fields')
        for p in posts:
            for field in ('category', 'tools', 'value_type', 'workflow', 'insight'):
                p.pop(field, None)

    for i, post in enumerate(posts, 1):
        if post.get('fetch_error'):
            print(f'[{i}/{len(posts)}] {post["id"]} fetch_error, skipping')
            continue

        if 'category' in post:
            print(f'[{i}/{len(posts)}] {post["id"]} already enriched, skipping')
            continue

        # Build existing categories from already-processed posts (preserving order)
        existing_cats = list(dict.fromkeys(
            p['category'] for p in posts
            if p.get('category') and not p.get('fetch_error')
        ))

        post_text = post.get('description', '')[:800]
        hashtags = post.get('hashtags', [])
        if hashtags:
            post_text += '\nHashtags: ' + ' '.join(hashtags[:20])

        print(f'[{i}/{len(posts)}] {post["id"]} (cats: {len(existing_cats)})')
        result = categorize_post(post_text, existing_cats)

        # Claude sometimes returns 'categories' (list) instead of 'category'
        category = result.get('category') or (result.get('categories') or ['Other'])[0]
        post['category'] = category or 'Other'
        post['tools'] = result.get('tools', [])
        post['value_type'] = result.get('value_type', 'другое')
        post['workflow'] = result.get('workflow', [])
        post['insight'] = result.get('insight', '')

        posts_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2))

    # Build indexes
    cat_index: dict[str, list[str]] = {}
    tools_count: dict[str, int] = {}
    tools_index: dict[str, list[str]] = {}
    values_index: dict[str, list[str]] = {}

    for post in posts:
        if post.get('fetch_error'):
            continue
        pid = post['id']
        cat = post.get('category', 'Other')
        cat_index.setdefault(cat, []).append(pid)

        for tool in post.get('tools', []):
            if tool:
                tools_index.setdefault(tool, []).append(pid)
                tools_count[tool] = tools_count.get(tool, 0) + 1

        vtype = post.get('value_type', 'другое')
        if vtype:
            values_index.setdefault(vtype, []).append(pid)

    # Sort tools by count desc
    tools_index = dict(
        sorted(tools_index.items(), key=lambda kv: tools_count[kv[0]], reverse=True)
    )

    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)

    data_dir.joinpath('categories.json').write_text(
        json.dumps(cat_index, ensure_ascii=False, indent=2)
    )
    data_dir.joinpath('tools.json').write_text(
        json.dumps(tools_index, ensure_ascii=False, indent=2)
    )
    data_dir.joinpath('values.json').write_text(
        json.dumps(values_index, ensure_ascii=False, indent=2)
    )

    ok = sum(1 for p in posts if not p.get('fetch_error') and p.get('category'))
    print(f'\nDone. Enriched: {ok}. Categories: {list(cat_index.keys())}')


if __name__ == '__main__':
    main()
