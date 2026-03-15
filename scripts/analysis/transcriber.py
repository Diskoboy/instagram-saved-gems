"""
Transcribe audio from video posts using faster-whisper.
Saves results to data/posts/{id}/transcription.json. Incremental by default.

Транскрибирует аудио из видеопостов через faster-whisper.
Сохраняет результаты в data/posts/{id}/transcription.json. По умолчанию инкрементальный.

Usage:
  python scripts/analysis/transcriber.py
  python scripts/analysis/transcriber.py --model small --device cpu
  python scripts/analysis/transcriber.py --force --ids abc123 def456
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from store import all_post_ids, load_meta, load_transcription, save_transcription  # noqa: E402


def needs_transcription(pid: str) -> bool:
    return not load_transcription(pid).get('text')


def transcribe_file(model, video_path: Path, language: str | None) -> dict:
    kwargs: dict = {}
    if language:
        kwargs['language'] = language

    segments_iter, info = model.transcribe(str(video_path), beam_size=5, **kwargs)

    text_parts = []
    seg_list = []
    for seg in segments_iter:
        text_parts.append(seg.text.strip())
        seg_list.append({
            'start': round(seg.start, 2),
            'end': round(seg.end, 2),
            'text': seg.text.strip(),
        })

    return {
        'text': ' '.join(text_parts),
        'language': info.language,
        'segments': seg_list,
    }


def main():
    parser = argparse.ArgumentParser(description='Transcribe audio from videos using faster-whisper')
    parser.add_argument('--model', default='base',
                        choices=['tiny', 'base', 'small', 'medium', 'large-v3'],
                        help='Whisper model size (default: base)')
    parser.add_argument('--device', default='auto', choices=['auto', 'cpu', 'cuda'],
                        help='Compute device (default: auto)')
    parser.add_argument('--compute-type', default='int8',
                        choices=['float32', 'float16', 'int8'],
                        help='Compute type; int8 recommended for CPU (default: int8)')
    parser.add_argument('--language', default=None,
                        help='Force language code (e.g. ru, en). Default: autodetect')
    parser.add_argument('--force', action='store_true',
                        help='Re-transcribe already processed records')
    parser.add_argument('--ids', nargs='*', metavar='ID',
                        help='Process only these record IDs')
    args = parser.parse_args()

    id_filter = set(args.ids) if args.ids else None
    all_ids = all_post_ids()

    to_process = []
    for pid in all_ids:
        if id_filter and pid not in id_filter:
            continue
        meta = load_meta(pid)
        if not meta or meta.get('fetch_error'):
            continue
        mp4_files = [m for m in meta.get('media', []) if m.endswith('.mp4')]
        if not mp4_files:
            continue
        if not args.force and not needs_transcription(pid):
            continue
        to_process.append((pid, mp4_files[0]))

    if not to_process:
        print('Nothing to transcribe.')
        return

    print(f'Loading faster-whisper model: {args.model} ({args.device}/{args.compute_type})')
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print('faster-whisper not installed. Run: pip install faster-whisper', file=sys.stderr)
        sys.exit(1)

    device = args.device
    if device == 'auto':
        try:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        except ImportError:
            device = 'cpu'

    model = WhisperModel(args.model, device=device, compute_type=args.compute_type)
    print(f'Model loaded on {device}. Processing {len(to_process)} records...')

    done = 0
    for i, (pid, local_path) in enumerate(to_process, 1):
        print(f'[{i}/{len(to_process)}] {pid}')

        if not Path(local_path).exists():
            print('  no video file, skipping', file=sys.stderr)
            continue

        try:
            result = transcribe_file(model, Path(local_path), args.language)
            save_transcription(pid, result)
            preview = result['text'][:80]
            suffix = '...' if len(result['text']) > 80 else ''
            print(f'  [{result["language"]}] {preview}{suffix}')
            done += 1
        except Exception as e:
            print(f'  error: {e}', file=sys.stderr)

    print(f'\nDone. Transcribed: {done}/{len(to_process)}')


if __name__ == '__main__':
    main()
