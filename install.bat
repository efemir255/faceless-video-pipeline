@echo off
:: install.bat — One-click installer for Faceless Video Pipeline (Windows)

echo 🛠️  Installing Faceless Video Pipeline...

:: 1. Check for Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Git is not installed. Please install Git from https://git-scm.com/
    pause
    exit /b
)

:: 2. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b
)

:: 3. Create Virtual Environment
echo 📦 Creating virtual environment...
if not exist venv (
    python -m venv venv
)

:: 4. Install dependencies
echo 📥 Installing requirements...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

:: 5. Create Desktop Shortcut
echo 🖥️  Creating Desktop shortcut...
python create_shortcut.py

:: 6. Setup .env
if not exist .env (
    if exist .env.example (
        copy .env.example .env
        echo 📝 Created .env file.
    )
)

echo.
echo ✅ Installation Complete!
echo 🚀 You can now use the shortcut on your Desktop to launch the app.
echo.
pause
