#!/usr/bin/env python3
"""
Video Analysis Pipeline

Usage:
  python run_analysis.py                              # full pipeline
  python run_analysis.py --from-posts data/posts.json
  python run_analysis.py --urls-file urls.txt
  python run_analysis.py --local-dir /path/to/videos
  python run_analysis.py --only transcribe            # only transcribe
  python run_analysis.py --skip ocr                   # skip OCR step
  python run_analysis.py --only report --no-llm       # just build report
"""
import argparse
import platform
import subprocess
import sys
from pathlib import Path

_venv = Path('.venv')
PYTHON = str(_venv / ('Scripts/python.exe' if platform.system() == 'Windows' else 'bin/python'))

STEPS = {
    'fetch':      'scripts/analysis/fetcher.py',
    'transcribe': 'scripts/analysis/transcriber.py',
    'ocr':        'scripts/analysis/ocr.py',
    'report':     'scripts/analysis/reporter.py',
}


def run_step(name: str, extra_args: list[str]) -> bool:
    script = STEPS[name]
    print(f'\n{"=" * 50}')
    print(f'  Step: {name}  ({script})')
    print(f'{"=" * 50}')
    result = subprocess.run([PYTHON, script] + extra_args)
    if result.returncode != 0:
        print(f'\nStep "{name}" failed with exit code {result.returncode}', file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='Video Analysis Pipeline')
    parser.add_argument('--only', choices=list(STEPS.keys()),
                        help='Run only this step')
    parser.add_argument('--skip', choices=list(STEPS.keys()), nargs='+',
                        help='Skip these steps')
    parser.add_argument('--force', action='store_true',
                        help='Force re-processing (passed to all steps)')

    # fetch args
    parser.add_argument('--from-posts', metavar='FILE',
                        help='data/posts.json as video source')
    parser.add_argument('--urls-file', metavar='FILE',
                        help='Text file with URLs (one per line)')
    parser.add_argument('--local-dir', metavar='DIR',
                        help='Directory with mp4 files')

    # transcribe args
    parser.add_argument('--model-whisper', metavar='SIZE', default='base',
                        choices=['tiny', 'base', 'small', 'medium', 'large-v3'],
                        help='Whisper model size (default: base)')

    # ocr/report args
    parser.add_argument('--model-ollama', metavar='MODEL', default=None,
                        help='Ollama model (default: from OLLAMA_MODEL env or gemma3:4b)')
    parser.add_argument('--ollama-url', metavar='URL', default=None,
                        help='Ollama base URL (default: from OLLAMA_URL env or http://localhost:11434)')

    # report args
    parser.add_argument('--no-llm', action='store_true',
                        help='Build report without LLM analysis (passed to report step)')

    args = parser.parse_args()

    skip = set(args.skip or [])
    if args.only:
        steps = [args.only]
    else:
        steps = [s for s in STEPS if s not in skip]

    # Build per-step args
    fetch_args: list[str] = []
    if args.from_posts:
        fetch_args += ['--from-posts', args.from_posts]
    if args.urls_file:
        fetch_args += ['--urls-file', args.urls_file]
    if args.local_dir:
        fetch_args += ['--local-dir', args.local_dir]
    if args.force:
        fetch_args += ['--force']

    transcribe_args: list[str] = ['--model', args.model_whisper]
    if args.force:
        transcribe_args += ['--force']

    ocr_args: list[str] = []
    if args.model_ollama:
        ocr_args += ['--model', args.model_ollama]
    if args.ollama_url:
        ocr_args += ['--ollama-url', args.ollama_url]
    if args.force:
        ocr_args += ['--force']

    report_args: list[str] = []
    if args.model_ollama:
        report_args += ['--model', args.model_ollama]
    if args.ollama_url:
        report_args += ['--ollama-url', args.ollama_url]
    if args.no_llm:
        report_args += ['--no-llm']

    step_args: dict[str, list[str]] = {
        'fetch':      fetch_args,
        'transcribe': transcribe_args,
        'ocr':        ocr_args,
        'report':     report_args,
    }

    for step in steps:
        if not run_step(step, step_args.get(step, [])):
            sys.exit(1)

    print('\nPipeline complete!')
    if 'report' in steps:
        print('  → Open html/analysis.html in your browser')


if __name__ == '__main__':
    main()
