"""
Base exchange adapter interface.

Defines the contract for exchange-specific implementations.
All adapters must implement these dry-safe methods.
Live order placement is not included in this base interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import StrEnum


class ExchangeType(StrEnum):
    """Supported exchange types."""
    BINANCE = "binance"
    BYBIT = "bybit"
    NONE = "none"


@dataclass
class AccountCapability:
    """Account capability summary."""
    can_trade: bool
    can_withdraw: bool
    can_deposit: bool
    requires_kyc: bool
    account_type: str
    restrictions: list[str]


@dataclass
class MarketMetadata:
    """Market metadata for a symbol."""
    symbol: str
    base_asset: str
    quote_asset: str
    min_quantity: float
    max_quantity: float
    quantity_precision: int
    price_precision: int
    min_notional: float
    is_trading: bool


class ExchangeAdapter(ABC):
    """Base exchange adapter interface."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = True,
    ):
        """
        Initialize exchange adapter.

        Args:
            api_key: Optional API key for authentication
            api_secret: Optional API secret for authentication
            sandbox: Whether to use sandbox/testnet environment
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.sandbox = sandbox

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to exchange format.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "BTC/USDT")

        Returns:
            Normalized symbol in exchange format
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validate that credentials are present and properly formatted.

        Returns:
            True if credentials are present, False otherwise
        """
        pass

    @abstractmethod
    def get_account_capability(self) -> AccountCapability:
        """
        Fetch account capability summary.

        This is a dry-safe method that only reads account metadata.
        It does not place any orders or modify account state.

        Returns:
            AccountCapability with account restrictions and permissions
        """
        pass

    @abstractmethod
    def get_market_metadata(self, symbol: str) -> Optional[MarketMetadata]:
        """
        Fetch market metadata for a symbol.

        This is a dry-safe method that only reads market metadata.
        It does not place any orders or modify market state.

        Args:
            symbol: Trading symbol

        Returns:
            MarketMetadata if symbol exists, None otherwise
        """
        pass

    def is_dry_safe(self) -> bool:
        """
        Check if adapter is in dry-safe mode.

        Base implementation always returns True.
        Subclasses may override if they have live execution capabilities.

        Returns:
            True if adapter is dry-safe (no live execution)
        """
        return True
