@echo off

rem Check for virtual environment and activate if it exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment (.venv)...
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    echo Activating virtual environment (venv)...
    call venv\Scripts\activate.bat
)

rem Check if .env exists, if not copy from .env.example
if not exist .env (
    if exist .env.example (
        echo Creating .env from .env.example...
        copy .env.example .env
    ) else (
        echo Warning: .env.example not found. Please create a .env file with your API keys.
    )
)

rem Run the streamlit app
echo Starting Faceless Video Pipeline...
python -m streamlit run app.py
pause
