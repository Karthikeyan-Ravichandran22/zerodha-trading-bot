"""
Commodity Multi-Strategy Scanner
OPTIMIZED: Gold Only Mode (Silver/Crude disabled - underperform in backtests)

Gold Strategy Performance (1-month backtest):
- Win Rate: 51.6%
- Net Profit: ₹35,412
- Average Win: ₹4,231 (+10.5%)
- Average Loss: ₹2,152 (-5.4%)

Integrates with Angel One balance checking
"""

from datetime import datetime, timedelta, timezone
from loguru import logger
from typing import List, Dict, Optional

IST = timezone(timedelta(hours=5, minutes=30))

# Approximate margin requirements for MCX commodities (in INR)
COMMODITY_MARGINS = {
    'GOLD': 40000,    # Gold Mini ~₹40,000
    'SILVER': 30000,  # Silver Mini ~₹30,000 (DISABLED - underperforms)
    'CRUDE': 25000,   # Crude Oil ~₹25,000 (DISABLED - underperforms)
}

# Active commodities (only Gold is profitable based on backtests)
ACTIVE_COMMODITIES = ['GOLD']  # Set to ['GOLD', 'SILVER', 'CRUDE'] to enable all


class CommodityScanner:
    """
    Unified scanner for commodity strategies
    
    GOLD ONLY MODE (Default):
    - Silver and Crude are disabled by default
    - They can be enabled by modifying ACTIVE_COMMODITIES
    
    Gold Strategy: EMA 9/21 + Max 1 Cross + Momentum + MACD
    - 51.6% Win Rate
    - 2:1 Reward:Risk Ratio
    """
    
    def __init__(self, capital: float = None, angel_client=None):
        """
        Initialize commodity scanner
        
        Args:
            capital: Manual capital override (optional)
            angel_client: Angel One SmartConnect instance for balance checking
        """
        self.angel_client = angel_client
        self.angel_refresh_token = None
        self.manual_capital = capital
        self.available_balance = 0
        self.balance_checked = False
        
        # Import strategies
        from .gold_strategy import GoldStrategy
        from .silver_strategy import SilverStrategy
        from .crude_oil_strategy import CrudeOilStrategy
        
        # Initialize strategies (capital will be set after balance check)
        self.gold = GoldStrategy(20000)
        self.silver = SilverStrategy(20000)
        self.crude = CrudeOilStrategy(20000)
        
        self.strategies = {
            'GOLD': self.gold,
            'SILVER': self.silver,
            'CRUDE': self.crude
        }
        
        self.active_signals = []
        self.all_signals_history = []
        self.tradeable_commodities = []
    
    def check_balance(self) -> Dict:
        """
        Check available balance from Angel One
        Returns balance info and updates tradeable commodities
        """
        balance_info = {
            'available': 0,
            'source': 'unknown',
            'tradeable': [],
            'not_tradeable': [],
            'timestamp': datetime.now(IST).isoformat()
        }
        
        # Try to get balance from Angel One
        if self.angel_client:
            try:
                # Get funds using rmsLimit (Angel One API)
                funds = self.angel_client.rmsLimit()
                
                if funds.get('status'):
                    # Angel One returns balance in 'net' field
                    self.available_balance = float(funds['data'].get('net', 0))
                    balance_info['source'] = 'angel_one'
                    logger.info(f"💰 Angel One Balance: ₹{self.available_balance:,.2f}")
                else:
                    logger.warning(f"Angel One balance check failed: {funds.get('message')}")
                    if self.manual_capital:
                        self.available_balance = self.manual_capital
                        balance_info['source'] = 'manual_override'
                
            except Exception as e:
                logger.warning(f"Could not fetch Angel One balance: {e}")
                if self.manual_capital:
                    self.available_balance = self.manual_capital
                    balance_info['source'] = 'manual_override'
        
        # Use manual capital if no Angel One client
        elif self.manual_capital:
            self.available_balance = self.manual_capital
            balance_info['source'] = 'manual'
        
        balance_info['available'] = self.available_balance
        
        # Determine which commodities are tradeable
        self.tradeable_commodities = []
        for commodity, margin_required in COMMODITY_MARGINS.items():
            if self.available_balance >= margin_required:
                self.tradeable_commodities.append(commodity)
                balance_info['tradeable'].append({
                    'commodity': commodity,
                    'margin_required': margin_required
                })
            else:
                balance_info['not_tradeable'].append({
                    'commodity': commodity,
                    'margin_required': margin_required,
                    'shortfall': margin_required - self.available_balance
                })
        
        # Update strategy capitals
        if self.tradeable_commodities:
            capital_per = self.available_balance / len(self.tradeable_commodities)
            if 'GOLD' in self.tradeable_commodities:
                self.gold.capital = capital_per
            if 'SILVER' in self.tradeable_commodities:
                self.silver.capital = capital_per
            if 'CRUDE' in self.tradeable_commodities:
                self.crude.capital = capital_per
        
        self.balance_checked = True
        logger.info(f"📊 Tradeable commodities: {self.tradeable_commodities}")
        
        return balance_info
    
    def set_angel_client(self, client, refresh_token=None):
        """Set Angel One client for balance checking"""
        self.angel_client = client
        self.angel_refresh_token = refresh_token
        self.balance_checked = False
    
    def scan_all(self, check_balance: bool = True) -> List[Dict]:
        """
        Scan active commodities for signals
        
        Note: By default only GOLD is scanned (ACTIVE_COMMODITIES)
        Silver and Crude underperform in backtests
        
        Args:
            check_balance: If True, checks Angel One balance first
        """
        signals = []
        
        # Check balance if requested
        if check_balance and not self.balance_checked:
            balance_info = self.check_balance()
            if self.available_balance <= 0:
                logger.warning("⚠️ No available balance for commodity trading")
                return []
        
        # Only scan ACTIVE commodities that are also tradeable (have sufficient balance)
        commodities_to_scan = [c for c in ACTIVE_COMMODITIES if c in self.tradeable_commodities] if self.balance_checked else ACTIVE_COMMODITIES
        
        logger.info(f"🏆 Scanning: {commodities_to_scan} (Active: {ACTIVE_COMMODITIES})")
        
        # Gold
        if 'GOLD' in commodities_to_scan:
            try:
                gold_sig = self.gold.generate_signal()
                if gold_sig:
                    signals.append({
                        'commodity': 'GOLD',
                        'symbol': gold_sig.symbol,
                        'signal': gold_sig.signal,
                        'entry': gold_sig.entry_price,
                        'sl': gold_sig.stop_loss,
                        'target': gold_sig.target,
                        'confidence': gold_sig.confidence,
                        'reason': gold_sig.reason,
                        'margin_required': COMMODITY_MARGINS['GOLD'],
                        'timestamp': gold_sig.timestamp
                    })
                    logger.info(f"🥇 GOLD Signal: {gold_sig.signal} @ {gold_sig.entry_price}")
            except Exception as e:
                logger.error(f"Gold scan error: {e}")
        else:
            logger.debug("⚠️ GOLD skipped - insufficient balance")
        
        # Silver
        if 'SILVER' in commodities_to_scan:
            try:
                silver_sig = self.silver.generate_signal()
                if silver_sig:
                    signals.append({
                        'commodity': 'SILVER',
                        'symbol': silver_sig.symbol,
                        'signal': silver_sig.signal,
                        'entry': silver_sig.entry_price,
                        'sl': silver_sig.stop_loss,
                        'target': silver_sig.target,
                        'confidence': silver_sig.confidence,
                        'reason': silver_sig.reason,
                        'margin_required': COMMODITY_MARGINS['SILVER'],
                        'timestamp': silver_sig.timestamp
                    })
                    logger.info(f"🥈 SILVER Signal: {silver_sig.signal} @ {silver_sig.entry_price}")
            except Exception as e:
                logger.error(f"Silver scan error: {e}")
        else:
            logger.debug("⚠️ SILVER skipped - insufficient balance")
        
        # Crude Oil
        if 'CRUDE' in commodities_to_scan:
            try:
                crude_sig = self.crude.generate_signal()
                if crude_sig:
                    signals.append({
                        'commodity': 'CRUDE',
                        'symbol': crude_sig.symbol,
                        'signal': crude_sig.signal,
                        'entry': crude_sig.entry_price,
                        'sl': crude_sig.stop_loss,
                        'target': crude_sig.target_2,
                        'confidence': crude_sig.confidence,
                        'reason': crude_sig.reason,
                        'strategy_type': crude_sig.strategy_type,
                        'margin_required': COMMODITY_MARGINS['CRUDE'],
                        'timestamp': crude_sig.timestamp
                    })
                    logger.info(f"🛢️ CRUDE Signal: {crude_sig.signal} @ {crude_sig.entry_price}")
            except Exception as e:
                logger.error(f"Crude scan error: {e}")
        else:
            logger.debug("⚠️ CRUDE skipped - insufficient balance")
        
        # Sort by confidence
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        
        self.active_signals = signals
        self.all_signals_history.extend(signals)
        
        return signals
    
    def get_balance_status(self) -> Dict:
        """Get current balance and tradeable commodity status"""
        return {
            'available_balance': self.available_balance,
            'balance_checked': self.balance_checked,
            'tradeable_commodities': self.tradeable_commodities,
            'margin_requirements': COMMODITY_MARGINS,
            'can_trade_any': len(self.tradeable_commodities) > 0,
            'broker': 'Angel One'
        }
    
    def get_market_overview(self) -> Dict:
        """Get market overview for all commodities"""
        overview = {
            'timestamp': datetime.now(IST).isoformat(),
            'balance': self.available_balance,
            'broker': 'Angel One',
            'tradeable': self.tradeable_commodities,
            'commodities': {}
        }
        
        # Gold analysis
        try:
            gold_data = self.gold.fetch_gold_data()
            if gold_data is not None:
                gold_df = self.gold.calculate_indicators(gold_data)
                latest = gold_df.iloc[-1]
                overview['commodities']['GOLD'] = {
                    'price': round(float(latest['Close']), 2),
                    'trend': latest['Trend'],
                    'rsi': round(float(latest['RSI']), 2),
                    'tradeable': 'GOLD' in self.tradeable_commodities,
                    'margin_required': COMMODITY_MARGINS['GOLD'],
                    'status': 'active'
                }
        except:
            overview['commodities']['GOLD'] = {'status': 'error'}
        
        # Silver analysis
        try:
            analysis = self.silver.get_market_analysis()
            if analysis['status'] == 'ok':
                overview['commodities']['SILVER'] = {
                    'price': analysis['price'],
                    'trend': analysis['trend'],
                    'rsi': analysis['rsi'],
                    'tradeable': 'SILVER' in self.tradeable_commodities,
                    'margin_required': COMMODITY_MARGINS['SILVER'],
                    'status': 'active'
                }
        except:
            overview['commodities']['SILVER'] = {'status': 'error'}
        
        # Crude analysis
        try:
            analysis = self.crude.get_analysis()
            if analysis['status'] == 'ok':
                overview['commodities']['CRUDE'] = {
                    'price': analysis['price'],
                    'trend': analysis['trend'],
                    'rsi': analysis['rsi'],
                    'tradeable': 'CRUDE' in self.tradeable_commodities,
                    'margin_required': COMMODITY_MARGINS['CRUDE'],
                    'status': 'active'
                }
        except:
            overview['commodities']['CRUDE'] = {'status': 'error'}
        
        return overview
    
    def get_combined_stats(self) -> Dict:
        """Get combined paper trading stats"""
        gold_stats = self.gold.get_paper_stats()
        silver_stats = self.silver.get_paper_stats()
        crude_stats = self.crude.get_stats()
        
        total_trades = gold_stats['total_trades'] + silver_stats['total_trades'] + crude_stats['total']
        total_pnl = gold_stats['pnl'] + silver_stats['pnl'] + crude_stats['pnl']
        
        return {
            'available_balance': self.available_balance,
            'broker': 'Angel One',
            'total_trades': total_trades,
            'total_pnl': round(total_pnl, 2),
            'by_commodity': {
                'GOLD': gold_stats,
                'SILVER': silver_stats,
                'CRUDE': crude_stats
            }
        }


