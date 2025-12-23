"""
Position Manager - Track positions and implement OCO (One-Cancels-Other) logic
"""

from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class PositionManager:
    """Manage open positions and their associated orders"""
    
    def __init__(self):
        # Track open positions with their SL and Target order IDs
        # Format: {symbol: {"entry_id": x, "sl_id": x, "target_id": x, "qty": x, "entry_price": x}}
        self.positions: Dict[str, dict] = {}
        self.client = None  # Kite client reference
        
    def set_client(self, client):
        """Set the Kite client for order operations"""
        self.client = client
    
    def add_position(self, symbol: str, entry_id: str, sl_id: Optional[str], 
                     target_id: Optional[str], qty: int, entry_price: float,
                     sl_price: float, target_price: float):
        """Add a new position to track"""
        self.positions[symbol] = {
            "entry_id": str(entry_id),
            "sl_id": str(sl_id) if sl_id else None,
            "target_id": str(target_id) if target_id else None,
            "qty": qty,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "target_price": target_price,
            "entry_time": datetime.now().strftime("%H:%M:%S"),
            "status": "OPEN"
        }
        logger.info(f"📋 Position tracked: {symbol} | Qty: {qty} | Entry: ₹{entry_price}")
        logger.info(f"   SL Order: {sl_id} | Target Order: {target_id}")
    
    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position info for a symbol"""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have an open position for this symbol"""
        pos = self.positions.get(symbol)
        return pos is not None and pos.get("status") == "OPEN"
    
    def get_open_positions(self) -> List[str]:
        """Get list of symbols with open positions"""
        return [sym for sym, pos in self.positions.items() if pos.get("status") == "OPEN"]
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel a pending order"""
        if not self.client or not order_id:
            return False
        
        try:
            self.client.cancel_order(variety="regular", order_id=order_id)
            logger.info(f"❌ Cancelled order {order_id} for {symbol}")
            return True
        except Exception as e:
            logger.warning(f"Could not cancel order {order_id}: {e}")
            return False
    
    def close_position(self, symbol: str, reason: str = "manual"):
        """Mark position as closed and cancel remaining orders"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        
        # Cancel SL order if exists
        if pos.get("sl_id"):
            self.cancel_order(pos["sl_id"], symbol)
        
        # Cancel Target order if exists
        if pos.get("target_id"):
            self.cancel_order(pos["target_id"], symbol)
        
        pos["status"] = "CLOSED"
        pos["close_reason"] = reason
        pos["close_time"] = datetime.now().strftime("%H:%M:%S")
        
        logger.info(f"✅ Position closed: {symbol} | Reason: {reason}")
    
    def check_and_manage_orders(self):
        """
        Check order statuses and implement OCO logic.
        Called periodically to manage positions.
        """
        if not self.client:
            return
        
        try:
            # Get all orders for today
            orders = self.client.orders()
            
            for symbol, pos in list(self.positions.items()):
                if pos.get("status") != "OPEN":
                    continue
                
                sl_id = pos.get("sl_id")
                target_id = pos.get("target_id")
                
                sl_filled = False
                target_filled = False
                
                # Check order statuses
                for order in orders:
                    order_id = str(order["order_id"])
                    status = order["status"]
                    
                    if order_id == sl_id and status == "COMPLETE":
                        sl_filled = True
                        logger.info(f"🛡️ SL HIT for {symbol}!")
                    
                    if order_id == target_id and status == "COMPLETE":
                        target_filled = True
                        logger.info(f"🎯 TARGET HIT for {symbol}!")
                
                # OCO Logic: If one filled, cancel the other
                if sl_filled:
                    # SL hit - cancel target order
                    if target_id:
                        self.cancel_order(target_id, symbol)
                    pos["status"] = "CLOSED"
                    pos["close_reason"] = "STOP_LOSS"
                    logger.info(f"💔 {symbol} closed at STOP LOSS")
                    
                    # Send notification
                    try:
                        from utils.notifications import send_telegram_message
                        pnl = (pos["sl_price"] - pos["entry_price"]) * pos["qty"]
                        send_telegram_message(f"🛡️ STOP LOSS HIT!\n\n{symbol}\nP&L: ₹{pnl:.2f}")
                    except:
                        pass
                
                elif target_filled:
                    # Target hit - cancel SL order
                    if sl_id:
                        self.cancel_order(sl_id, symbol)
                    pos["status"] = "CLOSED"
                    pos["close_reason"] = "TARGET"
                    logger.info(f"💚 {symbol} closed at TARGET")
                    
                    # Send notification
                    try:
                        from utils.notifications import send_telegram_message
                        pnl = (pos["target_price"] - pos["entry_price"]) * pos["qty"]
                        send_telegram_message(f"🎯 TARGET HIT!\n\n{symbol}\nProfit: ₹{pnl:.2f}")
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Error checking orders: {e}")
    
    def get_summary(self) -> dict:
        """Get summary of all positions"""
        open_count = len([p for p in self.positions.values() if p.get("status") == "OPEN"])
        closed_count = len([p for p in self.positions.values() if p.get("status") == "CLOSED"])
        
        return {
            "total": len(self.positions),
            "open": open_count,
            "closed": closed_count,
            "symbols": self.get_open_positions()
        }
    
    def sync_with_broker(self):
        """Sync positions with actual broker positions"""
        if not self.client:
            return
        
        try:
            positions = self.client.positions()
            day_positions = positions.get("day", [])
            
            # Log current positions
            for pos in day_positions:
                if pos["quantity"] != 0:
                    logger.info(f"📊 Broker Position: {pos['tradingsymbol']} | Qty: {pos['quantity']} | P&L: ₹{pos['pnl']:.2f}")
        
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
    
    def log_status(self):
        """Log current position status"""
        summary = self.get_summary()
        logger.info(f"📊 Positions: {summary['open']} open, {summary['closed']} closed")
        for symbol in summary['symbols']:
            pos = self.positions[symbol]
            logger.info(f"   📈 {symbol}: Qty {pos['qty']} @ ₹{pos['entry_price']}")


# Global instance
position_manager = PositionManager()
