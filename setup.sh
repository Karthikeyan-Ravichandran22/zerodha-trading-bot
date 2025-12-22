#!/bin/bash
# Setup script for Zerodha Trading Bot

echo "🚀 Setting up Zerodha Trading Bot..."

# Check Python version
python3 --version || { echo "❌ Python 3 is required"; exit 1; }

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your Zerodha API credentials!"
fi

# Create directories
mkdir -p logs data

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env file with your Zerodha Kite Connect API credentials"
echo "      - Get API key from: https://kite.trade (₹2000/month)"
echo "   2. (Optional) Add Telegram bot token for notifications"
echo "   3. Run paper trading mode first:"
echo "      python paper_trade.py"
echo ""
echo "📊 Available commands:"
echo "   python paper_trade.py          # Paper trading (safe testing)"
echo "   python main.py --mode signal   # Signal only mode"
echo "   python main.py --mode semi-auto # Semi-automatic (confirms before trading)"
echo "   python main.py --mode auto     # Fully automatic (USE WITH CAUTION!)"
echo ""
echo "🧪 Run backtest:"
echo "   python -m backtest.backtester --strategy vwap_bounce --symbol TATAMOTORS --days 30"
echo ""
