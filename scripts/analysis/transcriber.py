"""
Читает data/analysis.json, транскрибирует аудио через faster-whisper.
Обновляет поле transcription для каждой записи.

Usage:
  python scripts/analysis/transcriber.py
  python scripts/analysis/transcriber.py --model small --device cpu
  python scripts/analysis/transcriber.py --force --ids abc123 def456
"""
import argparse
import json
import sys
from pathlib import Path


def load_analysis(path: Path) -> list[dict]:
    if not path.exists():
        print(f'{path} not found. Run fetcher.py first.', file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding='utf-8'))


def save_analysis(data: list[dict], path: Path) -> None:
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def needs_transcription(record: dict) -> bool:
    if record.get('error'):
        return False
    t = record.get('transcription', {})
    return not t.get('text')


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
    parser.add_argument('--input', metavar='FILE', default='data/analysis.json')
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

    analysis_path = Path(args.input)
    records = load_analysis(analysis_path)

    id_filter = set(args.ids) if args.ids else None

    if args.force:
        for r in records:
            if id_filter is None or r['id'] in id_filter:
                r['transcription'] = {'text': '', 'language': '', 'segments': []}

    to_process = [
        r for r in records
        if needs_transcription(r) and (id_filter is None or r['id'] in id_filter)
    ]

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

    for i, record in enumerate(to_process, 1):
        print(f'[{i}/{len(to_process)}] {record["id"]}')

        local_path = record.get('local_path')
        if not local_path or not Path(local_path).exists():
            print('  no video file, skipping', file=sys.stderr)
            continue

        try:
            result = transcribe_file(model, Path(local_path), args.language)
            record['transcription'] = result
            preview = result['text'][:80]
            suffix = '...' if len(result['text']) > 80 else ''
            print(f'  [{result["language"]}] {preview}{suffix}')
        except Exception as e:
            print(f'  error: {e}', file=sys.stderr)
            record['error'] = f'transcription error: {e}'

        save_analysis(records, analysis_path)

    ok = sum(1 for r in records if r.get('transcription', {}).get('text'))
    print(f'\nDone. Transcribed: {ok}/{len(records)}')


if __name__ == '__main__':
    main()
