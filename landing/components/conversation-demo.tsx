"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const DOCS_URL = process.env.NEXT_PUBLIC_DOCS_URL || "/docs";

const PARAMS = [
  ["universe", "nasdaq100"],
  ["screen", "momentum_screen"],
  ["lookback", "200 days, top 20%"],
  ["rebalance", "monthly"],
  ["period", "2023-03-07 to 2025-03-07"],
  ["sizing", "equal_weight"],
  ["capital", "$100,000"],
];

const METRICS = [
  { label: "CAGR", value: "+34.2%", positive: true },
  { label: "Sharpe", value: "1.42", positive: true },
  { label: "Max Drawdown", value: "-8.7%", positive: false },
  { label: "Win Rate", value: "61%", positive: true },
];

const FACTORS = [
  { factor: "Mkt-RF", loading: "1.21", tstat: "14.3", note: "Market beta" },
  { factor: "SMB", loading: "0.08", tstat: "0.71", note: "No size tilt" },
  { factor: "HML", loading: "-0.31", tstat: "-3.12", note: "Growth-leaning" },
  { factor: "Mom", loading: "0.89", tstat: "9.45", note: "Strong momentum" },
];

export function ConversationDemo() {
  const [step, setStep] = useState(0);

  return (
    <section className="px-6 py-20 max-w-6xl mx-auto">
      <p
        className="text-[10px] uppercase tracking-[0.15em] mb-3"
        style={{ fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}
      >
        See it in action
      </p>
      <h2
        className="text-3xl mb-3"
        style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}
      >
        Describe a strategy. Get real analysis.
      </h2>
      <p
        className="text-sm mb-10"
        style={{ color: "var(--text-secondary)" }}
      >
        One prompt. The agent confirms the exact parameters it will use, runs the backtest, and breaks down the returns.
      </p>

      {/* Terminal window */}
      <div className="terminal max-w-4xl">
        <div className="terminal-chrome">
          <div className="terminal-dot" style={{ background: "#ef4444" }} />
          <div className="terminal-dot" style={{ background: "#eab308" }} />
          <div className="terminal-dot" style={{ background: "#22c55e" }} />
          <span
            className="ml-3 text-[11px]"
            style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.35)" }}
          >
            claude — quantcontext
          </span>
        </div>

        <div className="terminal-body space-y-5">
          {/* User prompt */}
          <div>
            <p
              className="text-[13px]"
              style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.45)" }}
            >
              &gt;{" "}
              <span style={{ color: "rgba(255,255,255,0.75)" }}>
                Backtest a top-20% momentum strategy on Nasdaq 100, monthly rebalance, last 2 years
              </span>
            </p>
          </div>

          {/* Step 1: Agent pre-run confirmation */}
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="space-y-3"
          >
            <span
              className="inline-block text-[10px] px-2 py-0.5 rounded"
              style={{
                fontFamily: "var(--font-mono)",
                background: "rgba(37,99,235,0.2)",
                color: "#60a5fa",
              }}
            >
              backtest_strategy
            </span>

            <div
              className="text-[12px] leading-relaxed pl-2 border-l-2"
              style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.55)", borderColor: "rgba(255,255,255,0.12)" }}
            >
              <p className="mb-2" style={{ color: "rgba(255,255,255,0.7)" }}>
                Strategy: Buy the top 20% of Nasdaq 100 stocks by 200-day price momentum, rebalanced monthly. Starting with $100,000.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1 mt-2">
                {PARAMS.map(([k, v]) => (
                  <p key={k}>
                    <span style={{ color: "rgba(255,255,255,0.35)" }}>{k}: </span>
                    <span style={{ color: "rgba(255,255,255,0.65)" }}>{v}</span>
                  </p>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Step 2: Backtest results */}
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.45 }}
            className="space-y-2"
          >
            <p
              className="text-[11px] uppercase tracking-wider"
              style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.3)" }}
            >
              Backtest Results — 2 years, 24 rebalances
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {METRICS.map((m) => (
                <div
                  key={m.label}
                  className="px-3 py-2.5 rounded"
                  style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  <p
                    className="text-[10px] mb-1"
                    style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.3)" }}
                  >
                    {m.label}
                  </p>
                  <p
                    className="text-[15px] font-medium"
                    style={{
                      fontFamily: "var(--font-mono)",
                      color: m.positive ? "#4ade80" : "#f87171",
                    }}
                  >
                    {m.value}
                  </p>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Step 3: Factor analysis */}
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.7 }}
            className="space-y-2"
          >
            <p
              className="text-[11px] uppercase tracking-wider"
              style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.3)" }}
            >
              Factor Analysis — Fama-French 4-Factor
            </p>

            <div className="flex gap-4 flex-wrap mb-2">
              <div
                className="px-3 py-2 rounded"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
              >
                <p className="text-[10px] mb-0.5" style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.3)" }}>
                  Annualized Alpha
                </p>
                <p className="text-[15px] font-medium" style={{ fontFamily: "var(--font-mono)", color: "#4ade80" }}>
                  +4.7%
                  <span className="text-[11px] ml-2" style={{ color: "rgba(255,255,255,0.4)" }}>t=1.87 (not significant)</span>
                </p>
              </div>
              <div
                className="px-3 py-2 rounded"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
              >
                <p className="text-[10px] mb-0.5" style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.3)" }}>
                  R-squared
                </p>
                <p className="text-[15px] font-medium" style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.7)" }}>
                  0.78
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
            <table className="w-full text-[12px]" style={{ fontFamily: "var(--font-mono)" }}>
              <thead>
                <tr style={{ color: "rgba(255,255,255,0.3)" }}>
                  <td className="py-1 pr-6">Factor</td>
                  <td className="py-1 pr-6">Loading</td>
                  <td className="py-1 pr-6">t-stat</td>
                  <td className="py-1">Note</td>
                </tr>
              </thead>
              <tbody>
                {FACTORS.map((f) => (
                  <tr key={f.factor} style={{ color: "rgba(255,255,255,0.6)" }}>
                    <td className="py-0.5 pr-6" style={{ color: "rgba(255,255,255,0.85)" }}>{f.factor}</td>
                    <td className="py-0.5 pr-6">{f.loading}</td>
                    <td className="py-0.5 pr-6">{f.tstat}</td>
                    <td className="py-0.5" style={{ color: "rgba(255,255,255,0.4)" }}>{f.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>

            <p
              className="text-[12px] pt-2 leading-relaxed"
              style={{ fontFamily: "var(--font-mono)", color: "rgba(255,255,255,0.45)", borderTop: "1px solid rgba(255,255,255,0.08)" }}
            >
              <span style={{ color: "rgba(255,255,255,0.6)" }}>Bottom line:</span> The 34% return is real, but mostly systematic exposure to market and momentum factors. Alpha of 4.7% is not statistically significant (|t| &lt; 2). The strategy earns the momentum premium, not idiosyncratic edge.
            </p>
          </motion.div>
        </div>
      </div>

      <motion.div
        className="mt-6 flex flex-wrap items-center gap-4 sm:gap-6"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: 0.9 }}
      >
        <p
          className="text-xs"
          style={{ fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}
        >
          Every number above was computed from historical market data.
        </p>
        <a
          href={DOCS_URL + "/examples/momentum-strategy"}
          className="text-xs underline underline-offset-4 decoration-1 whitespace-nowrap"
          style={{ fontFamily: "var(--font-mono)", color: "var(--color-accent)" }}
        >
          See full example in docs
        </a>
      </motion.div>
    </section>
  );
}
