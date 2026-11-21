"use client";

import {
  ArrowLeft,
  BadgeDollarSign,
  Loader2,
  RefreshCw,
  Server,
  Sparkles,
  TrendingUp,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchBilling, fetchUsage } from "@/lib/api";
import type {
  BillingOverview,
  UsageProvider,
  UsageSummary,
} from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

const RANGE_OPTIONS = [7, 30, 90, 365] as const;

const MODE_STYLE: Record<string, string> = {
  monthly: "bg-[#e6edf5] text-[#3f5f7f] border-[#c9d9e8]",
  payg: "bg-[#fff4dd] text-[#8a6a24] border-[#ecd9ae]",
  free: "bg-[#e1efe8] text-[#2f5d50] border-[#bfd8cc]",
  unpriced: "bg-[#f1ece2] text-[#6b6459] border-[#ddd6c9]",
};

const SERVICE_LABEL: Record<string, string> = {
  llm: "对话模型",
  embedding: "向量模型",
  search: "联网搜索",
  fetch: "网页抓取",
  ocr: "OCR 识别",
  asr: "语音转写",
  tts: "语音合成",
};

function currency(value: number): string {
  if (!value) return "¥0.00";
  if (value < 0.01) return `¥${value.toFixed(4)}`;
  return `¥${value.toFixed(2)}`;
}

function tokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

