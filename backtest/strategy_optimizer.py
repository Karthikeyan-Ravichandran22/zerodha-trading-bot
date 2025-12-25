"""
Strategy Optimizer - Find best parameters for 80% win rate

Tests different combinations:
1. Confirmation threshold (5/6 vs 6/6)
2. Only profitable stocks (PNB, SAIL)
3. Time filters (avoid first/last hour)
4. RSI zones
5. Volume requirements
6. Target/SL ratios
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import yfinance as yf
from dataclasses import dataclass
from typing import List, Tuple, Optional

IST = timezone(timedelta(hours=5, minutes=30))

@dataclass
class BacktestResult:
    params: dict
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float


def calculate_vwap(data):
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    return (typical_price * data['volume']).cumsum() / data['volume'].cumsum()

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_supertrend(data, period=10, multiplier=3):
    hl2 = (data['high'] + data['low']) / 2
    atr = data['high'].rolling(period).max() - data['low'].rolling(period).min()
    
    upper = hl2 + (multiplier * atr / period)
    lower = hl2 - (multiplier * atr / period)
    
    direction = pd.Series(index=data.index, dtype=float)
    direction.iloc[0] = 1
    
    for i in range(1, len(data)):
        if data['close'].iloc[i] > upper.iloc[i-1]:
            direction.iloc[i] = 1
        elif data['close'].iloc[i] < lower.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
    
    return direction


def run_backtest(
    stocks: List[str],
    min_confirmations: int = 5,
    target_pct: float = 0.5,
    sl_pct: float = 0.3,
    min_volume_ratio: float = 1.3,
    rsi_bull_min: int = 45,
    rsi_bull_max: int = 65,
    rsi_bear_min: int = 35,
    rsi_bear_max: int = 55,
    time_start_hour: int = 9,
    time_end_hour: int = 15,
    capital: float = 10000,
    risk_per_trade: float = 200
) -> BacktestResult:
    """Run backtest with given parameters"""
    
    all_trades = []
    
    for stock in stocks:
        symbol = stock + '.NS'
        
        try:
            # Fetch data
            data = yf.download(symbol, period='14d', interval='5m', progress=False)
            
            if data.empty or len(data) < 100:
                continue
            
            # Flatten columns
            if hasattr(data.columns, 'levels'):
                data.columns = data.columns.droplevel(1)
            
            # Lowercase columns
            data['open'] = data['Open']
            data['high'] = data['High']
            data['low'] = data['Low']
            data['close'] = data['Close']
            data['volume'] = data['Volume']
            
            # Calculate indicators
            data['vwap'] = calculate_vwap(data)
            data['ema9'] = calculate_ema(data['close'], 9)
            data['ema21'] = calculate_ema(data['close'], 21)
            data['rsi'] = calculate_rsi(data['close'], 14)
            data['st_direction'] = calculate_supertrend(data)
            data['vol_sma'] = data['volume'].rolling(20).mean()
            data['vol_ratio'] = data['volume'] / data['vol_sma']
            data['body'] = data['close'] - data['open']
            data['body_pct'] = abs(data['body']) / data['open'] * 100
            data['is_bullish'] = data['close'] > data['open']
            data['is_bearish'] = data['close'] < data['open']
            
            # Simulate trading
            in_trade = False
            entry_price = 0
            trade_type = None
            stop_loss = 0
            target = 0
            
            for i in range(50, len(data)):
                current = data.iloc[i]
                
                # Time filter
                hour = current.name.hour
                if hour < time_start_hour or hour >= time_end_hour:
                    continue
                
                if not in_trade:
                    # Check for LONG signal
                    long_score = 0
                    if current['close'] > current['vwap']:
                        long_score += 1
                    if current['ema9'] > current['ema21']:
                        long_score += 1
                    if rsi_bull_min <= current['rsi'] <= rsi_bull_max:
                        long_score += 1
                    if current['st_direction'] == 1:
                        long_score += 1
                    if current['vol_ratio'] > min_volume_ratio:
                        long_score += 1
                    if current['is_bullish'] and current['body_pct'] > 0.1:
                        long_score += 1
                    
                    if long_score >= min_confirmations:
                        in_trade = True
                        entry_price = current['close']
                        trade_type = 'BUY'
                        stop_loss = entry_price * (1 - sl_pct / 100)
                        target = entry_price * (1 + target_pct / 100)
                        continue
                    
                    # Check for SHORT signal
                    short_score = 0
                    if current['close'] < current['vwap']:
                        short_score += 1
                    if current['ema9'] < current['ema21']:
                        short_score += 1
                    if rsi_bear_min <= current['rsi'] <= rsi_bear_max:
                        short_score += 1
                    if current['st_direction'] == -1:
                        short_score += 1
                    if current['vol_ratio'] > min_volume_ratio:
                        short_score += 1
                    if current['is_bearish'] and current['body_pct'] > 0.1:
                        short_score += 1
                    
                    if short_score >= min_confirmations:
                        in_trade = True
                        entry_price = current['close']
                        trade_type = 'SELL'
                        stop_loss = entry_price * (1 + sl_pct / 100)
                        target = entry_price * (1 - target_pct / 100)
                
                else:
                    # Check exit
                    if trade_type == 'BUY':
                        if current['low'] <= stop_loss:
                            pnl = stop_loss - entry_price
                            result = 'LOSS'
                            in_trade = False
                        elif current['high'] >= target:
                            pnl = target - entry_price
                            result = 'WIN'
                            in_trade = False
                    else:
                        if current['high'] >= stop_loss:
                            pnl = entry_price - stop_loss
                            result = 'LOSS'
                            in_trade = False
                        elif current['low'] <= target:
                            pnl = entry_price - target
                            result = 'WIN'
                            in_trade = False
                    
                    if not in_trade:
                        risk_per_share = abs(entry_price - stop_loss)
                        qty = int(risk_per_trade / risk_per_share) if risk_per_share > 0 else 10
                        trade_pnl = pnl * qty - 40  # Brokerage
                        
                        all_trades.append({
                            'stock': stock,
                            'pnl': trade_pnl,
                            'result': result
                        })
        
        except Exception as e:
            continue
    
    # Calculate statistics
    total_trades = len(all_trades)
    wins = len([t for t in all_trades if t['result'] == 'WIN'])
    losses = len([t for t in all_trades if t['result'] == 'LOSS'])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    total_pnl = sum([t['pnl'] for t in all_trades])
    avg_win = np.mean([t['pnl'] for t in all_trades if t['result'] == 'WIN']) if wins > 0 else 0
    avg_loss = np.mean([t['pnl'] for t in all_trades if t['result'] == 'LOSS']) if losses > 0 else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    return BacktestResult(
        params={
            'stocks': stocks,
            'min_confirmations': min_confirmations,
            'target_pct': target_pct,
            'sl_pct': sl_pct,
            'min_volume_ratio': min_volume_ratio,
            'time_start': time_start_hour,
            'time_end': time_end_hour
        },
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        total_pnl=total_pnl,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor
    )


def optimize():
    """Run optimization to find best parameters"""
    print("=" * 70)
    print("🔧 STRATEGY OPTIMIZATION - FINDING 80% WIN RATE")
    print("=" * 70)
    print()
    
    results = []
    
    # Test different combinations
    test_configs = [
        # Config 1: Original (baseline)
        {
            'name': 'Original (5/6, All Stocks)',
            'stocks': ['PNB', 'SAIL', 'IDEA', 'IRFC', 'PFC', 'BPCL', 'BHEL'],
            'min_confirmations': 5,
            'target_pct': 0.5,
            'sl_pct': 0.3,
            'time_start': 9,
            'time_end': 16
        },
        # Config 2: 6/6 confirmations
        {
            'name': '6/6 Confirmations',
            'stocks': ['PNB', 'SAIL', 'IDEA', 'IRFC', 'PFC', 'BPCL', 'BHEL'],
            'min_confirmations': 6,
            'target_pct': 0.5,
            'sl_pct': 0.3,
            'time_start': 9,
            'time_end': 16
        },
        # Config 3: Only profitable stocks
        {
            'name': 'Only PNB, SAIL (5/6)',
            'stocks': ['PNB', 'SAIL'],
            'min_confirmations': 5,
            'target_pct': 0.5,
            'sl_pct': 0.3,
            'time_start': 9,
            'time_end': 16
        },
        # Config 4: Only PNB, SAIL with 6/6
        {
            'name': 'Only PNB, SAIL (6/6)',
            'stocks': ['PNB', 'SAIL'],
            'min_confirmations': 6,
            'target_pct': 0.5,
            'sl_pct': 0.3,
            'time_start': 9,
            'time_end': 16
        },
        # Config 5: Time filter 10-14
        {
            'name': 'Time 10-14 only (6/6)',
            'stocks': ['PNB', 'SAIL'],
            'min_confirmations': 6,
            'target_pct': 0.5,
            'sl_pct': 0.3,
            'time_start': 10,
            'time_end': 14
        },
        # Config 6: Higher target
        {
            'name': 'Higher Target 0.8% (6/6)',
            'stocks': ['PNB', 'SAIL'],
            'min_confirmations': 6,
            'target_pct': 0.8,
            'sl_pct': 0.4,
            'time_start': 10,
            'time_end': 14
        },
        # Config 7: Tighter SL
        {
            'name': 'Tighter SL 0.2% (6/6)',
            'stocks': ['PNB', 'SAIL'],
            'min_confirmations': 6,
            'target_pct': 0.4,
            'sl_pct': 0.2,
            'time_start': 10,
            'time_end': 14
        },
        # Config 8: Wider R:R
        {
            'name': 'R:R 3:1 (0.6/0.2)',
            'stocks': ['PNB', 'SAIL'],
            'min_confirmations': 6,
            'target_pct': 0.6,
            'sl_pct': 0.2,
            'time_start': 10,
            'time_end': 14
        },
        # Config 9: Add IRFC
        {
            'name': 'PNB, SAIL, IRFC (6/6)',
            'stocks': ['PNB', 'SAIL', 'IRFC'],
            'min_confirmations': 6,
            'target_pct': 0.5,
            'sl_pct': 0.3,
            'time_start': 10,
            'time_end': 14
        },
        # Config 10: Very strict 6/6 + time + higher volume
        {
            'name': 'Ultra Strict Setup',
            'stocks': ['PNB', 'SAIL'],
            'min_confirmations': 6,
            'target_pct': 0.4,
            'sl_pct': 0.2,
            'min_volume_ratio': 1.5,
            'time_start': 10,
            'time_end': 13
        },
    ]
    
    print(f"Testing {len(test_configs)} configurations...")
    print()
    
    for i, config in enumerate(test_configs):
        print(f"[{i+1}/{len(test_configs)}] Testing: {config['name']}...", end=" ")
        
        result = run_backtest(
            stocks=config['stocks'],
            min_confirmations=config['min_confirmations'],
            target_pct=config['target_pct'],
            sl_pct=config['sl_pct'],
            min_volume_ratio=config.get('min_volume_ratio', 1.3),
            time_start_hour=config['time_start'],
            time_end_hour=config['time_end']
        )
        
        print(f"Win Rate: {result.win_rate:.1f}% ({result.wins}/{result.total_trades})")
        
        results.append((config['name'], result))
    
    # Sort by win rate
    results.sort(key=lambda x: x[1].win_rate, reverse=True)
    
    print()
    print("=" * 70)
    print("📊 OPTIMIZATION RESULTS (Sorted by Win Rate)")
    print("=" * 70)
    print()
    
    print(f"{'Config':<30} {'Win Rate':>10} {'Trades':>8} {'P&L':>12}")
    print("-" * 65)
    
    for name, result in results:
        emoji = "✅" if result.win_rate >= 70 else "⚠️" if result.win_rate >= 50 else "❌"
        print(f"{emoji} {name:<28} {result.win_rate:>8.1f}% {result.total_trades:>8} ₹{result.total_pnl:>+10.2f}")
    
    # Best configuration
    best_name, best_result = results[0]
    
    print()
    print("=" * 70)
    print(f"🏆 BEST CONFIGURATION: {best_name}")
    print("=" * 70)
    print(f"   Win Rate: {best_result.win_rate:.1f}%")
    print(f"   Total Trades: {best_result.total_trades}")
    print(f"   Wins: {best_result.wins} | Losses: {best_result.losses}")
    print(f"   Total P&L: ₹{best_result.total_pnl:+,.2f}")
    print(f"   Avg Win: ₹{best_result.avg_win:+,.2f}")
    print(f"   Avg Loss: ₹{best_result.avg_loss:+,.2f}")
    print(f"   Profit Factor: {best_result.profit_factor:.2f}x")
    print()
    print("   Parameters:")
    for k, v in best_result.params.items():
        print(f"      {k}: {v}")
    
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    optimize()
