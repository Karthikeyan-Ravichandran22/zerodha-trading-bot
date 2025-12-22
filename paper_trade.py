"""
Paper Trading Mode - Simulate trades without real money
Perfect for testing strategies before going live
"""

import time
from datetime import datetime
from typing import Dict
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.live import Live

from config.settings import STOCK_WATCHLIST, TRADING_CAPITAL, print_config
from core.risk_manager import RiskManager
from core.data_fetcher import DataFetcher
from strategies import (
    VWAPBounceStrategy, ORBStrategy,
    GapAndGoStrategy, EMACrossoverStrategy
)
from strategies.base_strategy import TradeSignal, Signal
from utils.logger import setup_logger

console = Console()


class PaperTrader:
    """
    Paper trading simulator for testing strategies
    Uses historical/delayed data to simulate trading
    """
    
    def __init__(self):
        self.capital = TRADING_CAPITAL
        self.starting_capital = TRADING_CAPITAL
        self.risk_manager = RiskManager(self.capital)
        self.data_fetcher = DataFetcher()
        
        self.open_positions: Dict[str, dict] = {}
        self.closed_trades: list = []
        self.total_pnl = 0.0
        
        # Load all strategies
        self.strategies = [
            VWAPBounceStrategy(self.data_fetcher, self.risk_manager),
            ORBStrategy(self.data_fetcher, self.risk_manager),
            GapAndGoStrategy(self.data_fetcher, self.risk_manager),
            EMACrossoverStrategy(self.data_fetcher, self.risk_manager),
        ]
        
        setup_logger("paper_trading")
    
    def run_scan(self):
        """Scan for signals across all strategies"""
        console.print("\n[bold cyan]🔍 Scanning for trading signals...[/bold cyan]\n")
        
        all_signals = []
        
        for strategy in self.strategies:
            console.print(f"[yellow]📊 Running {strategy.name}...[/yellow]")
            signals = strategy.scan_symbols(STOCK_WATCHLIST[:5])  # Limit for demo
            
            for signal in signals:
                all_signals.append((strategy.name, signal))
                self._display_signal(strategy.name, signal)
        
        if not all_signals:
            console.print("[dim]No signals found at this time.[/dim]")
        
        return all_signals
    
    def _display_signal(self, strategy: str, signal: TradeSignal):
        """Display signal in formatted table"""
        table = Table(title=f"📢 {strategy} Signal")
        
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        color = "green" if signal.signal == Signal.BUY else "red"
        
        table.add_row("Symbol", signal.symbol)
        table.add_row("Action", f"[{color}]{signal.signal.value}[/{color}]")
        table.add_row("Entry Price", f"₹{signal.entry_price:,.2f}")
        table.add_row("Stop Loss", f"₹{signal.stop_loss:,.2f}")
        table.add_row("Target", f"₹{signal.target:,.2f}")
        table.add_row("Quantity", str(signal.quantity))
        table.add_row("Reason", signal.reason)
        
        risk = abs(signal.entry_price - signal.stop_loss) * signal.quantity
        reward = abs(signal.target - signal.entry_price) * signal.quantity
        table.add_row("Risk", f"₹{risk:,.2f}")
        table.add_row("Reward", f"₹{reward:,.2f}")
        
        console.print(table)
        console.print()
    
    def simulate_trade(self, signal: TradeSignal, strategy: str):
        """Simulate a paper trade"""
        trade_id = f"{signal.symbol}_{datetime.now().timestamp()}"
        
        self.open_positions[trade_id] = {
            "symbol": signal.symbol,
            "side": signal.signal.value,
            "entry": signal.entry_price,
            "sl": signal.stop_loss,
            "target": signal.target,
            "qty": signal.quantity,
            "strategy": strategy,
            "entry_time": datetime.now()
        }
        
        console.print(f"[green]✅ Paper trade opened: {signal.signal.value} {signal.quantity} {signal.symbol} @ ₹{signal.entry_price}[/green]")
        self.risk_manager.record_trade_entry()
        
        return trade_id
    
    def close_trade(self, trade_id: str, exit_price: float):
        """Close a paper trade"""
        if trade_id not in self.open_positions:
            return None
        
        trade = self.open_positions[trade_id]
        
        if trade["side"] == "BUY":
            pnl = (exit_price - trade["entry"]) * trade["qty"]
        else:
            pnl = (trade["entry"] - exit_price) * trade["qty"]
        
        trade["exit_price"] = exit_price
        trade["exit_time"] = datetime.now()
        trade["pnl"] = pnl
        
        self.closed_trades.append(trade)
        self.total_pnl += pnl
        self.capital += pnl
        
        del self.open_positions[trade_id]
        
        self.risk_manager.record_trade_exit(pnl)
        
        emoji = "💚" if pnl >= 0 else "💔"
        console.print(f"{emoji} Trade closed: {trade['symbol']} | P&L: ₹{pnl:,.2f}")
        
        return pnl
    
    def show_portfolio(self):
        """Display current portfolio status"""
        console.print("\n")
        
        # Summary table
        summary = Table(title="📊 Paper Trading Summary")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="green")
        
        summary.add_row("Starting Capital", f"₹{self.starting_capital:,.2f}")
        summary.add_row("Current Capital", f"₹{self.capital:,.2f}")
        summary.add_row("Total P&L", f"₹{self.total_pnl:,.2f}")
        summary.add_row("Return %", f"{(self.total_pnl/self.starting_capital)*100:.2f}%")
        summary.add_row("Open Positions", str(len(self.open_positions)))
        summary.add_row("Closed Trades", str(len(self.closed_trades)))
        
        if self.closed_trades:
            wins = sum(1 for t in self.closed_trades if t["pnl"] >= 0)
            win_rate = (wins / len(self.closed_trades)) * 100
            summary.add_row("Win Rate", f"{win_rate:.1f}%")
        
        console.print(summary)
        
        # Open positions table
        if self.open_positions:
            positions = Table(title="📈 Open Positions")
            positions.add_column("Symbol")
            positions.add_column("Side")
            positions.add_column("Entry")
            positions.add_column("Qty")
            positions.add_column("Strategy")
            
            for tid, pos in self.open_positions.items():
                positions.add_row(
                    pos["symbol"],
                    pos["side"],
                    f"₹{pos['entry']:,.2f}",
                    str(pos["qty"]),
                    pos["strategy"]
                )
            
            console.print(positions)
    
    def interactive_mode(self):
        """Run interactive paper trading session"""
        console.print("[bold magenta]🎮 Paper Trading Mode - Interactive Session[/bold magenta]")
        print_config()
        
        while True:
            console.print("\n[bold]Commands:[/bold]")
            console.print("  [cyan]1[/cyan] - Scan for signals")
            console.print("  [cyan]2[/cyan] - Show portfolio")
            console.print("  [cyan]3[/cyan] - Simulate trade from last signal")
            console.print("  [cyan]4[/cyan] - Close all positions")
            console.print("  [cyan]5[/cyan] - Risk status")
            console.print("  [cyan]q[/cyan] - Quit")
            
            choice = console.input("\n[yellow]Enter choice: [/yellow]").strip().lower()
            
            if choice == '1':
                self.last_signals = self.run_scan()
            elif choice == '2':
                self.show_portfolio()
            elif choice == '3':
                if hasattr(self, 'last_signals') and self.last_signals:
                    for strategy, signal in self.last_signals[:1]:  # Take first signal
                        self.simulate_trade(signal, strategy)
                else:
                    console.print("[dim]No signals to trade. Run scan first.[/dim]")
            elif choice == '4':
                for tid in list(self.open_positions.keys()):
                    # Simulate random exit (in real: would use current price)
                    pos = self.open_positions[tid]
                    exit_price = pos["target"] * 0.98  # Assume near target
                    self.close_trade(tid, exit_price)
            elif choice == '5':
                can_trade, reason = self.risk_manager.can_take_trade()
                console.print(f"\n{reason}")
                console.print(f"Daily P&L: ₹{self.risk_manager.daily_stats.total_pnl:,.2f}")
                console.print(f"Trades today: {self.risk_manager.daily_stats.trades_taken}")
            elif choice == 'q':
                console.print("[bold]Goodbye! 👋[/bold]")
                break
            else:
                console.print("[red]Invalid choice[/red]")


def main():
    """Run paper trading mode"""
    trader = PaperTrader()
    trader.interactive_mode()


if __name__ == "__main__":
    main()
