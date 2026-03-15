"""
OCR on-screen text extraction for all posts using LLM vision.
- image/carousel: reads jpg/png files directly
- reel/video: extracts frames via ffmpeg, then OCR

OCR для извлечения текста с экрана через LLM vision.
- image/carousel: читает jpg/png картинки напрямую
- reel/video: извлекает кадры через ffmpeg, затем OCR

Usage:
  python scripts/analysis/ocr.py
  python scripts/analysis/ocr.py --force
  python scripts/analysis/ocr.py --ids ID1 ID2
"""
import argparse
import base64
import json as _json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from llm import ask  # noqa: E402
from store import all_post_ids, load_meta, load_ocr, save_ocr  # noqa: E402

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
VIDEO_TYPES = {'reel', 'video'}
IMAGE_TYPES = {'image', 'carousel'}

OCR_PROMPT = (
    'Extract all text visible on screen in this image. '
    'Return ONLY the text you see, nothing else. '
    'If there is no text, return an empty string.'
)


def needs_ocr(pid: str) -> bool:
    return not load_ocr(pid).get('combined')


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode('ascii')


def clean_ocr_text(text: str) -> str:
    """Extract plain text from ollama response (handles JSON responses).
    Извлекает plain text из ответа ollama (обрабатывает JSON-ответы)."""
    text = text.strip()
    if not text.startswith('{') and not text.startswith('['):
        return text
    try:
        data = _json.loads(text)
        parts = []

        def extract(obj):
            if isinstance(obj, str) and obj.strip():
                parts.append(obj.strip())
            elif isinstance(obj, dict):
                for v in obj.values():
                    extract(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(data)
        return ' '.join(parts)
    except Exception:
        return text


def query_llm(base64_image: str) -> str:
    return clean_ocr_text(ask(OCR_PROMPT, image_b64=base64_image).strip())


def process_images(image_paths: list[Path]) -> dict:
    raw_frames = []
    for idx, img_path in enumerate(image_paths):
        if not img_path.exists():
            print(f'  image not found: {img_path}', file=sys.stderr)
            continue
        b64 = image_to_base64(img_path)
        try:
            text = query_llm(b64)
        except Exception as e:
            print(f'  image {idx} error: {e}', file=sys.stderr)
            text = ''
        raw_frames.append({'image_index': idx, 'path': str(img_path), 'text': text})

    combined = '\n\n'.join(f['text'] for f in raw_frames if f['text'].strip())
    return {'combined': combined, 'raw_frames': raw_frames}


def extract_video_frames(mp4_path: Path, max_frames: int = 2) -> tuple[list[Path], Path]:
    """Extract up to max_frames frames from video via ffmpeg. Returns (frames, tmp_dir)."""
    tmp_dir = Path(tempfile.mkdtemp())
    out_pattern = str(tmp_dir / 'frame_%03d.jpg')
    subprocess.run(
        ['ffmpeg', '-y', '-i', str(mp4_path),
         '-vf', f'fps=1,scale=640:-1', '-frames:v', str(max_frames),
         out_pattern],
        capture_output=True,
    )
    frames = sorted(tmp_dir.glob('frame_*.jpg'))
    return frames, tmp_dir


def main():
    parser = argparse.ArgumentParser(
        description='Extract on-screen text from images/video using LLM vision'
    )
    parser.add_argument('--force', action='store_true',
                        help='Re-process already processed records')
    parser.add_argument('--ids', nargs='*', metavar='ID',
                        help='Process only these record IDs')
    parser.add_argument('--video-frames', type=int, default=2, metavar='N',
                        help='Max frames to extract per video (default: 2)')
    args = parser.parse_args()

    id_filter = set(args.ids) if args.ids else None

    # Build processing queue: (pid, source, 'image'|'video')
    # Формируем очередь: (pid, источник, 'image'|'video')
    to_process = []
    for pid in all_post_ids():
        if id_filter and pid not in id_filter:
            continue
        meta = load_meta(pid)
        if not meta or meta.get('fetch_error'):
            continue
        post_type = meta.get('type', '')
        if not args.force and not needs_ocr(pid):
            continue

        if post_type in IMAGE_TYPES:
            image_files = [
                Path(m) for m in meta.get('media', [])
                if Path(m).suffix.lower() in IMAGE_EXTENSIONS
            ]
            if not image_files:
                continue
            to_process.append((pid, image_files, 'image'))

        elif post_type in VIDEO_TYPES:
            mp4_files = [
                Path(m) for m in meta.get('media', [])
                if Path(m).suffix.lower() == '.mp4' and Path(m).exists()
            ]
            if not mp4_files:
                continue
            to_process.append((pid, mp4_files[0], 'video'))

    if not to_process:
        print('Nothing to process.')
        return

    print(f'Processing {len(to_process)} records...')

    done = 0
    for i, (pid, source, kind) in enumerate(to_process, 1):
        tmp_dir = None
        try:
            if kind == 'image':
                print(f'[{i}/{len(to_process)}] {pid} ({len(source)} images)')
                result = process_images(source)
            else:
                print(f'[{i}/{len(to_process)}] {pid} (video → frames)')
                frames, tmp_dir = extract_video_frames(source, max_frames=args.video_frames)
                if not frames:
                    print(f'  no frames extracted', file=sys.stderr)
                    continue
                print(f'  extracted {len(frames)} frames')
                result = process_images(frames)

            save_ocr(pid, result)
            preview = result['combined'][:100].replace('\n', ' ')
            suffix = '...' if len(result['combined']) > 100 else ''
            print(f'  → "{preview}{suffix}"')
            done += 1
        except Exception as e:
            print(f'  error: {e}', file=sys.stderr)
        finally:
            if tmp_dir and tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f'\nDone. Processed: {done}/{len(to_process)}')


if __name__ == '__main__':
    main()
