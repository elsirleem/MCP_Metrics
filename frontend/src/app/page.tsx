"use client";

import { useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type DoraMetric = {
  date: string;
  deployment_frequency: number;
  avg_lead_time_minutes: number;
  change_failure_rate: number;
  mttr_minutes: number;
};

type OrgMetric = DoraMetric;

type Insight = {
  date: string;
  summary_text: string;
  risk_flags?: string[];
};

type Contributor = {
  author: string;
  commit_count: number;
};

export default function Home() {
  const [repo, setRepo] = useState("elsirleem/SE4IoT_project");
  const [lookback, setLookback] = useState(7);
  const [metrics, setMetrics] = useState<DoraMetric[]>([]);
  const [orgMetrics, setOrgMetrics] = useState<OrgMetric[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [chatMsg, setChatMsg] = useState("What shipped?");
  const [chatAnswer, setChatAnswer] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [orgMode, setOrgMode] = useState(false);
  const [contributors, setContributors] = useState<Contributor[]>([]);
  const [riskFlags, setRiskFlags] = useState<string[]>([]);
  const [drilldownDate, setDrilldownDate] = useState<string | null>(null);
  const [drilldownItems, setDrilldownItems] = useState<any[]>([]);

  const activeMetrics = orgMode ? orgMetrics : metrics;

  const totals = useMemo(() => {
    const dep = activeMetrics.reduce((s, m) => s + (m.deployment_frequency || 0), 0);
    const lead = activeMetrics.reduce((s, m) => s + (m.avg_lead_time_minutes || 0), 0);
    return {
      deployments: dep,
      avgLead: activeMetrics.length ? lead / activeMetrics.length : 0,
    };
  }, [activeMetrics]);

  async function runIngest() {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repositories: [repo], lookback_days: lookback }),
      });
      await loadMetrics();
      await loadInsights();
      await loadContributors();
    } finally {
      setLoading(false);
    }
  }

  async function loadMetrics() {
    if (orgMode) {
      const res = await fetch(`${API_BASE}/metrics/org?range_days=${lookback}`);
      const data = await res.json();
      setOrgMetrics(data.metrics || []);
    } else {
      const res = await fetch(`${API_BASE}/metrics/dora?repo=${encodeURIComponent(repo)}&range_days=${lookback}`);
      const data = await res.json();
      setMetrics(data.metrics || []);
    }
  }

  async function loadInsights() {
    const res = await fetch(`${API_BASE}/insights/daily?repo=${encodeURIComponent(repo)}&limit=5`);
    const data = await res.json();
    setInsights(data.insights || []);
  }

  async function loadContributors() {
    const res = await fetch(
      `${API_BASE}/metrics/contributors?repo=${encodeURIComponent(repo)}&lookback_days=${lookback}`
    );
    const data = await res.json();
    setContributors(data.authors || []);
    setRiskFlags(data.risk_flags || []);
  }

  async function sendChat() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo, message: chatMsg, lookback_days: lookback }),
      });
      const data = await res.json();
      setChatAnswer(data.answer || "");
    } finally {
      setLoading(false);
    }
  }

  async function loadDrilldown(date: string) {
    setDrilldownDate(date);
    const res = await fetch(
      `${API_BASE}/metrics/dora/drilldown?repo=${encodeURIComponent(repo)}&date=${encodeURIComponent(date)}`
    );
    const data = await res.json();
    setDrilldownItems(data.pull_requests || []);
  }

  useEffect(() => {
    loadMetrics();
    loadInsights();
    loadContributors();
      }, [repo, lookback, orgMode]);

      return (
        <main className="pb-16">
          <div className="mx-auto max-w-6xl px-4 space-y-8">
            <section className="rounded-2xl border border-white/10 bg-white/5 px-6 py-10 shadow-glass backdrop-blur">
              <div className="flex flex-col gap-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-200">MCP-powered insights</p>
                <h1 className="text-3xl sm:text-4xl font-bold leading-tight text-white">GitHub Productivity Command Center</h1>
                <p className="text-slate-200/80 max-w-2xl text-base leading-relaxed">
                  Ingest GitHub via MCP, compute DORA, surface risks, and chat with your repos—all in one teal-forward workspace.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-brand-500 to-emerald-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-900/40 transition hover:shadow-xl"
                    onClick={runIngest}
                    disabled={loading}
                  >
                    {loading ? "Working..." : "Run ingestion"}
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white/80 transition hover:border-brand-400/60 hover:text-white"
                    onClick={() => loadMetrics()}
                  >
                    Refresh metrics
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-semibold text-white/90">
                    Deployments: {totals.deployments}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-semibold text-white/90">
                    Avg lead (m): {totals.avgLead.toFixed(1)}
                  </span>
                </div>
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2 space-y-4">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-glass backdrop-blur">
                  <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap justify-between gap-2">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Ingest & Metrics</p>
                        <h3 className="text-xl font-semibold text-white">Track delivery in real time</h3>
                      </div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                      <label className="flex flex-col gap-2 text-sm text-slate-200/80">
                        Repository (owner/repo)
                        <input
                          className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-slate-400/80 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                          value={repo}
                          onChange={(e) => setRepo(e.target.value)}
                        />
                      </label>
                      <label className="flex items-center gap-2 text-sm text-slate-200/80">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-white/30 bg-white/10 text-brand-500 focus:ring-brand-500"
                          checked={orgMode}
                          onChange={(e) => setOrgMode(e.target.checked)}
                        />
                        Organization view (aggregate all repos)
                      </label>
                      <label className="flex flex-col gap-2 text-sm text-slate-200/80">
                        Lookback days
                        <input
                          type="number"
                          className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-slate-400/80 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                          value={lookback}
                          onChange={(e) => setLookback(Number(e.target.value))}
                          min={1}
                          max={90}
                        />
                      </label>
                    </div>
                    <div className="flex flex-wrap gap-3 pt-1">
                      <button
                        className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-brand-500 to-emerald-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-900/40 transition hover:shadow-xl disabled:opacity-60"
                        onClick={runIngest}
                        disabled={loading}
                      >
                        {loading ? "Working..." : "Run ingestion"}
                      </button>
                      <button
                        className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white/80 transition hover:border-brand-400/60 hover:text-white"
                        onClick={loadInsights}
                      >
                        Refresh insights
                      </button>
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-glass backdrop-blur">
                    <div className="mb-2 text-sm font-semibold text-white/90">Deployments & Lead Time</div>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={activeMetrics} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                          <XAxis dataKey="date" hide />
                          <YAxis stroke="#94a3b8" />
                          <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1f2937" }} />
                          <Line type="monotone" dataKey="deployment_frequency" stroke="#14b8a6" strokeWidth={2} name="Deployments" />
                          <Line type="monotone" dataKey="avg_lead_time_minutes" stroke="#22c55e" strokeWidth={2} name="Lead (m)" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-glass backdrop-blur">
                    <div className="mb-2 text-sm font-semibold text-white/90">Stability</div>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={activeMetrics} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                          <XAxis dataKey="date" hide />
                          <YAxis stroke="#94a3b8" />
                          <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1f2937" }} />
                          <Bar dataKey="change_failure_rate" fill="#f97316" name="CFR" radius={[8, 8, 0, 0]} />
                          <Bar dataKey="mttr_minutes" fill="#ef4444" name="MTTR (m)" radius={[8, 8, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-glass backdrop-blur">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Metrics table</p>
                      <h3 className="text-lg font-semibold text-white">Daily rollup</h3>
                    </div>
                  </div>
                  <div className="overflow-auto rounded-xl border border-white/10 bg-slate-900/40">
                    <table className="min-w-full text-sm text-slate-100/90">
                      <thead className="bg-white/5 text-left text-xs uppercase text-slate-300">
                        <tr>
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2">Deployments</th>
                          <th className="px-3 py-2">Lead Time (m)</th>
                          <th className="px-3 py-2">CFR</th>
                          <th className="px-3 py-2">MTTR (m)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeMetrics.map((m) => (
                          <tr
                            key={m.date}
                            className="border-t border-white/5 transition hover:bg-white/5 cursor-pointer"
                            onClick={() => loadDrilldown(m.date)}
                          >
                            <td className="px-3 py-2">{m.date}</td>
                            <td className="px-3 py-2 text-center">{m.deployment_frequency}</td>
                            <td className="px-3 py-2 text-center">{m.avg_lead_time_minutes.toFixed(1)}</td>
                            <td className="px-3 py-2 text-center">{m.change_failure_rate.toFixed(2)}</td>
                            <td className="px-3 py-2 text-center">{m.mttr_minutes.toFixed(1)}</td>
                          </tr>
                        ))}
                        {!activeMetrics.length && (
                          <tr>
                            <td className="px-3 py-3 text-center text-slate-400" colSpan={5}>
                              No metrics yet.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-glass backdrop-blur">
                  <div className="mb-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Chat</p>
                    <h3 className="text-lg font-semibold text-white">Ask your repo</h3>
                  </div>
                  <textarea
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-white placeholder:text-slate-400/80 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                    rows={5}
                    value={chatMsg}
                    onChange={(e) => setChatMsg(e.target.value)}
                    placeholder="What shipped last week?"
                  />
                  <button
                    className="mt-2 w-full rounded-xl bg-gradient-to-r from-brand-500 to-emerald-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-900/40 transition hover:shadow-xl disabled:opacity-60"
                    onClick={sendChat}
                    disabled={loading}
                  >
                    {loading ? "Sending..." : "Send"}
                  </button>
                  <p className="mt-3 text-sm text-slate-300 whitespace-pre-wrap">
                    {chatAnswer || "Response will appear here."}
                  </p>
                </div>
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-glass backdrop-blur">
                <div className="mb-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Daily Insights</p>
                  <h3 className="text-lg font-semibold text-white">Summaries & risks</h3>
                </div>
                <div className="space-y-3">
                  {insights.map((ins) => (
                    <div key={ins.date} className="rounded-xl border border-white/10 bg-slate-900/40 p-3">
                      <div className="mb-2 flex items-center gap-2">
                        <span className="rounded-full bg-brand-500/20 px-2.5 py-1 text-xs font-semibold text-brand-100">
                          {ins.date}
                        </span>
                        {ins.risk_flags?.length ? (
                          <span className="rounded-full bg-red-500/20 px-2.5 py-1 text-xs font-semibold text-red-100">
                            Risks
                          </span>
                        ) : null}
                      </div>
                      <div className="text-sm text-slate-100">{ins.summary_text}</div>
                      {ins.risk_flags?.length ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {ins.risk_flags.map((r) => (
                            <span key={r} className="rounded-lg border border-red-500/30 bg-red-500/10 px-2 py-1 text-xs text-red-100">
                              {r}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                  {!insights.length && <div className="text-sm text-slate-400">No insights yet.</div>}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-glass backdrop-blur">
                <div className="mb-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Contributor Risk</p>
                  <h3 className="text-lg font-semibold text-white">Who’s shipping</h3>
                </div>
                {riskFlags.length > 0 && (
                  <div className="mb-2 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                    Risk flags: {riskFlags.join(", ")}
                  </div>
                )}
                <div className="space-y-2">
                  {contributors.map((c) => (
                    <div key={c.author} className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-900/40 px-3 py-2">
                      <span className="text-sm text-white">{c.author}</span>
                      <span className="text-xs text-slate-300">{c.commit_count} commits</span>
                    </div>
                  ))}
                  {!contributors.length && <div className="text-sm text-slate-400">No contributor data yet.</div>}
                </div>
              </div>
            </section>
          </div>

          {drilldownDate && (
            <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/60 px-3 py-6" onClick={() => setDrilldownDate(null)}>
              <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-slate-900/90 p-5 shadow-2xl backdrop-blur" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Drilldown</p>
                    <h3 className="text-xl font-semibold text-white">{drilldownDate}</h3>
                  </div>
                  <button
                    className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm font-semibold text-white/80 transition hover:border-brand-400/60 hover:text-white"
                    onClick={() => setDrilldownDate(null)}
                  >
                    Close
                  </button>
                </div>
                <div className="mt-4 max-h-[420px] space-y-3 overflow-auto pr-1">
                  {drilldownItems.map((pr) => (
                    <div key={pr.id || pr.url} className="rounded-xl border border-white/10 bg-slate-800/60 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-white">{pr.title}</div>
                        {pr.html_url && (
                          <a className="text-sm font-semibold text-brand-200 hover:text-brand-100" href={pr.html_url} target="_blank" rel="noreferrer">
                            View PR
                          </a>
                        )}
                      </div>
                      <div className="text-xs text-slate-300">Merged at: {pr.merged_at}</div>
                    </div>
                  ))}
                  {!drilldownItems.length && <div className="text-sm text-slate-400">No pull requests merged that day.</div>}
                </div>
              </div>
            </div>
          )}
        </main>
      );
    }
