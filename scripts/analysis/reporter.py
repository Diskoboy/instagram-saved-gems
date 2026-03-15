"""
Read data/analysis.json, enrich via LLM, build html/analysis.html.
Two tabs: by tools and by value/meaning.

Читает data/analysis.json, анализирует через LLM, строит html/analysis.html.
Два таба: по инструментам и по смыслу/ценности.

Usage:
  python scripts/analysis/reporter.py
  python scripts/analysis/reporter.py --no-llm
  python scripts/analysis/reporter.py --output html/report.html
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from llm import ask  # noqa: E402


EXTRACT_PROMPT = """Analyze this video content and extract structured information.

Transcription (audio):
{transcription}

On-screen text:
{screen_text}

Return ONLY valid JSON:
{{
  "tools": ["tool1", "tool2"],
  "value_tags": ["time-saving", "automation"],
  "insight": "one sentence summary in Russian"
}}

tools: specific software, plugins, AI models, services mentioned (empty [] if none)
value_tags: what value this content provides — invent English tags like: time-saving, automation, tutorial, workflow, monetization, productivity, ai-coding, research, prompt-engineering, etc.
insight: key takeaway in Russian, one sentence

Return only the JSON, no explanation."""

CATEGORIZE_PROMPT = """You have a list of video insights and their value tags. Create meaningful categories in Russian.

Data:
{data}

Return ONLY valid JSON:
{{
  "categories": [
    {{
      "name": "Название категории",
      "description": "one line description in Russian",
      "ids": ["id1", "id2"]
    }}
  ]
}}

Rules:
- Create 3-8 categories based on the actual content
- Category names in Russian (2-4 words)
- Group by purpose/value, not by tool name
- Every ID must appear in exactly one category
- Put uncategorized items in "Разное"

