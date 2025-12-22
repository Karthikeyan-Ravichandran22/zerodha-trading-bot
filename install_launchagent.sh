#!/bin/bash
# Install/Uninstall LaunchAgent for Zerodha Trading Bot
# This makes the bot auto-start at 9:00 AM on weekdays

PLIST_NAME="com.zerodha.tradingbot.plist"
SOURCE_PLIST="$(dirname "$0")/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"

echo "🤖 Zerodha Trading Bot - LaunchAgent Setup"
echo "==========================================="
echo ""

case "$1" in
    install)
        echo "📦 Installing LaunchAgent..."
        
        # Create LaunchAgents directory if it doesn't exist
        mkdir -p "$TARGET_DIR"
        
        # Copy plist to LaunchAgents
        cp "$SOURCE_PLIST" "$TARGET_PLIST"
        
        # Set permissions
        chmod 644 "$TARGET_PLIST"
        
        # Load the LaunchAgent
        launchctl load "$TARGET_PLIST"
        
        echo ""
        echo "✅ LaunchAgent installed successfully!"
        echo ""
        echo "📅 Schedule:"
        echo "   • Runs at 9:00 AM every weekday (Mon-Fri)"
        echo "   • Logs saved to: logs/launchagent_*.log"
        echo ""
        echo "📝 Default mode: PAPER TRADING (safe)"
        echo ""
        echo "Commands:"
        echo "   Check status: launchctl list | grep zerodha"
        echo "   View logs:    tail -f logs/launchagent_stdout.log"
        echo "   Uninstall:    ./install_launchagent.sh uninstall"
        ;;
        
    uninstall)
        echo "🗑️ Uninstalling LaunchAgent..."
        
        # Unload the LaunchAgent
        launchctl unload "$TARGET_PLIST" 2>/dev/null
        
        # Remove plist
        rm -f "$TARGET_PLIST"
        
        echo "✅ LaunchAgent uninstalled successfully!"
        ;;
        
    status)
        echo "📊 LaunchAgent Status:"
        echo ""
        if launchctl list | grep -q "zerodha"; then
            echo "✅ LaunchAgent is LOADED"
            launchctl list | grep zerodha
        else
            echo "❌ LaunchAgent is NOT loaded"
        fi
        ;;
        
    start)
        echo "▶️ Starting bot now..."
        launchctl start com.zerodha.tradingbot
        echo "✅ Started. Check logs: tail -f logs/launchagent_stdout.log"
        ;;
        
    stop)
        echo "⏹️ Stopping bot..."
        launchctl stop com.zerodha.tradingbot
        echo "✅ Stopped"
        ;;
        
    *)
        echo "Usage: $0 {install|uninstall|status|start|stop}"
        echo ""
        echo "Commands:"
        echo "  install   - Install LaunchAgent (auto-start at 9 AM)"
        echo "  uninstall - Remove LaunchAgent"
        echo "  status    - Check if LaunchAgent is loaded"
        echo "  start     - Manually start the bot now"
        echo "  stop      - Stop the running bot"
        exit 1
        ;;
esac
