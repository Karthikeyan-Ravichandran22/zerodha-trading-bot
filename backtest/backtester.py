"""
Backtester - Test strategies on historical data
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass
from loguru import logger
import click

from strategies.base_strategy import BaseStrategy, TradeSignal, Signal
from strategies import VWAPBounceStrategy, ORBStrategy, GapAndGoStrategy, EMACrossoverStrategy
from core.risk_manager import RiskManager


@dataclass
class BacktestResult:
    strategy: str
    symbol: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    gross_profit: float
    gross_loss: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    avg_win: float
    avg_loss: float
    trades: List[dict]


class Backtester:
    """Backtest trading strategies on historical data"""
    
    def __init__(self, capital: float = 10000):
        self.capital = capital
        self.risk_manager = RiskManager(capital)
    
    def get_historical_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Fetch historical data using yfinance"""
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            end = datetime.now()
            start = end - timedelta(days=days)
            df = ticker.history(start=start, end=end, interval="15m")
            
            if df.empty:
                logger.warning(f"No data for {symbol}")
                return None
            
            df.columns = [c.lower() for c in df.columns]
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return None
    
    def run_backtest(
        self, 
        strategy: BaseStrategy, 
        symbol: str, 
        days: int = 30
    ) -> BacktestResult:
        """Run backtest for a strategy on a symbol"""
        
        logger.info(f"Backtesting {strategy.name} on {symbol} ({days} days)")
        
        # Get historical data
        data = self.get_historical_data(symbol, days)
        if data is None or data.empty:
            return None
        
        # Calculate indicators
        data = strategy.calculate_indicators(data)
        
        trades = []
        current_position = None
        
        # Walk through data
        for i in range(50, len(data)):
            window = data.iloc[:i+1]
            current = data.iloc[i]
            
            # If no position, look for entry
            if current_position is None:
                signal = strategy.analyze(symbol, window)
                if signal:
                    current_position = {
                        "entry_time": current.name,
                        "entry_price": signal.entry_price,
                        "stop_loss": signal.stop_loss,
                        "target": signal.target,
                        "side": signal.signal.value,
                        "quantity": signal.quantity
                    }
            
            # If in position, check for exit
            else:
                close = current['close']
                
                # Check stop loss
                if current_position["side"] == "BUY":
                    if close <= current_position["stop_loss"]:
                        pnl = (close - current_position["entry_price"]) * current_position["quantity"]
                        current_position["exit_price"] = close
                        current_position["exit_time"] = current.name
                        current_position["pnl"] = pnl
                        current_position["exit_reason"] = "SL"
                        trades.append(current_position)
                        current_position = None
                    elif close >= current_position["target"]:
                        pnl = (close - current_position["entry_price"]) * current_position["quantity"]
                        current_position["exit_price"] = close
                        current_position["exit_time"] = current.name
                        current_position["pnl"] = pnl
                        current_position["exit_reason"] = "TARGET"
                        trades.append(current_position)
                        current_position = None
                else:
                    if close >= current_position["stop_loss"]:
                        pnl = (current_position["entry_price"] - close) * current_position["quantity"]
                        current_position["exit_price"] = close
                        current_position["exit_time"] = current.name
                        current_position["pnl"] = pnl
                        current_position["exit_reason"] = "SL"
                        trades.append(current_position)
                        current_position = None
                    elif close <= current_position["target"]:
                        pnl = (current_position["entry_price"] - close) * current_position["quantity"]
                        current_position["exit_price"] = close
                        current_position["exit_time"] = current.name
                        current_position["pnl"] = pnl
                        current_position["exit_reason"] = "TARGET"
                        trades.append(current_position)
                        current_position = None
        
        # Calculate statistics
        return self._calculate_stats(strategy.name, symbol, trades)
    
    def _calculate_stats(self, strategy: str, symbol: str, trades: List[dict]) -> BacktestResult:
        """Calculate backtest statistics"""
        
        if not trades:
            return BacktestResult(
                strategy=strategy, symbol=symbol,
                total_trades=0, winning_trades=0, losing_trades=0,
                total_pnl=0, gross_profit=0, gross_loss=0,
                win_rate=0, profit_factor=0, max_drawdown=0,
                avg_win=0, avg_loss=0, trades=[]
            )
        
        winning = [t for t in trades if t["pnl"] > 0]
        losing = [t for t in trades if t["pnl"] <= 0]
        
        gross_profit = sum(t["pnl"] for t in winning)
        gross_loss = abs(sum(t["pnl"] for t in losing))
        total_pnl = gross_profit - gross_loss
        
        win_rate = len(winning) / len(trades) * 100 if trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        avg_win = gross_profit / len(winning) if winning else 0
        avg_loss = gross_loss / len(losing) if losing else 0
        
        # Calculate drawdown
        equity_curve = [self.capital]
        for t in trades:
            equity_curve.append(equity_curve[-1] + t["pnl"])
        
        max_equity = equity_curve[0]
        max_drawdown = 0
        for eq in equity_curve:
            if eq > max_equity:
                max_equity = eq
            drawdown = (max_equity - eq) / max_equity * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return BacktestResult(
            strategy=strategy,
            symbol=symbol,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=total_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            avg_win=avg_win,
            avg_loss=avg_loss,
            trades=trades
        )
    
    def print_results(self, result: BacktestResult):
        """Print backtest results"""
        if result is None:
            print("No results to display")
            return
        
        print(f"""
╔══════════════════════════════════════════════════════════╗
║                   BACKTEST RESULTS                        ║
╠══════════════════════════════════════════════════════════╣
║  Strategy: {result.strategy:<44} ║
║  Symbol: {result.symbol:<46} ║
╠══════════════════════════════════════════════════════════╣
║  Total Trades:   {result.total_trades:<39} ║
║  Winning:        {result.winning_trades:<39} ║
║  Losing:         {result.losing_trades:<39} ║
║  Win Rate:       {result.win_rate:.1f}%{' '*36} ║
╠══════════════════════════════════════════════════════════╣
║  Gross Profit:   ₹{result.gross_profit:>12,.2f}{' '*24} ║
║  Gross Loss:     ₹{result.gross_loss:>12,.2f}{' '*24} ║
║  Net P&L:        ₹{result.total_pnl:>12,.2f}{' '*24} ║
╠══════════════════════════════════════════════════════════╣
║  Avg Win:        ₹{result.avg_win:>12,.2f}{' '*24} ║
║  Avg Loss:       ₹{result.avg_loss:>12,.2f}{' '*24} ║
║  Profit Factor:  {result.profit_factor:.2f}{' '*38} ║
║  Max Drawdown:   {result.max_drawdown:.1f}%{' '*36} ║
╚══════════════════════════════════════════════════════════╝
""")


@click.command()
@click.option('--strategy', type=click.Choice(['vwap_bounce', 'orb', 'gap_and_go', 'ema_crossover']), 
              default='vwap_bounce')
@click.option('--symbol', default='TATAMOTORS')
@click.option('--days', default=30)
def main(strategy, symbol, days):
    """Run backtest"""
    strategy_map = {
        'vwap_bounce': VWAPBounceStrategy,
        'orb': ORBStrategy,
        'gap_and_go': GapAndGoStrategy,
        'ema_crossover': EMACrossoverStrategy
    }
    
    backtester = Backtester()
    strategy_obj = strategy_map[strategy]()
    
    result = backtester.run_backtest(strategy_obj, symbol, days)
    backtester.print_results(result)


if __name__ == "__main__":
    main()
