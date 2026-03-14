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
from pathlib import Path



ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from llm import ask  # noqa: E402
from store import all_post_ids, load_meta, load_ocr, save_ocr  # noqa: E402

DEFAULT_OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
DEFAULT_MODEL = os.environ.get('OLLAMA_MODEL', 'gemma3:4b')

OCR_PROMPT = (
    'Extract all text visible on screen in this image. '
    'Return ONLY the text you see, nothing else. '
    'If there is no text, return an empty string.'
)


def needs_ocr(pid: str) -> bool:
    return not load_ocr(pid).get('combined')


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


def query_llm(base64_image: str) -> str:
    return ask(OCR_PROMPT, image_b64=base64_image).strip()


def deduplicate_texts(texts: list[str]) -> list[str]:
    if not texts:
        return []
    result = [texts[0]]
    for text in texts[1:]:
        if text.strip() and text.strip() != result[-1].strip():
            result.append(text)
    return result


def process_video(
    local_path: Path,
    fps: float,
    max_frames: int,
    dedup: bool,
) -> dict:

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        frames = extract_frames(local_path, tmp_path, fps, max_frames)
        if not frames:
            return {'combined': '', 'raw_frames': []}

        raw_frames = []
        for timestamp, frame_path in frames:
            b64 = image_to_base64(frame_path)
            try:
                text = query_llm(b64)
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


def main():
    parser = argparse.ArgumentParser(
        description='Extract on-screen text from videos using LLM vision'
    )
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

    id_filter = set(args.ids) if args.ids else None

    to_process = []
    for pid in all_post_ids():
        if id_filter and pid not in id_filter:
            continue
        meta = load_meta(pid)
        if not meta or meta.get('fetch_error'):
            continue
        mp4_files = [m for m in meta.get('media', []) if m.endswith('.mp4')]
        if not mp4_files:
            continue
        if not args.force and not needs_ocr(pid):
            continue
        to_process.append((pid, mp4_files[0]))

    if not to_process:
        print('Nothing to process.')
        return

    print(f'fps: {args.fps}, max_frames: {args.max_frames}')
    print(f'Processing {len(to_process)} records...')

    done = 0
    for i, (pid, local_path_str) in enumerate(to_process, 1):
        print(f'[{i}/{len(to_process)}] {pid}')

        local_path = Path(local_path_str)
        if not local_path.exists():
            print('  no video file, skipping', file=sys.stderr)
            continue

        try:
            st = process_video(
                local_path,
                args.fps, args.max_frames, not args.no_dedup,
            )
            save_ocr(pid, st)
            preview = st['combined'][:100].replace('\n', ' ')
            suffix = '...' if len(st['combined']) > 100 else ''
            print(f'  {len(st["raw_frames"])} frames → "{preview}{suffix}"')
            done += 1
        except Exception as e:
            print(f'  error: {e}', file=sys.stderr)

    print(f'\nDone. Processed: {done}/{len(to_process)}')


if __name__ == '__main__':
    main()
