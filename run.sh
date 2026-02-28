#!/bin/bash

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
