#!/usr/bin/env python3
"""
Instagram Saved Gems Pipeline

Usage:
  python run.py                          # full pipeline
  python scripts/parser.py --txt inst.txt  # из текстового файла
  python run.py --only extract           # only parse HTML → links.json
  python run.py --only fetch             # only download media
  python run.py --only thumbnails        # only extract/download thumbnails
  python run.py --only transcribe        # only transcribe audio (Whisper)
  python run.py --only ocr              # only OCR image/carousel posts
  python run.py --only enrich            # only AI-enrich posts (needs LLM_PROVIDER)
  python run.py --only build             # only build HTML gallery
  python run.py --only obsidian          # only export to Obsidian
  python run.py --only export            # only flat-copy media to tmp/media/
"""
import argparse
import platform
import subprocess
import sys
from pathlib import Path

_venv = Path('.venv')
PYTHON = str(_venv / ('Scripts/python.exe' if platform.system() == 'Windows' else 'bin/python'))
STEPS = {
    'extract':    'scripts/parser.py',
    'fetch':      'scripts/fetch.py',
    'thumbnails': 'scripts/thumbnailer.py',
    'transcribe': 'scripts/analysis/transcriber.py',
    'ocr':        'scripts/analysis/ocr.py',
    'enrich':     'scripts/enricher.py',
    'build':      'scripts/builder.py',
    'obsidian':   'scripts/obsidian_export.py',
}
EXTRAS = {
    'export': 'scripts/export_flat.py',
}


def run_step(name: str) -> bool:
    script = STEPS.get(name) or EXTRAS[name]
    print(f'\n{"="*50}')
    print(f'  Step: {name}  ({script})')
    print(f'{"="*50}')
    result = subprocess.run([PYTHON, script])
    if result.returncode != 0:
        print(f'\nStep "{name}" failed with exit code {result.returncode}', file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='Instagram Save-Inst Pipeline')
    parser.add_argument(
        '--only',
        choices=list(STEPS.keys()) + list(EXTRAS.keys()),
        help='Run only this step',
    )
    args = parser.parse_args()

    if args.only:
        steps = [args.only]
    else:
        steps = list(STEPS.keys())

    for step in steps:
        if not run_step(step):
            sys.exit(1)

    print('\nPipeline complete!')
    if 'build' in steps:
        print('  → Open html/index.html in your browser')
    if 'obsidian' in steps:
        print('  → Notes exported to obsidian/')


if __name__ == '__main__':
    main()
