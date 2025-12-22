"""
Logger - Centralized logging configuration
"""

import sys
from pathlib import Path
from loguru import logger
from datetime import datetime

from config.settings import LOGS_DIR, LOG_LEVEL, LOG_TO_FILE, LOG_TO_CONSOLE


def setup_logger(name: str = "trading_bot"):
    """Configure logging for the application"""
    
    # Remove default handler
    logger.remove()
    
    # Console logging
    if LOG_TO_CONSOLE:
        logger.add(
            sys.stdout,
            level=LOG_LEVEL,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
            colorize=True
        )
    
    # File logging
    if LOG_TO_FILE:
        log_file = LOGS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        logger.add(
            log_file,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="1 day",
            retention="7 days",
            compression="zip"
        )
        
        # Separate file for trades only
        trade_log = LOGS_DIR / f"trades_{datetime.now().strftime('%Y%m%d')}.log"
        logger.add(
            trade_log,
            level="INFO",
            filter=lambda record: "TRADE" in record["message"],
            format="{time:YYYY-MM-DD HH:mm:ss} | {message}"
        )
    
    logger.info(f"Logger initialized: {name}")
    return logger


def log_trade(action: str, symbol: str, details: dict):
    """Log trade with structured format"""
    trade_msg = f"TRADE | {action} | {symbol} | "
    trade_msg += " | ".join([f"{k}={v}" for k, v in details.items()])
    logger.info(trade_msg)


def log_signal(strategy: str, symbol: str, signal_type: str, details: dict):
    """Log trading signal"""
    signal_msg = f"SIGNAL | {strategy} | {symbol} | {signal_type} | "
    signal_msg += " | ".join([f"{k}={v}" for k, v in details.items()])
    logger.info(signal_msg)
