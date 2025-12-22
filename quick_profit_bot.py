"""
QUICK PROFIT SCALPING BOT
Uses Multi-Confirmation Strategy for High Probability Trades

Features:
- Only trades when 5+/6 indicators confirm
- Quick 0.5% profit targets
- Tight 0.3% stop-loss
- Immediate exit if ANY indicator flips
- Targets 70-80% win rate (realistic max)

WARNING: 100% win rate is IMPOSSIBLE in trading!
"""

import time
from datetime import datetime, time as dtime
from typing import Optional, List
from dataclasses import dataclass
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from strategies.multi_confirmation import MultiConfirmationScalper
from core.risk_manager import RiskManager
from core.data_fetcher import DataFetcher
from core.order_manager import OrderManager, OrderSide


console = Console()


@dataclass
class TradeResult:
    symbol: str
    entry: float
    exit: float
    qty: int
    pnl: float
    result: str  # 'WIN' or 'LOSS'
    confirmations: int
    exit_reason: str


class QuickProfitBot:
    """
    Scalping bot that takes quick profits with high confirmation
    """
    
    def __init__(self, capital: float = 10000):
        self.capital = capital
        self.risk_manager = RiskManager(capital)
        self.data_fetcher = DataFetcher()
        self.order_manager = OrderManager()
        self.strategy = MultiConfirmationScalper(
            data_fetcher=self.data_fetcher,
            risk_manager=self.risk_manager
        )
        
        self.trades: List[TradeResult] = []
        self.current_pnl = 0.0
        
        # Stock watchlist - low price, high liquidity
        self.watchlist = [
            'SBIN', 'TATASTEEL', 'COALINDIA', 'PNB', 
            'IRFC', 'SAIL', 'IOC', 'ONGC'
        ]
    
    def print_status(self):
        """Print current status"""
        console.print(Panel.fit(
            f"[bold cyan]Quick Profit Scalping Bot[/bold cyan]\n"
            f"Capital: ₹{self.capital:,.2f}\n"
            f"Current P&L: ₹{self.current_pnl:+,.2f}\n"
            f"Trades: {len(self.trades)} | "
            f"Wins: {sum(1 for t in self.trades if t.result == 'WIN')}"
        ))
    
    def scan_all_stocks(self) -> List:
        """Scan all stocks for high-probability setups"""
        signals = []
        
        console.print("\n[cyan]🔍 Scanning for high-probability setups...[/cyan]")
        
        for symbol in self.watchlist:
            console.print(f"   Checking {symbol}...", end=" ")
            
            try:
                data = self.data_fetcher.get_ohlc_data(symbol, "5minute", 5)
                if data is not None and len(data) >= 30:
                    data = self.strategy.calculate_indicators(data)
                    signal = self.strategy.analyze(symbol, data)
                    
                    if signal:
                        console.print(f"[green]✅ SIGNAL FOUND![/green]")
                        signals.append(signal)
                    else:
                        console.print("[dim]No setup[/dim]")
                else:
                    console.print("[yellow]Insufficient data[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        return signals
    
    def execute_trade(self, signal) -> Optional[TradeResult]:
        """Execute a paper trade"""
        console.print(f"\n[bold green]📈 EXECUTING TRADE[/bold green]")
        
        # Show signal details
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="cyan", width=18)
        table.add_column("Value", style="white")
        
        table.add_row("Symbol", f"[bold]{signal.symbol}[/bold]")
        table.add_row("Action", f"[green]{signal.signal.value}[/green]")
        table.add_row("Entry", f"₹{signal.entry_price:.2f}")
        table.add_row("Stop Loss", f"₹{signal.stop_loss:.2f}")
        table.add_row("Target", f"₹{signal.target:.2f}")
        table.add_row("Quantity", f"{signal.quantity} shares")
        table.add_row("Confidence", f"{signal.confidence:.0f}%")
        
        console.print(table)
        
        # Simulate trade outcome (in paper mode)
        # Using realistic odds based on confirmation score
        import random
        win_probability = signal.confidence / 100 * 0.9  # Max 90% win rate
        
        is_winner = random.random() < win_probability
        
        if is_winner:
            exit_price = signal.target
            pnl = (signal.target - signal.entry_price) * signal.quantity
            result = "WIN"
            exit_reason = "Target Hit"
            console.print(f"\n[bold green]🎉 TARGET HIT! +₹{pnl:.2f}[/bold green]")
        else:
            exit_price = signal.stop_loss
            pnl = (signal.stop_loss - signal.entry_price) * signal.quantity
            result = "LOSS"
            exit_reason = "Stop Loss Hit"
            console.print(f"\n[bold red]🛑 STOP LOSS HIT! ₹{pnl:.2f}[/bold red]")
        
        trade = TradeResult(
            symbol=signal.symbol,
            entry=signal.entry_price,
            exit=exit_price,
            qty=signal.quantity,
            pnl=pnl,
            result=result,
            confirmations=int(signal.confidence / 100 * 6),
            exit_reason=exit_reason
        )
        
        self.trades.append(trade)
        self.current_pnl += pnl
        self.capital += pnl
        
        return trade
    
    def show_summary(self):
        """Show trading summary"""
        console.print("\n" + "="*60)
        console.print("[bold cyan]📊 TRADING SUMMARY[/bold cyan]")
        console.print("="*60)
        
        if not self.trades:
            console.print("[dim]No trades taken[/dim]")
            return
        
        # Trade log
        trade_table = Table(title="Trade Log")
        trade_table.add_column("Symbol")
        trade_table.add_column("Entry", justify="right")
        trade_table.add_column("Exit", justify="right")
        trade_table.add_column("Qty", justify="right")
        trade_table.add_column("P&L", justify="right")
        trade_table.add_column("Result")
        trade_table.add_column("Conf.")
        
        for t in self.trades:
            pnl_color = "green" if t.pnl > 0 else "red"
            trade_table.add_row(
                t.symbol,
                f"₹{t.entry:.2f}",
                f"₹{t.exit:.2f}",
                str(t.qty),
                f"[{pnl_color}]₹{t.pnl:+.2f}[/{pnl_color}]",
                f"[green]{t.result}[/green]" if t.result == "WIN" else f"[red]{t.result}[/red]",
                f"{t.confirmations}/6"
            )
        
        console.print(trade_table)
        
        # Stats
        wins = sum(1 for t in self.trades if t.result == "WIN")
        losses = len(self.trades) - wins
        win_rate = wins / len(self.trades) * 100 if self.trades else 0
        
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        
        stats_table = Table(show_header=False)
        stats_table.add_column("Metric", style="cyan", width=20)
        stats_table.add_column("Value", style="white")
        
        stats_table.add_row("Total Trades", str(len(self.trades)))
        stats_table.add_row("Winning Trades", f"[green]{wins}[/green]")
        stats_table.add_row("Losing Trades", f"[red]{losses}[/red]")
        stats_table.add_row("Win Rate", f"[bold]{win_rate:.1f}%[/bold]")
        stats_table.add_row("Gross Profit", f"[green]₹{gross_profit:,.2f}[/green]")
        stats_table.add_row("Gross Loss", f"[red]₹{gross_loss:,.2f}[/red]")
        stats_table.add_row("Net P&L", f"[bold]₹{self.current_pnl:+,.2f}[/bold]")
        stats_table.add_row("Final Capital", f"[bold]₹{self.capital:,.2f}[/bold]")
        
        console.print(stats_table)
    
    def run_demo(self, num_trades: int = 5):
        """Run demo with simulated trades"""
        console.print(Panel.fit(
            "[bold magenta]🤖 QUICK PROFIT SCALPING BOT[/bold magenta]\n\n"
            "Multi-Confirmation Strategy Demo\n"
            "Requires 5+/6 indicators to confirm trade\n\n"
            "[yellow]⚠️ Paper Trading Mode - No Real Orders[/yellow]",
            title="Welcome"
        ))
        
        console.print(f"\n📋 Watchlist: {', '.join(self.watchlist)}")
        console.print(f"💰 Starting Capital: ₹{self.capital:,.2f}")
        console.print(f"⚠️ Risk per trade: ₹200 (2%)")
        console.print(f"🎯 Target: 0.5% | Stop-Loss: 0.3%")
        
        # Simulate trades
        for i in range(num_trades):
            console.print(f"\n{'='*60}")
            console.print(f"[bold]Trade {i+1}/{num_trades}[/bold]")
            console.print('='*60)
            
            # Create simulated signal
            import random
            symbol = random.choice(self.watchlist)
            base_price = random.uniform(100, 500)
            confirmations = random.randint(5, 6)  # High confirmation
            
            from strategies.base_strategy import TradeSignal, Signal
            
            signal = TradeSignal(
                signal=Signal.BUY,
                symbol=symbol,
                entry_price=round(base_price, 2),
                stop_loss=round(base_price * 0.997, 2),  # 0.3% SL
                target=round(base_price * 1.005, 2),  # 0.5% target
                quantity=self.risk_manager.calculate_position_size(base_price, base_price * 0.997),
                reason=f"Multi-confirmation: {confirmations}/6 indicators bullish",
                confidence=confirmations / 6 * 100
            )
            
            self.execute_trade(signal)
            time.sleep(0.5)
        
        self.show_summary()


def main():
    """Run the quick profit bot demo"""
    bot = QuickProfitBot(capital=10000)
    bot.run_demo(num_trades=10)


if __name__ == "__main__":
    main()
