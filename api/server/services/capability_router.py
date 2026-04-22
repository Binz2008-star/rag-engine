"""Deterministic capability routing based on keyword matching.

Classifies questions into RAG, TRADING, ADMIN, or UNKNOWN capabilities.
Supports both English and Arabic keywords.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    RAG = "rag"
    TRADING = "trading"
    AGENT = "agent"
    ADMIN = "admin"
    GENERAL = "general"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class CapabilityRoute:
    capability: Capability
    reason: str
    confidence: float


class CapabilityRouter:
    def __init__(self) -> None:
        self._trading_keywords = {
            "trade",
            "trading",
            "signal",
            "buy",
            "sell",
            "stop loss",
            "take profit",
            "lot size",
            "risk reward",
            "forex",
            "crypto",
            "btc",
            "eth",
            "xauusd",
            "eurusd",
            "gbpusd",
            "gold",
            "silver",
            "oil",
            "nasdaq",
            "strategy",
            "backtest",
            "analyze",
            "analysis",
            "chart",
            "candlestick",
            "trend",
            "timeframe",
            "تداول",
            "صفقة",
            "شراء",
            "بيع",
            "وقف",
            "هدف",
            "مخاطرة",
            "ذهب",
            "يورو",
            "دولار",
            "بتكوين",
            "كريبتو",
            "استراتيجية",
        }
        self._admin_keywords = {
            "health",
            "status",
            "metrics",
            "debug",
            "logs",
            "حالة",
            "صحة",
            "سجلات",
            "مقاييس",
            "تشخيص",
        }
        self._agent_keywords = {
            "plan",
            "roadmap",
            "steps",
            "remind",
            "reminder",
            "schedule",
            "scheduled",
            "tomorrow",
            "todo",
            "task",
            "remember",
            "recall",
            "خطة",
            "خطوات",
            "ذكرني",
            "تذكير",
            "جدولة",
            "يومي",
            "أسبوعي",
            "غدًا",
            "مهمة",
            "تذكر",
        }
        self._general_keywords = {
            # Greetings
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening",
            "how are you",
            "thanks",
            "thank you",
            # Help/meta — strict meta-questions only, not document Q&A verbs
            "what can you do",
            "your capabilities",
            "who are you",
            "explain yourself",
        }

    def route(self, question: str) -> CapabilityRoute:
        normalized = " ".join(question.lower().split())

        if not normalized:
            return CapabilityRoute(
                capability=Capability.UNKNOWN,
                reason="empty question",
                confidence=0.0,
            )

        trading_hits = sum(
            1 for keyword in self._trading_keywords if keyword in normalized
        )
        if trading_hits > 0:
            return CapabilityRoute(
                capability=Capability.TRADING,
                reason=f"matched {trading_hits} trading keyword(s)",
                confidence=min(0.99, 0.55 + (0.08 * trading_hits)),
            )

        agent_hits = sum(
            1 for keyword in self._agent_keywords if keyword in normalized
        )
        if agent_hits > 0:
            return CapabilityRoute(
                capability=Capability.AGENT,
                reason=f"matched {agent_hits} agent keyword(s)",
                confidence=min(0.99, 0.55 + (0.08 * agent_hits)),
            )

        general_hits = sum(
            1 for keyword in self._general_keywords if keyword in normalized
        )
        if general_hits > 0:
            return CapabilityRoute(
                capability=Capability.GENERAL,
                reason=f"matched {general_hits} general keyword(s)",
                confidence=min(0.99, 0.55 + (0.08 * general_hits)),
            )

        admin_hits = sum(
            1 for keyword in self._admin_keywords if keyword in normalized
        )
        if admin_hits > 0:
            return CapabilityRoute(
                capability=Capability.ADMIN,
                reason=f"matched {admin_hits} admin keyword(s)",
                confidence=min(0.99, 0.55 + (0.08 * admin_hits)),
            )

        return CapabilityRoute(
            capability=Capability.RAG,
            reason="default rag route",
            confidence=0.75,
        )
