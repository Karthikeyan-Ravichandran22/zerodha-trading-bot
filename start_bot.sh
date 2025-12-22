#!/bin/bash
# Launch Script for Zerodha Trading Bot
# Run this to start the auto-scheduled trading bot

cd "$(dirname "$0")"

echo "🤖 Zerodha Auto Trading Bot"
echo "============================"
echo ""
echo "Current Time: $(date '+%H:%M:%S')"
echo "Market Hours: 9:15 AM - 3:30 PM IST"
echo ""

# Check if virtual environment exists
if [ ! -d "env" ]; then
    echo "❌ Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Activate virtual environment
source env/bin/activate

echo "Select mode:"
echo "  1) Paper Trading (Safe - No real orders)"
echo "  2) Signal Mode (Alerts only, manual trading)"
echo "  3) Semi-Auto (Confirms before each trade)"
echo "  4) Full Auto (⚠️ USE WITH CAUTION!)"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        export TRADING_MODE=paper
        echo "📝 Starting in PAPER TRADING mode..."
        ;;
    2)
        export TRADING_MODE=signal
        echo "📢 Starting in SIGNAL mode..."
        ;;
    3)
        export TRADING_MODE=semi-auto
        echo "🔔 Starting in SEMI-AUTO mode..."
        ;;
    4)
        echo "⚠️ WARNING: Full Auto mode will place REAL orders!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            echo "Cancelled."
            exit 0
        fi
        export TRADING_MODE=auto
        echo "🤖 Starting in FULL AUTO mode..."
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Starting scheduled bot..."
echo "Press Ctrl+C to stop"
echo ""

python scheduled_bot.py
