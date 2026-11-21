"use client";

import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock3,
  Coins,
  Flame,
  Loader2,
  RefreshCw,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { NotificationBell } from "@/components/NotificationBell";
import {
  fetchAnalyticsOverview,
  fetchUsage,
  fetchWeekPlan,
  fetchWeeklyReport,
  generateWeekPlan,
  togglePlanTask,
} from "@/lib/api";
import type {
  AnalyticsOverview,
  MasteryItem,
  ModuleScore,
  PlanTask,
  TrendPoint,
  UsageSummary,
  WeekPlan,
  WeeklyReport,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const RADAR_MODULES = [
  "言语理解与表达",
  "数量关系",
  "判断推理",
  "资料分析",
  "常识判断",
];

const MODULE_SHORT: Record<string, string> = {
  言语理解与表达: "言语",
  数量关系: "数量",
  判断推理: "判断",
  资料分析: "资料",
  常识判断: "常识",
};

const TASK_TYPE_LABELS: Record<string, string> = {
  review: "复习",
  practice: "练习",
  material: "阅读",
  exam: "小卷",
};

function todayISO(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function shortModule(value: string): string {
  return MODULE_SHORT[value] ?? value.slice(0, 2);
}

function masteryTone(score: number | null, status: string): string {
  if (status === "unpracticed" || score === null) {
    return "border-[#e7e1d8] bg-[#f1ece2] text-[#8a8475]";
  }
  if (score < 40) return "border-[#f0c2b8] bg-[#fbe9e7] text-[#a33a2a]";
  if (score < 60) return "border-[#f0d9a8] bg-[#fff4dd] text-[#8a6a24]";
  if (score < 80) return "border-[#b9d8cc] bg-[#eef7f3] text-[#2f5d50]";
  return "border-[#8fbfa9] bg-[#dcefe5] text-[#245c49]";
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [plan, setPlan] = useState<WeekPlan | null>(null);
  const [weekly, setWeekly] = useState<WeeklyReport | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [overviewData, planData, weeklyData, usageData] = await Promise.all([
        fetchAnalyticsOverview(),
        fetchWeekPlan(),
        fetchWeeklyReport(),
        fetchUsage(),
      ]);
      setOverview(overviewData);
      setPlan(planData);
      setWeekly(weeklyData);
      setUsage(usageData);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "加载学情看板失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const planData = await generateWeekPlan();
      setPlan(planData);
      setWeekly(await fetchWeeklyReport());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "生成计划失败");
    } finally {
      setGenerating(false);
    }
  };

  const handleToggle = async (task: PlanTask) => {
    setTogglingId(task.id);
    setError(null);
    try {
      await togglePlanTask(task.id, task.status !== "done");
      const [planData, weeklyData] = await Promise.all([
        fetchWeekPlan(),
        fetchWeeklyReport(),
      ]);
      setPlan(planData);
      setWeekly(weeklyData);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "更新任务失败");
    } finally {
      setTogglingId(null);
    }
  };

  const radarModules = useMemo<ModuleScore[]>(() => {
    if (!overview) return [];
    return RADAR_MODULES.map(
      (name) =>
        overview.modules.find(
          (item) => item.subject === "行测" && item.module === name,
        ) ?? {
          subject: "行测",
          module: name,
          score: null,
          attempts: 0,
          kp_count: 0,
          practiced: 0,
        },
    );
  }, [overview]);

  const shenlunModules = useMemo(
    () => overview?.modules.filter((item) => item.subject === "申论") ?? [],
    [overview],
  );

  const heatmapGroups = useMemo(() => {
    const groups: Record<string, MasteryItem[]> = {};
    for (const item of overview?.mastery ?? []) {
      if (item.subject !== "行测") continue;
      (groups[item.module || "未分类"] ??= []).push(item);
    }
    return groups;
  }, [overview]);

  if (loading) {
    return (
      <div className="flex h-dvh items-center justify-center bg-[var(--background)] text-sm text-muted">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在统计学情…
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-[var(--background)] px-4">
        <div className="w-full max-w-md rounded-2xl border border-line bg-paper p-6 text-center">
          <AlertTriangle className="mx-auto h-6 w-6 text-amber-600" />
          <h1 className="mt-3 text-base font-semibold">无法加载学情看板</h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            {error ?? "后端没有返回数据。"}
          </p>
          <button
            type="button"
            onClick={() => void refresh()}
            className="mt-4 rounded-xl bg-ink px-4 py-2.5 text-xs font-medium text-white"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  const stats = overview.stats;
  const hasData = stats.graded_attempts > 0;
  const today = todayISO();
  const todayTasks = plan?.days.find((day) => day.date === today)?.tasks ?? [];

  return (
    <div className="min-h-dvh bg-[var(--background)] text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-[#f7f4ee]/90 backdrop-blur">
        <div className="mx-auto flex min-h-16 w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-medium text-ink"
          >
            <ArrowLeft className="h-4 w-4" />
            返回对话
          </Link>
          <div className="text-sm font-semibold">学情看板</div>
          <div className="flex items-center gap-3 text-xs text-muted">
            <NotificationBell />
            <Link href="/exams" className="hover:text-ink">
              考试中心
            </Link>
            <Link href="/library" className="hover:text-ink">
              资料库
            </Link>
            <Link href="/settings" className="hover:text-ink">
              设置
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">学情看板</h1>
            <p className="mt-1 text-sm text-muted">
              所有数字来自真实作答记录；掌握度按难度、置信度和时间衰减计算。
            </p>
          </div>
          <div className="rounded-2xl border border-line bg-paper px-4 py-3">
            <div className="text-sm font-semibold text-ink">
              {overview.profile.name || "同学"}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-muted">
              <span>{overview.profile.target_exam || "国考"}</span>
              <span>·</span>
              <span>
                {overview.exam_countdown_days !== null
                  ? overview.exam_countdown_days >= 0
                    ? `距考试 ${overview.exam_countdown_days} 天`
                    : "考试日期已过"
                  : "未设置考试日期"}
              </span>
              <span>·</span>
              <span>每天 {overview.profile.daily_minutes} 分钟</span>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-5 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!hasData && (
          <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-[#f0d9a8] bg-[#fffaf0] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-semibold text-[#6f5320]">
                还没有做题记录
              </div>
              <p className="mt-1 text-xs leading-5 text-[#8a6a24]">
                先做一次 30 题的资料分析诊断卷，学情看板、薄弱点和周计划都会自动生成。
              </p>
            </div>
            <Link
              href="/exams"
              className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[#8a6a24] px-4 py-2.5 text-xs font-medium text-white"
            >
              去做诊断卷
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={BarChart3}
            label="练习次数"
            value={String(stats.graded_attempts)}
            hint={`共 ${stats.questions} 题`}
          />
          <StatCard
            icon={Target}
            label="正确率"
            value={`${stats.accuracy}%`}
            hint="按已批改试卷统计"
          />
          <StatCard
            icon={Clock3}
            label="学习时长"
            value={`${stats.study_minutes} 分钟`}
            hint="按交卷时间估算"
          />
          <StatCard
            icon={Flame}
            label="知识点覆盖"
            value={`${stats.coverage}%`}
            hint={`${stats.practiced_kps}/${stats.total_kps} 个知识点`}
          />
        </div>

        {overview.alerts.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {overview.alerts.map((alert, index) => (
              <span
                key={`${alert.text}-${index}`}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px]",
                  alert.level === "warning"
                    ? "border-[#f0d9a8] bg-[#fff4dd] text-[#8a6a24]"
                    : "border-line bg-paper text-muted",
                )}
              >
                {alert.level === "warning" ? (
                  <AlertTriangle className="h-3.5 w-3.5" />
                ) : (
                  <Target className="h-3.5 w-3.5" />
                )}
                {alert.text}
              </span>
            ))}
          </div>
        )}

        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <section className="rounded-2xl border border-line bg-paper p-5 lg:col-span-2">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold">模块掌握度</h2>
                <p className="mt-1 text-xs text-muted">
                  行测五个模块的加权掌握度；没有数据的模块按 0 显示。
                </p>
              </div>
              <span className="text-[10px] text-muted">0–100</span>
            </div>
            <div className="mt-3 grid gap-4 md:grid-cols-[280px_1fr] md:items-center">
              <RadarChart modules={radarModules} />
              <div className="space-y-3">
                {radarModules.map((module) => (
                  <ModuleBar key={module.module} module={module} />
                ))}
                {shenlunModules.length > 0 && (
                  <div className="mt-4 border-t border-line pt-3">
                    <div className="text-[10px] font-medium text-muted">
                      申论模块
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {shenlunModules.map((module) => (
                        <span
                          key={module.module}
                          className="rounded-full border border-line bg-white px-2 py-1 text-[10px] text-muted"
                          title={`${module.module} · ${module.score ?? "待评估"}`}
                        >
                          {module.module} ·{" "}
                          {module.score === null ? "待评估" : module.score}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>

          <WeeklyReportCard report={weekly} />
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <section className="rounded-2xl border border-line bg-paper p-5 lg:col-span-2">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold">最近 14 天正确率</h2>
              <span className="text-[10px] text-muted">按天统计</span>
            </div>
            <TrendChart trend={overview.trend} />
          </section>
          <WeakPointsCard weak={overview.weak_points} />
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <section className="rounded-2xl border border-line bg-paper p-5 lg:col-span-2">
            <PlanCard
              plan={plan}
              todayTasks={todayTasks}
              today={today}
              generating={generating}
              togglingId={togglingId}
              onGenerate={() => void handleGenerate()}
              onToggle={(task) => void handleToggle(task)}
            />
          </section>
          <HeatmapCard groups={heatmapGroups} />
        </div>

        <div className="mt-5">
          <UsageCard usage={usage} />
        </div>
      </main>
    </div>
  );
}

function UsageCard({ usage }: { usage: UsageSummary | null }) {
  const totals = usage?.totals;
  const daily = usage?.daily ?? [];
  const maxDay = Math.max(...daily.map((item) => item.total_tokens), 1);
  const roles = usage?.by_role ?? [];
  const maxRole = Math.max(...roles.map((item) => item.total_tokens), 1);
  const hasUsage = (totals?.total_tokens ?? 0) > 0;
  const hasPrice = (totals?.cost ?? 0) > 0;

  return (
    <section className="rounded-2xl border border-line bg-paper p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">模型用量与成本</h2>
          <p className="mt-1 text-xs text-muted">
            按角色统计真实 API token 用量；平台包月渠道不计单次费用，DeepSeek 等按量服务按官方价格估算。
          </p>
        </div>
        <Link
          href="/cost"
          className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 py-1 text-[10px] font-medium text-ink transition hover:border-[#cfc4b5]"
        >
          查看费用
        </Link>
      </div>

      {!hasUsage ? (
        <div className="mt-4 rounded-xl border border-dashed border-line px-4 py-5 text-xs leading-5 text-muted">
          还没有真实模型用量。本地演示模式不调用外部模型，所以不会产生 token；
          配置真实 LLM 后，对话和 AI 原创题都会记录在这里。
        </div>
      ) : (
        <div className="mt-4 grid gap-5 lg:grid-cols-[1.15fr_1fr]">
          <div>
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-line bg-white px-3 py-3">
                <div className="flex items-center gap-1.5 text-[10px] text-muted">
                  <Coins className="h-3 w-3" />
                  调用次数
                </div>
                <div className="mt-1.5 text-lg font-semibold text-ink">
                  {totals?.requests ?? 0}
                </div>
              </div>
              <div className="rounded-xl border border-line bg-white px-3 py-3">
                <div className="text-[10px] text-muted">总 token</div>
                <div className="mt-1.5 text-lg font-semibold text-ink">
                  {formatTokens(totals?.total_tokens ?? 0)}
                </div>
                <div className="mt-0.5 text-[9px] text-muted">
                  入 {formatTokens(totals?.prompt_tokens ?? 0)} · 出{" "}
                  {formatTokens(totals?.completion_tokens ?? 0)}
                </div>
              </div>
              <div className="rounded-xl border border-line bg-white px-3 py-3">
                <div className="text-[10px] text-muted">估算成本</div>
                <div className="mt-1.5 text-lg font-semibold text-ink">
                  {hasPrice ? `¥${totals?.cost.toFixed(2)}` : "—"}
                </div>
                <div className="mt-0.5 text-[9px] text-muted">
                  {hasPrice ? "按单价估算" : "未设置单价"}
                </div>
              </div>
            </div>

            <div className="mt-5">
              <div className="mb-2 flex items-center justify-between text-[10px] text-muted">
                <span>每日 token</span>
                <span>最高 {formatTokens(maxDay)}</span>
              </div>
              <div className="flex h-24 items-end gap-1">
                {daily.map((item) => (
                  <div
                    key={item.date}
                    className="group relative flex-1"
                    title={`${item.date} · ${formatTokens(item.total_tokens)} token`}
                  >
                    <div
                      className="w-full rounded-t bg-accent/70 transition group-hover:bg-accent"
                      style={{
                        height: `${Math.max(
                          (item.total_tokens / maxDay) * 88,
                          item.total_tokens > 0 ? 4 : 1,
                        )}px`,
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-1 flex justify-between text-[9px] text-muted">
                <span>{daily[0]?.date.slice(5) ?? ""}</span>
                <span>{daily[daily.length - 1]?.date.slice(5) ?? ""}</span>
              </div>
            </div>
          </div>

          <div>
            <div className="mb-2 text-[10px] text-muted">按角色</div>
            <div className="space-y-2.5">
              {roles.slice(0, 6).map((item) => (
                <div key={item.role}>
                  <div className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="text-ink">{item.role_label}</span>
                    <span className="text-muted">
                      {formatTokens(item.total_tokens)}
                      {item.cost > 0 ? ` · ¥${item.cost.toFixed(2)}` : ""}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#eee8dd]">
                    <div
                      className="h-full rounded-full bg-[#7f9c8d]"
                      style={{
                        width: `${Math.max(
                          (item.total_tokens / maxRole) * 100,
                          item.total_tokens > 0 ? 3 : 0,
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            {usage?.by_model && usage.by_model.length > 0 && (
              <div className="mt-4 border-t border-line pt-3 text-[10px] leading-5 text-muted">
                模型：
                {usage.by_model
                  .slice(0, 3)
                  .map(
                    (item) =>
                      `${item.model}（${formatTokens(item.total_tokens)}）`,
                  )
                  .join(" · ")}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(value);
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof BarChart3;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-2xl border border-line bg-paper p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-muted">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-2 text-xl font-semibold leading-none text-ink">
        {value}
      </div>
      <div className="mt-1.5 text-[10px] text-muted">{hint}</div>
    </div>
  );
}

function RadarChart({ modules }: { modules: ModuleScore[] }) {
  const size = 280;
  const center = size / 2;
  const radius = 92;
  const count = modules.length || 1;
  const points = modules.map((module, index) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / count;
    const value = Math.max(0, Math.min(100, module.score ?? 0));
    const distance = (value / 100) * radius;
    return {
      x: center + Math.cos(angle) * distance,
      y: center + Math.sin(angle) * distance,
      axisX: center + Math.cos(angle) * radius,
      axisY: center + Math.sin(angle) * radius,
      labelX: center + Math.cos(angle) * (radius + 28),
      labelY: center + Math.sin(angle) * (radius + 20),
      label: shortModule(module.module),
    };
  });
  const polygon = points.map((point) => `${point.x},${point.y}`).join(" ");
  const hasData = modules.some((module) => (module.score ?? 0) > 0);

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="mx-auto h-[280px] w-full max-w-[280px]"
      role="img"
      aria-label="行测模块掌握度雷达图"
    >
      {[0.25, 0.5, 0.75, 1].map((scale) => {
        const ring = modules
          .map((_, index) => {
            const angle = -Math.PI / 2 + (2 * Math.PI * index) / count;
            return `${center + Math.cos(angle) * radius * scale},${center + Math.sin(angle) * radius * scale}`;
          })
          .join(" ");
        return (
          <polygon
            key={scale}
            points={ring}
            fill="none"
            stroke="#e7e1d8"
            strokeWidth="1"
          />
        );
      })}
      {points.map((point, index) => (
        <line
          key={index}
          x1={center}
          y1={center}
          x2={point.axisX}
          y2={point.axisY}
          stroke="#e7e1d8"
          strokeWidth="1"
        />
      ))}
      <polygon
        points={polygon}
        fill="rgba(181, 70, 47, 0.14)"
        stroke="#b5462f"
        strokeWidth="2"
      />
      {points.map((point, index) => (
        <circle
          key={index}
          cx={point.x}
          cy={point.y}
          r="3"
          fill="#b5462f"
        />
      ))}
      {points.map((point, index) => (
        <text
          key={index}
          x={point.labelX}
          y={point.labelY}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="10"
          fill="#6b7280"
        >
          {point.label}
        </text>
      ))}
      {!hasData && (
        <text
          x={center}
          y={center + 4}
          textAnchor="middle"
          fontSize="11"
          fill="#a59d90"
        >
          还没有模块数据
        </text>
      )}
    </svg>
  );
}

function ModuleBar({ module }: { module: ModuleScore }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-2 text-[11px]">
        <span className="font-medium text-ink">{module.module}</span>
        <span className="text-muted">
          {module.score === null ? "待评估" : `${module.score}`}
        </span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-[#eee8dd]">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${Math.max(0, Math.min(100, module.score ?? 0))}%` }}
        />
      </div>
      <div className="mt-1 text-[9px] text-muted">
        已练 {module.practiced}/{module.kp_count} 个知识点 · {module.attempts} 题
      </div>
    </div>
  );
}

function TrendChart({ trend }: { trend: TrendPoint[] }) {
  const hasAttempts = trend.some((point) => point.attempts > 0);
  return (
    <div>
      <div className="mt-4 flex h-40 items-end gap-1.5">
        {trend.map((point) => (
          <div
            key={point.date}
            className="flex min-w-0 flex-1 flex-col items-center gap-1"
            title={`${point.date} · ${point.accuracy}% · ${point.attempts} 次`}
          >
            <div className="flex h-32 w-full items-end">
              <div
                className={cn(
                  "w-full rounded-t",
                  point.attempts > 0 ? "bg-accent/80" : "bg-[#eee8dd]",
                )}
                style={{
                  height: `${point.attempts > 0 ? Math.max(4, point.accuracy) : 4}%`,
                }}
              />
            </div>
            <span className="text-[8px] text-muted">{point.label}</span>
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[9px] text-muted">
        <span>{hasAttempts ? "每根柱 = 当天正确率" : "最近还没有练习记录"}</span>
        <span>100%</span>
      </div>
    </div>
  );
}

function WeeklyReportCard({ report }: { report: WeeklyReport | null }) {
  return (
    <section className="rounded-2xl border border-line bg-paper p-5">
      <div className="flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-accent" />
        <h2 className="text-base font-semibold">本周周报</h2>
      </div>
      {report ? (
        <>
          <p className="mt-3 text-xs leading-6 text-[#5f5a4d]">
            {report.summary}
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 text-[10px] text-muted">
            <ReportStat label="练习" value={`${report.attempts} 次`} />
            <ReportStat label="题量" value={`${report.questions} 题`} />
            <ReportStat label="正确率" value={`${report.accuracy}%`} />
            <ReportStat label="错题" value={`${report.wrong_count} 道`} />
            <ReportStat label="学习时长" value={`${report.study_minutes} 分钟`} />
            <ReportStat label="计划" value={`${report.plan_done}/${report.plan_total}`} />
          </div>
        </>
      ) : (
        <p className="mt-3 text-xs leading-6 text-muted">
          还没有周报。完成一次练习后，这里会自动生成本周总结。
        </p>
      )}
    </section>
  );
}

function ReportStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#faf7f1] px-2.5 py-2">
      <div className="text-[9px] text-muted">{label}</div>
      <div className="mt-0.5 text-xs font-medium text-ink">{value}</div>
    </div>
  );
}

function WeakPointsCard({ weak }: { weak: MasteryItem[] }) {
  return (
    <section className="rounded-2xl border border-line bg-paper p-5">
      <div className="flex items-center gap-2">
        <TrendingDown className="h-4 w-4 text-accent" />
        <h2 className="text-base font-semibold">薄弱知识点</h2>
      </div>
      {weak.length === 0 ? (
        <p className="mt-3 text-xs leading-6 text-muted">
          还没有薄弱点数据。做一次诊断卷后，会按掌握度排序显示。
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          {weak.slice(0, 5).map((item) => (
            <div
              key={item.knowledge_point_id}
              className="rounded-xl border border-line bg-white px-3 py-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-xs font-medium text-ink">
                    {item.knowledge_point_name}
                  </div>
                  <div className="mt-0.5 text-[9px] text-muted">
                    {item.module} · {item.attempts} 题 · 置信度{" "}
                    {Math.round(item.confidence * 100)}%
                  </div>
                </div>
                <div className="shrink-0 text-sm font-semibold text-accent">
                  {item.score ?? "—"}
                </div>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#eee8dd]">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{
                    width: `${Math.max(0, Math.min(100, item.score ?? 0))}%`,
                  }}
                />
              </div>
              <div className="mt-1.5 flex items-center justify-between text-[9px] text-muted">
                <span>
                  {item.due_at ? `复习到期：${item.due_at}` : "还没有复习计划"}
                </span>
                <Link href="/exams" className="font-medium text-accent">
                  去练习
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function HeatmapCard({ groups }: { groups: Record<string, MasteryItem[]> }) {
  const modules = Object.keys(groups);
  return (
    <section className="rounded-2xl border border-line bg-paper p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">知识点热力图</h2>
        <span className="text-[9px] text-muted">行测</span>
      </div>
      {modules.length === 0 ? (
        <p className="mt-3 text-xs text-muted">还没有知识点数据。</p>
      ) : (
        <div className="mt-3 space-y-3">
          {modules.map((module) => (
            <div key={module}>
              <div className="text-[10px] font-medium text-muted">{module}</div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {groups[module].map((item) => (
                  <span
                    key={item.knowledge_point_id}
                    title={`${item.knowledge_point_name} · ${item.score ?? "未练习"} · ${item.attempts} 题`}
                    className={cn(
                      "max-w-full truncate rounded-md border px-1.5 py-1 text-[9px]",
                      masteryTone(item.score, item.status),
                    )}
                  >
                    {item.knowledge_point_name}
                  </span>
                ))}
              </div>
            </div>
          ))}
          <div className="flex flex-wrap gap-2 pt-1 text-[9px] text-muted">
            <Legend className="bg-[#f1ece2]" label="未练习" />
            <Legend className="bg-[#fbe9e7]" label="<40" />
            <Legend className="bg-[#fff4dd]" label="40–60" />
            <Legend className="bg-[#eef7f3]" label="60–80" />
            <Legend className="bg-[#dcefe5]" label="80+" />
          </div>
        </div>
      )}
    </section>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={cn("h-2.5 w-2.5 rounded-sm border border-line", className)} />
      {label}
    </span>
  );
}

function PlanCard({
  plan,
  todayTasks,
  today,
  generating,
  togglingId,
  onGenerate,
  onToggle,
}: {
  plan: WeekPlan | null;
  todayTasks: PlanTask[];
  today: string;
  generating: boolean;
  togglingId: string | null;
  onGenerate: () => void;
  onToggle: (task: PlanTask) => void;
}) {
  const done = plan?.adherence.done ?? 0;
  const total = plan?.adherence.total ?? 0;
  const percent = plan?.adherence.percent ?? 0;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">本周学习计划</h2>
          <p className="mt-1 text-xs text-muted">
            {plan?.goal || "根据薄弱点和复习到期自动生成"}
          </p>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-white px-3 py-2 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
        >
          {generating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          {plan?.tasks.length ? "重新生成" : "生成本周计划"}
        </button>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between text-[10px] text-muted">
          <span>本周完成度</span>
          <span>
            {done}/{total} 项 · {percent}%
          </span>
        </div>
        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#eee8dd]">
          <div
            className="h-full rounded-full bg-[#3f7a66]"
            style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-7 gap-1.5">
        {(plan?.days ?? []).map((day) => {
          const dayDone = day.tasks.filter((task) => task.status === "done").length;
          const active = day.date === today;
          return (
            <div
              key={day.date}
              className={cn(
                "rounded-xl border px-1 py-2 text-center",
                active
                  ? "border-accent bg-[#fbf4ef]"
                  : "border-line bg-white",
              )}
              title={`${day.date} · ${dayDone}/${day.tasks.length} 完成`}
            >
              <div className="text-[9px] text-muted">{day.weekday}</div>
              <div className="mt-0.5 text-[10px] font-semibold text-ink">
                {day.date.slice(8)}
              </div>
              <div className="mt-1 text-[8px] text-muted">
                {dayDone}/{day.tasks.length}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between">
          <div className="text-xs font-medium text-ink">今天</div>
          <div className="text-[10px] text-muted">
            {plan?.daily_minutes || 0} 分钟/天
          </div>
        </div>
        {todayTasks.length === 0 ? (
          <div className="mt-2 rounded-xl border border-dashed border-line px-3 py-4 text-xs text-muted">
            {plan?.tasks.length
              ? "今天没有任务，可以重新生成一周计划。"
              : "还没有本周计划。点“生成本周计划”，会按薄弱点和复习到期自动安排。"}
          </div>
        ) : (
          <div className="mt-2 space-y-1.5">
            {todayTasks.map((task) => {
              const isDone = task.status === "done";
              const isToggling = togglingId === task.id;
              return (
                <div
                  key={task.id}
                  className="flex items-center gap-2.5 rounded-xl border border-line bg-white px-3 py-2.5"
                >
                  <button
                    type="button"
                    onClick={() => onToggle(task)}
                    disabled={isToggling}
                    className="shrink-0 text-accent disabled:opacity-50"
                    aria-label={isDone ? "标记未完成" : "标记完成"}
                  >
                    {isToggling ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : isDone ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <Circle className="h-4 w-4" />
                    )}
                  </button>
                  <div className="min-w-0 flex-1">
                    <div
                      className={cn(
                        "truncate text-xs font-medium",
                        isDone ? "text-muted line-through" : "text-ink",
                      )}
                    >
                      {task.title}
                    </div>
                    <div className="mt-0.5 text-[9px] text-muted">
                      {TASK_TYPE_LABELS[task.task_type] ?? "任务"} ·{" "}
                      {task.minutes} 分钟
                      {task.knowledge_point_name
                        ? ` · ${task.knowledge_point_name}`
                        : ""}
                    </div>
                  </div>
                  <span className="shrink-0 rounded-full bg-[#f1ece2] px-2 py-0.5 text-[9px] text-muted">
                    {TASK_TYPE_LABELS[task.task_type] ?? "任务"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {plan && plan.tasks.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-muted">
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="h-3 w-3" />
            {plan.week_start} → {plan.week_end}
          </span>
          <span className="inline-flex items-center gap-1">
            <TrendingUp className="h-3 w-3 text-[#3f7a66]" />
            完成后计划会按新的薄弱点调整
          </span>
        </div>
      )}
    </div>
  );
}
