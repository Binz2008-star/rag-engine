"""
Trading risk management service boundary.

Defines risk-check interface and typed result models
without hardcoded broker logic or legacy tight coupling.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .trading_runtime_types import (
    Symbol,
    OrderSide,
    Signal,
    RiskCheckResult,
    RiskCheckStatus,
    AccountBalance,
    Position,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RiskParameters:
    """Risk management parameters."""
    max_position_size_usd: float = 1000.0
    max_position_size_percent: float = 0.05  # 5% of balance
    max_open_trades: int = 3
    base_risk_per_trade: float = 0.02  # 2% of balance
    max_risk_per_trade: float = 0.05  # 5% of balance
    stop_loss_percent: float = 0.02  # 2%
    take_profit_percent: float = 0.03  # 3%
    trailing_stop_percent: float = 0.02  # 2%
    volatility_lookback: int = 14
    volatility_factor: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class RiskService(ABC):
    """
    Abstract risk management service interface.

    Defines the boundary for risk checks without hardcoded
    broker logic or legacy tight coupling.
    """

    @abstractmethod
    async def check_entry_risk(
        self,
        signal: Signal,
        account_balance: AccountBalance,
        open_positions: List[Position],
        risk_params: Optional[RiskParameters] = None,
    ) -> RiskCheckResult:
        """
        Check if a signal passes entry risk checks.

        Args:
            signal: Trading signal
            account_balance: Current account balance
            open_positions: List of open positions
            risk_params: Optional risk parameters

        Returns:
            Risk check result with approval status
        """
        pass

    @abstractmethod
    async def check_exit_risk(
        self,
        position: Position,
        current_price: float,
        account_balance: AccountBalance,
        risk_params: Optional[RiskParameters] = None,
    ) -> RiskCheckResult:
        """
        Check if a position should be closed based on risk rules.

        Args:
            position: Current position
            current_price: Current market price
            account_balance: Current account balance
            risk_params: Optional risk parameters

        Returns:
            Risk check result with exit recommendation
        """
        pass

    @abstractmethod
    async def calculate_position_size(
        self,
        signal: Signal,
        account_balance: AccountBalance,
        risk_params: Optional[RiskParameters] = None,
    ) -> float:
        """
        Calculate recommended position size based on risk parameters.

        Args:
            signal: Trading signal
            account_balance: Current account balance
            risk_params: Optional risk parameters

        Returns:
            Recommended position size in base currency
        """
        pass

    @abstractmethod
    async def validate_order(
        self,
        symbol: Symbol,
        side: OrderSide,
        quantity: float,
        price: Optional[float],
        account_balance: AccountBalance,
        open_positions: List[Position],
        risk_params: Optional[RiskParameters] = None,
    ) -> RiskCheckResult:
        """
        Validate an order against risk constraints.

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
            price: Order price (optional for market orders)
            account_balance: Current account balance
            open_positions: List of open positions
            risk_params: Optional risk parameters

        Returns:
            Risk check result with validation status
        """
        pass


class ShellRiskService(RiskService):
    """
    Shell implementation of risk service.

    This is a placeholder implementation that performs basic
    risk checks without live trading integration.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize shell risk service.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.default_params = RiskParameters()
        logger.info("ShellRiskService initialized")

    async def check_entry_risk(
        self,
        signal: Signal,
        account_balance: AccountBalance,
        open_positions: List[Position],
        risk_params: Optional[RiskParameters] = None,
    ) -> RiskCheckResult:
        """
        Check if a signal passes entry risk checks (shell implementation).

        Args:
            signal: Trading signal
            account_balance: Current account balance
            open_positions: List of open positions
            risk_params: Optional risk parameters

        Returns:
            Risk check result
        """
        params = risk_params or self.default_params

        # Check max open trades
        if len(open_positions) >= params.max_open_trades:
            return RiskCheckResult(
                status=RiskCheckStatus.REJECTED,
                reason=f"Maximum open trades reached ({params.max_open_trades})",
                warnings=["Max open trades limit"],
            )

        # Check for duplicate symbol
        for pos in open_positions:
            if pos.symbol.pair == signal.symbol.pair:
                return RiskCheckResult(
                    status=RiskCheckStatus.REJECTED,
                    reason=f"Already have open position for {signal.symbol.pair}",
                    warnings=["Duplicate symbol"],
                )

        # Calculate position size
        position_size = await self.calculate_position_size(signal, account_balance, params)

        return RiskCheckResult(
            status=RiskCheckStatus.APPROVED,
            reason="Risk checks passed",
            max_position_size=params.max_position_size_usd,
            recommended_quantity=position_size,
            risk_score=0.5,  # Placeholder
        )

    async def check_exit_risk(
        self,
        position: Position,
        current_price: float,
        account_balance: AccountBalance,
        risk_params: Optional[RiskParameters] = None,
    ) -> RiskCheckResult:
        """
        Check if a position should be closed based on risk rules (shell implementation).

        Args:
            position: Current position
            current_price: Current market price
            account_balance: Current account balance
            risk_params: Optional risk parameters

        Returns:
            Risk check result
        """
        params = risk_params or self.default_params

        # Calculate PnL
        if position.side == OrderSide.BUY:
            pnl = (current_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - current_price) * position.quantity

        pnl_percent = pnl / (position.entry_price * position.quantity)

        # Check take profit
        if pnl_percent >= params.take_profit_percent:
            return RiskCheckResult(
                status=RiskCheckStatus.APPROVED,
                reason=f"Take profit target reached ({pnl_percent:.2%})",
                warnings=[],
            )

        # Check stop loss
        if pnl_percent <= -params.stop_loss_percent:
            return RiskCheckResult(
                status=RiskCheckStatus.APPROVED,
                reason=f"Stop loss triggered ({pnl_percent:.2%})",
                warnings=[],
            )

        return RiskCheckResult(
            status=RiskCheckStatus.WARNING,
            reason="No exit signal",
            warnings=[],
        )

    async def calculate_position_size(
        self,
        signal: Signal,
        account_balance: AccountBalance,
        risk_params: Optional[RiskParameters] = None,
    ) -> float:
        """
        Calculate recommended position size (shell implementation).

        Args:
            signal: Trading signal
            account_balance: Current account balance
            risk_params: Optional risk parameters

        Returns:
            Recommended position size in base currency
        """
        params = risk_params or self.default_params

        # Calculate based on percentage of balance
        risk_amount = account_balance.available_balance * params.base_risk_per_trade

        # If signal has entry price, calculate quantity
        if signal.entry_price:
            quantity = risk_amount / signal.entry_price
        else:
            # Use current price from signal metadata if available
            current_price = signal.metadata.get("current_price", 0.0)
            if current_price > 0:
                quantity = risk_amount / current_price
            else:
                quantity = 0.0

        return quantity

    async def validate_order(
        self,
        symbol: Symbol,
        side: OrderSide,
        quantity: float,
        price: Optional[float],
        account_balance: AccountBalance,
        open_positions: List[Position],
        risk_params: Optional[RiskParameters] = None,
    ) -> RiskCheckResult:
        """
        Validate an order against risk constraints (shell implementation).

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
            price: Order price
            account_balance: Current account balance
            open_positions: List of open positions
            risk_params: Optional risk parameters

        Returns:
            Risk check result
        """
        params = risk_params or self.default_params

        # Calculate order value
        order_price = price or 0.0
        order_value = quantity * order_price

        # Check if order exceeds balance
        if order_value > account_balance.available_balance:
            return RiskCheckResult(
                status=RiskCheckStatus.REJECTED,
                reason=f"Order value ({order_value:.2f}) exceeds available balance ({account_balance.available_balance:.2f})",
                warnings=["Insufficient balance"],
            )

        # Check max position size
        if order_value > params.max_position_size_usd:
            return RiskCheckResult(
                status=RiskCheckStatus.REJECTED,
                reason=f"Order value ({order_value:.2f}) exceeds max position size ({params.max_position_size_usd:.2f})",
                warnings=["Max position size exceeded"],
            )

        return RiskCheckResult(
            status=RiskCheckStatus.APPROVED,
            reason="Order validation passed",
            recommended_quantity=quantity,
        )
