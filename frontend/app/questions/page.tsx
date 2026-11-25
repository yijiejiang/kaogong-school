"use client";

import {
  ArrowLeft,
  ChevronDown,
  FileQuestion,
  Loader2,
  Pencil,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  deleteQuestion,
  extractQuestions,
  fetchMaterials,
  fetchQuestions,
  fetchQuestionTags,
  updateQuestion,
} from "@/lib/api";
import type {
  BankQuestion,
  BankTagsResponse,
  Material,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const DIFFICULTY_LABEL: Record<number, string> = {
  1: "很易",
  2: "较易",
  3: "中等",
  4: "较难",
  5: "很难",
};

export default function QuestionBankPage() {
  const [questions, setQuestions] = useState<BankQuestion[]>([]);
  const [tagData, setTagData] = useState<BankTagsResponse | null>(null);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [tag, setTag] = useState("");
  const [module, setModule] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);
  const [editing, setEditing] = useState<BankQuestion | null>(null);

  const load = useCallback(async () => {
    try {
      const [rows, tags] = await Promise.all([
        fetchQuestions({ tag, module, search, limit: 300 }),
        fetchQuestionTags(),
      ]);
      setQuestions(rows);
      setTagData(tags);
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "加载题库失败",
      });
    } finally {
      setLoading(false);
    }
  }, [module, search, tag]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    fetchMaterials().then(setMaterials).catch(() => setMaterials([]));
  }, []);

  const visibleTags = useMemo(
    () => (tagData?.tags ?? []).slice(0, 40),
    [tagData],
  );

  const runExtract = async (materialId: string) => {
    setBusy(materialId);
    try {
      const result = await extractQuestions(materialId);
      setNotice({
        kind: "success",
        text: `识别完成：新增 ${result.questions} 道题（${result.model || "规则"}）${
          result.warning ? `。${result.warning}` : ""
        }`,
      });
      await load();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "识别失败",
      });
    } finally {
      setBusy("");
    }
  };

  const remove = async (id: string) => {
    setBusy(id);
    try {
      await deleteQuestion(id);
      setQuestions((current) => current.filter((item) => item.id !== id));
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "删除失败",
      });
    } finally {
      setBusy("");
    }
  };

  const save = async (
    question: BankQuestion,
    payload: Parameters<typeof updateQuestion>[1],
  ) => {
    setBusy(question.id);
    try {
      const updated = await updateQuestion(question.id, payload);
      setQuestions((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setEditing(null);
      await load();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "保存失败",
      });
    } finally {
      setBusy("");
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f4ee] text-ink">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <Link
          href="/library"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#8a8475] hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回资料库
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2 font-serif text-2xl font-semibold">
              <FileQuestion className="h-5 w-5 text-[#3f5f7f]" />
              题库
            </h1>
            <p className="mt-1.5 max-w-2xl text-xs leading-5 text-[#6b6459]">
              上传的题目会自动识别并打标签。出卷时可以直接按标签选题，比如「牛吃草」「概率问题」。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={module}
              onChange={(event) => setModule(event.target.value)}
              className="h-9 rounded-lg border border-[#d8d0c4] bg-white px-2.5 text-xs outline-none focus:border-ink"
            >
              <option value="">全部模块</option>
              {(tagData?.modules ?? []).map((item) => (
                <option key={item.module} value={item.module}>
                  {item.module}（{item.count}）
                </option>
              ))}
            </select>
            <select
              value=""
              onChange={(event) => {
                if (event.target.value) void runExtract(event.target.value);
              }}
              disabled={Boolean(busy)}
              className="h-9 max-w-[220px] rounded-lg border border-[#d8d0c4] bg-white px-2.5 text-xs outline-none focus:border-ink"
            >
              <option value="">从资料重新识别</option>
              {materials.map((material) => (
                <option key={material.id} value={material.id}>
                  {material.title}
                </option>
              ))}
            </select>
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
            <button type="button" onClick={() => setNotice(null)} aria-label="关闭">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-[#d8d0c4] bg-white px-2.5">
            <Search className="h-3.5 w-3.5 text-[#a59d90]" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索题干"
              className="h-9 w-48 bg-transparent text-xs outline-none"
            />
          </div>
          <span className="text-[11px] text-[#8a8475]">
            {tag || module || search ? (
              <>
                筛选出 <strong className="text-ink">{questions.length}</strong> 道
                {questions.length >= 300 ? "（上限 300，可再收窄条件）" : ""}
                {module ? ` · 模块「${module}」` : ""}
                {tag ? ` · 标签「${tag}」` : ""}
              </>
            ) : (
              <>
                共 <strong className="text-ink">{tagData?.total ?? 0}</strong> 道题
                {questions.length >= 300 ? "，当前显示前 300 道" : ""}
              </>
            )}
          </span>
          {(tag || module || search) && (
            <button
              type="button"
              onClick={() => {
                setTag("");
                setModule("");
                setSearch("");
              }}
              className="rounded-md border border-[#d8d0c4] bg-white px-2 py-1 text-[10px] text-[#6b6459] hover:border-ink hover:text-ink"
            >
              清除筛选
            </button>
          )}
        </div>

        {visibleTags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setTag("")}
              className={cn(
                "rounded-full border px-2.5 py-1 text-[10px] font-medium",
                tag === ""
                  ? "border-ink bg-ink text-white"
                  : "border-[#d8d0c4] bg-white text-[#6b6459]",
              )}
            >
              全部标签
            </button>
            {visibleTags.map((item) => (
              <button
                key={item.tag}
                type="button"
                onClick={() => setTag(tag === item.tag ? "" : item.tag)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-medium",
                  tag === item.tag
                    ? "border-[#3f5f7f] bg-[#e6edf5] text-[#3f5f7f]"
                    : "border-[#d8d0c4] bg-white text-[#6b6459]",
                )}
              >
                <Tag className="h-2.5 w-2.5" />
                {item.tag}
                <span className="text-[9px] text-[#a59d90]">{item.count}</span>
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className="mt-10 flex items-center justify-center gap-2 text-xs text-[#8a8475]">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载题库
          </div>
        ) : (
          <div className="mt-5 space-y-2">
            {questions.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#d8d0c4] bg-white/50 px-6 py-12 text-center text-xs leading-6 text-[#8a8475]">
                题库还是空的。上传带题目的资料后会自动识别，也可以在上面选一份资料重新识别。
              </div>
            ) : (
              questions.map((question) => (
                <QuestionCard
                  key={question.id}
                  question={question}
                  busy={busy === question.id}
                  onEdit={() => setEditing(question)}
                  onDelete={() => void remove(question.id)}
                />
              ))
            )}
          </div>
        )}
      </div>

      {editing && (
        <EditDrawer
          question={editing}
          busy={busy === editing.id}
          onClose={() => setEditing(null)}
          onSave={(payload) => void save(editing, payload)}
        />
      )}
    </main>
  );
}

