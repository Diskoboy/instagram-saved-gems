"""
Download or copy videos from various sources → content_analysis/<id>/video.mp4
Writes base records to data/analysis.json for further processing.

Скачивает/копирует видео из различных источников → content_analysis/<id>/video.mp4
Пишет базовые записи в data/analysis.json для дальнейшей обработки.

Usage:
  python scripts/analysis/fetcher.py --urls-file urls.txt
  python scripts/analysis/fetcher.py --local-dir /path/to/videos
  python scripts/analysis/fetcher.py --from-posts data/posts.json
  python scripts/analysis/fetcher.py --local-files a.mp4 b.mp4
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
BROWSER = os.environ.get('BROWSER', 'firefox')
FIREFOX_PROFILE = os.environ.get('FIREFOX_PROFILE', str(Path.home() / 'snap/firefox/common/.mozilla/firefox'))
CHROME_PROFILE = os.environ.get('CHROME_PROFILE', '')


def _ytdlp_bin() -> str:
    venv = ROOT / '.venv'
    candidate = venv / ('Scripts/yt-dlp.exe' if platform.system() == 'Windows' else 'bin/yt-dlp')
    if candidate.exists():
        return str(candidate)
    return 'yt-dlp'


def _ffmpeg_bin() -> str:
    # 1. Explicit path via env / Явный путь через env
    ffmpeg_path = os.environ.get('FFMPEG_PATH', '')
    if ffmpeg_path:
        return ffmpeg_path
    # 2. Local bin/ folder in project root / Локальная папка bin/ в корне проекта
    local = ROOT / 'bin' / ('ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
    if local.exists():
        return str(local)
    # 3. System PATH / Системный PATH
    return 'ffmpeg'


def generate_id(input_str: str) -> str:
    return hashlib.sha256(input_str.encode()).hexdigest()[:12]


def load_analysis(path: Path) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return []


def save_analysis(data: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def collect_inputs(args: argparse.Namespace) -> list[dict]:
    items = []

    if args.urls_file:
        urls_file = Path(args.urls_file)
        if not urls_file.exists():
            print(f'Error: {urls_file} not found', file=sys.stderr)
        else:
            for line in urls_file.read_text(encoding='utf-8').splitlines():
                url = line.strip()
                if url and not url.startswith('#'):
                    items.append({'id': generate_id(url), 'source': 'url', 'input': url})

    if args.local_dir:
        d = Path(args.local_dir)
        for f in sorted(d.glob('**/*.mp4')):
            items.append({'id': f.stem, 'source': 'local', 'input': str(f.resolve())})

    if args.local_files:
        for f_str in args.local_files:
            f = Path(f_str)
            items.append({'id': f.stem, 'source': 'local', 'input': str(f.resolve())})

    if args.from_posts:
        posts_path = Path(args.from_posts)
        if not posts_path.exists():
            print(f'Error: {posts_path} not found', file=sys.stderr)
        else:
            posts = json.loads(posts_path.read_text(encoding='utf-8'))
            for p in posts:
                if p.get('fetch_error'):
                    continue
                ptype = p.get('type', '')
                media = p.get('media', [])
                has_video = any(str(m).endswith('.mp4') for m in media)
                if ptype in ('reel', 'video') or has_video:
                    items.append({'id': p['id'], 'source': 'posts_json', 'input': p['url']})

    # Deduplicate by ID, first occurrence wins / Дедупликация по ID, первое вхождение побеждает
    seen: dict[str, dict] = {}
    for item in items:
        if item['id'] not in seen:
            seen[item['id']] = item
    return list(seen.values())


def download_url(url: str, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ytdlp = _ytdlp_bin()

    cookie_args: list[str] = []
    if 'instagram.com' in url:
        profile = CHROME_PROFILE if BROWSER == 'chrome' else FIREFOX_PROFILE
        if profile:
            cookie_args = ['--cookies-from-browser', f'{BROWSER}:{profile}']

    cmd = [
        ytdlp,
        '--no-playlist',
        '--socket-timeout', '30',
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '--merge-output-format', 'mp4',
        '-o', str(out_dir / 'video.%(ext)s'),
        *cookie_args,
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    mp4s = list(out_dir.glob('video.mp4'))
    if mp4s:
        return mp4s[0]

    all_mp4s = list(out_dir.glob('*.mp4'))
    if all_mp4s:
        return all_mp4s[0]

    if result.returncode != 0:
        print(f'  yt-dlp error: {result.stderr[-300:]}', file=sys.stderr)
    return None


def copy_local(src: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / 'video.mp4'
    if not dest.exists():
        shutil.copy2(src, dest)
    return dest


def _empty_record(item: dict) -> dict:
    return {
        'id': item['id'],
        'source': item['source'],
        'input': item['input'],
        'local_path': None,
        'transcription': {'text': '', 'language': '', 'segments': []},
        'screen_text': {'combined': '', 'raw_frames': []},
        'error': None,
    }


def fetch_one(item: dict, content_dir: Path, force: bool) -> dict:
    record = _empty_record(item)
    out_dir = content_dir / item['id']

    if item['source'] == 'local':
        src = Path(item['input'])
        if not src.exists():
            record['error'] = f'File not found: {item["input"]}'
            return record
        local_path = copy_local(src, out_dir)
        record['local_path'] = str(local_path)
    else:
        existing_mp4 = out_dir / 'video.mp4'
        if existing_mp4.exists() and not force:
            record['local_path'] = str(existing_mp4)
            return record

        local_path = download_url(item['input'], out_dir)
        if local_path is None:
            record['error'] = 'Download failed'
        else:
            record['local_path'] = str(local_path)

    return record


def main():
    parser = argparse.ArgumentParser(description='Fetch videos for analysis')
    parser.add_argument('--urls-file', metavar='FILE', help='Text file with URLs (one per line)')
    parser.add_argument('--local-dir', metavar='DIR', help='Directory with mp4 files')
    parser.add_argument('--local-files', metavar='FILE', nargs='+', help='Specific mp4 files')
    parser.add_argument('--from-posts', metavar='FILE', help='data/posts.json (video posts only)')
    parser.add_argument('--output', metavar='FILE', default='data/analysis.json')
    parser.add_argument('--content-dir', metavar='DIR', default='content_analysis')
    parser.add_argument('--force', action='store_true', help='Re-download even if already present')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    args = parser.parse_args()

    if not any([args.urls_file, args.local_dir, args.local_files, args.from_posts]):
        parser.print_help()
        sys.exit(1)

    analysis_path = Path(args.output)
    content_dir = Path(args.content_dir)

    existing_data = load_analysis(analysis_path)
    existing = {r['id']: r for r in existing_data}

    inputs = collect_inputs(args)
    print(f'Found {len(inputs)} inputs')

    if args.dry_run:
        for item in inputs:
            status = 'existing' if item['id'] in existing else 'new'
            print(f'  [{status}] {item["id"]} {item["input"][:80]}')
        return

    results: list[dict] = []
    for i, item in enumerate(inputs, 1):
        print(f'[{i}/{len(inputs)}] {item["id"]}')

        if item['id'] in existing and not args.force:
            prev = existing[item['id']]
            if not prev.get('error'):
                print('  already fetched, skipping')
                results.append(prev)
                continue
            print('  previous error, retrying...')

        record = fetch_one(item, content_dir, args.force)
        if record['error']:
            print(f'  error: {record["error"]}', file=sys.stderr)
        else:
            print(f'  ok: {record["local_path"]}')

        results.append(record)
        save_analysis(results, analysis_path)

    ok = sum(1 for r in results if not r.get('error'))
    err = sum(1 for r in results if r.get('error'))
    print(f'\nDone. {ok} OK, {err} errors → {analysis_path}')


if __name__ == '__main__':
    main()
