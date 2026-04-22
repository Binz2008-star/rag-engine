"""
Trading execution service boundary.

Defines abstract execution service interface for order placement
without enabling live trading. This is a shell implementation
designed for future runtime integration.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from .trading_runtime_types import (
    ExecutionRequest,
    ExecutionResult,
    OrderStatus,
    OrderSide,
    OrderType,
    Symbol,
)

logger = logging.getLogger(__name__)


class ExecutionService(ABC):
    """
    Abstract execution service interface.

    Defines the boundary for order execution without live trading.
    Implementations should handle order placement, cancellation,
    and status queries.
    """

    @abstractmethod
    async def execute_order(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute a trading order.

        Args:
            request: Order execution request

        Returns:
            Execution result with order details
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: Symbol) -> ExecutionResult:
        """
        Cancel an existing order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading symbol

        Returns:
            Execution result indicating cancellation status
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: Symbol) -> ExecutionResult:
        """
        Get the status of an order.

        Args:
            order_id: Order ID to query
            symbol: Trading symbol

        Returns:
            Execution result with current order status
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[Symbol] = None) -> List[ExecutionResult]:
        """
        Get all open orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open order results
        """
        pass


class ShellExecutionService(ExecutionService):
    """
    Shell implementation of execution service.

    This is a placeholder implementation that does not execute
    real orders. It returns mock results for testing and
    development purposes.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize shell execution service.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._enabled = False  # Live trading disabled by default
        logger.info("ShellExecutionService initialized (live trading disabled)")

    async def execute_order(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute a trading order (shell implementation).

        This is a stub that returns a mock result without placing
        actual orders.

        Args:
            request: Order execution request

        Returns:
            Mock execution result
        """
        if not self._enabled:
            logger.warning(
                f"Order execution blocked (live trading disabled): "
                f"{request.side.value} {request.quantity} {request.symbol.pair}"
            )
            return ExecutionResult(
                success=False,
                order_id=None,
                client_order_id=request.client_order_id,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                status=OrderStatus.REJECTED,
                executed_quantity=0.0,
                executed_price=None,
                error_message="Live trading is disabled",
                metadata={"reason": "shell_mode"},
            )

        # Placeholder for future live implementation
        logger.info(
            f"Would execute order: {request.side.value} {request.quantity} "
            f"{request.symbol.pair} @ {request.price}"
        )
        return ExecutionResult(
            success=True,
            order_id="mock_order_id",
            client_order_id=request.client_order_id,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            status=OrderStatus.FILLED,
            executed_quantity=request.quantity,
            executed_price=request.price or 0.0,
            metadata={"mode": "shell"},
        )

    async def cancel_order(self, order_id: str, symbol: Symbol) -> ExecutionResult:
        """
        Cancel an existing order (shell implementation).

        Args:
            order_id: Order ID to cancel
            symbol: Trading symbol

        Returns:
            Mock execution result
        """
        logger.warning(f"Order cancellation blocked (live trading disabled): {order_id}")
        return ExecutionResult(
            success=False,
            order_id=order_id,
            client_order_id=None,
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.REJECTED,
            executed_quantity=0.0,
            executed_price=None,
            error_message="Live trading is disabled",
            metadata={"reason": "shell_mode"},
        )

    async def get_order_status(self, order_id: str, symbol: Symbol) -> ExecutionResult:
        """
        Get the status of an order (shell implementation).

        Args:
            order_id: Order ID to query
            symbol: Trading symbol

        Returns:
            Mock execution result
        """
        return ExecutionResult(
            success=True,
            order_id=order_id,
            client_order_id=None,
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            executed_quantity=0.0,
            executed_price=None,
            metadata={"mode": "shell"},
        )

    async def get_open_orders(self, symbol: Optional[Symbol] = None) -> List[ExecutionResult]:
        """
        Get all open orders (shell implementation).

        Args:
            symbol: Optional symbol filter

        Returns:
            Empty list (shell mode)
        """
        logger.debug(f"Get open orders called (shell mode, symbol filter: {symbol})")
        return []

    def enable_live_trading(self, enabled: bool) -> None:
        """
        Enable or disable live trading (for future implementation).

        Args:
            enabled: Whether to enable live trading
        """
        self._enabled = enabled
        logger.warning(f"Live trading {'enabled' if enabled else 'disabled'}")
