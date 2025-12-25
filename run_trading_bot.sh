#!/bin/bash
# Trading Bot Launcher Script
# This script is designed to be called by macOS LaunchAgent

# Set the working directory
cd /Users/karthi-mac/Desktop/Work_Station/zeroda_trading

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Log the startup
echo "$(date): Starting Trading Bot..." >> logs/launchagent_stdout.log

# Activate virtual environment and run the bot
# Using bash -c to properly source the activate script
/bin/bash -c "source /Users/karthi-mac/Desktop/Work_Station/zeroda_trading/env/bin/activate && python /Users/karthi-mac/Desktop/Work_Station/zeroda_trading/cloud_bot.py"

# Log exit
echo "$(date): Trading Bot exited with code $?" >> logs/launchagent_stdout.log
