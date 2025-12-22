"""
AUTO-SCHEDULED TRADING BOT
Automatically runs at market open (9:15 AM) every trading day

Features:
- Starts at 9:15 AM IST automatically
- Runs Multi-Confirmation Strategy
- Sends Telegram alerts (if configured)
- Auto square-off at 3:10 PM
- Logs all trades

Run this script and leave it running:
    python scheduled_bot.py
"""

import time
import schedule
from datetime import datetime, date, timedelta
from typing import Optional, List
import threading
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from core.zerodha_client import get_zerodha_client
from core.risk_manager import get_risk_manager, RiskManager
from core.data_fetcher import DataFetcher
from core.order_manager import OrderManager, OrderSide
from strategies.multi_confirmation import MultiConfirmationScalper
from utils.notifications import send_telegram_message, send_trade_alert
from config.settings import (
    TRADING_MODE, STOCK_WATCHLIST, TRADING_CAPITAL,
    NOTIFICATIONS_ENABLED
)

console = Console()


class ScheduledTradingBot:
    """
    Auto-scheduled trading bot that runs at market hours
    """
    
    def __init__(self):
        self.capital = TRADING_CAPITAL
        self.risk_manager = get_risk_manager()
        self.data_fetcher = DataFetcher()
        self.order_manager = OrderManager()
        self.strategy = MultiConfirmationScalper(
            data_fetcher=self.data_fetcher,
            risk_manager=self.risk_manager
        )
        self.client = None
        
        # Trading state
        self.is_trading_active = False
        self.today_trades = []
        self.today_pnl = 0.0
        
        # Market hours (IST)
        self.market_open = "09:15"
        self.first_trade_time = "09:30"  # After first 15 mins
        self.last_trade_time = "14:30"   # No new trades after this
        self.square_off_time = "15:10"   # Close all positions
        self.market_close = "15:30"
        
        # Trading parameters
        self.scan_interval_minutes = 5
        self.max_trades_per_day = 5
        self.max_daily_loss = 300  # ₹300
        
        logger.add("logs/scheduled_bot_{time}.log", rotation="1 day")
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # Check if weekend
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Check if within market hours
        return self.market_open <= current_time <= self.market_close
    
    def is_trading_time(self) -> bool:
        """Check if it's time to take new trades"""
        current_time = datetime.now().strftime("%H:%M")
        return self.first_trade_time <= current_time <= self.last_trade_time
    
    def connect_zerodha(self) -> bool:
        """Connect to Zerodha"""
        if TRADING_MODE == "paper":
            logger.info("📝 Paper trading mode - no Zerodha connection needed")
            return True
        
        self.client = get_zerodha_client()
        if not self.client.initialize():
            return False
        
        # Try to use saved access token
        if self.client.authenticate():
            return True
        
        logger.error("❌ Zerodha authentication failed. Run main.py to authenticate.")
        return False
    
    def on_market_open(self):
        """Called when market opens at 9:15 AM"""
        logger.info("="*60)
        logger.info("🔔 MARKET OPEN - 9:15 AM")
        logger.info("="*60)
        
        self.is_trading_active = True
        self.today_trades = []
        self.today_pnl = 0.0
        
        # Reset risk manager for new day
        self.risk_manager = RiskManager(self.capital)
        
        # Send notification
        send_telegram_message("🔔 Market Open! Trading bot is active.")
        
        console.print(Panel.fit(
            f"[bold green]🔔 MARKET OPEN[/bold green]\n\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}\n"
            f"Capital: ₹{self.capital:,.2f}\n"
            f"Mode: {TRADING_MODE.upper()}\n"
            f"Max Trades: {self.max_trades_per_day}"
        ))
    
    def on_trading_start(self):
        """Called at 9:30 AM - start scanning for trades"""
        logger.info("🚀 Trading window open - Starting to scan for signals")
        send_telegram_message("🚀 Trading started! Scanning for high-probability setups...")
    
    def scan_and_trade(self):
        """Main scanning and trading logic"""
        if not self.is_trading_active:
            return
        
        if not self.is_trading_time():
            logger.debug("Outside trading hours, skipping scan")
            return
        
        # Check daily limits
        can_trade, reason = self.risk_manager.can_take_trade()
        if not can_trade:
            logger.warning(f"Cannot trade: {reason}")
            return
        
        if len(self.today_trades) >= self.max_trades_per_day:
            logger.info(f"Max trades ({self.max_trades_per_day}) reached for today")
            return
        
        if self.today_pnl <= -self.max_daily_loss:
            logger.warning(f"Daily loss limit hit: ₹{self.today_pnl:.2f}")
            return
        
        # Scan stocks
        logger.info(f"🔍 Scanning {len(STOCK_WATCHLIST)} stocks...")
        
        for symbol in STOCK_WATCHLIST:
            try:
                data = self.data_fetcher.get_ohlc_data(symbol, "5minute", 5)
                if data is None or len(data) < 30:
                    continue
                
                data = self.strategy.calculate_indicators(data)
                signal = self.strategy.analyze(symbol, data)
                
                if signal:
                    self.execute_signal(signal)
                    break  # One trade at a time
                    
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
    
    def execute_signal(self, signal):
        """Execute a trade signal"""
        logger.info(f"📢 SIGNAL: {signal.signal.value} {signal.symbol}")
        logger.info(f"   Entry: ₹{signal.entry_price} | SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        logger.info(f"   Quantity: {signal.quantity} | Confidence: {signal.confidence:.0f}%")
        
        # Send alert
        send_trade_alert(
            action=signal.signal.value,
            symbol=signal.symbol,
            entry=signal.entry_price,
            sl=signal.stop_loss,
            target=signal.target,
            qty=signal.quantity
        )
        
        if TRADING_MODE == "paper":
            logger.info("📝 [PAPER MODE] Trade logged, not executed")
            self.today_trades.append({
                "symbol": signal.symbol,
                "signal": signal.signal.value,
                "entry": signal.entry_price,
                "time": datetime.now().strftime("%H:%M:%S")
            })
            return
        
        if TRADING_MODE == "signal":
            logger.info("📢 [SIGNAL MODE] Alert sent, manual execution required")
            return
        
        # Auto/Semi-auto mode - place actual order
        if self.client and self.client.is_connected:
            side = OrderSide.BUY if signal.signal.value == "BUY" else OrderSide.SELL
            order = self.order_manager.place_bracket_order(
                symbol=signal.symbol,
                side=side,
                quantity=signal.quantity,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                target=signal.target,
                strategy="MultiConfirmation"
            )
            
            if order:
                self.today_trades.append({
                    "symbol": signal.symbol,
                    "order_id": order.order_id,
                    "signal": signal.signal.value,
                    "entry": signal.entry_price,
                    "time": datetime.now().strftime("%H:%M:%S")
                })
                self.risk_manager.record_trade_entry()
    
    def on_square_off(self):
        """Called at 3:10 PM - close all positions"""
        logger.info("🔔 SQUARE OFF TIME - Closing all positions")
        
        self.order_manager.square_off_all()
        
        # Send summary
        summary = (
            f"📊 Day Summary:\n"
            f"Trades: {len(self.today_trades)}\n"
            f"P&L: ₹{self.today_pnl:+,.2f}"
        )
        send_telegram_message(summary)
        
        console.print(Panel.fit(
            f"[bold yellow]🔔 SQUARE OFF[/bold yellow]\n\n"
            f"Trades Today: {len(self.today_trades)}\n"
            f"Net P&L: ₹{self.today_pnl:+,.2f}"
        ))
    
    def on_market_close(self):
        """Called at 3:30 PM - market closed"""
        logger.info("="*60)
        logger.info("🔒 MARKET CLOSED - 3:30 PM")
        logger.info("="*60)
        
        self.is_trading_active = False
        
        # Print day summary
        self.print_day_summary()
        
        send_telegram_message("🔒 Market closed. See you tomorrow!")
    
    def print_day_summary(self):
        """Print end of day summary"""
        console.print("\n" + "="*60)
        console.print("[bold cyan]📊 END OF DAY SUMMARY[/bold cyan]")
        console.print("="*60)
        console.print(f"Date: {date.today().strftime('%Y-%m-%d')}")
        console.print(f"Total Trades: {len(self.today_trades)}")
        console.print(f"Net P&L: ₹{self.today_pnl:+,.2f}")
        console.print(f"Capital: ₹{self.capital + self.today_pnl:,.2f}")
        console.print("="*60 + "\n")
    
    def setup_schedule(self):
        """Setup the daily schedule"""
        logger.info("📅 Setting up daily schedule...")
        
        # Market open
        schedule.every().day.at(self.market_open).do(self.on_market_open)
        
        # Start trading (after first 15 mins)
        schedule.every().day.at(self.first_trade_time).do(self.on_trading_start)
        
        # Scan for trades every 5 minutes during market hours
        for hour in range(9, 15):
            for minute in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]:
                time_str = f"{hour:02d}:{minute:02d}"
                if self.first_trade_time <= time_str <= self.last_trade_time:
                    schedule.every().day.at(time_str).do(self.scan_and_trade)
        
        # Square off
        schedule.every().day.at(self.square_off_time).do(self.on_square_off)
        
        # Market close
        schedule.every().day.at(self.market_close).do(self.on_market_close)
        
        logger.info("✅ Schedule configured:")
        logger.info(f"   Market Open: {self.market_open}")
        logger.info(f"   Trading Start: {self.first_trade_time}")
        logger.info(f"   Last Trade: {self.last_trade_time}")
        logger.info(f"   Square Off: {self.square_off_time}")
        logger.info(f"   Market Close: {self.market_close}")
        logger.info(f"   Scan Interval: Every 5 minutes")
    
    def run(self):
        """Main run loop"""
        console.print(Panel.fit(
            "[bold magenta]🤖 SCHEDULED TRADING BOT[/bold magenta]\n\n"
            "Auto-runs at market hours (9:15 AM - 3:30 PM)\n\n"
            f"Mode: {TRADING_MODE.upper()}\n"
            f"Capital: ₹{self.capital:,.2f}\n"
            f"Strategy: Multi-Confirmation Scalper",
            title="Starting"
        ))
        
        # Connect to Zerodha
        if not self.connect_zerodha():
            if TRADING_MODE not in ["paper", "signal"]:
                logger.error("Cannot start without Zerodha connection")
                return
        
        # Setup schedule
        self.setup_schedule()
        
        # Check if market is already open
        if self.is_market_open():
            logger.info("Market is currently open, starting immediately")
            self.on_market_open()
            if self.is_trading_time():
                self.on_trading_start()
        
        console.print("\n[bold green]✅ Bot is running. Press Ctrl+C to stop.[/bold green]")
        console.print(f"[dim]Current time: {datetime.now().strftime('%H:%M:%S')}[/dim]")
        console.print(f"[dim]Market opens at: {self.market_open}[/dim]\n")
        
        # Run forever
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down...")
            if self.is_trading_active:
                self.on_square_off()
            console.print("\n[bold]Goodbye! 👋[/bold]")


def main():
    """Entry point"""
    bot = ScheduledTradingBot()
    bot.run()


if __name__ == "__main__":
    main()