def create_scanner_with_angel():
    """Create commodity scanner with Angel One client integration"""
    try:
        import os
        import pyotp
        from SmartApi import SmartConnect
        
        api_key = os.getenv('ANGEL_API_KEY', '')
        client_id = os.getenv('ANGEL_CLIENT_ID', '')
        mpin = os.getenv('ANGEL_MPIN', '')
        totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')
        
        if not all([api_key, client_id, mpin, totp_secret]):
            logger.warning("Angel One credentials not configured, using manual capital")
            return CommodityScanner(capital=50000)
        
        # Generate TOTP and authenticate
        totp = pyotp.TOTP(totp_secret)
        otp = totp.now()
        
        smart_api = SmartConnect(api_key=api_key)
        data = smart_api.generateSession(
            clientCode=client_id,
            password=mpin,
            totp=otp
        )
        
        if data.get('status'):
            refresh_token = data['data']['refreshToken']
            scanner = CommodityScanner(angel_client=smart_api)
            scanner.angel_refresh_token = refresh_token
            scanner.check_balance()
            logger.info("✅ Commodity scanner initialized with Angel One")
            return scanner
        else:
            logger.warning(f"Angel One auth failed: {data.get('message')}")
            return CommodityScanner(capital=50000)
            
    except Exception as e:
        logger.warning(f"Could not initialize with Angel One: {e}")
        return CommodityScanner(capital=50000)


# Global instance (without broker by default, can be updated)
commodity_scanner = CommodityScanner(capital=50000)

