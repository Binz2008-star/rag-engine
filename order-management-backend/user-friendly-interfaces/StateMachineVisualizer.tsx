/**
 * DESIGN: "Operational Clarity"
 * StateMachineVisualizer — the core observability component
 *
 * Shows the full order lifecycle with:
 * - Current state: filled + strong color
 * - Past states: muted (completed)
 * - Future states: disabled (not yet reached)
 * - Off-path states (FAILED_DELIVERY, CANCELLED): shown separately
 * - Transition arrows: only valid transitions highlighted
 */
import { CheckCircle2, XCircle, AlertCircle, ArrowRight } from "lucide-react";
import {
  OrderStatus,
  STATE_FLOW,
  STATUS_CONFIG,
  ALLOWED_TRANSITIONS,
  isStatePast,
  isStateFuture,
  getFlowIndex,
} from "@/lib/orderStateMachine";

interface StateMachineVisualizerProps {
  currentStatus: OrderStatus;
  compact?: boolean;
}

type NodeState = "active" | "past" | "future" | "error" | "cancelled";

function getNodeState(state: OrderStatus, current: OrderStatus): NodeState {
  if (state === current) {
    if (state === "FAILED_DELIVERY") return "error";
    if (state === "CANCELLED") return "cancelled";
    return "active";
  }
  if (state === "FAILED_DELIVERY" || state === "CANCELLED") return "future";
  if (isStatePast(state, current)) return "past";
  if (isStateFuture(state, current)) return "future";
  return "future";
}

const NODE_STYLES: Record<NodeState, string> = {
  active:    "bg-indigo-600 text-white border-indigo-600 shadow-lg shadow-indigo-200 scale-110",
  past:      "bg-slate-100 text-slate-400 border-slate-200",
  future:    "bg-white text-slate-300 border-slate-200",
  error:     "bg-red-600 text-white border-red-600 shadow-lg shadow-red-200 scale-110",
  cancelled: "bg-gray-600 text-white border-gray-600 shadow-lg shadow-gray-200 scale-110",
};

const CONNECTOR_STYLES: Record<NodeState, string> = {
  active:    "bg-indigo-300",
  past:      "bg-slate-200",
  future:    "bg-slate-100",
  error:     "bg-red-200",
  cancelled: "bg-gray-200",
};

export default function StateMachineVisualizer({ currentStatus, compact = false }: StateMachineVisualizerProps) {
  const isFailed    = currentStatus === "FAILED_DELIVERY";
  const isCancelled = currentStatus === "CANCELLED";

  return (
    <div className="w-full">
      {/* Happy Path Flow */}
      <div className="flex items-center gap-0 overflow-x-auto pb-2">
        {STATE_FLOW.map((state, index) => {
          const nodeState = getNodeState(state, currentStatus);
          const cfg = STATUS_CONFIG[state];
          const isLast = index === STATE_FLOW.length - 1;
          const isCurrentNode = state === currentStatus;

          // Connector color: past if the NEXT state is past or active
          const nextState = STATE_FLOW[index + 1];
          const connectorState = nextState ? getNodeState(nextState, currentStatus) : "future";

          return (
            <div key={state} className="flex items-center flex-shrink-0">
              {/* Node */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`
                    ${compact ? "w-8 h-8 text-xs" : "w-10 h-10 text-xs"}
                    rounded-full border-2 flex items-center justify-center font-semibold
                    transition-all duration-300 relative
                    ${NODE_STYLES[nodeState]}
                  `}
                  title={cfg.label}
                >
                  {nodeState === "past" ? (
                    <CheckCircle2 className={`${compact ? "w-3.5 h-3.5" : "w-4 h-4"}`} />
                  ) : nodeState === "error" ? (
                    <AlertCircle className={`${compact ? "w-3.5 h-3.5" : "w-4 h-4"}`} />
                  ) : nodeState === "cancelled" ? (
                    <XCircle className={`${compact ? "w-3.5 h-3.5" : "w-4 h-4"}`} />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                  {isCurrentNode && (
                    <span className="absolute -top-1 -right-1 w-3 h-3 bg-white rounded-full border-2 border-indigo-600 animate-pulse" />
                  )}
                </div>
                {!compact && (
                  <span className={`text-xs font-medium text-center max-w-[64px] leading-tight ${
                    nodeState === "active" ? "text-indigo-700" :
                    nodeState === "past"   ? "text-slate-400" :
                                             "text-slate-300"
                  }`}>
                    {cfg.label}
                  </span>
                )}
              </div>

              {/* Connector */}
              {!isLast && (
                <div className={`
                  ${compact ? "w-6 h-0.5 mx-0.5" : "w-8 h-0.5 mx-1"}
                  rounded-full transition-all duration-300
                  ${connectorState === "past" || connectorState === "active" ? "bg-indigo-300" : "bg-slate-100"}
                `} />
              )}
            </div>
          );
        })}
      </div>

      {/* Off-path states: FAILED_DELIVERY and CANCELLED */}
      {!compact && (
        <div className="mt-4 flex items-start gap-4">
          {/* FAILED_DELIVERY branch */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${
            isFailed
              ? "bg-red-50 border-red-200 text-red-700"
              : "bg-white border-slate-200 text-slate-400"
          }`}>
            <AlertCircle className={`w-3.5 h-3.5 flex-shrink-0 ${isFailed ? "text-red-500" : "text-slate-300"}`} />
            <div>
              <div className="font-medium">Failed Delivery</div>
              <div className={`text-xs mt-0.5 ${isFailed ? "text-red-600" : "text-slate-300"}`}>
                Can retry → Out for Delivery, or Cancel
              </div>
            </div>
          </div>

          {/* CANCELLED branch */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${
            isCancelled
              ? "bg-gray-50 border-gray-300 text-gray-600"
              : "bg-white border-slate-200 text-slate-400"
          }`}>
            <XCircle className={`w-3.5 h-3.5 flex-shrink-0 ${isCancelled ? "text-gray-500" : "text-slate-300"}`} />
            <div>
              <div className="font-medium">Cancelled</div>
              <div className={`text-xs mt-0.5 ${isCancelled ? "text-gray-500" : "text-slate-300"}`}>
                Terminal state — no further transitions
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Current state label */}
      {compact && (
        <div className="mt-2 flex items-center gap-1.5">
          <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_CONFIG[currentStatus].className}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${STATUS_CONFIG[currentStatus].dotClass}`} />
            {STATUS_CONFIG[currentStatus].label}
          </span>
        </div>
      )}
    </div>
  );
}