export default function CostPage() {
  const [days, setDays] = useState<number>(30);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [billing, setBilling] = useState<BillingOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [usageData, billingData] = await Promise.all([
        fetchUsage(undefined, days),
        fetchBilling(),
      ]);
      setUsage(usageData);
      setBilling(billingData);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载费用失败");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  const maxDaily = useMemo(
    () => Math.max(0.0001, ...(usage?.daily ?? []).map((item) => item.cost)),
    [usage],
  );

  const paidProviders = (usage?.by_provider ?? []).filter(
    (item) => item.billing_mode !== "monthly",
  );

  return (
    <main className="min-h-screen bg-[#f7f4ee] text-ink">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-[#8a8475] hover:text-ink"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回学情看板
            </Link>
            <h1 className="mt-3 flex items-center gap-2 font-serif text-2xl font-semibold">
              <Wallet className="h-5 w-5 text-[#b08244]" />
              费用
            </h1>
            <p className="mt-1.5 max-w-2xl text-xs leading-5 text-[#6b6459]">
              平台接入默认按包月订阅，不计单次费用；DeepSeek 等按量服务按官方价格结算。所有金额都是估算，以供应商账单为准。
            </p>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#d8d0c4] bg-white px-3 text-xs font-medium disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            刷新
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-[#ecc9c2] bg-[#fbe9e7] px-4 py-3 text-xs text-[#a33a2a]">
            {error}
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-1.5">
          {RANGE_OPTIONS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setDays(value)}
              className={cn(
                "rounded-full border px-3 py-1 text-[11px] font-medium transition",
                days === value
                  ? "border-ink bg-ink text-white"
                  : "border-[#d8d0c4] bg-white text-[#6b6459]",
              )}
            >
              近 {value} 天
            </button>
          ))}
        </div>

        {loading && !usage ? (
          <div className="mt-10 flex items-center justify-center gap-2 text-xs text-[#8a8475]">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在统计
          </div>
        ) : (
          usage && (
            <>
              <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard
                  label="按量费用"
                  value={currency(usage.totals.cost)}
                  hint="不含包月订阅"
                  accent="text-[#8a6a24]"
                />
                <StatCard
                  label="包月渠道"
                  value={String(usage.totals.monthly_services)}
                  hint="不计单次费用"
                  accent="text-[#3f5f7f]"
                />
                <StatCard
                  label="调用次数"
                  value={String(usage.totals.requests)}
                  hint={
                    usage.totals.requests === 0
                      ? "还没有调用"
                      : `近 ${usage.days} 天`
                  }
                  accent="text-[#3f5f7a]"
                />
                <StatCard
                  label="Token"
                  value={tokens(usage.totals.total_tokens)}
                  hint={`输入 ${tokens(usage.totals.prompt_tokens)} · 输出 ${tokens(
                    usage.totals.completion_tokens,
                  )}`}
                  accent="text-[#2f5d50]"
                />
              </div>

              {billing && billing.sources.length > 0 && (
                <section className="mt-6 rounded-2xl border border-[#e5ded1] bg-white/70 p-4">
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    <Server className="h-4 w-4 text-[#3f5f7f]" />
                    已接入渠道
                  </h2>
                  <div className="mt-3 space-y-2">
                    {billing.sources.map((source) => (
                      <div
                        key={`${source.provider}-${source.service}`}
                        className="flex flex-wrap items-center gap-2 rounded-xl border border-[#ece6da] bg-white px-3 py-2"
                      >
                        <span className="text-xs font-medium">
                          {source.label}
                        </span>
                        <span className="text-[10px] text-muted">
                          {source.service === "llm"
                            ? source.model || "对话"
                            : SERVICE_LABEL[source.service] ?? source.service}
                        </span>
                        <span className="truncate text-[10px] text-[#a59d90]">
                          {source.base}
                        </span>
                        <span
                          className={cn(
                            "ml-auto rounded-full border px-2 py-0.5 text-[10px] font-medium",
                            MODE_STYLE[source.billing_mode] ??
                              MODE_STYLE.unpriced,
                          )}
                        >
                          {source.billing_label}
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] leading-5 text-[#a59d90]">
                    渠道计费方式按服务商识别，可在设置页按需调整；DeepSeek 官方始终按量计费。
                  </p>
                </section>
              )}

              <section className="mt-6 grid gap-4 sm:grid-cols-2">
                <Panel title="按渠道" icon={<TrendingUp className="h-4 w-4" />}>
                  {usage.by_provider.length === 0 ? (
                    <Empty text="还没有调用记录。" />
                  ) : (
                    <div className="space-y-2">
                      {usage.by_provider.map((item) => (
                        <ProviderRow key={item.provider} item={item} />
                      ))}
                    </div>
                  )}
                </Panel>

                <Panel title="按服务" icon={<Sparkles className="h-4 w-4" />}>
                  {usage.by_service.length === 0 ? (
                    <Empty text="还没有调用记录。" />
                  ) : (
                    <div className="space-y-2">
                      {usage.by_service.map((item) => (
                        <div
                          key={item.service}
                          className="flex items-center justify-between gap-3 rounded-lg border border-[#ece6da] bg-white px-3 py-2"
                        >
                          <div className="min-w-0">
                            <div className="text-xs font-medium">
                              {item.label || SERVICE_LABEL[item.service]}
                            </div>
                            <div className="text-[10px] text-muted">
                              {item.requests} 次
                              {item.units > 0
                                ? ` · ${formatUnits(item.service, item.units)}`
                                : ""}
                            </div>
                          </div>
                          <div className="text-xs font-medium">
                            {currency(item.cost)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>
              </section>

              <section className="mt-6 rounded-2xl border border-[#e5ded1] bg-white/70 p-4">
                <h2 className="text-sm font-semibold">每日费用</h2>
                <div className="mt-4 flex h-32 items-end gap-[2px]">
                  {usage.daily.map((item) => (
                    <div
                      key={item.date}
                      className="group relative flex-1 rounded-t bg-[#b08244]/70 transition hover:bg-[#8a6a24]"
                      style={{
                        height: `${Math.max(
                          2,
                          (item.cost / maxDaily) * 100,
                        )}%`,
                        minWidth: 2,
                      }}
                      title={`${item.date} · ${currency(item.cost)} · ${tokens(
                        item.total_tokens,
                      )} tokens`}
                    />
                  ))}
                </div>
                <div className="mt-1 flex justify-between text-[9px] text-[#a59d90]">
                  <span>{usage.daily[0]?.date}</span>
                  <span>{usage.daily[usage.daily.length - 1]?.date}</span>
                </div>
              </section>

              <section className="mt-6 rounded-2xl border border-[#e5ded1] bg-white/70 p-4">
                <h2 className="text-sm font-semibold">最近调用</h2>
                {usage.recent.length === 0 ? (
                  <Empty text="还没有调用记录。" />
                ) : (
                  <div className="mt-3 space-y-1.5">
                    {usage.recent.slice(0, 12).map((item) => (
                      <div
                        key={item.id}
                        className="flex flex-wrap items-center gap-2 rounded-lg border border-[#ece6da] bg-white px-3 py-2 text-[11px]"
                      >
                        <span className="rounded-full bg-[#f1ece2] px-2 py-0.5 text-[10px]">
                          {item.provider_label}
                        </span>
                        <span className="font-medium">{item.role_label}</span>
                        <span className="truncate text-[10px] text-[#a59d90]">
                          {item.model}
                        </span>
                        <span className="text-[10px] text-muted">
                          {item.total_tokens
                            ? `${tokens(item.total_tokens)} tokens`
                            : formatUnits(item.service, item.units)}
                        </span>
                        <span className="ml-auto text-[10px] text-[#a59d90]">
                          {formatRelative(item.created_at)}
                        </span>
                        <span className="w-16 text-right font-medium">
                          {item.billing_mode === "monthly"
                            ? "包月"
                            : currency(item.cost)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {billing?.price_catalog.deepseek && (
                <section className="mt-6 rounded-2xl border border-[#e5ded1] bg-white/70 p-4">
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    <BadgeDollarSign className="h-4 w-4 text-[#b08244]" />
                    DeepSeek 官方价目
                  </h2>
                  <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
                    {[
                      ["deepseek-flash 输入/输出（高峰）", "¥2 / ¥8 每百万 tokens"],
                      ["deepseek-flash 输入/输出（空闲）", "¥1 / ¥4 每百万 tokens"],
                      ["deepseek-v4-pro 输入/输出（高峰）", "¥9 / ¥27 每百万 tokens"],
                      ["deepseek-v4-pro 输入/输出（空闲）", "¥4.5 / ¥13.5 每百万 tokens"],
                      ["Search / Fetch", "¥5 / 1000 次"],
                      ["OCR", "¥1.5 / 1000 页"],
                      ["ASR", "¥0.39 / 小时（限时 5 折）"],
                    ].map(([label, value]) => (
                      <div
                        key={label}
                        className="flex justify-between gap-3 rounded-lg border border-[#ece6da] bg-white px-3 py-2"
                      >
                        <span className="text-[#6b6459]">{label}</span>
                        <span className="font-medium">{value}</span>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] leading-5 text-[#a59d90]">
                    高峰时段：北京时间周一至周五 9:00–12:00、14:00–18:00，其余为空闲时段。价格以 DeepSeek 官网为准。
                  </p>
                </section>
              )}

              {paidProviders.length === 0 && (
                <p className="mt-4 rounded-xl border border-dashed border-[#d8d0c4] bg-white/50 px-4 py-3 text-[11px] text-[#8a8475]">
                  当前所有已识别渠道都按包月或免费处理，不会产生单次费用。
                </p>
              )}
            </>
          )
        )}
      </div>
    </main>
  );
}

function StatCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint: string;
  accent: string;
}) {
  return (
    <div className="rounded-xl border border-[#e5ded1] bg-white/80 px-4 py-3">
      <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-[#8a8475]">
        {label}
      </div>
      <div className={cn("mt-1 font-serif text-xl", accent)}>{value}</div>
      <div className="mt-0.5 text-[10px] text-[#a59d90]">{hint}</div>
    </div>
  );
}

function Panel({
  title,
  icon,
  children,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-[#e5ded1] bg-white/70 p-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        {icon}
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function ProviderRow({ item }: { item: UsageProvider }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-[#ece6da] bg-white px-3 py-2">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-medium">{item.provider_label}</span>
          <span
            className={cn(
              "rounded-full border px-1.5 py-0.5 text-[9px]",
              MODE_STYLE[item.billing_mode] ?? MODE_STYLE.unpriced,
            )}
          >
            {item.billing_label}
          </span>
        </div>
        <div className="mt-0.5 text-[10px] text-muted">
          {item.requests} 次
          {item.total_tokens > 0 ? ` · ${tokens(item.total_tokens)} tokens` : ""}
        </div>
      </div>
      <div className="text-right">
        <div className="text-xs font-medium">
          {item.billing_mode === "monthly" ? "包月" : currency(item.cost)}
        </div>
      </div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[#d8d0c4] px-3 py-6 text-center text-[11px] text-[#8a8475]">
      {text}
    </div>
  );
}

function formatUnits(service: string, units: number): string {
  if (!units) return "";
  if (service === "asr") {
    const minutes = units / 60;
    return minutes >= 1
      ? `${minutes.toFixed(1)} 分钟音频`
      : `${units.toFixed(0)} 秒音频`;
  }
  if (service === "ocr") return `${Math.round(units)} 页`;
  if (service === "search" || service === "fetch") {
    return `${Math.round(units)} 次`;
  }
  return `${units.toFixed(2)}`;
}
