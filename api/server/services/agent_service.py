from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentIntent(StrEnum):
    PLAN = "plan"
    TASK = "task"
    SCHEDULE = "schedule"
    MEMORY = "memory"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class AgentAnalysisResult:
    capability: str
    intent: str
    prompt: str
    summary: str
    suggested_tools: list[str]
    status: str


class AgentService:
    def __init__(self) -> None:
        self._planning_terms = {
            "plan",
            "roadmap",
            "steps",
            "strategy",
            "architecture",
            "workflow",
            "خطة",
            "خطوات",
            "استراتيجية",
            "معمارية",
            "سير العمل",
        }
        self._task_terms = {
            "do this later",
            "follow up",
            "remind",
            "todo",
            "task",
            "execute later",
            "ذكرني",
            "مهمة",
            "تابع",
            "لاحقًا",
        }
        self._schedule_terms = {
            "schedule",
            "daily",
            "weekly",
            "tomorrow",
            "every day",
            "cron",
            "جدولة",
            "يومي",
            "أسبوعي",
            "غدًا",
            "كل يوم",
        }
        self._memory_terms = {
            "remember",
            "recall",
            "context",
            "memory",
            "history",
            "تذكر",
            "ذاكرة",
            "سياق",
            "محفوظ",
            "سجل",
        }

    def analyze(self, question: str) -> AgentAnalysisResult:
        normalized = " ".join(question.lower().split())

        intent = self._detect_intent(normalized)
        suggested_tools = self._suggest_tools(intent)

        return AgentAnalysisResult(
            capability="agent",
            intent=intent.value,
            prompt=question.strip(),
            summary=self._build_summary(intent),
            suggested_tools=suggested_tools,
            status="accepted",
        )

    def _detect_intent(self, text: str) -> AgentIntent:
        if any(term in text for term in self._memory_terms):
            return AgentIntent.MEMORY
        if any(term in text for term in self._planning_terms):
            return AgentIntent.PLAN
        if any(term in text for term in self._schedule_terms):
            return AgentIntent.SCHEDULE
        if any(term in text for term in self._task_terms):
            return AgentIntent.TASK
        return AgentIntent.UNKNOWN

    def _suggest_tools(self, intent: AgentIntent) -> list[str]:
        if intent == AgentIntent.SCHEDULE:
            return ["scheduler", "task_store"]
        if intent == AgentIntent.TASK:
            return ["task_store", "executor"]
        if intent == AgentIntent.MEMORY:
            return ["context_service", "interaction_log"]
        if intent == AgentIntent.PLAN:
            return ["planner", "capability_router"]
        return ["capability_router"]

    def _build_summary(self, intent: AgentIntent) -> str:
        if intent == AgentIntent.SCHEDULE:
            return "This request looks like a scheduled or recurring agent task."
        if intent == AgentIntent.TASK:
            return "This request looks like a deferred execution task."
        if intent == AgentIntent.MEMORY:
            return "This request looks like a memory or recall operation."
        if intent == AgentIntent.PLAN:
            return "This request looks like a planning or orchestration request."
        return (
            "This request was accepted by the agent shell but did not match a "
            "specific agent intent."
        )