Return only the JSON."""

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru" x-data="app()" x-init="init()">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Video Analysis Report</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <style>[x-cloak] { display: none !important; }</style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen" x-cloak>

<header class="sticky top-0 z-40 bg-gray-900 border-b border-gray-800 px-4 py-3">
  <div class="flex items-center gap-4 mb-2">
    <span class="text-lg font-bold text-blue-400">Video Analysis</span>
    <span class="text-sm text-gray-500" x-text="totalCount + ' videos'"></span>
  </div>
  <nav class="flex gap-1">
    <template x-for="t in tabs" :key="t.id">
      <button
        @click="tab = t.id"
        :class="tab === t.id ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'"
        class="px-3 py-1.5 rounded-lg text-sm font-medium transition"
        x-text="t.label"
      ></button>
    </template>
  </nav>
</header>

<!-- TAB: BY TOOLS -->
<main x-show="tab === 'tools'" class="p-4 max-w-3xl mx-auto">
  <div class="space-y-2">
    <template x-for="item in toolsList" :key="item.name">
      <div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <button
          class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800 transition text-left"
          @click="item.open = !item.open"
        >
          <span class="font-medium text-white" x-text="item.name"></span>
          <div class="flex items-center gap-3">
            <span class="text-sm text-blue-400 font-semibold" x-text="item.videos.length + ' видео'"></span>
            <span class="text-gray-500 text-sm" x-text="item.open ? '▲' : '▼'"></span>
          </div>
        </button>
        <template x-if="item.open">
          <div class="border-t border-gray-800 p-3 space-y-2">
            <template x-for="vid in item.videos" :key="vid.id">
              <div
                class="p-3 rounded-lg bg-gray-800 cursor-pointer hover:bg-gray-700 transition"
                @click="openModal(vid)"
              >
                <div class="text-xs text-gray-500 mb-1" x-text="vid.id"></div>
                <div class="text-sm text-gray-200" x-text="vid.insight || '(no insight)'"></div>
                <div class="flex flex-wrap gap-1 mt-1">
                  <template x-for="tag in (vid.value_tags || [])" :key="tag">
                    <span class="text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded" x-text="tag"></span>
                  </template>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </template>
    <div x-show="toolsList.length === 0" class="text-center text-gray-600 py-20 text-lg">
      Нет данных об инструментах
    </div>
  </div>
</main>

<!-- TAB: BY VALUE -->
<main x-show="tab === 'value'" class="p-4 max-w-4xl mx-auto">
  <template x-for="cat in valueCategories" :key="cat.name">
    <div class="mb-8">
      <h2 class="text-lg font-bold text-blue-400 mb-1" x-text="cat.name"></h2>
      <p class="text-sm text-gray-500 mb-3" x-text="cat.description"></p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <template x-for="vid in cat.videos" :key="vid.id">
          <div
            class="bg-gray-900 border border-gray-800 rounded-xl p-3 cursor-pointer hover:border-blue-500 transition"
            @click="openModal(vid)"
          >
            <div class="text-xs text-gray-500 mb-1" x-text="vid.id"></div>
            <div class="text-sm text-gray-200 mb-2" x-text="vid.insight || '(no insight)'"></div>
            <div class="flex flex-wrap gap-1">
              <template x-for="tool in (vid.tools || []).slice(0, 3)" :key="tool">
                <span class="text-[10px] bg-blue-900/50 text-blue-300 px-1.5 py-0.5 rounded" x-text="tool"></span>
              </template>
              <template x-if="(vid.tools || []).length > 3">
                <span class="text-[10px] text-gray-600" x-text="'+' + ((vid.tools || []).length - 3)"></span>
              </template>
            </div>
          </div>
        </template>
      </div>
    </div>
  </template>
  <div x-show="valueCategories.length === 0" class="text-center text-gray-600 py-20 text-lg">
    Нет данных
  </div>
</main>

<!-- MODAL -->
<div
  x-show="modal"
  @click.self="modal = null"
  class="fixed inset-0 z-50 bg-black/80 backdrop-blur flex items-center justify-center p-4"
>
  <div
    x-show="modal"
    x-transition
    class="bg-gray-900 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-gray-700"
  >
    <template x-if="modal">
      <div class="p-4">
        <div class="flex justify-between items-start mb-3">
          <div class="text-sm text-gray-400 font-mono" x-text="modal.id"></div>
          <button @click="modal = null" class="text-gray-500 hover:text-white text-2xl leading-none">&times;</button>
        </div>

        <div class="text-white font-medium mb-3" x-text="modal.insight || '(no insight)'"></div>

        <div class="flex flex-wrap gap-1.5 mb-4">
          <template x-for="tool in (modal.tools || [])" :key="tool">
            <span class="bg-blue-900/50 text-blue-300 text-xs px-2 py-0.5 rounded-full" x-text="tool"></span>
          </template>
          <template x-for="tag in (modal.value_tags || [])" :key="tag">
            <span class="bg-gray-800 text-gray-400 text-xs px-2 py-0.5 rounded-full" x-text="tag"></span>
          </template>
        </div>

        <template x-if="modal.transcription">
          <div class="mb-3">
            <div class="text-xs text-gray-500 font-semibold uppercase mb-1">Транскрипция</div>
            <div class="bg-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300 max-h-48 overflow-y-auto" x-text="modal.transcription"></div>
          </div>
        </template>

        <template x-if="modal.screen_text">
          <div class="mb-3">
            <div class="text-xs text-gray-500 font-semibold uppercase mb-1">Текст на экране</div>
            <div class="bg-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300 max-h-48 overflow-y-auto whitespace-pre-wrap" x-text="modal.screen_text"></div>
          </div>
        </template>
      </div>
    </template>
  </div>
</div>

<script>
const ANALYSIS_DATA = __ANALYSIS_DATA__;

function app() {
  return {
    tab: 'tools',
    tabs: [
      { id: 'tools', label: 'По инструментам' },
      { id: 'value',  label: 'По смыслу' },
    ],
    modal: null,

    init() {},

    get totalCount() {
      return ANALYSIS_DATA.records.length;
    },

    get toolsList() {
      const map = {};
      for (const r of ANALYSIS_DATA.records) {
        for (const tool of (r.tools || [])) {
          if (!tool) continue;
          if (!map[tool]) map[tool] = [];
          map[tool].push(r);
        }
      }
      return Object.entries(map)
        .sort((a, b) => b[1].length - a[1].length)
        .map(([name, videos]) => ({ name, videos, open: false }));
    },

    get valueCategories() {
      const byId = {};
      for (const r of ANALYSIS_DATA.records) byId[r.id] = r;
      return (ANALYSIS_DATA.categories || []).map(cat => ({
        ...cat,
        videos: (cat.ids || []).map(id => byId[id]).filter(Boolean),
      }));
    },

    openModal(vid) {
      this.modal = vid;
    },
  };
}
</script>
</body>
</html>
"""


