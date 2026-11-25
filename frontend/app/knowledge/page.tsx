"use client";

import {
  ArrowLeft,
  BadgeCheck,
  Check,
  ChevronDown,
  ChevronRight,
  CircleSlash,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createKnowledgeUnit,
  createPointFromUnit,
  extractMaterialUnits,
  fetchKnowledgeUnits,
  fetchMaterials,
  fetchSkills,
  updateKnowledgeUnit,
  updateSkill,
} from "@/lib/api";
import type { KnowledgeUnit, Material, Skill } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

const CHUNK_TYPE_LABEL: Record<string, string> = {
  method: "方法",
  formula: "公式",
  definition: "定义",
  trap: "陷阱",
  example: "例题",
  question: "题目",
  summary: "摘要",
};

const STATUS_META: Record<
  string,
  { label: string; className: string }
> = {
  draft: { label: "待审核", className: "bg-[#fff4dd] text-[#8a6a24]" },
  approved: { label: "已通过", className: "bg-[#e1efe8] text-[#2f5d50]" },
  rejected: { label: "已驳回", className: "bg-[#fbe9e7] text-[#a33a2a]" },
};

type StatusFilter =
  | "all"
  | "draft"
  | "approved"
  | "rejected"
  | "proposal";

export default function KnowledgeMiningPage() {
  const [units, setUnits] = useState<KnowledgeUnit[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [tab, setTab] = useState<"units" | "skills">("units");
  const [status, setStatus] = useState<StatusFilter>("draft");
  const [materialId, setMaterialId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);

  const load = useCallback(async () => {
    try {
      const [unitList, skillList] = await Promise.all([
        fetchKnowledgeUnits({
          materialId,
          limit: 200,
        }),
        fetchSkills({ limit: 200 }),
      ]);
      setUnits(unitList);
      setSkills(skillList);
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "加载知识挖掘结果失败",
      });
    } finally {
      setLoading(false);
    }
  }, [materialId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    fetchMaterials()
      .then(setMaterials)
      .catch(() => setMaterials([]));
  }, []);

  const counts = useMemo(
    () => ({
      draft: units.filter((unit) => unit.status === "draft").length,
      approved: units.filter((unit) => unit.status === "approved").length,
      rejected: units.filter((unit) => unit.status === "rejected").length,
      skills: skills.length,
    }),
    [skills, units],
  );

  const visibleUnits = useMemo(() => {
    if (status === "all") return units;
    if (status === "proposal") {
      return units.filter((unit) => Boolean(unit.proposed_knowledge_point));
    }
    return units.filter((unit) => unit.status === status);
  }, [status, units]);

  const visibleSkills = useMemo(
    () =>
      status === "all"
        ? skills
        : skills.filter((skill) => skill.status === status),
    [skills, status],
  );

  const patchUnit = async (
    unit: KnowledgeUnit,
    payload: Parameters<typeof updateKnowledgeUnit>[1],
  ) => {
    setBusyId(unit.id);
    try {
      const updated = await updateKnowledgeUnit(unit.id, payload);
      setUnits((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice({ kind: "success", text: "已更新知识单元" });
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "更新失败",
      });
    } finally {
      setBusyId("");
    }
  };

  const patchSkill = async (
    skill: Skill,
    payload: Parameters<typeof updateSkill>[1],
  ) => {
    setBusyId(skill.id);
    try {
      const updated = await updateSkill(skill.id, payload);
      setSkills((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice({ kind: "success", text: "已更新技能" });
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "更新失败",
      });
    } finally {
      setBusyId("");
    }
  };

  const handleCreatePoint = async (unit: KnowledgeUnit) => {
    setBusyId(unit.id);
    try {
      const result = await createPointFromUnit(unit.id);
      setNotice({
        kind: "success",
        text: `已创建知识点「${result.knowledge_point.name}」，可在知识树中查看。`,
      });
      await load();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "创建知识点失败",
      });
    } finally {
      setBusyId("");
    }
  };

  const handleExtract = async () => {
    if (!materialId) {
      setNotice({ kind: "error", text: "请先选择一份资料" });
      return;
    }
    setExtracting(true);
    try {
      const result = await extractMaterialUnits(materialId);
      setNotice({
        kind: "success",
        text: `抽取完成：${result.units} 个知识单元、${result.skills} 个技能（${
          result.model || "规则"
        }）${result.warning ? `。${result.warning}` : ""}`,
      });
      await load();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "抽取失败",
      });
    } finally {
      setExtracting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f4ee] text-ink">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link
              href="/library"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-[#8a8475] hover:text-ink"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回资料库
            </Link>
            <h1 className="mt-3 flex items-center gap-2 font-serif text-2xl font-semibold">
              <Sparkles className="h-5 w-5 text-[#b08244]" />
              知识挖掘
            </h1>
            <p className="mt-1.5 max-w-2xl text-xs leading-5 text-[#6b6459]">
              单题的深度分析存在这里。在对话里让答疑老师讲完一道题，说「保存到知识挖掘」就会出现在下面；也可以点右上角「手动新增」自己写。
              技能地图是另一层：保存的是可反复套用的方法，不是单道题。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={materialId}
              onChange={(event) => setMaterialId(event.target.value)}
              className="h-9 max-w-[240px] rounded-lg border border-[#d8d0c4] bg-white px-2.5 text-xs outline-none focus:border-ink"
            >
              <option value="">全部资料</option>
              {materials.map((material) => (
                <option key={material.id} value={material.id}>
                  {material.title}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-ink bg-ink px-3 text-xs font-medium text-white"
            >
              <Plus className="h-3.5 w-3.5" />
              手动新增
            </button>
            <button
              type="button"
              onClick={handleExtract}
              disabled={extracting || !materialId}
              title="从整份资料批量抽取知识单元。日常用法是在对话里让答疑老师分析单题后保存。"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#d8d0c4] bg-white px-3 text-xs font-medium text-[#6b6459] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {extracting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              {extracting ? "抽取中" : "批量抽取"}
            </button>
          </div>
        </div>

        {notice && (
          <div
            className={cn(
              "mt-4 flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-xs leading-5",
              notice.kind === "success"
                ? "border-[#c8ded4] bg-[#eef7f2] text-[#2f5d50]"
                : "border-[#ecc9c2] bg-[#fbe9e7] text-[#a33a2a]",
            )}
          >
            <span>{notice.text}</span>
            <button
              type="button"
              onClick={() => setNotice(null)}
              aria-label="关闭提示"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "待审核单元", value: counts.draft, accent: "text-[#8a6a24]" },
            {
              label: "已通过单元",
              value: counts.approved,
              accent: "text-[#2f5d50]",
            },
            {
              label: "已驳回单元",
              value: counts.rejected,
              accent: "text-[#a33a2a]",
            },
            { label: "技能", value: counts.skills, accent: "text-[#3f5f7a]" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-xl border border-[#e5ded1] bg-white/80 px-4 py-3"
            >
              <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-[#8a8475]">
                {item.label}
              </div>
              <div className={cn("mt-1 font-serif text-xl", item.accent)}>
                {item.value}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex rounded-lg bg-[#ece7dc] p-1 text-xs">
            {(
              [
                ["units", "知识单元"],
                ["skills", "技能"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTab(value)}
                className={cn(
                  "rounded-md px-3 py-1.5 font-medium transition",
                  tab === value
                    ? "bg-white text-ink shadow-sm"
                    : "text-[#6b6459]",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(
              [
                ["draft", "待审核"],
                ["proposal", "新知识点"],
                ["approved", "已通过"],
                ["rejected", "已驳回"],
                ["all", "全部"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setStatus(value)}
                className={cn(
                  "rounded-full border px-3 py-1 text-[11px] font-medium transition",
                  status === value
                    ? "border-ink bg-ink text-white"
                    : "border-[#d8d0c4] bg-white text-[#6b6459] hover:border-[#b8ae9c]",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="mt-10 flex items-center justify-center gap-2 text-xs text-[#8a8475]">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载
          </div>
        ) : tab === "units" ? (
          <div className="mt-4 space-y-3">
            {visibleUnits.length === 0 ? (
              <EmptyState
                text={
                  materialId
                    ? "这份资料在当前筛选下没有内容。"
                    : "还没有知识笔记。可以让答疑老师分析一道题后说「保存到知识挖掘」，或点右上角「手动新增」自己写一条。"
                }
              />
            ) : (
              visibleUnits.map((unit) => (
                <UnitCard
                  key={unit.id}
                  unit={unit}
                  materials={materials}
                  busy={busyId === unit.id}
                  onStatus={(next) => patchUnit(unit, { status: next })}
                  onSave={(payload) => patchUnit(unit, payload)}
                  onCreatePoint={() => void handleCreatePoint(unit)}
                />
              ))
            )}
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {visibleSkills.length === 0 ? (
              <EmptyState text="当前筛选下暂无技能。技能地图已内置花生十三体系，需要新增时在对话里说「把这个技能加到技能地图」。" />
            ) : (
              visibleSkills.map((skill) => (
                <SkillCard
                  key={skill.id}
                  skill={skill}
                  busy={busyId === skill.id}
                  onStatus={(next) => patchSkill(skill, { status: next })}
                  onSave={(payload) => patchSkill(skill, payload)}
                />
              ))
            )}
          </div>
        )}
      </div>

      {creating && (
        <CreateUnitDialog
          onClose={() => setCreating(false)}
          onCreate={async (payload) => {
            try {
              await createKnowledgeUnit(payload);
              setCreating(false);
              setNotice({ kind: "success", text: "已新增知识条目" });
              await load();
            } catch (error) {
              setNotice({
                kind: "error",
                text: error instanceof Error ? error.message : "新增失败",
              });
            }
          }}
        />
      )}
    </main>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[#d8d0c4] bg-white/50 px-6 py-12 text-center text-xs leading-6 text-[#8a8475]">
      {text}
    </div>
  );
}

type UnitCardProps = {
  unit: KnowledgeUnit;
  materials: Material[];
  busy: boolean;
  onStatus: (status: string) => void;
  onSave: (
    payload: Parameters<typeof updateKnowledgeUnit>[1],
  ) => void;
  onCreatePoint: () => void;
};

function UnitCard({
  unit,
  materials,
  busy,
  onStatus,
  onSave,
  onCreatePoint,
}: UnitCardProps) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(unit.title);
  const [summary, setSummary] = useState(unit.summary);
  const material = materials.find((item) => item.id === unit.material_id);
  const meta = STATUS_META[unit.status] ?? STATUS_META.draft;

  const save = () => {
    onSave({ title: title.trim(), summary: summary.trim() });
    setEditing(false);
  };

  return (
    <article className="rounded-xl border border-[#e5ded1] bg-white/85 px-4 py-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 rounded-md bg-[#f0ebe1] px-2 py-0.5 text-[10px] font-medium text-[#6b6459]">
          {CHUNK_TYPE_LABEL[unit.chunk_type] ?? unit.chunk_type}
        </span>
        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="w-full rounded-lg border border-[#d8d0c4] bg-white px-2.5 py-1.5 text-sm font-medium outline-none focus:border-ink"
            />
          ) : (
            <h3 className="text-sm font-semibold leading-6">{unit.title}</h3>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[#8a8475]">
            {unit.knowledge_point_name && (
              <span>知识点：{unit.knowledge_point_name}</span>
            )}
            {unit.proposed_knowledge_point && (
              <span className="rounded-full bg-[#e6edf5] px-1.5 py-0.5 text-[#3f5f7f]">
                新知识点候选：{unit.proposed_knowledge_point}
              </span>
            )}
            {unit.skill_name && <span>技能：{unit.skill_name}</span>}
            <span>置信度 {Math.round(unit.confidence * 100)}%</span>
            <span>{unit.extraction_model || "rule"}</span>
            {material && <span className="truncate">{material.title}</span>}
            <span>{formatRelative(unit.created_at)}</span>
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium",
            meta.className,
          )}
        >
          {meta.label}
        </span>
      </div>

      {editing ? (
        <div className="mt-3">
          <textarea
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            rows={3}
            className="w-full rounded-lg border border-[#d8d0c4] bg-white px-3 py-2 text-xs leading-5 outline-none focus:border-ink"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={save}
              className="rounded-lg bg-ink px-3 py-1.5 text-[11px] font-medium text-white"
            >
              保存
            </button>
            <button
              type="button"
              onClick={() => {
                setTitle(unit.title);
                setSummary(unit.summary);
                setEditing(false);
              }}
              className="rounded-lg border border-[#d8d0c4] px-3 py-1.5 text-[11px] text-[#6b6459]"
            >
              取消
            </button>
          </div>
        </div>
      ) : (
        unit.summary && (
          <p className="mt-2 line-clamp-3 text-xs leading-5 text-[#5f5a4d]">
            {unit.summary}
          </p>
        )
      )}

      {open && <UnitDetail unit={unit} />}

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[#f0ebe1] pt-3">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#6b6459] hover:text-ink"
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          {open ? "收起详情" : "查看详情"}
        </button>
        <span className="flex-1" />
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-[#8a8475]" />}
        <button
          type="button"
          disabled={busy}
          onClick={() => setEditing(true)}
          className="inline-flex items-center gap-1 rounded-lg border border-[#d8d0c4] px-2.5 py-1 text-[11px] text-[#6b6459] disabled:opacity-40"
        >
          <Pencil className="h-3 w-3" />
          编辑
        </button>
        {unit.proposed_knowledge_point && (
          <button
            type="button"
            disabled={busy}
            onClick={onCreatePoint}
            className="inline-flex items-center gap-1 rounded-lg border border-[#c9d9e8] bg-[#eef4fa] px-2.5 py-1 text-[11px] font-medium text-[#3f5f7a] disabled:opacity-40"
          >
            <Sparkles className="h-3 w-3" />
            创建知识点
          </button>
        )}
        <button
          type="button"
          disabled={busy || unit.status === "approved"}
          onClick={() => onStatus("approved")}
          className="inline-flex items-center gap-1 rounded-lg border border-[#c8ded4] bg-[#eef7f2] px-2.5 py-1 text-[11px] font-medium text-[#2f5d50] disabled:opacity-40"
        >
          <Check className="h-3 w-3" />
          通过
        </button>
        <button
          type="button"
          disabled={busy || unit.status === "rejected"}
          onClick={() => onStatus("rejected")}
          className="inline-flex items-center gap-1 rounded-lg border border-[#ecc9c2] bg-[#fbe9e7] px-2.5 py-1 text-[11px] font-medium text-[#a33a2a] disabled:opacity-40"
        >
          <CircleSlash className="h-3 w-3" />
          驳回
        </button>
        {unit.status !== "draft" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onStatus("draft")}
            className="inline-flex items-center gap-1 rounded-lg border border-[#d8d0c4] px-2.5 py-1 text-[11px] text-[#6b6459] disabled:opacity-40"
          >
            <RefreshCw className="h-3 w-3" />
            退回
          </button>
        )}
      </div>
    </article>
  );
}

function UnitDetail({ unit }: { unit: KnowledgeUnit }) {
  const sections: Array<[string, string[]]> = [
    ["题目识别信号", unit.signals],
    ["适用条件", unit.conditions],
    ["步骤", unit.steps],
    ["易错点", unit.pitfalls],
    ["常见变式", unit.variants],
    ["出题人怎么设干扰", unit.question_design],
    ["例子", unit.examples],
  ];
  return (
    <div className="mt-3 space-y-3 rounded-lg bg-[#faf7f1] px-3 py-3 text-xs leading-5 text-[#5f5a4d]">
      {unit.definition && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8a8475]">
            定义
          </div>
          <p className="mt-1 whitespace-pre-wrap">{unit.definition}</p>
        </div>
      )}
      {unit.exam_pattern && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8a8475]">
            怎么考
          </div>
          <p className="mt-1 whitespace-pre-wrap">{unit.exam_pattern}</p>
        </div>
      )}
      {sections.map(([label, items]) =>
        items.length > 0 ? (
          <div key={label}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8a8475]">
              {label}
            </div>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              {items.map((item, index) => (
                <li key={`${label}-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
      {unit.evidence.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8a8475]">
            原文依据
          </div>
          {unit.evidence.map((item, index) => (
            <p
              key={`evidence-${index}`}
              className="mt-1 rounded-md bg-white/70 px-2 py-1.5 text-[11px] text-[#6b6459]"
            >
              {item.page ? `第 ${item.page} 页 · ` : ""}
              {item.quote}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

type SkillCardProps = {
  skill: Skill;
  busy: boolean;
  onStatus: (status: string) => void;
  onSave: (payload: Parameters<typeof updateSkill>[1]) => void;
};

function SkillCard({ skill, busy, onStatus, onSave }: SkillCardProps) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(skill.name);
  const [summary, setSummary] = useState(skill.summary);
  const meta = STATUS_META[skill.status] ?? STATUS_META.draft;

  return (
    <article className="rounded-xl border border-[#e5ded1] bg-white/85 px-4 py-4">
      <div className="flex items-start gap-3">
        <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#3f5f7a]" />
        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full rounded-lg border border-[#d8d0c4] bg-white px-2.5 py-1.5 text-sm font-medium outline-none focus:border-ink"
            />
          ) : (
            <h3 className="text-sm font-semibold leading-6">{skill.name}</h3>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[#8a8475]">
            {skill.knowledge_point_name && (
              <span>知识点：{skill.knowledge_point_name}</span>
            )}
            {skill.subject && <span>{skill.subject}</span>}
            {skill.module && <span>{skill.module}</span>}
            <span>来源单元 {skill.source_unit_ids.length}</span>
            <span>置信度 {Math.round(skill.confidence * 100)}%</span>
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium",
            meta.className,
          )}
        >
          {meta.label}
        </span>
      </div>

      {editing ? (
        <div className="mt-3">
          <textarea
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            rows={3}
            className="w-full rounded-lg border border-[#d8d0c4] bg-white px-3 py-2 text-xs leading-5 outline-none focus:border-ink"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => {
                onSave({ name: name.trim(), summary: summary.trim() });
                setEditing(false);
              }}
              className="rounded-lg bg-ink px-3 py-1.5 text-[11px] font-medium text-white"
            >
              保存
            </button>
            <button
              type="button"
              onClick={() => {
                setName(skill.name);
                setSummary(skill.summary);
                setEditing(false);
              }}
              className="rounded-lg border border-[#d8d0c4] px-3 py-1.5 text-[11px] text-[#6b6459]"
            >
              取消
            </button>
          </div>
        </div>
      ) : (
        skill.summary && (
          <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#5f5a4d]">
            {skill.summary}
          </p>
        )
      )}

      {open && (
        <div className="mt-3 space-y-2 rounded-lg bg-[#faf7f1] px-3 py-3 text-xs leading-5 text-[#5f5a4d]">
          {(
            [
              ["怎么考", skill.exam_patterns],
              ["题目识别信号", skill.signals],
              ["适用条件", skill.conditions],
              ["步骤", skill.steps],
              ["易错点", skill.pitfalls],
              ["常见变式", skill.variants],
              ["出题人怎么设干扰", skill.question_design],
              ["例子", skill.examples],
            ] as Array<[string, string[]]>
          ).map(([label, items]) =>
            items.length > 0 ? (
              <div key={label}>
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8a8475]">
                  {label}
                </div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5">
                  {items.map((item, index) => (
                    <li key={`${label}-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[#f0ebe1] pt-3">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#6b6459] hover:text-ink"
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          {open ? "收起详情" : "查看步骤"}
        </button>
        <span className="flex-1" />
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-[#8a8475]" />}
        <button
          type="button"
          disabled={busy}
          onClick={() => setEditing(true)}
          className="inline-flex items-center gap-1 rounded-lg border border-[#d8d0c4] px-2.5 py-1 text-[11px] text-[#6b6459] disabled:opacity-40"
        >
          <Pencil className="h-3 w-3" />
          编辑
        </button>
        <button
          type="button"
          disabled={busy || skill.status === "approved"}
          onClick={() => onStatus("approved")}
          className="inline-flex items-center gap-1 rounded-lg border border-[#c8ded4] bg-[#eef7f2] px-2.5 py-1 text-[11px] font-medium text-[#2f5d50] disabled:opacity-40"
        >
          <Check className="h-3 w-3" />
          通过
        </button>
        <button
          type="button"
          disabled={busy || skill.status === "rejected"}
          onClick={() => onStatus("rejected")}
          className="inline-flex items-center gap-1 rounded-lg border border-[#ecc9c2] bg-[#fbe9e7] px-2.5 py-1 text-[11px] font-medium text-[#a33a2a] disabled:opacity-40"
        >
          <CircleSlash className="h-3 w-3" />
          驳回
        </button>
        {skill.status !== "draft" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onStatus("draft")}
            className="inline-flex items-center gap-1 rounded-lg border border-[#d8d0c4] px-2.5 py-1 text-[11px] text-[#6b6459] disabled:opacity-40"
          >
            <RefreshCw className="h-3 w-3" />
            退回
          </button>
        )}
      </div>
    </article>
  );
}

function CreateUnitDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (payload: Parameters<typeof createKnowledgeUnit>[0]) => void;
}) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [definition, setDefinition] = useState("");
  const [steps, setSteps] = useState("");
  const [pitfalls, setPitfalls] = useState("");
  const [variants, setVariants] = useState("");
  const [kpName, setKpName] = useState("");

  const splitLines = (value: string) =>
    value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

  const submit = () => {
    if (!title.trim()) return;
    onCreate({
      title: title.trim(),
      summary: summary.trim(),
      definition: definition.trim(),
      steps: splitLines(steps),
      pitfalls: splitLines(pitfalls),
      variants: splitLines(variants),
      knowledge_point_name: kpName.trim(),
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/30 p-4 sm:items-center">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-5 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">手动新增知识条目</h2>
          <button type="button" onClick={onClose} aria-label="关闭">
            <X className="h-4 w-4 text-[#8a8475]" />
          </button>
        </div>
        <p className="mt-1 text-[11px] leading-5 text-[#8a8475]">
          做题后自己整理的分析可以直接写在这里，不必回对话让答疑老师代劳。
          列表、陷阱、变式每行一条。
        </p>

        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="text-[11px] font-medium text-[#6b6459]">标题 *</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="例：牛吃草的三种变形"
              className="mt-1 h-9 w-full rounded-lg border border-[#d8d0c4] px-2.5 text-xs outline-none focus:border-ink"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-medium text-[#6b6459]">一句话概括</span>
            <input
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              placeholder="这题考什么、怎么识别"
              className="mt-1 h-9 w-full rounded-lg border border-[#d8d0c4] px-2.5 text-xs outline-none focus:border-ink"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-medium text-[#6b6459]">知识点（可选）</span>
            <input
              value={kpName}
              onChange={(event) => setKpName(event.target.value)}
              placeholder="例：牛吃草"
              className="mt-1 h-9 w-full rounded-lg border border-[#d8d0c4] px-2.5 text-xs outline-none focus:border-ink"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-medium text-[#6b6459]">详细说明</span>
            <textarea
              value={definition}
              onChange={(event) => setDefinition(event.target.value)}
              rows={3}
              className="mt-1 w-full rounded-lg border border-[#d8d0c4] px-2.5 py-2 text-xs leading-5 outline-none focus:border-ink"
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="text-[11px] font-medium text-[#6b6459]">解题步骤</span>
              <textarea
                value={steps}
                onChange={(event) => setSteps(event.target.value)}
                rows={4}
                placeholder={"设原有草量\n求每天增长量\n代入求解"}
                className="mt-1 w-full rounded-lg border border-[#d8d0c4] px-2.5 py-2 text-xs leading-5 outline-none focus:border-ink"
              />
            </label>
            <label className="block">
              <span className="text-[11px] font-medium text-[#6b6459]">易错点</span>
              <textarea
                value={pitfalls}
                onChange={(event) => setPitfalls(event.target.value)}
                rows={4}
                placeholder={"忽略草量增长\n单位没统一"}
                className="mt-1 w-full rounded-lg border border-[#d8d0c4] px-2.5 py-2 text-xs leading-5 outline-none focus:border-ink"
              />
            </label>
            <label className="block">
              <span className="text-[11px] font-medium text-[#6b6459]">变式</span>
              <textarea
                value={variants}
                onChange={(event) => setVariants(event.target.value)}
                rows={4}
                placeholder={"改成牛数递减\n改成两片草地"}
                className="mt-1 w-full rounded-lg border border-[#d8d0c4] px-2.5 py-2 text-xs leading-5 outline-none focus:border-ink"
              />
            </label>
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-lg border border-[#d8d0c4] px-3 text-xs text-[#6b6459]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!title.trim()}
            className="h-9 rounded-lg bg-ink px-4 text-xs font-medium text-white disabled:opacity-40"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
