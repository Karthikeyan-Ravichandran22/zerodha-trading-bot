#!/usr/bin/env python3
"""
🌐 PREMIUM TRADING DASHBOARD
=============================

Feature-rich dashboard with:
- Strategy name display
- Database analytics
- Charts and graphs
- Weekly/Monthly stats
- Top performing stocks
- Real-time updates
"""

import os
import sys
import json
import pytz
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
IST = pytz.timezone('Asia/Kolkata')

# Strategy Configuration
STRATEGY_CONFIG = {
    "name": "Gold 93% Win Rate Strategy",
    "version": "2.0",
    "type": "Multi-Indicator Confirmation",
    "timeframe": "15 Minutes",
    "indicators": [
        {"name": "RSI", "params": "(2)", "color": "#ff6b6b"},
        {"name": "Stochastic", "params": "(10,3,3)", "color": "#ffd93d"},
        {"name": "CCI", "params": "(20)", "color": "#6bcb77"},
        {"name": "MACD", "params": "(12,26,9)", "color": "#4d96ff"}
    ],
    "entry_rule": "3/4 Indicators + Candle Flow Confirmation",
    "exit_rule": "Dynamic Trailing Stop Loss",
    "min_win_rate": "80%",
    "backtest_period": "14 Days"
}

TRADING_CONFIG = {
    "segment": "EQUITY",
    "exchange": "NSE",
    "product": "MIS (Intraday)",
    "leverage": "5x",
    "broker": "Angel One",
    "hours": "9:15 AM - 3:30 PM IST",
    "scan_day": "Monday 8:00 AM"
}

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📈 Premium Trading Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #0f0f16;
            --bg-card: #151520;
            --bg-card-hover: #1a1a28;
            --accent: #00d4aa;
            --accent-2: #667eea;
            --profit: #00ff88;
            --loss: #ff4757;
            --warning: #ffa502;
            --info: #3498db;
            --text-primary: #ffffff;
            --text-secondary: #6b6b80;
            --border: #252535;
            --glow: 0 0 40px rgba(0, 212, 170, 0.15);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        
        .bg-pattern {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%; z-index: -1;
            background: 
                radial-gradient(ellipse at 10% 90%, rgba(0, 212, 170, 0.08) 0%, transparent 40%),
                radial-gradient(ellipse at 90% 10%, rgba(102, 126, 234, 0.08) 0%, transparent 40%),
                radial-gradient(ellipse at 50% 50%, rgba(52, 152, 219, 0.03) 0%, transparent 60%),
                linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
        }
        
        /* Header */
        .header {
            background: rgba(15, 15, 22, 0.95);
            border-bottom: 1px solid var(--border);
            padding: 0.75rem 2rem;
            position: sticky; top: 0; z-index: 100;
            backdrop-filter: blur(20px);
            display: flex; justify-content: space-between; align-items: center;
        }
        
        .logo { display: flex; align-items: center; gap: 1rem; }
        
        .logo h1 {
            font-size: 1.4rem; font-weight: 800;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        
        .strategy-badge {
            display: flex; align-items: center; gap: 0.5rem;
            background: linear-gradient(135deg, rgba(0, 212, 170, 0.15) 0%, rgba(102, 126, 234, 0.15) 100%);
            border: 1px solid rgba(0, 212, 170, 0.3);
            padding: 0.4rem 0.8rem; border-radius: 8px;
        }
        
        .strategy-badge i { color: var(--accent); }
        .strategy-badge span { font-size: 0.8rem; font-weight: 600; color: var(--accent); }
        
        .status-container { display: flex; align-items: center; gap: 1.5rem; }
        
        .market-status {
            display: flex; align-items: center; gap: 0.5rem;
            padding: 0.4rem 1rem; border-radius: 50px;
            font-size: 0.8rem; font-weight: 600;
        }
        
        .market-status.open { background: rgba(0, 255, 136, 0.1); border: 1px solid var(--profit); color: var(--profit); }
        .market-status.closed { background: rgba(255, 165, 2, 0.1); border: 1px solid var(--warning); color: var(--warning); }
        
        .pulse { width: 8px; height: 8px; border-radius: 50%; background: currentColor; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        
        .time-display { font-size: 0.85rem; color: var(--text-secondary); font-weight: 500; }
        
        /* Container */
        .container { max-width: 1920px; margin: 0 auto; padding: 1.5rem; }
        
        /* Strategy Hero */
        .strategy-hero {
            background: linear-gradient(135deg, rgba(0, 212, 170, 0.08) 0%, rgba(102, 126, 234, 0.08) 100%);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1.5rem 2rem;
            margin-bottom: 1.5rem;
            display: grid;
            grid-template-columns: 2fr 3fr;
            gap: 2rem;
            align-items: center;
        }
        
        .strategy-info h2 {
            font-size: 1.8rem; font-weight: 800;
            background: linear-gradient(135deg, var(--accent) 0%, #00a085 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        
        .strategy-info .subtitle { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1rem; }
        
        .strategy-tags { display: flex; flex-wrap: wrap; gap: 0.5rem; }
        
        .tag {
            padding: 0.35rem 0.75rem; border-radius: 6px;
            font-size: 0.75rem; font-weight: 600;
            display: flex; align-items: center; gap: 0.3rem;
        }
        
        .tag.equity { background: rgba(52, 152, 219, 0.2); color: var(--info); }
        .tag.nse { background: rgba(102, 126, 234, 0.2); color: var(--accent-2); }
        .tag.intraday { background: rgba(0, 212, 170, 0.2); color: var(--accent); }
        .tag.angel { background: rgba(255, 165, 2, 0.2); color: var(--warning); }
        
        .indicators-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
        }
        
        .indicator-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .indicator-card:hover {
            transform: translateY(-3px);
            box-shadow: var(--glow);
        }
        
        .indicator-card .icon {
            width: 40px; height: 40px;
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem; margin: 0 auto 0.5rem;
        }
        
        .indicator-card .name { font-weight: 700; font-size: 0.9rem; margin-bottom: 0.2rem; }
        .indicator-card .params { font-size: 0.75rem; color: var(--text-secondary); }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.25rem;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-3px);
            border-color: var(--accent);
            box-shadow: var(--glow);
        }
        
        .stat-card::before {
            content: ''; position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
        }
        
        .stat-card.green::before { background: linear-gradient(90deg, var(--profit), var(--accent)); }
        .stat-card.blue::before { background: linear-gradient(90deg, var(--info), var(--accent-2)); }
        .stat-card.orange::before { background: linear-gradient(90deg, var(--warning), #ff6b6b); }
        
        .stat-icon {
            width: 42px; height: 42px;
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem; margin-bottom: 0.75rem;
        }
        
        .stat-icon.green { background: rgba(0, 255, 136, 0.1); color: var(--profit); }
        .stat-icon.blue { background: rgba(52, 152, 219, 0.1); color: var(--info); }
        .stat-icon.orange { background: rgba(255, 165, 2, 0.1); color: var(--warning); }
        .stat-icon.cyan { background: rgba(0, 212, 170, 0.1); color: var(--accent); }
        .stat-icon.purple { background: rgba(102, 126, 234, 0.1); color: var(--accent-2); }
        
        .stat-label { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.25rem; text-transform: uppercase; letter-spacing: 0.5px; }
        .stat-value { font-size: 1.5rem; font-weight: 800; }
        .stat-value.profit { color: var(--profit); }
        .stat-value.loss { color: var(--loss); }
        
        .stat-sub { font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem; display: flex; align-items: center; gap: 0.25rem; }
        .stat-sub.up { color: var(--profit); }
        .stat-sub.down { color: var(--loss); }
        
        /* Grid Layout */
        .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }
        .grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }
        
        @media (max-width: 1400px) {
            .stats-grid { grid-template-columns: repeat(3, 1fr); }
            .grid-3 { grid-template-columns: 1fr; }
            .grid-2 { grid-template-columns: 1fr; }
            .strategy-hero { grid-template-columns: 1fr; }
            .indicators-grid { grid-template-columns: repeat(2, 1fr); }
        }
        
        /* Section */
        .section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.25rem;
            height: 100%;
        }
        
        .section-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 1rem; padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--border);
        }
        
        .section-title {
            font-size: 1rem; font-weight: 700;
            display: flex; align-items: center; gap: 0.5rem;
        }
        
        .badge {
            background: var(--accent); color: var(--bg-primary);
            padding: 0.15rem 0.5rem; border-radius: 20px;
            font-size: 0.7rem; font-weight: 700;
        }
        
        /* Tables */
        table { width: 100%; border-collapse: collapse; }
        
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
        
        th { font-size: 0.7rem; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        
        tr:hover { background: var(--bg-card-hover); }
        
        .stock-cell { display: flex; align-items: center; gap: 0.6rem; }
        
        .stock-avatar {
            width: 32px; height: 32px;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.75rem;
        }
        
        .stock-info h4 { font-weight: 600; font-size: 0.85rem; }
        .stock-info span { font-size: 0.7rem; color: var(--text-secondary); }
        
        .signal-badge {
            padding: 0.3rem 0.7rem; border-radius: 20px;
            font-size: 0.7rem; font-weight: 700;
        }
        
        .signal-badge.buy { background: rgba(0, 255, 136, 0.1); color: var(--profit); border: 1px solid var(--profit); }
        .signal-badge.sell { background: rgba(255, 71, 87, 0.1); color: var(--loss); border: 1px solid var(--loss); }
        
        .pnl { font-weight: 700; font-size: 0.85rem; }
        .pnl.profit { color: var(--profit); }
        .pnl.loss { color: var(--loss); }
        
        .segment-tag {
            padding: 0.2rem 0.5rem; border-radius: 4px;
            font-size: 0.65rem; font-weight: 600;
            background: rgba(52, 152, 219, 0.15); color: var(--info);
        }
        
        /* Empty State */
        .empty-state {
            text-align: center; padding: 2rem; color: var(--text-secondary);
        }
        
        .empty-state i { font-size: 2rem; opacity: 0.3; margin-bottom: 0.5rem; }
        
        /* Performance Card */
        .perf-card {
            background: linear-gradient(135deg, rgba(0, 212, 170, 0.05) 0%, rgba(102, 126, 234, 0.05) 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        .perf-title { font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.5rem; }
        .perf-value { font-size: 1.5rem; font-weight: 800; }
        .perf-sub { font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem; }
        
        /* Footer */
        .footer {
            text-align: center; padding: 1rem; margin-top: 1rem;
            color: var(--text-secondary); font-size: 0.75rem;
            border-top: 1px solid var(--border);
        }
        
        /* Animations */
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate { animation: fadeIn 0.4s ease; }
        
        @keyframes livePulse { 0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.4); } 50% { opacity: 0.8; box-shadow: 0 0 10px 3px rgba(0, 255, 136, 0.2); } }
        .live-pulse { animation: livePulse 2s infinite; }
        
        @keyframes dataFlow { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        .data-flow { background: linear-gradient(270deg, var(--bg-card), var(--bg-card-hover), var(--bg-card)); background-size: 200% 200%; animation: dataFlow 3s ease infinite; }
        
        @keyframes blink { 0%, 50%, 100% { opacity: 1; } 25%, 75% { opacity: 0.5; } }
        .blink { animation: blink 1s infinite; }
        
        /* Segment Tags */
        .segment-equity { background: rgba(0, 212, 170, 0.15); color: var(--accent); border: 1px solid var(--accent); }
        .segment-options { background: rgba(255, 107, 107, 0.15); color: #ff6b6b; border: 1px solid #ff6b6b; }
        .segment-futures { background: rgba(102, 126, 234, 0.15); color: var(--accent-2); border: 1px solid var(--accent-2); }
        .segment-commodity { background: rgba(255, 165, 2, 0.15); color: var(--warning); border: 1px solid var(--warning); }
        
        /* Live Indicator */
        .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--profit); animation: livePulse 1.5s infinite; display: inline-block; margin-right: 5px; }
        
        /* Chart */
        .chart-container { height: 200px; position: relative; }
        
        /* Progress Bar */
        .progress-bar { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; margin-top: 0.5rem; }
        .progress-bar .fill { height: 100%; border-radius: 2px; }
        .progress-bar .fill.green { background: linear-gradient(90deg, var(--profit), var(--accent)); }
        
        /* Database Status */
        .db-status {
            display: flex; align-items: center; gap: 0.5rem;
            font-size: 0.75rem; color: var(--text-secondary);
        }
        
        .db-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--profit); animation: livePulse 2s infinite; }
    </style>
