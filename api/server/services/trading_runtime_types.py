"""
Trading runtime domain models and types.

Defines typed domain models for trading execution, risk management,
and exchange interaction without enabling live trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class OrderSide(StrEnum):
    """Order side (buy or sell)."""
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"


class OrderStatus(StrEnum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Timeframe(StrEnum):
    """Candlestick timeframe."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class SignalDirection(StrEnum):
    """Signal direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class RiskCheckStatus(StrEnum):
    """Risk check result status."""
    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"


@dataclass(slots=True, frozen=True)
class Symbol:
    """Trading symbol identifier."""
    base: str
    quote: str
    exchange: str = "binance"

    @property
    def pair(self) -> str:
        """Return symbol pair string (e.g., BTCUSDT)."""
        return f"{self.base}{self.quote}"


@dataclass(slots=True)
class MarketData:
    """Market data snapshot."""
    symbol: Symbol
    timeframe: Timeframe
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: Optional[datetime] = None
    quote_volume: Optional[float] = None
    trades_count: Optional[int] = None
    taker_buy_base: Optional[float] = None
    taker_buy_quote: Optional[float] = None


@dataclass(slots=True)
class Signal:
    """Trading signal."""
    direction: SignalDirection
    confidence: float  # 0.0 to 1.0
    symbol: Symbol
    timeframe: Timeframe
    timestamp: datetime
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionRequest:
    """Order execution request."""
    symbol: Symbol
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None  # Required for limit orders
    stop_price: Optional[float] = None  # Required for stop orders
    client_order_id: Optional[str] = None
    time_in_force: str = "GTC"  # GTC, IOC, FOK
    reduce_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionResult:
    """Order execution result."""
    success: bool
    order_id: Optional[str]
    client_order_id: Optional[str]
    symbol: Symbol
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    executed_quantity: float
    executed_price: Optional[float]
    fee: Optional[float] = None
    fee_currency: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskCheckResult:
    """Risk management check result."""
    status: RiskCheckStatus
    reason: str
    max_position_size: Optional[float] = None
    recommended_quantity: Optional[float] = None
    risk_score: Optional[float] = None  # 0.0 to 1.0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    """Current position snapshot."""
    symbol: Symbol
    side: OrderSide
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccountBalance:
    """Account balance snapshot."""
    total_balance: float
    available_balance: float
    currency: str = "USDT"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExchangePositionSnapshot:
    """Complete exchange position snapshot."""
    positions: List[Position]
    balances: Dict[str, AccountBalance]
    timestamp: datetime = field(default_factory=datetime.utcnow)


# Pydantic models for API serialization

class MarketDataModel(BaseModel):
    """Market data model for API serialization."""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: Optional[datetime] = None
    quote_volume: Optional[float] = None


class SignalModel(BaseModel):
    """Signal model for API serialization."""
    direction: str
    confidence: float
    symbol: str
    timeframe: str
    timestamp: datetime
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: Optional[str] = None


class ExecutionRequestModel(BaseModel):
    """Execution request model for API serialization."""
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None
    time_in_force: str = "GTC"
    reduce_only: bool = False


class ExecutionResultModel(BaseModel):
    """Execution result model for API serialization."""
    success: bool
    order_id: Optional[str]
    client_order_id: Optional[str]
    symbol: str
    side: str
    order_type: str
    status: str
    executed_quantity: float
    executed_price: Optional[float]
    fee: Optional[float] = None
    fee_currency: Optional[str] = None
    timestamp: datetime
    error_message: Optional[str] = None


class RiskCheckResultModel(BaseModel):
    """Risk check result model for API serialization."""
    status: str
    reason: str
    max_position_size: Optional[float] = None
    recommended_quantity: Optional[float] = None
    risk_score: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)


class PositionModel(BaseModel):
    """Position model for API serialization."""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    timestamp: datetime


class AccountBalanceModel(BaseModel):
    """Account balance model for API serialization."""
    total_balance: float
    available_balance: float
    currency: str = "USDT"
    timestamp: datetime
