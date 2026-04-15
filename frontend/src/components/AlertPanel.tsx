"use client";

import {
  type AlertRulesResponse,
  type AlertEventsResponse,
  TICKER_LABELS,
} from "@/lib/api";

interface Props {
  rules: AlertRulesResponse | undefined;
  events: AlertEventsResponse | undefined;
}

export default function AlertPanel({ rules, events }: Props) {
  if (!rules && !events) {
    return (
      <div className="h-full flex items-center justify-center text-text-muted text-xs font-mono">
        Loading alerts…
      </div>
    );
  }

  const activeRules = rules?.rules?.filter((r) => r.is_active) || [];
  const recentEvents = events?.events || [];

  // Count active alerts by severity
  const breachCount = recentEvents.filter((e) => e.severity === "breach").length;
  const warningCount = recentEvents.filter((e) => e.severity === "warning").length;

  return (
    <div className="h-full flex flex-col px-3 pt-2 pb-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
          Alert Monitor
        </span>
        <div className="flex items-center gap-2">
          {breachCount > 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-red-500/15 text-red-400">
              {breachCount} breach
            </span>
          )}
          {warningCount > 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-yellow-500/15 text-yellow-400">
              {warningCount} warn
            </span>
          )}
          {breachCount === 0 && warningCount === 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-green-500/15 text-green-400">
              All clear
            </span>
          )}
        </div>
      </div>

      {/* Active rules summary */}
      <div className="rounded-md bg-bg/50 border border-border/30 px-2 py-1.5 mb-2">
        <span className="text-[8px] font-mono text-text-muted uppercase tracking-wider">
          Active Rules ({activeRules.length})
        </span>
        <div className="mt-1 space-y-0.5 max-h-[80px] overflow-y-auto">
          {activeRules.slice(0, 6).map((rule) => {
            const ticker = rule.ticker || "PORTFOLIO";
            const opSym = { gt: ">", gte: "≥", lt: "<", lte: "≤" }[
              rule.operator
            ] || rule.operator;
            return (
              <div
                key={rule.id}
                className="flex items-center justify-between text-[8px] font-mono"
              >
                <span className="text-text-dim">
                  {TICKER_LABELS[ticker] || ticker} {rule.metric_name}
                </span>
                <span className="flex items-center gap-1">
                  <span className="text-text-muted">
                    {opSym} {rule.threshold}
                  </span>
                  <span
                    className={`px-1 rounded ${
                      rule.severity === "breach"
                        ? "bg-red-500/15 text-red-400"
                        : "bg-yellow-500/15 text-yellow-400"
                    }`}
                  >
                    {rule.severity}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent events */}
      <div className="flex-1 overflow-y-auto">
        <span className="text-[9px] font-mono text-text-muted uppercase tracking-wider block mb-1">
          Recent Events
        </span>
        {recentEvents.length === 0 ? (
          <div className="text-center text-text-muted text-[10px] font-mono py-4">
            No recent alerts
          </div>
        ) : (
          <div className="space-y-1">
            {recentEvents.slice(0, 10).map((event, i) => {
              const isBreach = event.severity === "breach";
              const time = new Date(event.time).toLocaleDateString("en-GB", {
                day: "2-digit",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <div
                  key={`${event.rule_id}-${event.time}-${i}`}
                  className={`flex items-start gap-2 rounded px-2 py-1.5 ${
                    isBreach ? "bg-red-500/10" : "bg-yellow-500/10"
                  }`}
                >
                  <div
                    className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${
                      isBreach ? "bg-red-500" : "bg-yellow-500"
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-[9px] font-mono text-text-dim truncate">
                      {event.message}
                    </div>
                    <div className="text-[8px] font-mono text-text-muted mt-0.5">
                      {time}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Compact alert count badge for the dashboard header.
 */
export function AlertBadge({
  events,
}: {
  events: AlertEventsResponse | undefined;
}) {
  if (!events || events.count === 0) return null;

  const breaches = events.events.filter((e) => e.severity === "breach").length;
  const warnings = events.events.filter((e) => e.severity === "warning").length;

  if (breaches === 0 && warnings === 0) return null;

  return (
    <div
      className={`flex items-center gap-1 px-2 py-0.5 rounded ${
        breaches > 0 ? "bg-red-500/15" : "bg-yellow-500/15"
      }`}
    >
      <div
        className={`w-1.5 h-1.5 rounded-full ${
          breaches > 0 ? "bg-red-500" : "bg-yellow-500"
        }`}
      />
      <span
        className={`text-[10px] font-mono ${
          breaches > 0 ? "text-red-400" : "text-yellow-400"
        }`}
      >
        {breaches > 0 ? `${breaches} breach` : `${warnings} warn`}
      </span>
    </div>
  );
}