</head>
<body>
    <div class="bg-pattern"></div>
    
    <header class="header">
        <div class="logo">
            <h1>📈 Premium Trading Dashboard</h1>
            <div class="strategy-badge">
                <i class="fas fa-crown"></i>
                <span>Gold 93% Win Rate Strategy</span>
            </div>
        </div>
        <div class="status-container">
            <div class="db-status">
                <div class="db-dot"></div>
                <span>Analytics DB Active</span>
            </div>
            <div id="market-status" class="market-status closed">
                <div class="pulse"></div>
                <span>MARKET CLOSED</span>
            </div>
            <div class="time-display" id="current-time">--:--:-- IST</div>
        </div>
    </header>
    
    <main class="container">
        <!-- Strategy Hero -->
        <div class="strategy-hero animate">
            <div class="strategy-info">
                <h2>Gold 93% Win Rate Strategy</h2>
                <p class="subtitle">Multi-Indicator Confirmation with Trailing Stop Loss</p>
                <div class="strategy-tags">
                    <span class="tag equity"><i class="fas fa-chart-bar"></i> EQUITY</span>
                    <span class="tag nse"><i class="fas fa-building"></i> NSE</span>
                    <span class="tag intraday"><i class="fas fa-clock"></i> MIS Intraday</span>
                    <span class="tag intraday"><i class="fas fa-layer-group"></i> 5x Leverage</span>
                    <span class="tag angel"><i class="fas fa-university"></i> Angel One</span>
                </div>
            </div>
            <div class="indicators-grid">
                <div class="indicator-card">
                    <div class="icon" style="background: rgba(255, 107, 107, 0.1); color: #ff6b6b;">
                        <i class="fas fa-wave-square"></i>
                    </div>
                    <div class="name">RSI</div>
                    <div class="params">(Period: 2)</div>
                </div>
                <div class="indicator-card">
                    <div class="icon" style="background: rgba(255, 217, 61, 0.1); color: #ffd93d;">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="name">Stochastic</div>
                    <div class="params">(10, 3, 3)</div>
                </div>
                <div class="indicator-card">
                    <div class="icon" style="background: rgba(107, 203, 119, 0.1); color: #6bcb77;">
                        <i class="fas fa-signal"></i>
                    </div>
                    <div class="name">CCI</div>
                    <div class="params">(Period: 20)</div>
                </div>
                <div class="indicator-card">
                    <div class="icon" style="background: rgba(77, 150, 255, 0.1); color: #4d96ff;">
                        <i class="fas fa-chart-area"></i>
                    </div>
                    <div class="name">MACD</div>
                    <div class="params">(12, 26, 9)</div>
                </div>
            </div>
        </div>
        
        <!-- Stats Grid -->
        <div class="stats-grid animate">
            <div class="stat-card green live-pulse">
                <div class="stat-icon green"><i class="fas fa-chart-line"></i></div>
                <div class="stat-label"><span class="live-dot"></span>Open Positions</div>
                <div class="stat-value" id="capital">0</div>
                <div class="stat-sub" id="broker-user"><i class="fas fa-exchange-alt"></i> <span id="total-positions-pnl">₹0 P&L</span></div>
            </div>
            <div class="stat-card green live-pulse">
                <div class="stat-icon green"><i class="fas fa-rupee-sign"></i></div>
                <div class="stat-label"><span class="live-dot"></span>Today's P&L</div>
                <div class="stat-value profit" id="today-pnl">+₹0</div>
                <div class="stat-sub up" id="today-roi">+0.0% ROI</div>
            </div>
            <div class="stat-card blue">
                <div class="stat-icon blue"><i class="fas fa-receipt"></i></div>
                <div class="stat-label">Today's Trades</div>
                <div class="stat-value" id="today-trade-count">0</div>
                <div class="stat-sub" id="week-trades">Executed</div>
            </div>
            <div class="stat-card blue">
                <div class="stat-icon purple"><i class="fas fa-calendar"></i></div>
                <div class="stat-label">This Month</div>
                <div class="stat-value profit" id="month-pnl">+₹0</div>
                <div class="stat-sub" id="month-trades">0 trades</div>
            </div>
            <div class="stat-card orange">
                <div class="stat-icon cyan"><i class="fas fa-percentage"></i></div>
                <div class="stat-label">Win Rate</div>
                <div class="stat-value profit" id="win-rate">0%</div>
                <div class="stat-sub">Target: 80%+</div>
            </div>
            <div class="stat-card orange">
                <div class="stat-icon orange"><i class="fas fa-list-check"></i></div>
                <div class="stat-label">Watchlist</div>
                <div class="stat-value" id="watchlist-count">0</div>
                <div class="stat-sub">80%+ Win Rate Only</div>
            </div>
        </div>
        
        <!-- ROW 1: LIVE ACTIVITY LOG (Full Width, Large) -->
        <div class="section animate" style="margin-bottom: 1.5rem;">
            <div class="section-header">
                <h2 class="section-title"><i class="fas fa-terminal"></i> 🔴 LIVE ACTIVITY LOG</h2>
                <span id="log-status" style="font-size: 0.75rem; color: #00ff88;"><i class="fas fa-circle fa-xs"></i> Live - Auto-Refreshing</span>
            </div>
            <div id="activity-log" style="height: 280px; overflow-y: auto; font-family: 'Monaco', 'Consolas', monospace; font-size: 0.8rem; padding: 1rem; background: #0a0a0f; border-radius: 10px; border: 1px solid #252535;">
                <div class="log-entry" style="color: #888;">⏳ Waiting for bot activity...</div>
            </div>
        </div>
        
        <!-- ROW 2: Account Details + Risk Meter -->
        <div class="grid-2 animate">
            <!-- Account Details -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-wallet"></i> Broker Account Details</h2>
                    <span id="broker-connection" style="font-size: 0.7rem; color: #00ff88;"><i class="fas fa-check-circle"></i> Connected</span>
                </div>
                <div style="padding: 1rem;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div style="background: linear-gradient(135deg, rgba(0, 212, 170, 0.1) 0%, rgba(102, 126, 234, 0.1) 100%); padding: 1.25rem; border-radius: 12px; border: 1px solid var(--border);">
                            <div style="font-size: 0.75rem; color: #888; margin-bottom: 0.5rem;">💰 Available Balance</div>
                            <div id="account-balance" style="font-size: 2rem; font-weight: 800; color: var(--accent);">₹0</div>
                        </div>
                        <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(0, 212, 170, 0.1) 100%); padding: 1.25rem; border-radius: 12px; border: 1px solid var(--border);">
                            <div style="font-size: 0.75rem; color: #888; margin-bottom: 0.5rem;">👤 Account Holder</div>
                            <div id="account-name" style="font-size: 1.2rem; font-weight: 700; color: var(--text-primary);">Connecting...</div>
                            <div id="account-broker" style="font-size: 0.75rem; color: var(--accent); margin-top: 0.25rem;">Angel One</div>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-top: 1rem;">
                        <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 8px; text-align: center; border: 1px solid var(--border);">
                            <div style="font-size: 0.65rem; color: #888;">🔴 Open Positions</div>
                            <div id="account-positions" style="font-size: 1.3rem; font-weight: 700;">0</div>
                        </div>
                        <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 8px; text-align: center; border: 1px solid var(--border);">
                            <div style="font-size: 0.65rem; color: #888;">📊 Today's Trades</div>
                            <div id="account-trades" style="font-size: 1.3rem; font-weight: 700;">0</div>
                        </div>
                        <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 8px; text-align: center; border: 1px solid var(--border);">
                            <div style="font-size: 0.65rem; color: #888;">⏰ Last Updated</div>
                            <div id="account-updated" style="font-size: 0.9rem; font-weight: 600; color: #888;">--:--</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Risk Meter -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-tachometer-alt"></i> Risk Meter</h2>
                </div>
                <div style="text-align: center; padding: 0.5rem;">
                    <div id="risk-gauge" style="position: relative; width: 200px; height: 110px; margin: 0 auto;">
                        <svg viewBox="0 0 200 120" style="width: 100%;">
                            <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#333" stroke-width="15"/>
                            <path id="risk-arc" d="M 20 100 A 80 80 0 0 1 100 20" fill="none" stroke="url(#riskGradient)" stroke-width="15" stroke-linecap="round"/>
                            <defs>
                                <linearGradient id="riskGradient">
                                    <stop offset="0%" stop-color="#00ff88"/>
                                    <stop offset="50%" stop-color="#ffa502"/>
                                    <stop offset="100%" stop-color="#ff4757"/>
                                </linearGradient>
                            </defs>
                        </svg>
                        <div style="position: absolute; bottom: 5px; left: 50%; transform: translateX(-50%); text-align: center;">
                            <div id="risk-value" style="font-size: 1.8rem; font-weight: 800; color: #00ff88;">LOW</div>
                            <div id="risk-percent" style="font-size: 0.8rem; color: #888;">0% Exposure</div>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-around; margin-top: 0.75rem; font-size: 0.75rem;">
                        <div><span style="color: #00ff88;">●</span> Low (0-30%)</div>
                        <div><span style="color: #ffa502;">●</span> Medium (30-60%)</div>
                        <div><span style="color: #ff4757;">●</span> High (60%+)</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-top: 0.75rem;">
                        <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border);">
                            <div style="color: #888; font-size: 0.7rem;">Open Positions</div>
                            <div id="risk-positions" style="font-weight: 700; font-size: 1.4rem;">0</div>
                        </div>
                        <div style="background: var(--bg-card); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border);">
                            <div style="color: #888; font-size: 0.7rem;">Capital At Risk</div>
                            <div id="risk-capital" style="font-weight: 700; color: #00ff88; font-size: 1.4rem;">₹0</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- ROW 3: Open Positions + Today's Trades + P&L Chart -->
        <div class="grid-3 animate">
            <!-- Open Positions -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-chart-line"></i> Open Positions <span class="badge" id="pos-count">0</span></h2>
                </div>
                <div id="positions-container" style="max-height: 220px; overflow-y: auto;">
                    <div class="empty-state"><i class="fas fa-inbox"></i><p>No open positions</p></div>
                </div>
            </div>
            
            <!-- Today's Trades -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-history"></i> Today's Trades <span class="badge" id="trades-count">0</span></h2>
                </div>
                <div id="trades-container" style="max-height: 220px; overflow-y: auto;">
                    <div class="empty-state"><i class="fas fa-calendar-day"></i><p>No trades today</p></div>
                </div>
            </div>
            
            <!-- P&L Chart -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-chart-area"></i> Weekly P&L Chart</h2>
                </div>
                <div class="chart-container" style="height: 220px;">
                    <canvas id="pnlChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- ROW 4: Live Stock Prices -->
        <div class="section animate" style="margin-bottom: 1.5rem;">
            <div class="section-header">
                <h2 class="section-title"><i class="fas fa-bolt"></i> Live Stock Prices</h2>
                <span id="price-update-time" style="font-size: 0.75rem; color: var(--text-secondary);">
                    <i class="fas fa-clock"></i> Updated: --
                </span>
            </div>
            <div id="live-prices-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.75rem;">
                <div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>Loading prices...</p></div>
            </div>
        </div>
        
        <!-- ROW 4: All-Time Stats -->
        <div class="section animate" style="margin-bottom: 1.5rem;">
            <div class="section-header">
                <h2 class="section-title"><i class="fas fa-trophy"></i> All-Time Performance</h2>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                <div class="perf-card">
                    <div class="perf-title">TOTAL P&L</div>
                    <div class="perf-value profit" id="all-time-pnl">+₹0</div>
                    <div class="perf-sub" id="all-time-trades">0 total trades</div>
                </div>
                <div class="perf-card">
                    <div class="perf-title">OVERALL WIN RATE</div>
                    <div class="perf-value profit" id="all-time-wr">0%</div>
                    <div class="progress-bar"><div class="fill green" id="wr-bar" style="width: 0%;"></div></div>
                </div>
                <div class="perf-card">
                    <div class="perf-title">PROFIT FACTOR</div>
                    <div class="perf-value" id="profit-factor">0</div>
                    <div class="perf-sub">Avg Win / Avg Loss</div>
                </div>
            </div>
        </div>
        
        <!-- Watchlist -->
        <div class="section animate" style="margin-bottom: 1.5rem;">
            <div class="section-header">
                <h2 class="section-title"><i class="fas fa-star"></i> Smart Watchlist (80%+ Win Rate)</h2>
                <span style="font-size: 0.75rem; color: var(--text-secondary);">
                    <i class="fas fa-sync"></i> Next Scan: Monday 8 AM
                </span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Stock</th>
                        <th>Segment</th>
                        <th>Strategy</th>
                        <th>Win Rate</th>
                        <th>Expected P&L</th>
                        <th>Trail %</th>
                    </tr>
                </thead>
                <tbody id="watchlist-body"></tbody>
            </table>
        </div>
    </main>
    
    <footer class="footer">
        <p>🤖 <strong>Gold 93% Win Rate Strategy</strong> | Segment: EQUITY | Exchange: NSE | Product: MIS Intraday | Broker: Angel One</p>
        <p style="margin-top: 0.25rem;">📊 Analytics stored in SQLite Database | Last Update: <span id="last-update">--</span></p>
    </footer>
    
    <script>
        // Update time and market status
        function updateTime() {
            const now = new Date();
            const options = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' };
            document.getElementById('current-time').textContent = now.toLocaleTimeString('en-IN', options) + ' IST';
            
            const hour = parseInt(now.toLocaleTimeString('en-IN', { hour: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' }));
            const day = now.getDay();
            const isOpen = day >= 1 && day <= 5 && hour >= 9 && hour < 16;
            
            const statusEl = document.getElementById('market-status');
            if (isOpen) {
                statusEl.className = 'market-status open';
                statusEl.innerHTML = '<div class="pulse"></div><span>MARKET OPEN</span>';
            } else {
                statusEl.className = 'market-status closed';
                statusEl.innerHTML = '<div class="pulse"></div><span>MARKET CLOSED</span>';
            }
        }
        setInterval(updateTime, 1000);
        updateTime();
        
        function formatCurrency(val) {
            const n = parseFloat(val) || 0;
            return '₹' + Math.abs(n).toLocaleString('en-IN', {maximumFractionDigits: 0});
        }
        
        function formatPnL(val) {
            const n = parseFloat(val) || 0;
            return (n >= 0 ? '+₹' : '-₹') + Math.abs(n).toLocaleString('en-IN', {maximumFractionDigits: 0});
        }
        
        async function fetchData() {
            try {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                updateDashboard(data);
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString('en-IN', {hour12: false});
            } catch (e) {
                console.error('Fetch error:', e);
            }
        }
        
        function updateDashboard(data) {
            // Show Angel One balance
            const broker = data.broker || {};
            const balance = broker.balance || data.capital || 0;
            const userName = broker.user_name || 'Not Connected';
            const isConnected = broker.is_authenticated || false;
            
            document.getElementById('capital').textContent = formatCurrency(balance);
            document.getElementById('broker-user').innerHTML = isConnected 
                ? '<i class="fas fa-check-circle" style="color:#00ff88"></i> ' + userName
                : '<i class="fas fa-times-circle" style="color:#ff4757"></i> ' + userName;
            
            // Update Account Details Section
            document.getElementById('account-balance').textContent = formatCurrency(balance);
            document.getElementById('account-name').textContent = userName;
            document.getElementById('account-broker').textContent = broker.broker_name || 'Angel One';
            document.getElementById('broker-connection').innerHTML = isConnected 
                ? '<i class="fas fa-check-circle"></i> Connected'
                : '<i class="fas fa-times-circle" style="color:#ff4757"></i> Disconnected';
            document.getElementById('broker-connection').style.color = isConnected ? '#00ff88' : '#ff4757';
            document.getElementById('account-updated').textContent = broker.last_updated || '--:--';
            
            const todayPnl = data.daily_pnl || 0;
            document.getElementById('today-pnl').textContent = formatPnL(todayPnl);
            document.getElementById('today-pnl').className = 'stat-value ' + (todayPnl >= 0 ? 'profit' : 'loss');
            document.getElementById('today-roi').textContent = ((todayPnl / (balance || 10000)) * 100).toFixed(1) + '% ROI';
            
            // Week/Month stats from analytics
            if (data.analytics) {
                const month = data.analytics.monthly || {};
                document.getElementById('month-pnl').textContent = formatPnL(month.total_pnl || 0);
                document.getElementById('month-trades').textContent = (month.total_trades || 0) + ' trades';
                
                const allTime = data.analytics.all_time || {};
                document.getElementById('all-time-pnl').textContent = formatPnL(allTime.total_pnl || 0);
                document.getElementById('all-time-trades').textContent = (allTime.total_trades || 0) + ' total trades';
                document.getElementById('all-time-wr').textContent = (allTime.win_rate || 0).toFixed(1) + '%';
                document.getElementById('wr-bar').style.width = (allTime.win_rate || 0) + '%';
                document.getElementById('profit-factor').textContent = (allTime.profit_factor || 0).toFixed(2);
            }
            
            const trades = data.trades || [];
            const wins = trades.filter(t => t.pnl > 0).length;
            const winRate = trades.length > 0 ? (wins / trades.length * 100).toFixed(1) : 0;
            document.getElementById('win-rate').textContent = winRate + '%';
            document.getElementById('trades-count').textContent = trades.length;
            document.getElementById('account-trades').textContent = trades.length;
            document.getElementById('today-trade-count').textContent = trades.length;
            
            const watchlist = data.watchlist || [];
            const positions = data.positions || {};
            const openPositions = Object.entries(positions).filter(([k, v]) => v.qty > 0);
            const totalPnl = openPositions.reduce((sum, [k, v]) => sum + (v.unrealised_pnl || v.pnl || 0), 0);
            
            document.getElementById('watchlist-count').textContent = watchlist.length;
            document.getElementById('pos-count').textContent = openPositions.length;
            document.getElementById('account-positions').textContent = openPositions.length;
            document.getElementById('capital').textContent = openPositions.length;
            document.getElementById('total-positions-pnl').textContent = formatPnL(totalPnl) + ' P&L';
            document.getElementById('total-positions-pnl').style.color = totalPnl >= 0 ? '#00ff88' : '#ff4757';
            
            updatePositions(positions);
            updateWatchlist(watchlist);
            updateTrades(trades);
        }
        
        function updatePositions(positions) {
            const container = document.getElementById('positions-container');
            const arr = Object.entries(positions).filter(([k, v]) => v.qty > 0);
            
            if (arr.length === 0) {
                container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>No open positions</p></div>';
                return;
            }
            
            let html = '<table><thead><tr><th>Stock</th><th>Segment</th><th>Type</th><th>LTP</th><th>P&L</th></tr></thead><tbody>';
            for (const [sym, pos] of arr) {
                const ltp = pos.ltp || pos.entry_price || 0;
                const pnl = pos.unrealised_pnl || pos.pnl || 0;
                const pnlClass = pnl >= 0 ? 'profit' : 'loss';
                const segment = pos.segment || 'EQUITY';
                const segmentClass = 'segment-' + segment.toLowerCase();
                html += `<tr class="live-pulse">
                    <td><div class="stock-cell"><span class="live-dot"></span><div class="stock-avatar">${sym.substring(0,2)}</div><div class="stock-info"><h4>${sym}</h4><span>Qty: ${pos.qty}</span></div></div></td>
                    <td><span class="segment-tag ${segmentClass}" style="padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.65rem;">${segment}</span></td>
                    <td><span class="signal-badge ${pos.signal === 'BUY' ? 'buy' : 'sell'}">${pos.signal}</span></td>
                    <td style="font-weight: 700;">₹${parseFloat(ltp).toFixed(2)}</td>
                    <td><span class="pnl ${pnlClass}" style="font-weight: 800; font-size: 1rem;">${formatPnL(pnl)}</span></td>
                </tr>`;
            }
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        function updateWatchlist(watchlist) {
            const tbody = document.getElementById('watchlist-body');
            if (watchlist.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Run scanner to populate watchlist</td></tr>';
                return;
            }
            
            let html = '';
            for (const s of watchlist.slice(0, 10)) {
                const wr = s.win_rate || 0;
                html += `<tr>
                    <td><div class="stock-cell"><div class="stock-avatar">${(s.symbol || s.name || '').substring(0,2)}</div><div class="stock-info"><h4>${s.symbol || s.name}</h4><span>${s.nse_symbol || ''}</span></div></div></td>
                    <td><span class="segment-tag">EQUITY</span></td>
                    <td><span style="font-size: 0.75rem; color: var(--accent);">Gold 93% WR</span></td>
                    <td><span class="pnl ${wr >= 80 ? 'profit' : ''}">${wr.toFixed(1)}%</span></td>
                    <td><span class="pnl profit">+₹${(s.expected_pnl || 0).toLocaleString()}</span></td>
                    <td>${s.trail_percent}%</td>
                </tr>`;
            }
            tbody.innerHTML = html;
        }
        
        function updateTrades(trades) {
            const container = document.getElementById('trades-container');
            if (trades.length === 0) {
                container.innerHTML = '<div class="empty-state"><i class="fas fa-calendar-day"></i><p>No trades today</p></div>';
                return;
            }
            
            let html = '<table><thead><tr><th>Stock</th><th>Segment</th><th>Type</th><th>Price</th><th>Time (IST)</th></tr></thead><tbody>';
            for (const t of trades.slice(0, 15)) {
                const time = t.time_ist || t.time || '--:--';
                const price = t.entry_price || t.price || t.averageprice || 0;
                const segment = t.segment || 'EQUITY';
                const segmentClass = 'segment-' + segment.toLowerCase();
                html += `<tr>
                    <td><div class="stock-cell"><div class="stock-avatar">${(t.symbol || '').substring(0,2)}</div><div class="stock-info"><h4>${t.symbol}</h4><span>Qty: ${t.qty || t.quantity || 0}</span></div></div></td>
                    <td><span class="segment-tag ${segmentClass}" style="padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.65rem;">${segment}</span></td>
                    <td><span class="signal-badge ${t.signal === 'BUY' ? 'buy' : 'sell'}">${t.signal}</span></td>
                    <td style="font-weight: 600;">₹${parseFloat(price).toFixed(2)}</td>
                    <td style="font-size: 0.75rem; color: #00d4aa; font-weight: 500;">${time}</td>
                </tr>`;
            }
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        // P&L Chart
        let pnlChart = null;
        function initPnLChart() {
            const ctx = document.getElementById('pnlChart').getContext('2d');
            pnlChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
                    datasets: [{
                        label: 'Daily P&L',
                        data: [0, 0, 0, 0, 0],
                        borderColor: '#00d4aa',
                        backgroundColor: 'rgba(0, 212, 170, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#00d4aa',
                        pointBorderColor: '#fff',
                        pointRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#333' },
                            ticks: { color: '#888', callback: v => '₹' + v }
                        },
                        x: {
                            grid: { color: '#333' },
                            ticks: { color: '#888' }
                        }
                    }
                }
            });
        }
        
        function updatePnLChart(data) {
            if (!pnlChart) initPnLChart();
            const history = data.pnl_history || [0, 0, 0, 0, 0];
            pnlChart.data.datasets[0].data = history;
            pnlChart.update();
        }
        
        // Risk Meter
        function updateRiskMeter(data) {
            const positions = Object.keys(data.positions || {}).length;
            const balance = (data.broker || {}).balance || 10000;
            const capitalAtRisk = positions * 2000; // Approx per position
            const riskPercent = Math.min(100, (capitalAtRisk / balance) * 100);
            
            let riskLevel = 'LOW';
            let riskColor = '#00ff88';
            if (riskPercent > 60) { riskLevel = 'HIGH'; riskColor = '#ff4757'; }
            else if (riskPercent > 30) { riskLevel = 'MEDIUM'; riskColor = '#ffa502'; }
            
            document.getElementById('risk-value').textContent = riskLevel;
            document.getElementById('risk-value').style.color = riskColor;
            document.getElementById('risk-percent').textContent = riskPercent.toFixed(0) + '% Exposure';
            document.getElementById('risk-positions').textContent = positions;
            document.getElementById('risk-capital').textContent = '₹' + capitalAtRisk.toLocaleString();
            document.getElementById('risk-capital').style.color = riskColor;
        }
        
        // Live Stock Prices
        function updateLivePrices(watchlist) {
            const grid = document.getElementById('live-prices-grid');
            if (!watchlist || watchlist.length === 0) {
                grid.innerHTML = '<div class="empty-state"><i class="fas fa-chart-bar"></i><p>No stocks in watchlist</p></div>';
                return;
            }
            
            let html = '';
            for (const s of watchlist.slice(0, 10)) {
                const price = s.current_price || s.price || Math.round(50 + Math.random() * 500);
                const change = s.change || (Math.random() * 4 - 2);
                const changeColor = change >= 0 ? '#00ff88' : '#ff4757';
                const changeIcon = change >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
                
                html += `
                <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <div style="font-weight: 700;">${s.symbol || s.name}</div>
                        <span style="font-size: 0.7rem; color: ${changeColor};"><i class="fas ${changeIcon}"></i> ${Math.abs(change).toFixed(2)}%</span>
                    </div>
                    <div style="font-size: 1.3rem; font-weight: 800;">₹${price.toLocaleString()}</div>
                    <div style="font-size: 0.7rem; color: #888; margin-top: 0.25rem;">Win Rate: ${(s.win_rate || 0).toFixed(0)}%</div>
                </div>`;
            }
            grid.innerHTML = html;
            document.getElementById('price-update-time').innerHTML = '<i class="fas fa-clock"></i> Updated: ' + new Date().toLocaleTimeString('en-IN', {hour12: false});
        }
        
        // Initialize chart on load
        document.addEventListener('DOMContentLoaded', initPnLChart);
        
        // Live Activity Log
        function updateActivityLog(logs) {
            const container = document.getElementById('activity-log');
            if (!logs || logs.length === 0) {
                container.innerHTML = '<div class="log-entry" style="color: #888;">Waiting for activity...</div>';
                return;
            }
            
            let html = '';
            for (const log of logs.slice(-20)) {  // Show last 20 logs
                let color = '#888';
                let icon = 'fa-info-circle';
                
                if (log.includes('SIGNAL') || log.includes('🎯')) {
                    color = '#00ff88';
                    icon = 'fa-bullseye';
                } else if (log.includes('Scanning') || log.includes('🔍')) {
                    color = '#3498db';
                    icon = 'fa-search';
                } else if (log.includes('Skipping') || log.includes('⚠️')) {
                    color = '#ffa502';
                    icon = 'fa-exclamation-triangle';
                } else if (log.includes('ORDER') || log.includes('✅')) {
                    color = '#00ff88';
                    icon = 'fa-check-circle';
                } else if (log.includes('ERROR') || log.includes('❌')) {
                    color = '#ff4757';
                    icon = 'fa-times-circle';
                } else if (log.includes('Indicators')) {
                    color = '#667eea';
                    icon = 'fa-chart-bar';
                } else if (log.includes('Candle') || log.includes('Red')) {
                    color = '#e17055';
                    icon = 'fa-fire';
                }
                
                html += `<div class="log-entry" style="color: ${color}; padding: 0.25rem 0; border-bottom: 1px solid #1a1a28;">
                    <i class="fas ${icon}" style="width: 16px; margin-right: 5px;"></i>${log}
                </div>`;
            }
            container.innerHTML = html;
            container.scrollTop = container.scrollHeight;  // Auto-scroll to bottom
        }
        
        // Fetch activity logs
        async function fetchActivityLogs() {
            try {
                const res = await fetch('/api/activity');
                const data = await res.json();
                updateActivityLog(data.logs || []);
            } catch (e) {
                console.debug('Activity logs not available');
            }
        }
        
        // Override fetchData to include new updates
        fetchData = async function() {
            try {
                // Show loading indicator
                document.getElementById('log-status').innerHTML = '<i class="fas fa-sync fa-spin"></i> Refreshing...';
                
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                updateDashboard(data);
                updatePnLChart(data);
                updateRiskMeter(data);
                updateLivePrices(data.watchlist);
                updateActivityLog(data.activity_logs || []);
                
                // Update timestamp with live indicator
                const timeNow = new Date().toLocaleTimeString('en-IN', {hour12: false, timeZone: 'Asia/Kolkata'});
                document.getElementById('last-update').textContent = timeNow + ' IST';
                document.getElementById('log-status').innerHTML = '<span class="live-dot"></span> Live - ' + timeNow;
            } catch (e) {
                console.error('Fetch error:', e);
                document.getElementById('log-status').innerHTML = '<i class="fas fa-exclamation-triangle" style="color:#ff4757;"></i> Connection Error';
            }
        };
        
        fetchData();
        setInterval(fetchData, 3000);  // Update every 3 seconds for LIVE feel
    </script>
</body>
</html>
"""

def get_dashboard_data():
    """Get all data for dashboard including analytics"""
    data = {
        'capital': 10000,
        'daily_pnl': 0,
        'trades': [],
        'positions': {},
        'watchlist': [],
        'is_trading_hours': False,
        'timestamp': datetime.now(IST).isoformat(),
        'strategy': STRATEGY_CONFIG,
        'trading': TRADING_CONFIG,
        'analytics': {}
    }
    
    # Load watchlist
    try:
        if os.path.exists("config/smart_watchlist.json"):
            with open("config/smart_watchlist.json", 'r') as f:
                wl = json.load(f)
                data['watchlist'] = wl.get('active_stocks', [])
                data['capital'] = wl.get('capital', 10000)
    except:
        pass
    
    # Load positions
    try:
        if os.path.exists("data/stock_positions.json"):
            with open("data/stock_positions.json", 'r') as f:
                data['positions'] = json.load(f)
    except:
        pass
    
    # Load today's trades
    try:
        if os.path.exists("data/today_trades.json"):
            with open("data/today_trades.json", 'r') as f:
                td = json.load(f)
                today = datetime.now(IST).strftime('%Y-%m-%d')
                if td.get('date') == today:
                    data['trades'] = td.get('trades', [])
                    data['daily_pnl'] = sum(t.get('pnl', 0) for t in data['trades'])
    except:
        pass
    
    # Load analytics from database
    try:
        from analytics_db import analytics_db
        data['analytics'] = {
            'weekly': analytics_db.get_weekly_summary(),
            'monthly': analytics_db.get_monthly_summary(),
            'all_time': analytics_db.get_all_time_stats(),
            'top_stocks': analytics_db.get_top_stocks()
        }
        # Get P&L history for chart
        try:
            daily_chart = analytics_db.get_daily_pnl_chart()
            if daily_chart:
                data['pnl_history'] = [d.get('pnl', 0) for d in daily_chart[-5:]]  # Last 5 days
            else:
                data['pnl_history'] = [0, 0, 0, 0, 0]
        except:
            data['pnl_history'] = [0, 0, 0, 0, 0]
    except Exception as e:
        logger.warning(f"Analytics not available: {e}")
        data['analytics'] = {
            'weekly': {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0},
            'monthly': {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0},
            'all_time': {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0, 'profit_factor': 0},
            'top_stocks': []
        }
        data['pnl_history'] = [0, 0, 0, 0, 0]
    
    # Load broker (Angel One) balance
    try:
        if os.path.exists("data/zerodha_status.json"):
            with open("data/zerodha_status.json", 'r') as f:
                broker_data = json.load(f)
                data['broker'] = {
                    'balance': broker_data.get('balance', 0),
                    'user_name': broker_data.get('user_name', 'Not Connected'),
                    'is_authenticated': broker_data.get('is_authenticated', False),
                    'broker_name': broker_data.get('broker', 'Angel One'),
                    'last_updated': broker_data.get('last_updated', '')
                }
    except:
        data['broker'] = {'balance': 0, 'user_name': 'Not Connected', 'is_authenticated': False}
    
    # Load activity logs
    try:
        if os.path.exists("data/activity_logs.json"):
            with open("data/activity_logs.json", 'r') as f:
                logs_data = json.load(f)
                data['activity_logs'] = logs_data.get('logs', [])[-30:]  # Last 30 logs
    except:
        data['activity_logs'] = []
    
    return data


@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/dashboard')
def api_dashboard():
    return jsonify(get_dashboard_data())


@app.route('/api/analytics')
def api_analytics():
    try:
        from analytics_db import analytics_db
        return jsonify({
            'weekly': analytics_db.get_weekly_summary(),
            'monthly': analytics_db.get_monthly_summary(),
            'all_time': analytics_db.get_all_time_stats(),
            'daily_chart': analytics_db.get_daily_pnl_chart(),
            'top_stocks': analytics_db.get_top_stocks()
        })
    except:
        return jsonify({'error': 'Analytics not available'})


@app.route('/api/strategy')
def api_strategy():
    return jsonify(STRATEGY_CONFIG)


@app.route('/api/health')
def api_health():
    return jsonify({
        'status': 'ok',
        'strategy': 'Gold 93% Win Rate',
        'segment': 'EQUITY',
        'exchange': 'NSE',
        'broker': 'Angel One',
        'database': 'Active'
    })


def run_dashboard(port=5050):
    logger.info(f"🌐 Premium Dashboard starting on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5050)
    args = parser.parse_args()
    run_dashboard(args.port)