function QuestionCard({
  question,
  busy,
  onEdit,
  onDelete,
}: {
  question: BankQuestion;
  busy: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article className="rounded-xl border border-[#e5ded1] bg-white/85 px-4 py-3">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0 rounded-md bg-[#f0ebe1] px-2 py-0.5 text-[10px] text-[#6b6459]">
          {question.module || "未分类"}
        </span>
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-xs leading-5 text-[#3f3a32]">
            {question.stem}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {question.tags.map((item) => (
              <span
                key={item}
                className="rounded-full bg-[#e6edf5] px-2 py-0.5 text-[10px] text-[#3f5f7f]"
              >
                {item}
              </span>
            ))}
            <span className="text-[10px] text-[#a59d90]">
              {DIFFICULTY_LABEL[question.difficulty] ?? question.difficulty}
              {question.answer ? ` · 答案 ${question.answer}` : ""}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-[#8a8475]" />}
          <button
            type="button"
            onClick={onEdit}
            disabled={busy}
            className="rounded-md border border-[#d8d0c4] p-1.5 text-[#6b6459] disabled:opacity-40"
            aria-label="编辑题目"
          >
            <Pencil className="h-3 w-3" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={busy}
            className="rounded-md border border-[#ecc9c2] p-1.5 text-[#a33a2a] disabled:opacity-40"
            aria-label="删除题目"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="mt-2 inline-flex items-center gap-1 text-[10px] text-[#8a8475]"
      >
        <ChevronDown
          className={cn("h-3 w-3 transition", open && "rotate-180")}
        />
        {open ? "收起" : "展开选项与解析"}
      </button>

      {open && (
        <div className="mt-2 space-y-2 rounded-lg bg-[#faf7f1] px-3 py-2 text-[11px] leading-5 text-[#5f5a4d]">
          {question.options.length > 0 && (
            <div className="space-y-1">
              {question.options.map((option) => (
                <div key={option.key} className="flex gap-2">
                  <span
                    className={cn(
                      "shrink-0 font-medium",
                      option.key === question.answer
                        ? "text-[#2f5d50]"
                        : "text-[#8a8475]",
                    )}
                  >
                    {option.key}.
                  </span>
                  <span>{option.text}</span>
                </div>
              ))}
            </div>
          )}
          {question.explanation && (
            <p>
              <span className="text-[#8a8475]">解析：</span>
              {question.explanation}
            </p>
          )}
          {question.source && (
            <p className="text-[9px] text-[#a59d90]">
              来源：{question.source}
              {question.material_id ? ` · ${question.material_id.slice(0, 8)}` : ""}
            </p>
          )}
        </div>
      )}
    </article>
  );
}

function EditDrawer({
  question,
  busy,
  onClose,
  onSave,
}: {
  question: BankQuestion;
  busy: boolean;
  onClose: () => void;
  onSave: (payload: Parameters<typeof updateQuestion>[1]) => void;
}) {
  const [tagText, setTagText] = useState(question.tags.join("、"));
  const [module, setModule] = useState(question.module);
  const [answer, setAnswer] = useState(question.answer);
  const [difficulty, setDifficulty] = useState(question.difficulty);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 p-0 sm:p-4">
      <button
        type="button"
        aria-label="关闭"
        onClick={onClose}
        className="absolute inset-0 cursor-default"
      />
      <aside className="relative z-10 h-full w-full max-w-md overflow-y-auto rounded-none border-l border-line bg-[#fdfbf7] p-5 shadow-2xl sm:rounded-2xl sm:border">
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-serif text-lg font-semibold">编辑题目</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="rounded-lg border border-line bg-white p-1.5 text-[#6b6459]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 line-clamp-3 text-[11px] leading-5 text-[#6b6459]">
          {question.stem}
        </p>

        <label className="mt-4 block">
          <span className="mb-1 block text-xs font-medium">模块</span>
          <input
            value={module}
            onChange={(event) => setModule(event.target.value)}
            className="w-full rounded-lg border border-[#d8d0c4] bg-white px-3 py-2 text-xs outline-none focus:border-ink"
          />
        </label>

        <label className="mt-3 block">
          <span className="mb-1 block text-xs font-medium">
            标签（用顿号或逗号分隔）
          </span>
          <input
            value={tagText}
            onChange={(event) => setTagText(event.target.value)}
            placeholder="牛吃草、工程问题"
            className="w-full rounded-lg border border-[#d8d0c4] bg-white px-3 py-2 text-xs outline-none focus:border-ink"
          />
        </label>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium">答案</span>
            <input
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder="B"
              className="w-full rounded-lg border border-[#d8d0c4] bg-white px-3 py-2 text-xs outline-none focus:border-ink"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium">难度</span>
            <select
              value={difficulty}
              onChange={(event) => setDifficulty(Number(event.target.value))}
              className="w-full rounded-lg border border-[#d8d0c4] bg-white px-3 py-2 text-xs outline-none focus:border-ink"
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {DIFFICULTY_LABEL[value]}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={() =>
            onSave({
              module,
              answer,
              difficulty,
              tags: tagText
                .split(/[、,，;；\s]+/)
                .map((item) => item.trim())
                .filter(Boolean),
            })
          }
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-ink px-3 py-2 text-xs font-medium text-white disabled:opacity-40"
        >
          {busy ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          保存
        </button>
      </aside>
    </div>
  );
}
