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

type PerformanceLevel = {
  deployment_frequency: string;
  lead_time: string;
  change_failure_rate: string;
  mttr: string;
  overall: string;
};

type BusinessCorrelation = {
  status: string;
  correlations: Record<string, number | null>;
  insights: Array<{
    type: string;
    insight: string;
    recommendation: string;
  }>;
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
  const [error, setError] = useState<string | null>(null);
  const [githubPat, setGithubPat] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [performanceLevel, setPerformanceLevel] = useState<PerformanceLevel | null>(null);
  const [businessCorrelations, setBusinessCorrelations] = useState<BusinessCorrelation | null>(null);
  const [showBusinessPanel, setShowBusinessPanel] = useState(false);
  const invalidRepo = !repo.includes("/");
  const safeLookback = Math.max(1, Number(lookback) || 1);

  const activeMetrics = orgMode ? orgMetrics : metrics;

  // Calculate all four DORA metrics
  const doraStats = useMemo(() => {
    if (activeMetrics.length === 0) {
      return {
        deploymentFrequency: 0,
        avgLeadTime: 0,
        changeFailureRate: 0,
        mttr: 0,
        totalDeployments: 0,
        daysWithData: 0,
      };
    }

    const totalDeployments = activeMetrics.reduce((s, m) => s + (m.deployment_frequency || 0), 0);
    const avgLeadTime = activeMetrics.reduce((s, m) => s + (m.avg_lead_time_minutes || 0), 0) / activeMetrics.length;
    const avgCfr = activeMetrics.reduce((s, m) => s + (m.change_failure_rate || 0), 0) / activeMetrics.length;
    const avgMttr = activeMetrics.reduce((s, m) => s + (m.mttr_minutes || 0), 0) / activeMetrics.length;
    
    // Deployment frequency as deploys per day
    const deploymentFrequency = totalDeployments / activeMetrics.length;

    return {
      deploymentFrequency,
      avgLeadTime,
      changeFailureRate: avgCfr,
      mttr: avgMttr,
      totalDeployments,
      daysWithData: activeMetrics.length,
    };
  }, [activeMetrics]);

  // Keep legacy totals for backward compatibility
  const totals = useMemo(() => ({
    deployments: doraStats.totalDeployments,
    avgLead: doraStats.avgLeadTime,
  }), [doraStats]);

  async function runIngest() {
    if (invalidRepo) {
      setError("Repo must be in owner/repo format");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          repositories: [repo], 
          lookback_days: safeLookback,
          github_pat: githubPat || undefined 
        }),
      });
      await loadMetrics();
      await loadInsights();
      await loadContributors();
    } catch (e: any) {
      setError(e?.message || "Ingestion failed");
    } finally {
      setLoading(false);
    }
  }

  async function loadMetrics() {
    const patParam = githubPat ? `&github_pat=${encodeURIComponent(githubPat)}` : "";
    if (orgMode) {
      try {
        const res = await fetch(`${API_BASE}/metrics/org?range_days=${safeLookback}`);
        const data = await res.json();
        setOrgMetrics(data.metrics || []);
        setError(null);
      } catch (e: any) {
        setError(e?.message || "Failed to load org metrics");
      }
    } else {
      try {
        const res = await fetch(`${API_BASE}/metrics/dora?repo=${encodeURIComponent(repo)}&range_days=${safeLookback}`);
        const data = await res.json();
        setMetrics(data.metrics || []);
        setError(null);
      } catch (e: any) {
        setError(e?.message || "Failed to load metrics");
      }
    }
  }

  async function loadInsights() {
    try {
      const res = await fetch(`${API_BASE}/insights/daily?repo=${encodeURIComponent(repo)}&limit=5`);
      const data = await res.json();
      setInsights(data.insights || []);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load insights");
    }
  }

  async function loadContributors() {
    try {
      const patParam = githubPat ? `&github_pat=${encodeURIComponent(githubPat)}` : "";
      const res = await fetch(
        `${API_BASE}/metrics/contributors?repo=${encodeURIComponent(repo)}&lookback_days=${safeLookback}${patParam}`
      );
      const data = await res.json();
      setContributors(data.authors || []);
      setRiskFlags(data.risk_flags || []);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load contributors");
    }
  }

  async function sendChat() {
    if (invalidRepo) {
      setError("Repo must be in owner/repo format");
      return;
    }
    if (!chatMsg.trim()) {
      setError("Ask a question before sending");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          repo, 
          message: chatMsg.trim(), 
          lookback_days: safeLookback,
          github_pat: githubPat || undefined 
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = (data && (data.detail || data.message)) || "Chat failed";
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        setChatAnswer("");
        return;
      }
      setChatAnswer(data.answer || "");
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Chat failed");
    } finally {
      setLoading(false);
    }
  }

  async function loadDrilldown(date: string) {
    setDrilldownDate(date);
    try {
      const patParam = githubPat ? `&github_pat=${encodeURIComponent(githubPat)}` : "";
      const res = await fetch(
        `${API_BASE}/metrics/dora/drilldown?repo=${encodeURIComponent(repo)}&date=${encodeURIComponent(date)}${patParam}`
      );
      const data = await res.json();
      setDrilldownItems(data.pull_requests || []);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Failed to load pull requests");
    }
  }

  async function loadPerformanceLevel() {
    try {
      const repoParam = repo ? `repo=${encodeURIComponent(repo)}&` : "";
      const res = await fetch(
        `${API_BASE}/business/performance-level?${repoParam}range_days=${safeLookback}`
      );
      const data = await res.json();
      if (data.performance_levels) {
        setPerformanceLevel(data.performance_levels);
      }
    } catch (e: any) {
      console.error("Failed to load performance level:", e);
    }
  }

  async function loadBusinessCorrelations() {
    try {
      const res = await fetch(
        `${API_BASE}/business/correlations?org_id=default&range_days=90`
      );
      const data = await res.json();
      setBusinessCorrelations(data);
    } catch (e: any) {
      console.error("Failed to load business correlations:", e);
    }
  }

  useEffect(() => {
    loadMetrics();
    loadPerformanceLevel();
    loadInsights();
    loadContributors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo, lookback, orgMode]);

      return (
        <main className="pb-16">
          <div className="mx-auto max-w-6xl px-4 space-y-8">
            <section className="rounded-2xl border border-white/10 bg-white/5 px-6 py-10 shadow-glass backdrop-blur">
              <div className="flex flex-col gap-4">
                {error && (
                  <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                    {error}
                  </div>
                )}
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-200">MCP-powered insights</p>
                <h1 className="text-3xl sm:text-4xl font-bold leading-tight text-white">Technical Metrics Observation Dashboard</h1>
                <p className="text-slate-200/80 max-w-2xl text-base leading-relaxed">
                  Ingest GitHub via MCP, compute DORA, surface risks, and chat with your repos—all in one teal-forward workspace.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-brand-500 to-emerald-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-900/40 transition hover:shadow-xl"
                    onClick={runIngest}
                    disabled={loading || invalidRepo}
                  >
                    {loading ? "Working..." : "Run ingestion"}
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white/80 transition hover:border-brand-400/60 hover:text-white"
                    onClick={() => loadMetrics()}
                  >
                    Refresh metrics
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white/80 transition hover:border-brand-400/60 hover:text-white"
                    onClick={() => setShowSettings(!showSettings)}
                  >
                    ⚙️ Settings
                  </button>
                </div>
                
                {/* Settings Panel */}
                {showSettings && (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-white">GitHub Configuration</h4>
                      <button
                        className="text-xs text-slate-400 hover:text-white"
                        onClick={() => setShowSettings(false)}
                      >
                        ✕ Close
                      </button>
                    </div>
                    <label className="flex flex-col gap-2 text-sm text-slate-200/80">
                      GitHub Personal Access Token (PAT)
                      <input
                        type="password"
                        className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-slate-400/80 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                        value={githubPat}
                        onChange={(e) => setGithubPat(e.target.value)}
                        placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                      />
                      <span className="text-xs text-slate-400">
                        Enter your GitHub PAT to access private repos or increase rate limits. 
                        {githubPat ? " ✓ Token configured" : " Leave empty to use server default."}
                      </span>
                    </label>
                  </div>
                )}
              </div>
            </section>

            {/* DORA Metrics Cards - All Four Key Metrics */}
            <section className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-glass backdrop-blur">
              <div className="mb-6">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Key Performance Indicators</p>
                <h2 className="text-2xl font-bold text-white">DORA Metrics</h2>
                <p className="text-sm text-slate-400 mt-1">
                  {doraStats.daysWithData > 0 
                    ? `Based on ${doraStats.daysWithData} days of data (${doraStats.totalDeployments} total deployments)`
                    : "Run ingestion to collect metrics"
                  }
                </p>
              </div>
              
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {/* Deployment Frequency */}
                <div className="rounded-xl border border-white/10 bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/20 text-xl">
                      🚀
                    </div>
                    <div>
                      <p className="text-xs font-medium text-emerald-300/80 uppercase tracking-wide">Deployment Frequency</p>
                    </div>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">
                      {doraStats.deploymentFrequency.toFixed(1)}
                    </span>
                    <span className="text-sm text-slate-400">deploys/day</span>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    Total: {doraStats.totalDeployments} deployments
                  </div>
                  {performanceLevel && (
                    <div className={`mt-3 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      performanceLevel.deployment_frequency === "Elite" ? "bg-emerald-500/20 text-emerald-300" :
                      performanceLevel.deployment_frequency === "High" ? "bg-blue-500/20 text-blue-300" :
                      performanceLevel.deployment_frequency === "Medium" ? "bg-yellow-500/20 text-yellow-300" :
                      "bg-red-500/20 text-red-300"
                    }`}>
                      {performanceLevel.deployment_frequency}
                    </div>
                  )}
                </div>

                {/* Lead Time for Changes */}
                <div className="rounded-xl border border-white/10 bg-gradient-to-br from-blue-500/10 to-blue-600/5 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/20 text-xl">
                      ⏱️
                    </div>
                    <div>
                      <p className="text-xs font-medium text-blue-300/80 uppercase tracking-wide">Lead Time for Changes</p>
                    </div>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">
                      {doraStats.avgLeadTime < 60 
                        ? doraStats.avgLeadTime.toFixed(0) 
                        : (doraStats.avgLeadTime / 60).toFixed(1)
                      }
                    </span>
                    <span className="text-sm text-slate-400">
                      {doraStats.avgLeadTime < 60 ? "minutes" : "hours"}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    From commit to production
                  </div>
                  {performanceLevel && (
                    <div className={`mt-3 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      performanceLevel.lead_time === "Elite" ? "bg-emerald-500/20 text-emerald-300" :
                      performanceLevel.lead_time === "High" ? "bg-blue-500/20 text-blue-300" :
                      performanceLevel.lead_time === "Medium" ? "bg-yellow-500/20 text-yellow-300" :
                      "bg-red-500/20 text-red-300"
                    }`}>
                      {performanceLevel.lead_time}
                    </div>
                  )}
                </div>

                {/* Change Failure Rate */}
                <div className="rounded-xl border border-white/10 bg-gradient-to-br from-amber-500/10 to-amber-600/5 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/20 text-xl">
                      🛡️
                    </div>
                    <div>
                      <p className="text-xs font-medium text-amber-300/80 uppercase tracking-wide">Change Failure Rate</p>
                    </div>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">
                      {(doraStats.changeFailureRate * 100).toFixed(1)}
                    </span>
                    <span className="text-sm text-slate-400">%</span>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    Deployments causing failures
                  </div>
                  {performanceLevel && (
                    <div className={`mt-3 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      performanceLevel.change_failure_rate === "Elite" ? "bg-emerald-500/20 text-emerald-300" :
                      performanceLevel.change_failure_rate === "High" ? "bg-blue-500/20 text-blue-300" :
                      performanceLevel.change_failure_rate === "Medium" ? "bg-yellow-500/20 text-yellow-300" :
                      "bg-red-500/20 text-red-300"
                    }`}>
                      {performanceLevel.change_failure_rate}
                    </div>
                  )}
                </div>

                {/* Mean Time to Restore */}
                <div className="rounded-xl border border-white/10 bg-gradient-to-br from-purple-500/10 to-purple-600/5 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/20 text-xl">
                      🔧
                    </div>
                    <div>
                      <p className="text-xs font-medium text-purple-300/80 uppercase tracking-wide">Mean Time to Restore</p>
                    </div>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">
                      {doraStats.mttr < 60 
                        ? doraStats.mttr.toFixed(0) 
                        : doraStats.mttr < 1440
                          ? (doraStats.mttr / 60).toFixed(1)
                          : (doraStats.mttr / 1440).toFixed(1)
                      }
                    </span>
                    <span className="text-sm text-slate-400">
                      {doraStats.mttr < 60 ? "minutes" : doraStats.mttr < 1440 ? "hours" : "days"}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    Recovery from incidents
                  </div>
                  {performanceLevel && (
                    <div className={`mt-3 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      performanceLevel.mttr === "Elite" ? "bg-emerald-500/20 text-emerald-300" :
                      performanceLevel.mttr === "High" ? "bg-blue-500/20 text-blue-300" :
                      performanceLevel.mttr === "Medium" ? "bg-yellow-500/20 text-yellow-300" :
                      "bg-red-500/20 text-red-300"
                    }`}>
                      {performanceLevel.mttr}
                    </div>
                  )}
                </div>
              </div>

              {/* Overall Performance Badge */}
              {performanceLevel && (
                <div className="mt-6 flex items-center justify-center">
                  <div className={`inline-flex items-center gap-3 rounded-full px-6 py-3 ${
                    performanceLevel.overall === "Elite" ? "bg-emerald-500/20 border border-emerald-500/30" :
                    performanceLevel.overall === "High" ? "bg-blue-500/20 border border-blue-500/30" :
                    performanceLevel.overall === "Medium" ? "bg-yellow-500/20 border border-yellow-500/30" :
                    "bg-red-500/20 border border-red-500/30"
                  }`}>
                    <span className="text-2xl">
                      {performanceLevel.overall === "Elite" ? "🏆" :
                       performanceLevel.overall === "High" ? "⭐" :
                       performanceLevel.overall === "Medium" ? "📈" : "🎯"}
                    </span>
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wide">Overall Performance</p>
                      <p className={`text-lg font-bold ${
                        performanceLevel.overall === "Elite" ? "text-emerald-300" :
                        performanceLevel.overall === "High" ? "text-blue-300" :
                        performanceLevel.overall === "Medium" ? "text-yellow-300" :
                        "text-red-300"
                      }`}>
                        {performanceLevel.overall} Performer
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </section>

            {/* Performance Level & Business Impact Section */}
            {performanceLevel && (
              <section className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-glass backdrop-blur">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">Business Impact</p>
                    <h3 className="text-xl font-semibold text-white">DORA Performance Levels</h3>
                  </div>
                  <button
                    className="text-sm text-brand-200 hover:text-brand-100"
                    onClick={() => setShowBusinessPanel(!showBusinessPanel)}
                  >
                    {showBusinessPanel ? "Hide Details" : "Show Details"}
                  </button>
                </div>
                
                <div className="grid gap-4 md:grid-cols-4">
                  {[
                    { key: "deployment_frequency", label: "Deploy Frequency", icon: "🚀" },
                    { key: "lead_time", label: "Lead Time", icon: "⏱️" },
                    { key: "change_failure_rate", label: "Failure Rate", icon: "🛡️" },
                    { key: "mttr", label: "Recovery Time", icon: "🔧" },
                  ].map(({ key, label, icon }) => {
                    const level = performanceLevel[key as keyof PerformanceLevel];
                    return (
                      <div key={key} className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
                        <div className="text-2xl mb-1">{icon}</div>
                        <div className="text-xs text-slate-400 mb-1">{label}</div>
                        <div className={`text-sm font-semibold ${
                          level === "Elite" ? "text-emerald-400" :
                          level === "High" ? "text-blue-400" :
                          level === "Medium" ? "text-yellow-400" :
                          "text-red-400"
                        }`}>
                          {level}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {showBusinessPanel && (
                  <div className="mt-4 space-y-4">
                    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                      <h4 className="text-sm font-semibold text-white mb-3">What This Means for Your Business</h4>
                      <div className="space-y-2 text-sm text-slate-300">
                        {performanceLevel.overall === "Elite" && (
                          <>
                            <p>✅ <strong>Elite teams</strong> deploy 973x more frequently than low performers</p>
                            <p>✅ Your engineering velocity directly enables faster time-to-market</p>
                            <p>✅ Lower incident rates mean higher customer satisfaction</p>
                          </>
                        )}
                        {performanceLevel.overall === "High" && (
                          <>
                            <p>📈 <strong>High performers</strong> are well-positioned for growth</p>
                            <p>📈 Focus on reducing lead time to reach elite status</p>
                            <p>📈 Consider investing in deployment automation</p>
                          </>
                        )}
                        {performanceLevel.overall === "Medium" && (
                          <>
                            <p>⚠️ <strong>Medium performers</strong> have room for significant improvement</p>
                            <p>⚠️ Slower delivery may impact competitive advantage</p>
                            <p>⚠️ Higher failure rates increase operational costs</p>
                          </>
                        )}
                        {performanceLevel.overall === "Low" && (
                          <>
                            <p>🚨 <strong>Low performers</strong> face significant business risks</p>
                            <p>🚨 Slow delivery cycles hurt time-to-market</p>
                            <p>🚨 High failure rates impact customer trust and revenue</p>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                      <h4 className="text-sm font-semibold text-white mb-3">DORA Research Benchmarks</h4>
                      <div className="overflow-auto">
                        <table className="w-full text-xs text-slate-300">
                          <thead>
                            <tr className="text-left text-slate-400">
                              <th className="pb-2">Metric</th>
                              <th className="pb-2">Elite</th>
                              <th className="pb-2">High</th>
                              <th className="pb-2">Medium</th>
                              <th className="pb-2">Low</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td className="py-1">Deploy Frequency</td>
                              <td className="text-emerald-400">Multiple/day</td>
                              <td className="text-blue-400">Daily-Weekly</td>
                              <td className="text-yellow-400">Weekly-Monthly</td>
                              <td className="text-red-400">&lt; Monthly</td>
                            </tr>
                            <tr>
                              <td className="py-1">Lead Time</td>
                              <td className="text-emerald-400">&lt; 1 hour</td>
                              <td className="text-blue-400">&lt; 1 day</td>
                              <td className="text-yellow-400">&lt; 1 week</td>
                              <td className="text-red-400">&gt; 1 week</td>
                            </tr>
                            <tr>
                              <td className="py-1">Failure Rate</td>
                              <td className="text-emerald-400">0-15%</td>
                              <td className="text-blue-400">16-30%</td>
                              <td className="text-yellow-400">31-45%</td>
                              <td className="text-red-400">&gt; 45%</td>
                            </tr>
                            <tr>
                              <td className="py-1">Recovery Time</td>
                              <td className="text-emerald-400">&lt; 1 hour</td>
                              <td className="text-blue-400">&lt; 1 day</td>
                              <td className="text-yellow-400">&lt; 1 week</td>
                              <td className="text-red-400">&gt; 1 week</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {businessCorrelations && businessCorrelations.insights && businessCorrelations.insights.length > 0 && (
                      <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                        <h4 className="text-sm font-semibold text-white mb-3">Business Correlation Insights</h4>
                        <div className="space-y-2">
                          {businessCorrelations.insights.map((insight, i) => (
                            <div key={i} className={`rounded-lg p-3 ${
                              insight.type === "positive" ? "bg-emerald-500/10 border border-emerald-500/30" :
                              insight.type === "warning" ? "bg-yellow-500/10 border border-yellow-500/30" :
                              "bg-slate-500/10 border border-slate-500/30"
                            }`}>
                              <p className="text-sm text-white">{insight.insight}</p>
                              <p className="text-xs text-slate-400 mt-1">💡 {insight.recommendation}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </section>
            )}

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
