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
  risk_flags: string[];
  top_contributors: { author: string; pr_count: number }[];
};

type Contributor = { author: string; commit_count: number };

export default function Home() {
  const [repo, setRepo] = useState("owner/repo");
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
    <main className="min-h-screen p-8">
      <div className="max-w-5xl mx-auto space-y-10">
        <header>
          <h1 className="text-3xl font-semibold mb-2">GitHub MCP Productivity Engine</h1>
          <p className="text-slate-600">Ingest GitHub via MCP, compute DORA, view insights, and chat.</p>
        </header>

        <section className="grid gap-6 md:grid-cols-3">
          <div className="p-4 rounded-lg border bg-white shadow-sm md:col-span-2">
            <h2 className="text-lg font-semibold mb-3">Ingest & Metrics</h2>
            <div className="flex flex-col gap-3 mb-4">
              <label className="flex flex-col text-sm">
                Repository (owner/repo)
                <input
                  className="border rounded px-2 py-1"
                  value={repo}
                  onChange={(e) => setRepo(e.target.value)}
                />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={orgMode}
                  onChange={(e) => setOrgMode(e.target.checked)}
                />
                Organization view (aggregate all repos)
              </label>
              <label className="flex flex-col text-sm">
                Lookback days
                <input
                  type="number"
                  className="border rounded px-2 py-1"
                  value={lookback}
                  onChange={(e) => setLookback(Number(e.target.value))}
                  min={1}
                  max={90}
                />
              </label>
              <button
                className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-50"
                onClick={runIngest}
                disabled={loading}
              >
                {loading ? "Working..." : "Run Ingestion"}
              </button>
            </div>
            <div className="flex gap-6 text-sm text-slate-700">
              <div>Deployments: <strong>{totals.deployments}</strong></div>
              <div>Avg Lead (min): <strong>{totals.avgLead.toFixed(1)}</strong></div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="h-64 border rounded p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={activeMetrics} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" hide />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="deployment_frequency" stroke="#2563eb" name="Deployments" />
                    <Line type="monotone" dataKey="avg_lead_time_minutes" stroke="#16a34a" name="Lead (m)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="h-64 border rounded p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={activeMetrics} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" hide />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="change_failure_rate" fill="#f97316" name="CFR" />
                    <Bar dataKey="mttr_minutes" fill="#ef4444" name="MTTR (m)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="mt-4 overflow-auto">
              <table className="min-w-full text-sm border">
                <thead className="bg-slate-100">
                  <tr>
                    <th className="px-2 py-1 border">Date</th>
                    <th className="px-2 py-1 border">Deployments</th>
                    <th className="px-2 py-1 border">Lead Time (m)</th>
                    <th className="px-2 py-1 border">CFR</th>
                    <th className="px-2 py-1 border">MTTR (m)</th>
                  </tr>
                </thead>
                <tbody>
                  {activeMetrics.map((m) => (
                    <tr
                      key={m.date}
                      className="odd:bg-white even:bg-slate-50 hover:bg-blue-50 cursor-pointer"
                      onClick={() => loadDrilldown(m.date)}
                    >
                      <td className="px-2 py-1 border">{m.date}</td>
                      <td className="px-2 py-1 border text-center">{m.deployment_frequency}</td>
                      <td className="px-2 py-1 border text-center">{m.avg_lead_time_minutes.toFixed(1)}</td>
                      <td className="px-2 py-1 border text-center">{m.change_failure_rate.toFixed(2)}</td>
                      <td className="px-2 py-1 border text-center">{m.mttr_minutes.toFixed(1)}</td>
                    </tr>
                  ))}
                  {!activeMetrics.length && (
                    <tr>
                      <td className="px-2 py-2 border text-center" colSpan={5}>No metrics yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="p-4 rounded-lg border bg-white shadow-sm">
            <h2 className="text-lg font-semibold mb-3">Chat</h2>
            <textarea
              className="w-full border rounded px-2 py-1 text-sm"
              rows={4}
              value={chatMsg}
              onChange={(e) => setChatMsg(e.target.value)}
            />
            <button
              className="mt-2 bg-slate-900 text-white px-3 py-2 rounded disabled:opacity-50"
              onClick={sendChat}
              disabled={loading}
            >
              {loading ? "Sending..." : "Send"}
            </button>
            <p className="text-sm text-slate-700 mt-3 whitespace-pre-wrap">{chatAnswer}</p>
          </div>
        </section>

        <section className="p-4 rounded-lg border bg-white shadow-sm">
          <h2 className="text-lg font-semibold mb-3">Daily Insights</h2>
          <div className="space-y-2 text-sm">
            {insights.map((ins) => (
              <div key={ins.date} className="p-3 border rounded">
                <div className="font-semibold">{ins.date}</div>
                <div className="text-slate-700">{ins.summary_text}</div>
                {ins.risk_flags?.length ? (
                  <div className="text-red-600">Risks: {ins.risk_flags.join(", ")}</div>
                ) : null}
              </div>
            ))}
            {!insights.length && <div className="text-slate-600">No insights yet.</div>}
          </div>
        </section>

        <section className="p-4 rounded-lg border bg-white shadow-sm">
          <h2 className="text-lg font-semibold mb-3">Contributor Risk</h2>
          {riskFlags.length > 0 && (
            <div className="text-red-600 text-sm mb-2">Risk flags: {riskFlags.join(", ")}</div>
          )}
          <div className="space-y-1 text-sm">
            {contributors.map((c) => (
              <div key={c.author} className="flex justify-between border rounded px-2 py-1">
                <span>{c.author}</span>
                <span>{c.commit_count} commits</span>
              </div>
            ))}
            {!contributors.length && <div className="text-slate-600">No contributor data yet.</div>}
          </div>
        </section>

        {drilldownDate && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-20" onClick={() => setDrilldownDate(null)}>
            <div className="bg-white rounded-lg shadow-lg max-w-xl w-full p-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-lg font-semibold">Drilldown for {drilldownDate}</h3>
                <button className="text-sm text-blue-600" onClick={() => setDrilldownDate(null)}>Close</button>
              </div>
              <div className="space-y-2 max-h-96 overflow-auto text-sm">
                {drilldownItems.map((pr) => (
                  <div key={pr.id || pr.url} className="border rounded p-2">
                    <div className="font-semibold">{pr.title}</div>
                    <div className="text-slate-600">Merged at: {pr.merged_at}</div>
                    {pr.html_url && (
                      <a className="text-blue-600" href={pr.html_url} target="_blank" rel="noreferrer">View PR</a>
                    )}
                  </div>
                ))}
                {!drilldownItems.length && <div className="text-slate-600">No pull requests merged that day.</div>}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
