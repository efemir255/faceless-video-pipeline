#!/bin/bash

# Check for virtual environment and activate if it exists
if [ -d .venv ]; then
    echo "Activating virtual environment (.venv)..."
    source .venv/bin/activate
elif [ -d venv ]; then
    echo "Activating virtual environment (venv)..."
    source venv/bin/activate
fi

# Check if .env exists, if not copy from .env.example
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
    else
        echo "Warning: .env.example not found. Please create a .env file with your API keys."
    fi
fi

# Run the streamlit app
echo "Starting Faceless Video Pipeline..."
python -m streamlit run app.py
