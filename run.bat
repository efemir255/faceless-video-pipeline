@echo off
:: run.bat — One-click launch for Faceless Video Pipeline (Windows)

echo 🚀 Starting Faceless Video Pipeline...

:: 1. Ensure .env exists
if not exist .env (
    if exist .env.example (
        echo 📝 Creating .env from .env.example...
        copy .env.example .env
        echo ⚠️  Please edit .env and add your API keys!
    ) else (
        echo ❌ .env.example not found. Cannot create .env.
    )
)

:: 2. Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

:: 3. Launch streamlit (it will automatically open the browser)
streamlit run app.py --server.headless false

pause
