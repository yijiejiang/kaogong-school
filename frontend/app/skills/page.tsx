"use client";

import {
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Loader2,
  Map as MapIcon,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchSkillDetail, fetchSkillMap } from "@/lib/api";
import type { SkillDetail, SkillMap, SkillMapItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const MASTERY_META: Record<
  string,
  { label: string; tile: string; bar: string; dot: string; text: string }
> = {
  strong: {
    label: "熟练",
    tile: "border-[#bfd8cc] bg-[#eef7f2]",
    bar: "bg-[#2f5d50]",
    dot: "bg-[#2f5d50]",
    text: "text-[#2f5d50]",
  },
  practicing: {
    label: "会用",
    tile: "border-[#c9d9e8] bg-[#eef4fa]",
    bar: "bg-[#3f5f7a]",
    dot: "bg-[#3f5f7a]",
    text: "text-[#3f5f7a]",
  },
  learning: {
    label: "了解",
    tile: "border-[#ecd9ae] bg-[#fff8e8]",
    bar: "bg-[#b08244]",
    dot: "bg-[#b08244]",
    text: "text-[#8a6a24]",
  },
  unpracticed: {
    label: "不清楚",
    tile: "border-[#ddd6c9] bg-[#f7f4ee]",
    bar: "bg-[#b8ae9c]",
    dot: "bg-[#b8ae9c]",
    text: "text-[#8a8475]",
  },
  due: {
    label: "待复习",
    tile: "border-[#ecc9c2] bg-[#fdf0ee]",
    bar: "bg-[#c25b45]",
    dot: "bg-[#c25b45]",
    text: "text-[#a33a2a]",
  },
};

export default function SkillMapPage() {
  const [data, setData] = useState<SkillMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [subject, setSubject] = useState("");
  const [focus, setFocus] = useState<"all" | "weak" | "due">("all");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<SkillMapItem | null>(null);
  const [detail, setDetail] = useState<SkillDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await fetchSkillMap());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载技能地图失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const subjects = useMemo(
    () => [...new Set((data?.subjects ?? []).map((item) => item.subject))],
    [data],
  );

  const groups = useMemo(
    () =>
      (data?.subjects ?? [])
        .filter((item) => !subject || item.subject === subject)
        .map((item) => ({
          ...item,
          visibleSkills: item.skills.filter((skill) => {
            if (focus === "weak") {
              return (
                skill.mastery_status === "learning" ||
                skill.mastery_status === "unpracticed"
              );
            }
            if (focus === "due") return skill.mastery_status === "due";
            return true;
          }),
        }))
        .filter((item) => item.visibleSkills.length > 0),
    [data, focus, subject],
  );

  const totals = useMemo(() => {
    const summary = data?.summary ?? {};
    return {
      strong: summary.strong ?? 0,
      practicing: summary.practicing ?? 0,
      learning: summary.learning ?? 0,
      unpracticed: summary.unpracticed ?? 0,
      due: summary.due ?? 0,
      total: summary.total ?? 0,
    };
  }, [data]);

  const openSkill = async (skill: SkillMapItem) => {
    setSelected(skill);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await fetchSkillDetail(skill.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载技能详情失败");
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f4ee] text-ink">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-[#8a8475] hover:text-ink"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回对话
            </Link>
            <h1 className="mt-3 flex items-center gap-2 font-serif text-2xl font-semibold">
              <MapIcon className="h-5 w-5 text-[#3f5f7a]" />
              技能地图
            </h1>
            <p className="mt-1.5 max-w-2xl text-xs leading-5 text-[#6b6459]">
              技能按花生十三体系分类。先看哪个模块最弱，再逐项点开；颜色越深越熟练，灰块表示还没练过。
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              className="h-9 rounded-lg border border-[#d8d0c4] bg-white px-2.5 text-xs outline-none focus:border-ink"
            >
              <option value="">全部科目</option>
              {subjects.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-[#ecc9c2] bg-[#fbe9e7] px-4 py-3 text-xs text-[#a33a2a]">
            {error}
          </div>
        )}

        {loading ? (
          <div className="mt-10 flex items-center justify-center gap-2 text-xs text-[#8a8475]">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在生成技能地图
          </div>
        ) : (
          <>
            <section className="mt-5 rounded-2xl border border-[#e5ded1] bg-white/75 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-medium text-ink">
                  {data?.headline || "技能地图已生成"}
                </p>
                <span className="text-[11px] text-[#8a8475]">
                  共 {totals.total} 项技能
                </span>
              </div>
              <StackedBar totals={totals} />
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
                {(
                  [
                    ["strong", "熟练"],
                    ["practicing", "会用"],
                    ["learning", "了解"],
                    ["unpracticed", "不清楚"],
                    ["due", "待复习"],
                  ] as const
                ).map(([key, label]) => (
                  <span
                    key={key}
                    className="inline-flex items-center gap-1.5 text-[10px] text-[#6b6459]"
                  >
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-sm",
                        MASTERY_META[key].dot,
                      )}
                    />
                    {label} {totals[key]}
                  </span>
                ))}
              </div>
              <div className="mt-3 flex gap-1.5">
                {(
                  [
                    ["all", "全部"],
                    ["weak", "只看薄弱"],
                    ["due", "只看待复习"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setFocus(value)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-[10px] font-medium transition",
                      focus === value
                        ? "border-ink bg-ink text-white"
                        : "border-[#d8d0c4] bg-white text-[#6b6459]",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </section>

            <div className="mt-5 space-y-3">
              {groups.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#d8d0c4] bg-white/50 px-6 py-12 text-center text-xs text-[#8a8475]">
                  当前筛选下没有技能。换个筛选条件，或先在资料库上传资料。
                </div>
              ) : (
                groups.map((group) => {
                  const key = `${group.subject}-${group.module}`;
                  const isCollapsed = collapsed[key] ?? false;
                  return (
                    <section
                      key={key}
                      className="overflow-hidden rounded-2xl border border-[#e5ded1] bg-white/70"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setCollapsed((prev) => ({
                            ...prev,
                            [key]: !isCollapsed,
                          }))
                        }
                        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white"
                      >
                        <Target className="h-4 w-4 shrink-0 text-[#b08244]" />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold">
                              {group.subject} · {group.module}
                            </span>
                            <span className="text-[10px] text-[#8a8475]">
                              {group.total} 项
                            </span>
                            {group.needs_work > 0 && (
                              <span className="rounded-full bg-[#fff4dd] px-2 py-0.5 text-[10px] text-[#8a6a24]">
                                待补 {group.needs_work}
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5 flex items-center gap-2">
                            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#efe9dd]">
                              <div
                                className={cn(
                                  "h-full rounded-full",
                                  group.health >= 70
                                    ? "bg-[#2f5d50]"
                                    : group.health >= 45
                                      ? "bg-[#3f5f7a]"
                                      : group.health >= 25
                                        ? "bg-[#b08244]"
                                        : "bg-[#c25b45]",
                                )}
                                style={{ width: `${Math.max(2, group.health)}%` }}
                              />
                            </div>
                            <span className="w-10 text-right text-[10px] text-[#8a8475]">
                              {Math.round(group.health)}
                            </span>
                          </div>
                        </div>
                        <ChevronRight
                          className={cn(
                            "h-4 w-4 shrink-0 text-[#a59d90] transition",
                            !isCollapsed && "rotate-90",
                          )}
                        />
                      </button>

                      {!isCollapsed && (
                        <div className="border-t border-[#f0ebe1] px-4 py-3">
                          <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5 lg:grid-cols-8">
                            {group.visibleSkills.map((skill) => (
                              <SkillChip
                                key={skill.id}
                                skill={skill}
                                onClick={() => void openSkill(skill)}
                              />
                            ))}
                          </div>
                          {group.visibleSkills.length < group.total && (
                            <p className="mt-2 text-[10px] text-[#a59d90]">
                              已隐藏{" "}
                              {group.total - group.visibleSkills.length}{" "}
                              项已练熟的技能
                            </p>
                          )}
                        </div>
                      )}
                    </section>
                  );
                })
              )}
            </div>
          </>
        )}
      </div>

      {selected && (
        <SkillDrawer
          skill={selected}
          detail={detail}
          loading={detailLoading}
          onClose={() => {
            setSelected(null);
            setDetail(null);
          }}
        />
      )}
    </main>
  );
}

function StackedBar({
  totals,
}: {
  totals: {
    strong: number;
    practicing: number;
    learning: number;
    unpracticed: number;
    due: number;
    total: number;
  };
}) {
  const total = Math.max(totals.total, 1);
  const parts = (
    [
      ["strong", totals.strong],
      ["practicing", totals.practicing],
      ["learning", totals.learning],
      ["unpracticed", totals.unpracticed],
      ["due", totals.due],
    ] as const
  ).filter(([, value]) => value > 0);
  return (
    <div className="mt-2.5 flex h-2.5 overflow-hidden rounded-full bg-[#efe9dd]">
      {parts.map(([key, value]) => (
        <div
          key={key}
          className={cn("h-full", MASTERY_META[key].bar)}
          style={{ width: `${(value / total) * 100}%` }}
          title={`${MASTERY_META[key].label} ${value}`}
        />
      ))}
    </div>
  );
}

function SkillChip({
  skill,
  onClick,
}: {
  skill: SkillMapItem;
  onClick: () => void;
}) {
  const meta = MASTERY_META[skill.mastery_status] ?? MASTERY_META.unpracticed;
  const score = skill.score;
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${skill.name} · ${meta.label}${
        score != null ? ` · ${Math.round(score)} 分` : ""
      }`}
      className={cn(
        "group flex h-14 flex-col justify-between rounded-lg border px-2 py-1.5 text-left transition hover:-translate-y-0.5 hover:shadow-sm",
        meta.tile,
      )}
    >
      <span className="line-clamp-2 text-[10px] font-medium leading-4">
        {skill.name}
      </span>
      <span className={cn("flex items-center justify-between text-[9px]", meta.text)}>
        <span>{meta.label}</span>
        {score != null && <span>{Math.round(score)}</span>}
      </span>
    </button>
  );
}

function SkillDrawer({
  skill,
  detail,
  loading,
  onClose,
}: {
  skill: SkillMapItem;
  detail: SkillDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  const meta = MASTERY_META[skill.mastery_status] ?? MASTERY_META.unpracticed;
  const data = detail?.skill;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 p-0 sm:p-4">
      <button
        type="button"
        aria-label="关闭"
        onClick={onClose}
        className="absolute inset-0 cursor-default"
      />
      <aside className="relative z-10 h-full w-full max-w-xl overflow-y-auto rounded-none border-l border-line bg-[#fdfbf7] p-5 shadow-2xl sm:rounded-2xl sm:border">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-serif text-xl font-semibold">{skill.name}</h2>
              <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", meta.tile, meta.text)}>
                {meta.label}
              </span>
            </div>
            <div className="mt-1 text-[11px] text-[#8a8475]">
              {skill.knowledge_point_name || "未关联知识点"} · 来源{" "}
              {skill.source_unit_count} 个单元 · 练习 {skill.attempts} 次
              {skill.mastery_source === "knowledge_point"
                ? " · 按知识点估算"
                : ""}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-line bg-white p-1.5 text-[#6b6459]"
            aria-label="关闭技能详情"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {loading ? (
          <div className="mt-8 flex items-center gap-2 text-xs text-[#8a8475]">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载技能详情
          </div>
        ) : (
          <div className="mt-5 space-y-4 text-xs leading-6 text-[#5f5a4d]">
            {skill.summary && (
              <p className="rounded-xl bg-white/80 px-3 py-2.5">
                {skill.summary}
              </p>
            )}

            <DrawerSection
              icon={<Sparkles className="h-3.5 w-3.5" />}
              title="怎么考"
              items={data?.exam_patterns ?? skill.exam_patterns}
            />
            <DrawerSection
              icon={<CircleHelp className="h-3.5 w-3.5" />}
              title="题目识别信号"
              items={data?.signals ?? skill.signals}
            />
            <DrawerSection
              icon={<BookOpenCheck className="h-3.5 w-3.5" />}
              title="标准步骤"
              items={data?.steps ?? skill.steps}
              ordered
            />
            <DrawerSection
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              title="易错点"
              items={data?.pitfalls ?? skill.pitfalls}
            />
            <DrawerSection
              title="常见变式"
              items={data?.variants ?? skill.variants}
            />
            <DrawerSection
              title="出题人怎么设干扰"
              items={data?.question_design ?? skill.question_design}
            />
            {(data?.connections ?? skill.connections).length > 0 && (
              <div>
                <SectionTitle title="关联知识点" />
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {(data?.connections ?? skill.connections).map((item) => (
                    <span
                      key={`${item.name}-${item.relation}`}
                      className="rounded-full border border-[#d8d0c4] bg-white px-2 py-0.5 text-[10px]"
                    >
                      {item.relation}：{item.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {detail?.units?.length ? (
              <div>
                <SectionTitle title="来源资料" />
                <div className="mt-1.5 space-y-1.5">
                  {detail.units.map((unit) => (
                    <div
                      key={unit.id}
                      className="rounded-lg border border-[#ece6da] bg-white px-3 py-2"
                    >
                      <div className="text-[11px] font-medium text-ink">
                        {unit.title}
                      </div>
                      <div className="text-[10px] text-[#8a8475]">
                        {unit.material_title || "资料"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <Link
              href="/exams"
              className="inline-flex items-center gap-1.5 rounded-lg bg-ink px-3 py-2 text-[11px] font-medium text-white"
            >
              去考试中心练习
              <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        )}
      </aside>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8a8475]">
      {title}
    </div>
  );
}

function DrawerSection({
  title,
  items,
  icon,
  ordered = false,
}: {
  title: string;
  items: string[];
  icon?: ReactNode;
  ordered?: boolean;
}) {
  if (!items.length) return null;
  const List = ordered ? "ol" : "ul";
  return (
    <div>
      <div className="flex items-center gap-1.5">
        {icon}
        <SectionTitle title={title} />
      </div>
      <List
        className={cn(
          "mt-1.5 space-y-1",
          ordered ? "list-decimal pl-5" : "list-disc pl-5",
        )}
      >
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </List>
    </div>
  );
}
