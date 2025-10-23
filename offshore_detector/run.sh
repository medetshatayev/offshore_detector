#!/bin/bash
# Startup script for Offshore Transaction Risk Detection System

set -e

echo "========================================"
echo "Offshore Transaction Risk Detection"
echo "========================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it with your configuration."
        exit 1
    else
        echo "❌ Error: .env.example not found"
        exit 1
    fi
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Check for OpenAI API key
if ! grep -q "OPENAI_API_KEY=sk-" .env 2>/dev/null; then
    echo "⚠️  Warning: OPENAI_API_KEY not set in .env"
    echo "The application will not function without a valid API key."
fi

# Run the application
echo "🚀 Starting application..."
echo "========================================"
python main.py
