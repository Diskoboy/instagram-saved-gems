#!/usr/bin/env python3
"""
Instagram Save-Inst Pipeline

Usage:
  python run.py                          # full pipeline
  python run.py --only extract           # only parse HTML → links.json
  python run.py --only fetch             # only download media
  python run.py --only thumbnails        # only extract/download thumbnails
  python run.py --only categorize        # only categorize posts
  python run.py --only build             # only build HTML gallery
  python run.py --only obsidian          # only export to Obsidian
"""
import argparse
import platform
import subprocess
import sys
from pathlib import Path

_venv = Path('.venv')
PYTHON = str(_venv / ('Scripts/python.exe' if platform.system() == 'Windows' else 'bin/python'))
STEPS = {
    'extract': 'scripts/parser.py',
    'fetch': 'scripts/fetch.py',
    'thumbnails': 'scripts/thumbnailer.py',
    'categorize': 'scripts/categorizer.py',
    'build': 'scripts/builder.py',
    'obsidian': 'scripts/obsidian_export.py',
}


def run_step(name: str) -> bool:
    script = STEPS[name]
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
        choices=list(STEPS.keys()),
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
