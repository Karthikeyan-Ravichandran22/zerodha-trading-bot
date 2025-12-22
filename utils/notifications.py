"""
Notifications - Send alerts via Telegram
"""

import requests
from loguru import logger
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, NOTIFICATIONS_ENABLED


def send_telegram_message(message: str, parse_mode: str = "HTML") -> bool:
    """
    Send message via Telegram bot
    
    Args:
        message: Message to send (supports HTML formatting)
        parse_mode: HTML or Markdown
    
    Returns:
        True if sent successfully
    """
    if not NOTIFICATIONS_ENABLED:
        logger.debug(f"Notifications disabled. Message: {message}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": parse_mode
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.debug("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram API error: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_trade_alert(action: str, symbol: str, entry: float, sl: float, target: float, qty: int):
    """Send formatted trade alert"""
    emoji = "🟢" if action == "BUY" else "🔴"
    message = f"""
{emoji} <b>TRADE SIGNAL</b>

<b>Action:</b> {action}
<b>Symbol:</b> {symbol}
<b>Quantity:</b> {qty}

<b>Entry:</b> ₹{entry:,.2f}
<b>Stop Loss:</b> ₹{sl:,.2f}
<b>Target:</b> ₹{target:,.2f}

<b>Risk:</b> ₹{abs(entry - sl) * qty:,.2f}
<b>Reward:</b> ₹{abs(target - entry) * qty:,.2f}
"""
    return send_telegram_message(message)


def send_exit_alert(symbol: str, exit_price: float, pnl: float):
    """Send trade exit alert"""
    emoji = "💚" if pnl >= 0 else "💔"
    message = f"""
{emoji} <b>TRADE CLOSED</b>

<b>Symbol:</b> {symbol}
<b>Exit Price:</b> ₹{exit_price:,.2f}
<b>P&L:</b> ₹{pnl:,.2f}
"""
    return send_telegram_message(message)


def send_daily_summary(stats: dict):
    """Send end of day summary"""
    message = f"""
📊 <b>DAILY SUMMARY</b>

<b>Trades:</b> {stats.get('trades', 0)}
<b>Wins:</b> {stats.get('wins', 0)}
<b>Losses:</b> {stats.get('losses', 0)}
<b>Win Rate:</b> {stats.get('win_rate', 0):.1f}%

<b>Gross Profit:</b> ₹{stats.get('gross_profit', 0):,.2f}
<b>Gross Loss:</b> ₹{stats.get('gross_loss', 0):,.2f}
<b>Net P&L:</b> ₹{stats.get('net_pnl', 0):,.2f}
"""
    return send_telegram_message(message)
