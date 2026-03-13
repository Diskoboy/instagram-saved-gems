"""
Читает data/analysis.json, извлекает текст с экрана через ollama (vision).
Обновляет поле screen_text для каждой записи.

Usage:
  python scripts/analysis/ocr.py
  python scripts/analysis/ocr.py --model llava:7b --fps 1
  python scripts/analysis/ocr.py --ollama-url http://localhost:11434
"""
import argparse
import base64
import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DEFAULT_OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
DEFAULT_MODEL = os.environ.get('OLLAMA_MODEL', 'gemma3:4b')

OCR_PROMPT = (
    'Extract all text visible on screen in this image. '
    'Return ONLY the text you see, nothing else. '
    'If there is no text, return an empty string.'
)


def load_analysis(path: Path) -> list[dict]:
    if not path.exists():
        print(f'{path} not found. Run fetcher.py first.', file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding='utf-8'))


def save_analysis(data: list[dict], path: Path) -> None:
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def needs_ocr(record: dict) -> bool:
    if record.get('error'):
        return False
    st = record.get('screen_text', {})
    return not st.get('combined')


def _ffmpeg_bin() -> str:
    # 1. Явный путь через env
    ffmpeg_path = os.environ.get('FFMPEG_PATH', '')
    if ffmpeg_path:
        return ffmpeg_path
    # 2. Локальная папка bin/ в корне проекта (Windows: bin/ffmpeg.exe)
    local = ROOT / 'bin' / ('ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')
    if local.exists():
        return str(local)
    # 3. Системный PATH
    return 'ffmpeg'


def extract_frames(
    video_path: Path,
    tmp_dir: Path,
    fps: float,
    max_frames: int,
) -> list[tuple[float, Path]]:
    ffmpeg = _ffmpeg_bin()
    output_pattern = str(tmp_dir / 'frame_%04d.jpg')

    cmd = [
        ffmpeg, '-y',
        '-i', str(video_path),
        '-vf', f'fps={fps}',
        '-vframes', str(max_frames),
        '-q:v', '3',
        output_pattern,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg error: {result.stderr[-200:]}')

    frames = sorted(tmp_dir.glob('frame_*.jpg'))
    return [(i / fps, frame) for i, frame in enumerate(frames)]


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode('ascii')


def query_ollama(base64_image: str, model: str, ollama_url: str) -> str:
    payload = json.dumps({
        'model': model,
        'prompt': OCR_PROMPT,
        'images': [base64_image],
        'stream': False,
    }).encode('utf-8')

    req = urllib.request.Request(
        f'{ollama_url}/api/generate',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data.get('response', '').strip()
    except urllib.error.URLError as e:
        raise RuntimeError(f'ollama request failed: {e}')


def deduplicate_texts(texts: list[str]) -> list[str]:
    if not texts:
        return []
    result = [texts[0]]
    for text in texts[1:]:
        if text.strip() and text.strip() != result[-1].strip():
            result.append(text)
    return result


def process_video(
    record: dict,
    model: str,
    ollama_url: str,
    fps: float,
    max_frames: int,
    dedup: bool,
) -> dict:
    local_path = Path(record['local_path'])

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        frames = extract_frames(local_path, tmp_path, fps, max_frames)
        if not frames:
            return {'combined': '', 'raw_frames': []}

        raw_frames = []
        for timestamp, frame_path in frames:
            b64 = image_to_base64(frame_path)
            try:
                text = query_ollama(b64, model, ollama_url)
            except RuntimeError as e:
                print(f'  frame {timestamp:.1f}s error: {e}', file=sys.stderr)
                text = ''

            if text:
                raw_frames.append({'timestamp_sec': round(timestamp, 1), 'text': text})

        texts = [f['text'] for f in raw_frames]
        if dedup:
            texts = deduplicate_texts(texts)
        combined = '\n'.join(t for t in texts if t.strip())

        return {'combined': combined, 'raw_frames': raw_frames}


def check_ollama(ollama_url: str) -> bool:
    try:
        urllib.request.urlopen(f'{ollama_url}/api/tags', timeout=5)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Extract on-screen text from videos using ollama vision'
    )
    parser.add_argument('--input', metavar='FILE', default='data/analysis.json')
    parser.add_argument('--model', default=DEFAULT_MODEL,
                        help='Ollama vision model (default: gemma3:4b). '
                             'Must support vision: gemma3:4b, llava:7b, moondream. '
                             'Text-only models (gemma2, llama3) do NOT work.')
    parser.add_argument('--ollama-url', default=DEFAULT_OLLAMA_URL)
    parser.add_argument('--fps', type=float, default=0.5,
                        help='Frames per second to extract (default: 0.5 = 1 frame per 2s)')
    parser.add_argument('--max-frames', type=int, default=30,
                        help='Max frames per video (default: 30)')
    parser.add_argument('--force', action='store_true',
                        help='Re-process already processed records')
    parser.add_argument('--ids', nargs='*', metavar='ID',
                        help='Process only these record IDs')
    parser.add_argument('--no-dedup', action='store_true',
                        help='Disable text deduplication between frames')
    args = parser.parse_args()

    analysis_path = Path(args.input)
    records = load_analysis(analysis_path)

    id_filter = set(args.ids) if args.ids else None

    if args.force:
        for r in records:
            if id_filter is None or r['id'] in id_filter:
                r['screen_text'] = {'combined': '', 'raw_frames': []}

    to_process = [
        r for r in records
        if needs_ocr(r) and (id_filter is None or r['id'] in id_filter)
    ]

    if not to_process:
        print('Nothing to process.')
        return

    print(f'Checking ollama at {args.ollama_url}...')
    if not check_ollama(args.ollama_url):
        print(f'Error: ollama not reachable at {args.ollama_url}', file=sys.stderr)
        print('Install: https://ollama.com/download', file=sys.stderr)
        print(f'Then run: ollama pull {args.model}', file=sys.stderr)
        sys.exit(1)
    print('ollama OK')

    print(f'Model: {args.model}, fps: {args.fps}, max_frames: {args.max_frames}')
    print(f'Processing {len(to_process)} records...')

    for i, record in enumerate(to_process, 1):
        print(f'[{i}/{len(to_process)}] {record["id"]}')

        local_path = record.get('local_path')
        if not local_path or not Path(local_path).exists():
            print('  no video file, skipping', file=sys.stderr)
            continue

        try:
            st = process_video(
                record, args.model, args.ollama_url,
                args.fps, args.max_frames, not args.no_dedup,
            )
            record['screen_text'] = st
            preview = st['combined'][:100].replace('\n', ' ')
            suffix = '...' if len(st['combined']) > 100 else ''
            print(f'  {len(st["raw_frames"])} frames → "{preview}{suffix}"')
        except Exception as e:
            print(f'  error: {e}', file=sys.stderr)
            record['error'] = f'ocr error: {e}'

        save_analysis(records, analysis_path)

    ok = sum(1 for r in records if r.get('screen_text', {}).get('combined'))
    print(f'\nDone. Processed: {ok}/{len(records)}')


if __name__ == '__main__':
    main()
