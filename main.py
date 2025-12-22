"""
Zerodha Automated Trading Bot - Main Entry Point
"""

import sys
import time
import schedule
from datetime import datetime, time as dtime
from typing import List
import click
from loguru import logger

from config.settings import (
    TRADING_MODE, ACTIVE_STRATEGIES, STOCK_WATCHLIST,
    MARKET_OPEN, MARKET_CLOSE, SQUARE_OFF_TIME, NO_NEW_TRADES_AFTER,
    MORNING_SESSION_START, MORNING_SESSION_END,
    AFTERNOON_SESSION_START, AFTERNOON_SESSION_END,
    print_config, validate_config
)
from core.zerodha_client import get_zerodha_client
from core.risk_manager import get_risk_manager
from core.order_manager import OrderManager, OrderSide
from core.data_fetcher import DataFetcher
from strategies import (
    VWAPBounceStrategy, ORBStrategy, 
    GapAndGoStrategy, EMACrossoverStrategy
)
from utils.logger import setup_logger
from utils.notifications import send_telegram_message, send_trade_alert


class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self, mode: str = None):
        self.mode = mode or TRADING_MODE
        self.client = get_zerodha_client()
        self.risk_manager = get_risk_manager()
        self.data_fetcher = DataFetcher(self.client)
        self.order_manager = OrderManager(self.client)
        self.strategies = []
        self.is_running = False
        
        setup_logger("trading_bot")
    
    def initialize(self, request_token: str = None) -> bool:
        """Initialize bot and connect to Zerodha"""
        logger.info("🚀 Initializing Trading Bot...")
        print_config()
        
        # Validate configuration
        errors = validate_config()
        if errors:
            for err in errors:
                logger.error(f"Config Error: {err}")
            return False
        
        # Initialize Zerodha client
        if self.mode in ["auto", "semi-auto"]:
            if not self.client.initialize():
                return False
            if not self.client.authenticate(request_token):
                return False
        else:
            logger.info(f"📝 Running in {self.mode.upper()} mode - no Zerodha connection needed")
        
        # Initialize strategies
        self._load_strategies()
        
        logger.info("✅ Bot initialized successfully!")
        return True
    
    def _load_strategies(self):
        """Load active strategies"""
        strategy_map = {
            "vwap_bounce": VWAPBounceStrategy,
            "orb": ORBStrategy,
            "gap_and_go": GapAndGoStrategy,
            "ema_crossover": EMACrossoverStrategy
        }
        
        for strategy_name in ACTIVE_STRATEGIES:
            strategy_name = strategy_name.strip().lower()
            if strategy_name in strategy_map:
                strategy = strategy_map[strategy_name](
                    data_fetcher=self.data_fetcher,
                    risk_manager=self.risk_manager
                )
                self.strategies.append(strategy)
                logger.info(f"📈 Loaded strategy: {strategy.name}")
    
    def is_market_hours(self) -> bool:
        """Check if current time is within market hours"""
        now = datetime.now().time()
        return MARKET_OPEN <= now <= MARKET_CLOSE
    
    def is_trading_window(self) -> bool:
        """Check if current time is within trading windows"""
        now = datetime.now().time()
        
        # Morning session: 9:30 - 11:30
        in_morning = MORNING_SESSION_START <= now <= MORNING_SESSION_END
        
        # Afternoon session: 1:00 - 2:30
        in_afternoon = AFTERNOON_SESSION_START <= now <= AFTERNOON_SESSION_END
        
        return in_morning or in_afternoon
    
    def should_stop_new_trades(self) -> bool:
        """Check if we should stop taking new trades"""
        now = datetime.now().time()
        return now >= NO_NEW_TRADES_AFTER
    
    def scan_for_signals(self):
        """Scan all stocks for trading signals"""
        can_trade, reason = self.risk_manager.can_take_trade()
        if not can_trade:
            logger.warning(reason)
            return
        
        if self.should_stop_new_trades():
            logger.info("⏰ No new trades after 2:30 PM")
            return
        
        logger.info(f"🔍 Scanning {len(STOCK_WATCHLIST)} stocks...")
        
        for strategy in self.strategies:
            signals = strategy.scan_symbols(STOCK_WATCHLIST)
            for signal in signals:
                self._process_signal(signal, strategy.name)
    
    def _process_signal(self, signal, strategy_name: str):
        """Process a trading signal"""
        logger.info(f"\n{'='*50}")
        logger.info(f"📢 SIGNAL from {strategy_name}")
        logger.info(f"   {signal.signal.value} {signal.symbol}")
        logger.info(f"   Entry: ₹{signal.entry_price}")
        logger.info(f"   SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        logger.info(f"   Qty: {signal.quantity} | Reason: {signal.reason}")
        logger.info(f"{'='*50}\n")
        
        # Send notification
        send_trade_alert(
            action=signal.signal.value,
            symbol=signal.symbol,
            entry=signal.entry_price,
            sl=signal.stop_loss,
            target=signal.target,
            qty=signal.quantity
        )
        
        if self.mode == "signal":
            logger.info("📢 Signal mode - not placing order")
            return
        
        if self.mode == "semi-auto":
            confirm = input(f"Place order? (y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("Order cancelled by user")
                return
        
        # Place order
        side = OrderSide.BUY if signal.signal.value == "BUY" else OrderSide.SELL
        order = self.order_manager.place_bracket_order(
            symbol=signal.symbol,
            side=side,
            quantity=signal.quantity,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target=signal.target,
            strategy=strategy_name
        )
        
        if order:
            self.risk_manager.record_trade_entry()
    
    def check_positions(self):
        """Check and manage open positions"""
        positions = self.order_manager.get_open_positions()
        if not positions:
            return
        
        logger.info(f"📊 Open positions: {len(positions)}")
        for pos in positions:
            logger.info(f"   {pos.symbol}: {pos.side.value} {pos.quantity} @ ₹{pos.price}")
    
    def square_off_all(self):
        """Square off all positions"""
        logger.warning("🔔 Squaring off all positions!")
        self.order_manager.square_off_all()
        send_telegram_message("🔔 All positions squared off for the day")
    
    def run(self):
        """Main run loop"""
        self.is_running = True
        logger.info("🤖 Bot is now running...")
        
        # Schedule tasks
        schedule.every(1).minutes.do(self.scan_for_signals)
        schedule.every(30).seconds.do(self.check_positions)
        schedule.every().day.at("15:10").do(self.square_off_all)
        
        try:
            while self.is_running:
                if not self.is_market_hours():
                    logger.info("⏳ Market closed. Waiting...")
                    time.sleep(60)
                    continue
                
                if not self.is_trading_window():
                    logger.debug("Outside trading window")
                    time.sleep(30)
                    continue
                
                schedule.run_pending()
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down...")
            self.is_running = False
            self.square_off_all()


@click.command()
@click.option('--mode', type=click.Choice(['paper', 'signal', 'semi-auto', 'auto']), 
              default=None, help='Trading mode')
@click.option('--token', default=None, help='Zerodha request token for authentication')
def main(mode, token):
    """Zerodha Automated Trading Bot"""
    bot = TradingBot(mode=mode)
    
    if not bot.initialize(request_token=token):
        logger.error("Failed to initialize bot")
        sys.exit(1)
    
    bot.run()


if __name__ == "__main__":
    main()
