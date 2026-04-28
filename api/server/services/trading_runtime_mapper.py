"""
Trading runtime mapper.

Maps existing TradingAnalyzeRequest / trading analysis output into
runtime domain types. Converts question-derived trading intent
into typed execution/risk input structures.

Pure mapping helpers only - no network calls, no side effects, no exchange logic.
"""

from __future__ import annotations

import re
import logging
from typing import Optional, Dict, Any

from .trading_runtime_types import (
    Symbol,
    Timeframe,
    OrderSide,
    OrderType,
    Signal,
    SignalDirection,
    ExecutionRequest,
    RiskParameters,
)

logger = logging.getLogger(__name__)


class TradingRuntimeMapper:
    """Mapper for converting trading analysis to runtime domain types."""

    # Common forex pairs
    FOREX_PAIRS = {
        "EURUSD": ("EUR", "USD"),
        "GBPUSD": ("GBP", "USD"),
        "USDJPY": ("USD", "JPY"),
        "AUDUSD": ("AUD", "USD"),
        "USDCAD": ("USD", "CAD"),
        "USDCHF": ("USD", "CHF"),
        "NZDUSD": ("NZD", "USD"),
    }

    # Common crypto pairs
    CRYPTO_PAIRS = {
        "BTCUSDT": ("BTC", "USDT"),
        "ETHUSDT": ("ETH", "USDT"),
        "XRPUSDT": ("XRP", "USDT"),
        "BNBUSDT": ("BNB", "USDT"),
        "SOLUSDT": ("SOL", "USDT"),
    }

    @staticmethod
    def parse_symbol(question: str) -> Symbol:
        """
        Parse asset/symbol from question into Symbol model.

        Args:
            question: Trading analysis question

        Returns:
            Symbol model
        """
        question_upper = question.upper()

        # Try forex pairs first
        for pair, (base, quote) in TradingRuntimeMapper.FOREX_PAIRS.items():
            if pair in question_upper:
                return Symbol(base=base, quote=quote, exchange="forex")

        # Try crypto pairs
        for pair, (base, quote) in TradingRuntimeMapper.CRYPTO_PAIRS.items():
            if pair in question_upper:
                return Symbol(base=base, quote=quote, exchange="binance")

        # Fallback: try to extract any 6+ letter uppercase sequence
        match = re.search(r"([A-Z]{6,})", question_upper)
        if match:
            symbol_str = match.group(1)
            # Heuristic: first 3-4 chars are base, rest are quote
            if len(symbol_str) == 6:
                return Symbol(base=symbol_str[:3], quote=symbol_str[3:], exchange="binance")
            elif len(symbol_str) == 7:
                return Symbol(base=symbol_str[:4], quote=symbol_str[3:], exchange="binance")

        # Default fallback
        logger.warning(f"Could not parse symbol from question: {question}")
        return Symbol(base="BTC", quote="USDT", exchange="binance")

    @staticmethod
    def parse_timeframe(question: str) -> Timeframe:
        """
        Parse timeframe from question into typed Timeframe enum.

        Args:
            question: Trading analysis question

        Returns:
            Timeframe enum
        """
        question_upper = question.upper()

        # Map common timeframe patterns
        timeframe_map = {
            "M1": Timeframe.M1,
            "1M": Timeframe.M1,
            "1MIN": Timeframe.M1,
            "M5": Timeframe.M5,
            "5M": Timeframe.M5,
            "5MIN": Timeframe.M5,
            "M15": Timeframe.M15,
            "15M": Timeframe.M15,
            "15MIN": Timeframe.M15,
            "M30": Timeframe.M30,
            "30M": Timeframe.M30,
            "30MIN": Timeframe.M30,
            "H1": Timeframe.H1,
            "1H": Timeframe.H1,
            "1HR": Timeframe.H1,
            "H4": Timeframe.H4,
            "4H": Timeframe.H4,
            "4HR": Timeframe.H4,
            "D1": Timeframe.D1,
            "1D": Timeframe.D1,
            "DAILY": Timeframe.D1,
        }

        for pattern, timeframe in timeframe_map.items():
            if pattern in question_upper:
                return timeframe

        # Default fallback
        logger.warning(f"Could not parse timeframe from question: {question}, defaulting to H1")
        return Timeframe.H1

    @staticmethod
    def infer_signal_direction(question: str) -> SignalDirection:
        """
        Infer signal direction from question.

        Args:
            question: Trading analysis question

        Returns:
            SignalDirection enum
        """
        question_lower = question.lower()

        buy_keywords = ["buy", "long", "bullish", "uptrend", "breakout"]
        sell_keywords = ["sell", "short", "bearish", "downtrend", "breakdown"]

        buy_score = sum(1 for kw in buy_keywords if kw in question_lower)
        sell_score = sum(1 for kw in sell_keywords if kw in question_lower)

        if buy_score > sell_score:
            return SignalDirection.LONG
        elif sell_score > buy_score:
            return SignalDirection.SHORT

        return SignalDirection.NEUTRAL

    @staticmethod
    def question_to_signal(question: str, analysis_result: Optional[Dict[str, Any]] = None) -> Signal:
        """
        Convert trading analysis into Signal model.

        Args:
            question: Trading analysis question
            analysis_result: Optional analysis result from existing shell

        Returns:
            Signal model
        """
        symbol = TradingRuntimeMapper.parse_symbol(question)
        timeframe = TradingRuntimeMapper.parse_timeframe(question)
        direction = TradingRuntimeMapper.infer_signal_direction(question)

        # Extract confidence from analysis result if available
        confidence = 0.5
        if analysis_result:
            confidence = analysis_result.get("confidence", 0.5)

        # Extract entry price from analysis result if available
        entry_price = None
        if analysis_result:
            entry_price = analysis_result.get("entry_price")

        return Signal(
            direction=direction,
            confidence=confidence,
            symbol=symbol,
            timeframe=timeframe,
            entry_price=entry_price,
            reason="Inferred from trading analysis question",
            metadata={"source": "question_mapping", "original_question": question},
        )

    @staticmethod
    def question_to_execution_request(
        question: str,
        analysis_result: Optional[Dict[str, Any]] = None,
        quantity: Optional[float] = None,
    ) -> ExecutionRequest:
        """
        Convert trading analysis into ExecutionRequest draft.

        Args:
            question: Trading analysis question
            analysis_result: Optional analysis result from existing shell
            quantity: Optional quantity (will use safe default if None)

        Returns:
            ExecutionRequest model
        """
        signal = TradingRuntimeMapper.question_to_signal(question, analysis_result)

        # Determine order side from signal direction
        side = OrderSide.BUY if signal.direction == SignalDirection.LONG else OrderSide.SELL

        # Use safe default quantity
        safe_quantity = quantity or 0.001

        return ExecutionRequest(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=safe_quantity,
            price=signal.entry_price,
            metadata={
                "source": "question_mapping",
                "signal_direction": signal.direction.value,
                "signal_confidence": signal.confidence,
                "original_question": question,
            },
        )

    @staticmethod
    def get_default_risk_parameters() -> RiskParameters:
        """
        Get default risk parameters for dry-run.

        Returns:
            RiskParameters model
        """
        return RiskParameters()

    @staticmethod
    def create_dry_run_plan(
        question: str,
        analysis_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a typed dry-run plan from question and analysis.

        Args:
            question: Trading analysis question
            analysis_result: Optional analysis result from existing shell

        Returns:
            Dry-run plan dictionary
        """
        signal = TradingRuntimeMapper.question_to_signal(question, analysis_result)
        execution_request = TradingRuntimeMapper.question_to_execution_request(question, analysis_result)
        risk_params = TradingRuntimeMapper.get_default_risk_parameters()

        return {
            "signal": signal,
            "execution_request": execution_request,
            "risk_parameters": risk_params,
            "execution_mode": "dry_run",
            "normalized_symbol": signal.symbol.pair,
            "timeframe": signal.timeframe.value,
            "direction": signal.direction.value,
            "confidence": signal.confidence,
        }
