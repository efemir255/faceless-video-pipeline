#!/bin/bash
# run.sh — One-click launch for Faceless Video Pipeline (Linux/macOS)

echo "🚀 Starting Faceless Video Pipeline..."

# 1. Ensure .env exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝 Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  Please edit .env and add your API keys!"
    else
        echo "❌ .env.example not found. Cannot create .env."
    fi
fi

# 2. Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# 3. Launch streamlit (it will automatically open the browser)
streamlit run app.py --server.headless false
