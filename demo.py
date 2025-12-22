#!/usr/bin/env python3
"""
Paper Trading Demo - Shows how the bot works without real money
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from core.risk_manager import RiskManager
import time

console = Console()

print()
console.print(Panel.fit(
    '[bold magenta]🎮 PAPER TRADING SIMULATION[/bold magenta]\n\n'
    'Demonstrating the trading bot with sample data',
    title='Welcome'
))

# Initialize Risk Manager
rm = RiskManager(10000)

# Sample market data (simulated)
stocks_data = [
    {'symbol': 'SBIN', 'price': 815.50, 'change': -1.2, 'ema9': 820, 'ema21': 810, 'rsi': 45, 'signal': '📈 BULLISH'},
    {'symbol': 'TATASTEEL', 'price': 142.30, 'change': 0.8, 'ema9': 140, 'ema21': 138, 'rsi': 58, 'signal': '📈 BULLISH'},
    {'symbol': 'ITC', 'price': 465.20, 'change': -0.3, 'ema9': 468, 'ema21': 470, 'rsi': 42, 'signal': '➖ NEUTRAL'},
    {'symbol': 'COALINDIA', 'price': 385.75, 'change': 1.5, 'ema9': 380, 'ema21': 375, 'rsi': 62, 'signal': '📈 BULLISH'},
]

# Market Overview
market_table = Table(title='📊 Current Market Overview (Simulated)')
market_table.add_column('Symbol', style='cyan')
market_table.add_column('Price', justify='right', style='green')
market_table.add_column('Change', justify='right')
market_table.add_column('EMA9', justify='right')
market_table.add_column('EMA21', justify='right')
market_table.add_column('RSI', justify='right')
market_table.add_column('Signal', justify='center')

for s in stocks_data:
    change_color = 'green' if s['change'] >= 0 else 'red'
    market_table.add_row(
        s['symbol'],
        f"₹{s['price']:,.2f}",
        f"[{change_color}]{s['change']:+.2f}%[/{change_color}]",
        f"{s['ema9']:.0f}",
        f"{s['ema21']:.0f}",
        f"{s['rsi']:.0f}",
        s['signal']
    )

console.print(market_table)

# Sample Trade Signal
console.print('\n' + '='*60)
console.print('[bold yellow]📢 TRADE SIGNAL GENERATED[/bold yellow]')
console.print('='*60)

# Calculate position for TATASTEEL
entry = 142.30
stop_loss = 139.00  # ~2.3% below
target = 147.50  # ~3.7% above
qty = rm.calculate_position_size(entry, stop_loss)

signal_table = Table(show_header=False, box=None)
signal_table.add_column('Field', style='cyan', width=20)
signal_table.add_column('Value', style='green')

signal_table.add_row('Strategy', 'VWAP Bounce + EMA Confirmation')
signal_table.add_row('Symbol', '[bold]TATASTEEL[/bold]')
signal_table.add_row('Action', '[bold green]🟢 BUY[/bold green]')
signal_table.add_row('Entry Price', f'₹{entry:.2f}')
signal_table.add_row('Stop Loss', f'₹{stop_loss:.2f} (-2.3%)')
signal_table.add_row('Target', f'₹{target:.2f} (+3.7%)')
signal_table.add_row('Quantity', f'{qty} shares')
signal_table.add_row('Position Value', f'₹{entry * qty:,.2f}')
signal_table.add_row('Risk Amount', f'₹{(entry - stop_loss) * qty:.2f}')
signal_table.add_row('Potential Profit', f'₹{(target - entry) * qty:.2f}')
signal_table.add_row('Risk:Reward', '1:1.6')

console.print(signal_table)

# Simulate trade execution in paper mode
console.print('\n[bold cyan]📝 PAPER TRADE EXECUTED[/bold cyan]')
console.print(f'   ✅ BUY {qty} TATASTEEL @ ₹{entry}')
console.print(f'   🛑 SL Order placed @ ₹{stop_loss}')
console.print(f'   🎯 Target Order placed @ ₹{target}')

# Simulate outcome
console.print('\n[bold]⏳ Simulating market movement...[/bold]')
time.sleep(1)
console.print('[dim]   Price: ₹142.30 → ₹143.50 → ₹145.00 → ₹146.80 → ₹147.50[/dim]')
console.print('\n[bold green]🎉 TARGET HIT![/bold green]')

profit = (target - entry) * qty
console.print(f'   💰 Profit: ₹{profit:,.2f}')

# Portfolio Summary
console.print('\n' + '='*60)
console.print('[bold cyan]📊 PAPER TRADING PORTFOLIO[/bold cyan]')
console.print('='*60)

portfolio_table = Table(show_header=False)
portfolio_table.add_column('Metric', style='cyan', width=25)
portfolio_table.add_column('Value', style='white')

portfolio_table.add_row('Starting Capital', '₹10,000.00')
portfolio_table.add_row('Trade Profit', f'[green]+₹{profit:.2f}[/green]')
portfolio_table.add_row('Current Capital', f'[bold green]₹{10000 + profit:,.2f}[/bold green]')
portfolio_table.add_row('Return', f'[green]+{profit/10000*100:.2f}%[/green]')
portfolio_table.add_row('Trades Today', '1')
portfolio_table.add_row('Win Rate', '100% (1/1)')
portfolio_table.add_row('Trading Mode', '[yellow]PAPER[/yellow]')

console.print(portfolio_table)

console.print('\n[dim]This is a paper trading simulation. No real orders were placed.[/dim]')
console.print('[bold green]✅ Paper trading demo complete![/bold green]\n')
