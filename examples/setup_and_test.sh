#!/bin/bash
# Quick setup & test Fish-Speech + E2E Pipeline
# Usage: bash examples/setup_and_test.sh

set -e  # Exit on error

echo "🚀 Assistant E2E Pipeline - Setup & Test"
echo "========================================"

# 1. Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Docker found"

# 2. Start Fish-Speech if not running
echo ""
echo "🐟 Checking Fish-Speech..."

if docker ps | grep -q fish-speech; then
    echo "✅ Fish-Speech container already running"
else
    echo "⏳ Starting Fish-Speech container..."
    docker pull fish-audio/fish-speech:latest
    docker run -d \
      --name fish-speech \
      -p 8000:8000 \
      -v fish-speech-models:/app/models \
      --restart unless-stopped \
      fish-audio/fish-speech:latest 2>/dev/null || true
    
    echo "⏳ Waiting for Fish-Speech to be healthy..."
    sleep 10
fi

# 3. Health check Fish-Speech
echo ""
echo "🏥 Health check Fish-Speech..."
if curl -s http://localhost:8000/health | grep -q "ok\|OK\|200"; then
    echo "✅ Fish-Speech is healthy"
else
    echo "⚠️  Fish-Speech may not be ready yet (give it 30 seconds...)"
    sleep 20
fi

# 4. Load environment
echo ""
echo "📋 Loading environment..."
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ .env loaded"
else
    echo "⚠️  .env not found. Using defaults"
fi

# 5. Run E2E pipeline test
echo ""
echo "🌊 Running E2E Pipeline Test..."
echo "========================================"

python examples/test_e2e_pipeline.py

echo ""
echo "✨ Test complete!"
echo "========================================"
echo ""
echo "📊 Next steps:"
echo "   1. Check results above"
echo "   2. Run demo: python examples/demo_conversation.py"
echo "   3. Interactive: python examples/test_voice.py"
echo ""
echo "🧊 Stop Fish-Speech:"
echo "   docker stop fish-speech && docker rm fish-speech"
