#!/usr/bin/env bash
set -e

echo "=== Save-Inst Setup ==="

# Проверяем Python
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install Python 3.11+" >&2
    exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python $PYTHON_VER found"

# Создаём venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists, skipping"
fi

# Устанавливаем зависимости
echo "Installing dependencies..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet

# Копируем .env если его нет
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit it before running"
else
    echo ".env already exists"
fi

echo ""
echo "=== Done! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env (set FIREFOX_PROFILE to your Firefox profile path)"
echo "  2. Put saved_posts.html and saved_collections.html in this directory"
echo "  3. Run: python run.py"
echo ""
echo "For Instagram auth details, see README.md → 'Авторизация в Instagram'"
