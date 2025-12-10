#!/bin/bash

# Quick Start Script for Jira Auto-Assignment Service
# This script sets up and runs the service for the first time

set -e  # Exit on error

echo "🚀 Jira Auto-Assignment Service - Quick Start"
echo "=============================================="
echo ""

# Check Python version
echo "📋 Checking Python version..."
python3 --version || {
    echo "❌ Python 3 is required but not installed."
    exit 1
}

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "🔧 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env with your Jira credentials:"
    echo "   - JIRA_BASE_URL"
    echo "   - JIRA_EMAIL"
    echo "   - JIRA_API_TOKEN"
    echo "   - TECHNICAL_OWNER_TEAM"
    echo ""
    read -p "Press Enter to continue after editing .env..."
else
    echo "✅ .env file already exists"
fi

# Verify dev_profiles.csv exists
if [ ! -f "dev_profiles.csv" ]; then
    echo "❌ dev_profiles.csv not found!"
    echo "Please ensure dev_profiles.csv is in the project root."
    exit 1
else
    echo "✅ dev_profiles.csv found"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Starting the service..."
echo "The service will be available at: http://localhost:8000"
echo ""
echo "Useful endpoints:"
echo "  - Health check: http://localhost:8000/health"
echo "  - Statistics:   http://localhost:8000/stats"
echo "  - API docs:     http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the service"
echo ""

# Run the service
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
