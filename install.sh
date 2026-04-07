#!/bin/bash
# NPC Dialogue System - Quick Install Script
# Run this to set up everything automatically

set -e

echo "🎮 Installing NPC Dialogue System..."
echo "================================"
echo ""

# Check Python
echo "📦 Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✅ Python $PYTHON_VERSION found"
else
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi

echo ""

# Install pip dependencies
echo "📥 Installing Python dependencies..."
if pip3 install requests 2>/dev/null; then
    echo "✅ Dependencies installed"
elif pip3 install --user requests 2>/dev/null; then
    echo "✅ Dependencies installed to user directory"
else
    echo "⚠️  Could not install dependencies automatically"
    echo "📝 Try: pip3 install requests"
    echo "   Or: pip3 install --user requests"
fi
echo ""

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x main.py
chmod +x setup_check.py
chmod +x test_structure.py
echo "✅ Scripts executable"
echo ""

# Check if Ollama is installed
echo "🔍 Checking Ollama..."
if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>&1)
    echo "✅ Ollama installed: $OLLAMA_VERSION"
else
    echo "⚠️  Ollama not found"
    echo ""
    echo "📝 To install Ollama, run:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
fi

echo ""
echo "================================"
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Install Ollama (if not already):"
echo "      curl -fsSL https://ollama.com/install.sh | sh"
echo ""
echo "   2. Start Ollama:"
echo "      ollama serve"
echo ""
echo "   3. Pull a model (in a new terminal):"
echo "      ollama pull llama3.2:1b      # For 8GB RAM"
echo "      ollama pull llama3.2:3b      # For 16GB RAM"
echo ""
echo "   4. Run the demo:"
echo "      cd ~/npc-dialogue-system"
echo "      python3 main.py"
echo ""
echo "================================"
echo ""
echo "📚 Documentation:"
echo "   - QUICKSTART.md: 5-minute setup guide"
echo "   - README.md: Full documentation"
echo "   - PROJECT_SUMMARY.md: Overview & roadmap"
echo ""
echo "🎮 Happy game building!"
