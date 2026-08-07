"use client";

import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { motion } from "framer-motion";
import {
  BarChart3,
  BookOpen,
  MessageSquareX,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";

import Sidebar from "@/components/ui/sidebar";
import LoginForm from "@/components/auth/LoginForm";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";
import {
  getAnalyticsStats,
  getTopSources,
  getKnowledgeGaps,
  AnalyticsStats,
  TopSource,
  KnowledgeGap,
  ApiError,
} from "@/lib/api-client";

// ── Stat Card ───────────────────────────────────────────────────────────────
function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  delay = 0,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
  value: string | number;
  sub?: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      className="rounded-2xl border border-border/60 bg-card p-5 flex items-start gap-4"
    >
      <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
        <Icon className="size-5 text-primary" />
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
          {label}
        </p>
        <p className="mt-0.5 text-2xl font-bold text-foreground tabular-nums">
          {value}
        </p>
        {sub && (
          <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
        )}
      </div>
    </motion.div>
  );
}

// ── Empty placeholder ───────────────────────────────────────────────────────
function EmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td
        colSpan={99}
        className="py-8 text-center text-sm text-muted-foreground"
      >
        {message}
      </td>
    </tr>
  );
}

// ── Shimmer skeleton ────────────────────────────────────────────────────────
function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`shimmer rounded-lg ${className}`} />
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [sources, setSources] = useState<TopSource[]>([]);
  const [gaps, setGaps] = useState<KnowledgeGap[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = getToken();
    if (t && !isTokenExpired(t)) {
      setToken(t);
    } else {
      clearToken();
    }
    setAuthChecked(true);
  }, []);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError(null);

    Promise.all([
      getAnalyticsStats(token),
      getTopSources(token),
      getKnowledgeGaps(token),
    ])
      .then(([s, src, g]) => {
        setStats(s);
        setSources(src.top_sources);
        setGaps(g.knowledge_gaps);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setError("Admin access required to view analytics.");
        } else {
          setError(
            err instanceof Error ? err.message : "Failed to load analytics"
          );
        }
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (!authChecked) return null;
  if (!token)
    return <LoginForm onSuccess={() => setToken(getToken())} />;

  // Format date labels: "Aug 5"
  const chartData =
    stats?.daily_volume.map((d) => ({
      date: new Date(d.date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      queries: d.count,
    })) ?? [];

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 overflow-y-auto scrollbar">
        <div className="max-w-5xl mx-auto px-6 py-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <div className="flex items-center gap-3 mb-1">
              <div className="flex size-9 items-center justify-center rounded-xl gradient-brand">
                <BarChart3 className="size-5 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
            </div>
            <p className="text-sm text-muted-foreground ml-12">
              Real-time insights from the audit log and knowledge base.
            </p>
          </motion.div>

          {/* Error */}
          {error && (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
              <AlertTriangle className="size-4 text-destructive shrink-0 mt-0.5" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* Stat Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
            {loading ? (
              <>
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
              </>
            ) : (
              <>
                <StatCard
                  icon={TrendingUp}
                  label="Total Queries"
                  value={stats?.total_queries.toLocaleString() ?? "—"}
                  sub="lifetime"
                  delay={0}
                />
                <StatCard
                  icon={BarChart3}
                  label="Avg Confidence"
                  value={stats ? `${stats.avg_confidence}%` : "—"}
                  sub="across all answered queries"
                  delay={0.06}
                />
                <StatCard
                  icon={BookOpen}
                  label="Answer Rate"
                  value={stats ? `${stats.answer_rate}%` : "—"}
                  sub="queries routed as 'answer'"
                  delay={0.12}
                />
              </>
            )}
          </div>

          {/* Volume Chart */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18, duration: 0.35 }}
            className="rounded-2xl border border-border/60 bg-card p-6 mb-8"
          >
            <h2 className="text-sm font-semibold text-foreground mb-4">
              Query Volume — Last 30 Days
            </h2>
            {loading ? (
              <Skeleton className="h-48" />
            ) : chartData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
                No query data yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="brandGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor="oklch(0.68 0.28 265)"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="oklch(0.68 0.28 265)"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    interval="preserveStartEnd"
                    stroke="oklch(0.60 0.03 265)"
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={32}
                    stroke="oklch(0.60 0.03 265)"
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "oklch(0.14 0.025 265)",
                      border: "1px solid oklch(1 0 0 / 10%)",
                      borderRadius: "12px",
                      fontSize: 12,
                    }}
                    itemStyle={{ color: "oklch(0.90 0.01 265)" }}
                    labelStyle={{ color: "oklch(0.60 0.03 265)", marginBottom: 4 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="queries"
                    name="Queries"
                    stroke="oklch(0.68 0.28 265)"
                    strokeWidth={2}
                    fill="url(#brandGrad)"
                    dot={false}
                    activeDot={{ r: 4, fill: "oklch(0.68 0.28 265)" }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </motion.div>

          {/* Bottom grid: Top Sources + Knowledge Gaps */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Sources */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.24, duration: 0.35 }}
              className="rounded-2xl border border-border/60 bg-card p-6"
            >
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <BookOpen className="size-4 text-primary" />
                Top Sources
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left border-b border-border/50">
                      <th className="pb-2 text-xs font-semibold text-muted-foreground/60 uppercase tracking-wider">
                        Document
                      </th>
                      <th className="pb-2 text-xs font-semibold text-muted-foreground/60 uppercase tracking-wider text-right">
                        Citations
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={2} className="pt-4">
                          <div className="space-y-2">
                            {[...Array(4)].map((_, i) => (
                              <Skeleton key={i} className="h-5" />
                            ))}
                          </div>
                        </td>
                      </tr>
                    ) : sources.length === 0 ? (
                      <EmptyRow message="No source data yet." />
                    ) : (
                      sources.map((s, i) => (
                        <tr
                          key={s.title}
                          className="border-b border-border/30 last:border-0"
                        >
                          <td className="py-2.5 pr-4">
                            <div className="flex items-center gap-2">
                              <span className="text-xs tabular-nums text-muted-foreground/50 w-4">
                                {i + 1}
                              </span>
                              <span className="font-medium text-foreground text-xs truncate max-w-[200px]">
                                {s.title}
                              </span>
                            </div>
                          </td>
                          <td className="py-2.5 text-right">
                            <span className="rounded-full bg-primary/10 text-primary text-xs font-semibold px-2 py-0.5 tabular-nums">
                              {s.citations}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </motion.div>

            {/* Knowledge Gaps */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.30, duration: 0.35 }}
              className="rounded-2xl border border-border/60 bg-card p-6"
            >
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <MessageSquareX className="size-4 text-amber-500" />
                Knowledge Gaps
                <span className="ml-auto text-xs text-muted-foreground font-normal">
                  Low-confidence / unanswered
                </span>
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left border-b border-border/50">
                      <th className="pb-2 text-xs font-semibold text-muted-foreground/60 uppercase tracking-wider">
                        Query
                      </th>
                      <th className="pb-2 text-xs font-semibold text-muted-foreground/60 uppercase tracking-wider text-right">
                        Conf.
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={2} className="pt-4">
                          <div className="space-y-2">
                            {[...Array(4)].map((_, i) => (
                              <Skeleton key={i} className="h-5" />
                            ))}
                          </div>
                        </td>
                      </tr>
                    ) : gaps.length === 0 ? (
                      <EmptyRow message="No knowledge gaps recorded." />
                    ) : (
                      gaps.slice(0, 10).map((g) => (
                        <tr
                          key={g.id}
                          className="border-b border-border/30 last:border-0"
                        >
                          <td className="py-2.5 pr-4">
                            <p className="text-xs text-foreground font-medium truncate max-w-[220px]">
                              {g.query}
                            </p>
                            <p className="text-[10px] text-muted-foreground/60 mt-0.5">
                              {new Date(g.created_at).toLocaleDateString()}
                            </p>
                          </td>
                          <td className="py-2.5 text-right">
                            <span className="rounded-full bg-amber-500/10 text-amber-500 text-xs font-semibold px-2 py-0.5 tabular-nums">
                              {Math.round(g.confidence)}%
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </motion.div>
          </div>
        </div>
      </main>
    </div>
  );
}
