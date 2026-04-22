from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TradingIntent(StrEnum):
    ANALYZE = "analyze"
    SIGNAL = "signal"
    RISK = "risk"
    BACKTEST = "backtest"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class TradingAnalysisResult:
    capability: str
    intent: str
    market: str | None
    asset: str | None
    timeframe: str | None
    prompt: str
    status: str


class TradingService:
    def __init__(self) -> None:
        self._timeframes = {
            "m1", "m5", "m15", "m30", "h1", "h4", "d1", "w1",
            "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w",
        }
        self._assets = {
            "eurusd",
            "xauusd",
            "btcusd",
            "gbpusd",
            "btc",
            "eth",
            "nasdaq",
            "spx",
            "us30",
            "oil",
            "silver",
        }
        # English common names → canonical ticker
        self._asset_aliases: dict[str, str] = {
            "gold": "XAUUSD",
            "silver": "XAGUSD",
            "oil": "USOIL",
        }

    def analyze(self, question: str) -> TradingAnalysisResult:
        normalized = " ".join(question.lower().split())

        intent = self._detect_intent(normalized)
        asset = self._detect_asset(normalized)
        timeframe = self._detect_timeframe(normalized)
        market = self._detect_market(normalized, asset)

        return TradingAnalysisResult(
            capability="trading",
            intent=intent.value,
            market=market,
            asset=asset,
            timeframe=timeframe,
            prompt=question.strip(),
            status="accepted",
        )

    def _detect_intent(self, text: str) -> TradingIntent:
        if any(term in text for term in {"backtest", "باك تست", "اختبار"}):
            return TradingIntent.BACKTEST
        if any(term in text for term in {"risk", "risk reward", "مخاطرة", "مخاطر"}):
            return TradingIntent.RISK
        if any(term in text for term in {"signal", "entry", "buy", "sell", "اشارة", "شراء", "بيع"}):
            return TradingIntent.SIGNAL
        if any(term in text for term in {"analyze", "analysis", "chart", "trend", "حلل", "تحليل", "اتجاه"}):
            return TradingIntent.ANALYZE
        return TradingIntent.UNKNOWN

    def _detect_asset(self, text: str) -> str | None:
        for alias, ticker in self._asset_aliases.items():
            if alias in text:
                return ticker
        for asset in self._assets:
            if asset in text:
                return asset.upper()
        if "ذهب" in text:
            return "XAUUSD"
        if "بتكوين" in text:
            return "BTCUSD"
        if "يورو" in text and "دولار" in text:
            return "EURUSD"
        return None

    def _detect_timeframe(self, text: str) -> str | None:
        for timeframe in self._timeframes:
            if timeframe in text:
                return timeframe.upper()
        if "daily" in text:
            return "D1"
        if "weekly" in text:
            return "W1"
        if "hourly" in text:
            return "H1"
        if "ساعة" in text:
            return "H1"
        if "4 ساعات" in text or "اربع ساعات" in text:
            return "H4"
        if "يومي" in text or "يوميً" in text:
            return "D1"
        return None

    def _detect_market(self, text: str, asset: str | None) -> str | None:
        if any(term in text for term in {"forex", "eurusd", "xauusd", "ذهب", "يورو"}):
            return "forex"
        if any(term in text for term in {"crypto", "btc", "eth", "بتكوين", "كريبتو"}):
            return "crypto"
        if any(term in text for term in {"stocks", "nasdaq", "spx", "us30", "اسهم"}):
            return "equities"
        if asset in {"EURUSD", "XAUUSD"}:
            return "forex"
        if asset in {"BTCUSD", "BTC", "ETH"}:
            return "crypto"
        return None