def load_analysis(path: Path) -> list[dict]:
    if not path.exists():
        print(f'{path} not found. Run fetcher.py first.', file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding='utf-8'))


def parse_json_response(text: str) -> dict:
    start = text.find('{')
    end = text.rfind('}') + 1
    if start == -1:
        return {}
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return {}


def extract_tools_for_record(record: dict) -> dict:
    transcription = record.get('transcription', {}).get('text', '')[:1500]
    screen_text = record.get('screen_text', {}).get('combined', '')[:800]

    if not transcription and not screen_text:
        return {'tools': [], 'value_tags': [], 'insight': ''}

    prompt = EXTRACT_PROMPT.format(
        transcription=transcription or '(no audio)',
        screen_text=screen_text or '(no on-screen text)',
    )

    response = ask(prompt)
    result = parse_json_response(response)

    return {
        'tools': result.get('tools', []),
        'value_tags': result.get('value_tags', []),
        'insight': result.get('insight', ''),
    }


def categorize_by_value(enriched: list[dict]) -> list[dict]:
    data_for_prompt = [
        {'id': r['id'], 'insight': r.get('insight', ''), 'value_tags': r.get('value_tags', [])}
        for r in enriched
        if r.get('insight') or r.get('value_tags')
    ]

    if not data_for_prompt:
        return [{'name': 'Все видео', 'description': '', 'ids': [r['id'] for r in enriched]}]

    prompt = CATEGORIZE_PROMPT.format(
        data=json.dumps(data_for_prompt, ensure_ascii=False, indent=2)
    )

    response = ask(prompt)
    result = parse_json_response(response)

    return result.get(
        'categories',
        [{'name': 'Все видео', 'description': '', 'ids': [r['id'] for r in enriched]}]
    )


def build_html(records: list[dict], categories: list[dict]) -> str:
    data = {'records': records, 'categories': categories}
    data_js = json.dumps(data, ensure_ascii=False, indent=2)
    return HTML_TEMPLATE.replace('__ANALYSIS_DATA__', data_js)


def main():
    parser = argparse.ArgumentParser(description='Build HTML report from analysis.json')
    parser.add_argument('--input', metavar='FILE', default='data/analysis.json')
    parser.add_argument('--output', metavar='FILE', default='html/analysis.html')
    parser.add_argument('--no-llm', action='store_true',
                        help='Build report without LLM analysis (just raw data)')
    args = parser.parse_args()

    analysis_path = Path(args.input)
    records = load_analysis(analysis_path)

    if not records:
        print('No records to report.')
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    enriched = []

    if args.no_llm:
        for r in records:
            enriched.append({
                'id': r['id'],
                'tools': [],
                'value_tags': [],
                'insight': r.get('transcription', {}).get('text', '')[:120],
                'transcription': r.get('transcription', {}).get('text', ''),
                'screen_text': r.get('screen_text', {}).get('combined', ''),
            })
        categories = [{'name': 'Все видео', 'description': '', 'ids': [r['id'] for r in enriched]}]
    else:
        print(f'Extracting tools/insights from {len(records)} records...')
        for i, record in enumerate(records, 1):
            print(f'[{i}/{len(records)}] {record["id"]}')

            if record.get('error'):
                print('  has error, skipping')
                continue

            try:
                info = extract_tools_for_record(record)
            except RuntimeError as e:
                print(f'  error: {e}', file=sys.stderr)
                info = {'tools': [], 'value_tags': [], 'insight': ''}

            enriched.append({
                'id': record['id'],
                'tools': info['tools'],
                'value_tags': info['value_tags'],
                'insight': info['insight'],
                'transcription': record.get('transcription', {}).get('text', ''),
                'screen_text': record.get('screen_text', {}).get('combined', ''),
            })

            tools_preview = info['tools'][:3]
            insight_preview = info['insight'][:60]
            print(f'  tools: {tools_preview}  →  {insight_preview}')

        print('\nCategorizing by value...')
        try:
            categories = categorize_by_value(enriched)
        except RuntimeError as e:
            print(f'Categorization error: {e}', file=sys.stderr)
            categories = [{'name': 'Все видео', 'description': '', 'ids': [r['id'] for r in enriched]}]

    html = build_html(enriched, categories)
    output_path.write_text(html, encoding='utf-8')

    print(f'\nReport built: {output_path}')
    print(f'  {len(enriched)} videos, {len(categories)} categories')
    print('Open in browser to view')


if __name__ == '__main__':
    main()
