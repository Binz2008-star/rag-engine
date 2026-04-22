"""
Trading runtime service.

Orchestrates mapper -> risk service -> execution service for dry-run only.
No exchange execution, no real order placement.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .trading_runtime_types import (
    Symbol,
    Signal,
    ExecutionRequest,
    ExecutionResult,
    RiskCheckResult,
    RiskCheckStatus,
    AccountBalance,
    Position,
    OrderSide,
)
from .trading_runtime_mapper import TradingRuntimeMapper
from .trading_execution_service import ExecutionService
from .trading_risk_service import RiskService
from .trading_exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class TradingRuntimeService:
    """
    Trading runtime orchestration service.

    Orchestrates mapper -> risk service -> execution service
    for dry-run analysis without real order placement.
    """

    def __init__(
        self,
        execution_service: ExecutionService,
        risk_service: RiskService,
        exchange_client: ExchangeClient,
    ):
        """
        Initialize trading runtime service.

        Args:
            execution_service: Execution service implementation
            risk_service: Risk service implementation
            exchange_client: Exchange client implementation
        """
        self.execution_service = execution_service
        self.risk_service = risk_service
        self.exchange_client = exchange_client
        self.mapper = TradingRuntimeMapper()
        logger.info("TradingRuntimeService initialized (dry-run mode)")

    async def run_dry_analysis(
        self,
        question: str,
        analysis_result: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run dry-run analysis for a trading question.

        Args:
            question: Trading analysis question
            analysis_result: Optional analysis result from existing shell
            session_id: Optional session identifier
            user_id: Optional user identifier

        Returns:
            Typed dry-run result dictionary
        """
        try:
            # Step 1: Map question to runtime domain types
            dry_run_plan = self.mapper.create_dry_run_plan(question, analysis_result)
            signal = dry_run_plan["signal"]
            execution_request = dry_run_plan["execution_request"]
            risk_params = dry_run_plan["risk_parameters"]

            logger.info(
                f"Dry-run analysis for {signal.symbol.pair} {signal.timeframe.value} "
                f"direction={signal.direction.value} confidence={signal.confidence}"
            )

            # Step 2: Get account balance (mock in shell mode)
            account_balance = await self.exchange_client.get_balance("USDT")
            if not account_balance:
                account_balance = AccountBalance(
                    total_balance=10000.0,
                    available_balance=10000.0,
                    currency="USDT",
                )

            # Step 3: Get open positions (mock in shell mode)
            open_positions = await self.exchange_client.get_positions()

            # Step 4: Run entry risk check
            risk_result = await self.risk_service.check_entry_risk(
                signal=signal,
                account_balance=account_balance,
                open_positions=open_positions,
                risk_params=risk_params,
            )

            # Step 5: Build execution plan summary
            execution_summary = {
                "order_type": execution_request.order_type.value,
                "side": execution_request.side.value,
                "quantity": execution_request.quantity,
                "price": execution_request.price,
                "estimated_value": execution_request.quantity * (execution_request.price or 0),
            }

            # Step 6: Build response
            response = {
                "accepted": risk_result.status == RiskCheckStatus.APPROVED,
                "normalized_symbol": dry_run_plan["normalized_symbol"],
                "timeframe": dry_run_plan["timeframe"],
                "direction": dry_run_plan["direction"],
                "confidence": dry_run_plan["confidence"],
                "risk_approved": risk_result.status == RiskCheckStatus.APPROVED,
                "risk_status": risk_result.status.value,
                "risk_reason": risk_result.reason,
                "risk_score": risk_result.risk_score,
                "max_position_size": risk_result.max_position_size,
                "recommended_quantity": risk_result.recommended_quantity,
                "risk_warnings": risk_result.warnings,
                "execution_mode": "dry_run",
                "execution_summary": execution_summary,
                "execution_blocked": risk_result.status == RiskCheckStatus.REJECTED,
                "warnings": [],
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "user_id": user_id,
            }

            # Add warnings if risk check failed
            if risk_result.status == RiskCheckStatus.REJECTED:
                response["warnings"].append(f"Risk check rejected: {risk_result.reason}")
            elif risk_result.status == RiskCheckStatus.WARNING:
                response["warnings"].append(f"Risk check warning: {risk_result.reason}")

            logger.info(f"Dry-run analysis completed: accepted={response['accepted']}")
            return response

        except Exception as exc:
            logger.exception("Dry-run analysis failed")
            return {
                "accepted": False,
                "error": str(exc),
                "execution_mode": "dry_run",
                "execution_blocked": True,
                "warnings": [f"Internal error: {str(exc)}"],
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "user_id": user_id,
            }

    async def run_dry_execution_plan(
        self,
        execution_request: ExecutionRequest,
        risk_params: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Run dry-run execution plan.

        Args:
            execution_request: Execution request
            risk_params: Optional risk parameters

        Returns:
            Typed dry-run result dictionary
        """
        try:
            # Get account balance
            account_balance = await self.exchange_client.get_balance("USDT")
            if not account_balance:
                account_balance = AccountBalance(
                    total_balance=10000.0,
                    available_balance=10000.0,
                    currency="USDT",
                )

            # Get open positions
            open_positions = await self.exchange_client.get_positions()

            # Validate order against risk constraints
            risk_result = await self.risk_service.validate_order(
                symbol=execution_request.symbol,
                side=execution_request.side,
                quantity=execution_request.quantity,
                price=execution_request.price,
                account_balance=account_balance,
                open_positions=open_positions,
                risk_params=risk_params,
            )

            # Build response
            response = {
                "accepted": risk_result.status == RiskCheckStatus.APPROVED,
                "normalized_symbol": execution_request.symbol.pair,
                "order_type": execution_request.order_type.value,
                "side": execution_request.side.value,
                "quantity": execution_request.quantity,
                "price": execution_request.price,
                "risk_approved": risk_result.status == RiskCheckStatus.APPROVED,
                "risk_status": risk_result.status.value,
                "risk_reason": risk_result.reason,
                "risk_warnings": risk_result.warnings,
                "execution_mode": "dry_run",
                "execution_blocked": risk_result.status == RiskCheckStatus.REJECTED,
                "warnings": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

            return response

        except Exception as exc:
            logger.exception("Dry-run execution plan failed")
            return {
                "accepted": False,
                "error": str(exc),
                "execution_mode": "dry_run",
                "execution_blocked": True,
                "warnings": [f"Internal error: {str(exc)}"],
                "timestamp": datetime.utcnow().isoformat(),
            }
