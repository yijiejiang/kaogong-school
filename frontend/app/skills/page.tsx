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
  { label: string; tile: string; bar: string; text: string }
> = {
  strong: {
    label: "熟练",
    tile: "border-[#bfd8cc] bg-[#eef7f2]",
    bar: "bg-[#2f5d50]",
    text: "text-[#2f5d50]",
  },
  practicing: {
    label: "会用",
    tile: "border-[#c9d9e8] bg-[#eef4fa]",
    bar: "bg-[#3f5f7a]",
    text: "text-[#3f5f7a]",
  },
  learning: {
    label: "了解",
    tile: "border-[#ecd9ae] bg-[#fff8e8]",
    bar: "bg-[#b08244]",
    text: "text-[#8a6a24]",
  },
  unpracticed: {
    label: "不清楚",
    tile: "border-[#ddd6c9] bg-[#f7f4ee]",
    bar: "bg-[#b8ae9c]",
    text: "text-[#8a8475]",
  },
  due: {
    label: "待复习",
    tile: "border-[#ecc9c2] bg-[#fdf0ee]",
    bar: "bg-[#c25b45]",
    text: "text-[#a33a2a]",
  },
};

export default function SkillMapPage() {
  const [data, setData] = useState<SkillMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [subject, setSubject] = useState("");
  const [module, setModule] = useState("");
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
  const modules = useMemo(
    () => [
      ...new Set(
        (data?.subjects ?? [])
          .filter((item) => !subject || item.subject === subject)
          .map((item) => item.module),
      ),
    ],
    [data, subject],
  );
  const groups = useMemo(
    () =>
      (data?.subjects ?? []).filter(
        (item) =>
          (!subject || item.subject === subject) &&
          (!module || item.module === module),
      ),
    [data, module, subject],
  );

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
              按板块查看每项技能的掌握状态。颜色越深表示越熟练；点开可以看到它怎么考、怎么识别、步骤和变式。
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={subject}
              onChange={(event) => {
                setSubject(event.target.value);
                setModule("");
              }}
              className="h-9 rounded-lg border border-[#d8d0c4] bg-white px-2.5 text-xs outline-none focus:border-ink"
            >
              <option value="">全部科目</option>
              {subjects.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <select
              value={module}
              onChange={(event) => setModule(event.target.value)}
              className="h-9 rounded-lg border border-[#d8d0c4] bg-white px-2.5 text-xs outline-none focus:border-ink"
            >
              <option value="">全部模块</option>
              {modules.map((item) => (
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
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                ["熟练", data?.summary.strong ?? 0, "strong"],
                ["会用", data?.summary.practicing ?? 0, "practicing"],
                ["了解", data?.summary.learning ?? 0, "learning"],
                ["不清楚", data?.summary.unpracticed ?? 0, "unpracticed"],
                ["待复习", data?.summary.due ?? 0, "due"],
              ].map(([label, value, tone]) => (
                <div
                  key={String(label)}
                  className="rounded-xl border border-[#e5ded1] bg-white/80 px-4 py-3"
                >
                  <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-[#8a8475]">
                    {label}
                  </div>
                  <div
                    className={cn(
                      "mt-1 font-serif text-xl",
                      MASTERY_META[String(tone)]?.text,
                    )}
                  >
                    {value}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 space-y-6">
              {groups.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#d8d0c4] bg-white/50 px-6 py-12 text-center text-xs text-[#8a8475]">
                  还没有技能。先在资料库上传资料，入库后会自动挖掘技能。
                </div>
              ) : (
                groups.map((group) => (
                  <section
                    key={`${group.subject}-${group.module}`}
                    className="rounded-2xl border border-[#e5ded1] bg-white/60 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Target className="h-4 w-4 text-[#b08244]" />
                        <h2 className="text-sm font-semibold">
                          {group.subject} · {group.module}
                        </h2>
                        <span className="text-[10px] text-[#8a8475]">
                          {group.skills.length} 项技能
                        </span>
                      </div>
                      <div className="text-[10px] text-[#8a8475]">
                        {group.average_score != null
                          ? `平均掌握 ${group.average_score}`
                          : "暂无练习数据"}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                      {group.skills.map((skill) => (
                        <SkillTile
                          key={skill.id}
                          skill={skill}
                          onClick={() => void openSkill(skill)}
                        />
                      ))}
                    </div>
                  </section>
                ))
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

function SkillTile({
  skill,
  onClick,
}: {
  skill: SkillMapItem;
  onClick: () => void;
}) {
  const meta = MASTERY_META[skill.mastery_status] ?? MASTERY_META.unpracticed;
  const score = skill.score ?? 0;
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group rounded-xl border p-3 text-left transition hover:-translate-y-0.5 hover:shadow-sm",
        meta.tile,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold">{skill.name}</div>
          <div className="mt-0.5 truncate text-[10px] text-[#8a8475]">
            {skill.knowledge_point_name || "未关联知识点"}
          </div>
        </div>
        <span className={cn("shrink-0 text-[10px] font-medium", meta.text)}>
          {meta.label}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/70">
        <div
          className={cn("h-full rounded-full", meta.bar)}
          style={{ width: `${Math.max(4, Math.min(100, score))}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-[10px] text-[#8a8475]">
        <span>
          {score ? `${Math.round(score)} 分` : "未练习"} · 来源{" "}
          {skill.source_unit_count}
          {skill.mastery_source === "knowledge_point" ? " · 知识点估算" : ""}
        </span>
        <ChevronRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
      </div>
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
