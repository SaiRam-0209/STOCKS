"""Order management — place, track, and cancel orders via Angel One.

Supports:
    - Market / Limit orders
    - Bracket orders (entry + SL + target in one call)
    - Position exit (market close)
    - Order status tracking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from project.broker.angel import AngelBroker
from project.broker.symbols import SymbolMapper

log = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PLACED = "PLACED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXITED = "EXITED"


@dataclass
class TradeOrder:
    """Represents a single trade with entry, SL, and target."""
    ticker: str
    side: OrderSide
    quantity: int
    entry_price: float
    stoploss: float
    target: float
    # Filled by broker
    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    fill_price: float = 0.0
    exit_price: float = 0.0
    pnl: float = 0.0
    placed_at: str = ""
    filled_at: str = ""
    exited_at: str = ""


class OrderManager:
    """High-level order management for the ORB trading strategy."""

    def __init__(self, broker: AngelBroker, mapper: SymbolMapper | None = None):
        self.broker = broker
        self.mapper = mapper or SymbolMapper()
        self.active_orders: dict[str, TradeOrder] = {}  # order_id → TradeOrder

    def place_bracket_order(self, trade: TradeOrder) -> bool:
        """Place a bracket order: entry + stoploss + target.

        Angel One bracket order automatically:
        - Places entry as limit order
        - Attaches SL and target as child orders
        - When SL or target hits, the other is auto-cancelled
        """
        token = self.mapper.get_token(trade.ticker)
        trading_symbol = self.mapper.get_trading_symbol(trade.ticker)
        if not token or not trading_symbol:
            log.error("Symbol not found: %s", trade.ticker)
            trade.status = OrderStatus.REJECTED
            return False

        # Calculate SL and target distances from entry
        if trade.side == OrderSide.BUY:
            sl_distance = round(trade.entry_price - trade.stoploss, 2)
            target_distance = round(trade.target - trade.entry_price, 2)
        else:
            sl_distance = round(trade.stoploss - trade.entry_price, 2)
            target_distance = round(trade.entry_price - trade.target, 2)

        if sl_distance <= 0 or target_distance <= 0:
            log.error("Invalid SL/target for %s: sl_dist=%s, tgt_dist=%s",
                      trade.ticker, sl_distance, target_distance)
            trade.status = OrderStatus.REJECTED
            return False

        order_params = {
            "variety": "ROBO",  # Bracket order variety in Angel One
            "tradingsymbol": trading_symbol,
            "symboltoken": token,
            "transactiontype": trade.side.value,
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": "BO",
            "duration": "DAY",
            "price": str(trade.entry_price),
            "squareoff": str(target_distance),
            "stoploss": str(sl_distance),
            "quantity": str(trade.quantity),
            "triggerprice": "0",
        }

        order_id = self.broker.place_order(order_params)
        if order_id:
            trade.order_id = order_id
            trade.status = OrderStatus.PLACED
            trade.placed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.active_orders[order_id] = trade
            log.info("Bracket order placed: %s %s %d @ ₹%.2f | SL ₹%.2f | TGT ₹%.2f",
                      trade.side.value, trade.ticker, trade.quantity,
                      trade.entry_price, trade.stoploss, trade.target)
            return True

        trade.status = OrderStatus.REJECTED
        return False

    def place_market_order(self, ticker: str, side: OrderSide, quantity: int) -> str | None:
        """Place a simple market order (used for emergency exits)."""
        token = self.mapper.get_token(ticker)
        trading_symbol = self.mapper.get_trading_symbol(ticker)
        if not token or not trading_symbol:
            return None

        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": trading_symbol,
            "symboltoken": token,
            "transactiontype": side.value,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "quantity": str(quantity),
            "triggerprice": "0",
        }
        return self.broker.place_order(order_params)

    def exit_all_positions(self) -> int:
        """Emergency exit: close all open positions at market price.

        Returns number of positions closed.
        """
        positions = self.broker.get_positions()
        closed = 0
        for pos in positions:
            net_qty = int(pos.get("netqty", 0))
            if net_qty == 0:
                continue

            ticker = pos.get("tradingsymbol", "")
            token = pos.get("symboltoken", "")
            side = OrderSide.SELL if net_qty > 0 else OrderSide.BUY

            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": ticker,
                "symboltoken": token,
                "transactiontype": side.value,
                "exchange": "NSE",
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": "0",
                "quantity": str(abs(net_qty)),
                "triggerprice": "0",
            }
            result = self.broker.place_order(order_params)
            if result:
                closed += 1
                log.info("Emergency exit: %s %s %d shares", side.value, ticker, abs(net_qty))

        return closed

    def cancel_all_pending(self) -> int:
        """Cancel all pending/open orders."""
        orders = self.broker.get_order_book()
        cancelled = 0
        for order in orders:
            status = order.get("status", "").lower()
            if status in ("open", "pending", "trigger pending"):
                oid = order.get("orderid", "")
                variety = order.get("variety", "NORMAL")
                if self.broker.cancel_order(oid, variety):
                    cancelled += 1
        return cancelled

    def sync_order_status(self):
        """Update status of all active orders from broker order book."""
        orders = self.broker.get_order_book()
        order_map = {o.get("orderid"): o for o in orders if o}

        for oid, trade in self.active_orders.items():
            if oid not in order_map:
                continue
            broker_order = order_map[oid]
            broker_status = broker_order.get("status", "").lower()

            if broker_status == "complete":
                trade.status = OrderStatus.FILLED
                trade.fill_price = float(broker_order.get("averageprice", trade.entry_price))
                trade.filled_at = broker_order.get("updatetime", "")
            elif broker_status in ("cancelled", "rejected"):
                trade.status = OrderStatus.CANCELLED if "cancel" in broker_status else OrderStatus.REJECTED

    def get_active_trades(self) -> list[TradeOrder]:
        """Return list of currently active (placed/filled) trades."""
        return [t for t in self.active_orders.values()
                if t.status in (OrderStatus.PLACED, OrderStatus.FILLED)]

    def get_today_pnl(self) -> float:
        """Calculate realized P&L from today's completed trades."""
        total = 0.0
        for trade in self.active_orders.values():
            if trade.status == OrderStatus.EXITED:
                total += trade.pnl
        return total
