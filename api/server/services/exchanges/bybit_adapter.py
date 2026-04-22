"""
Bybit exchange adapter implementation.

Implements dry-safe methods for Bybit integration.
No live order placement in this adapter - that requires explicit feature flag.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .base import (
    ExchangeAdapter,
    AccountCapability,
    MarketMetadata,
)

logger = logging.getLogger(__name__)


class BybitAdapter(ExchangeAdapter):
    """Bybit exchange adapter - dry-safe methods only."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = True,
    ):
        """
        Initialize Bybit adapter.

        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            sandbox: Whether to use Bybit testnet (default: True)
        """
        super().__init__(api_key=api_key, api_secret=api_secret, sandbox=sandbox)
        self._base_url = self._get_base_url()
        logger.info(
            f"BybitAdapter initialized (sandbox={sandbox}, api_key_present={bool(api_key)})"
        )

    def _get_base_url(self) -> str:
        """Get appropriate base URL based on sandbox setting."""
        if self.sandbox:
            return "https://api-testnet.bybit.com"
        return "https://api.bybit.com"

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to Bybit format.

        Bybit uses uppercase format without separators for spot (e.g., "BTCUSDT").
        For derivatives, uses format like "BTCUSDT" or "BTCUSD".

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT", "btcusdt", "BTC-USDT")

        Returns:
            Normalized symbol in Bybit format (e.g., "BTCUSDT")
        """
        # Remove any separators and convert to uppercase
        normalized = re.sub(r"[/-]", "", symbol).upper()
        logger.debug(f"Normalized symbol '{symbol}' to '{normalized}'")
        return normalized

    def validate_credentials(self) -> bool:
        """
        Validate that Bybit credentials are present.

        This is a dry-safe check - it only validates presence, not validity.
        Actual credential validation requires an API call which is not done here.

        Returns:
            True if both api_key and api_secret are present, False otherwise
        """
        has_key = bool(self.api_key and len(self.api_key) > 0)
        has_secret = bool(self.api_secret and len(self.api_secret) > 0)
        valid = has_key and has_secret
        logger.info(
            f"Bybit credential validation: key_present={has_key}, secret_present={has_secret}, valid={valid}"
        )
        return valid

    def get_account_capability(self) -> AccountCapability:
        """
        Fetch account capability summary for Bybit.

        This is a dry-safe method that returns mock data.
        Actual implementation would call Bybit API to fetch account restrictions.

        Returns:
            AccountCapability with mock Bybit account restrictions
        """
        logger.info("Fetching Bybit account capability (dry-safe mock)")
        return AccountCapability(
            can_trade=True,
            can_withdraw=False,  # Withdrawals require additional permissions
            can_deposit=True,
            requires_kyc=True,
            account_type="UNIFIED",
            restrictions=[
                "No API withdrawals enabled",
                "IP whitelist may apply",
                "Daily withdrawal limits apply",
                "API rate limits apply",
            ],
        )

    def get_market_metadata(self, symbol: str) -> Optional[MarketMetadata]:
        """
        Fetch market metadata for a Bybit symbol.

        This is a dry-safe method that returns mock data.
        Actual implementation would call Bybit API to fetch symbol info.

        Args:
            symbol: Trading symbol (will be normalized)

        Returns:
            MarketMetadata if symbol is recognized, None otherwise
        """
        normalized = self.normalize_symbol(symbol)
        logger.info(f"Fetching Bybit market metadata for {normalized} (dry-safe mock)")

        # Mock metadata for common symbols
        mock_metadata = {
            "BTCUSDT": MarketMetadata(
                symbol="BTCUSDT",
                base_asset="BTC",
                quote_asset="USDT",
                min_quantity=0.001,
                max_quantity=1000.0,
                quantity_precision=3,
                price_precision=2,
                min_notional=1.0,
                is_trading=True,
            ),
            "ETHUSDT": MarketMetadata(
                symbol="ETHUSDT",
                base_asset="ETH",
                quote_asset="USDT",
                min_quantity=0.01,
                max_quantity=10000.0,
                quantity_precision=2,
                price_precision=2,
                min_notional=1.0,
                is_trading=True,
            ),
            "EURUSD": MarketMetadata(
                symbol="EURUSD",
                base_asset="EUR",
                quote_asset="USD",
                min_quantity=0.01,
                max_quantity=100000.0,
                quantity_precision=2,
                price_precision=5,
                min_notional=1.0,
                is_trading=False,  # Forex not on Bybit spot
            ),
        }

        return mock_metadata.get(normalized)
