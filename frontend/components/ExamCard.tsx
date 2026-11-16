import { Clock3, FileText, Layers3 } from "lucide-react";
import Link from "next/link";

import type { UiPayload } from "@/lib/types";

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "简单",
  medium: "中等",
  hard: "困难",
  mixed: "混合",
};

export function ExamCard({ payload }: { payload: UiPayload }) {
  if (payload.type !== "exam_card") return null;

  const questionCount =
    typeof payload.questions === "number" ? payload.questions : 0;
  const minutes =
    typeof payload.duration_minutes === "number" ? payload.duration_minutes : 0;
  const subject =
    typeof payload.subject === "string" ? payload.subject : "行测";
  const moduleName =
    typeof payload.module === "string" ? payload.module : subject;
  const difficulty =
    typeof payload.difficulty === "string" ? payload.difficulty : "medium";
  const examId = typeof payload.exam_id === "string" ? payload.exam_id : "";
  const title =
    typeof payload.title === "string" ? payload.title : "模拟试卷";
  const subtitle = typeof payload.subtitle === "string" ? payload.subtitle : "";
  const isReal = Boolean(examId) && !examId.startsWith("demo-");

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-line bg-paper shadow-[0_1px_0_rgba(31,35,40,0.03)]">
      <div className="flex items-start justify-between gap-4 border-b border-line bg-[#faf7f1] px-5 py-4">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent">
            {isReal ? "P2 · 模拟试卷" : "P0 · 演示试卷"}
          </div>
          <div className="mt-1 truncate text-base font-semibold text-ink">
            {title}
          </div>
          <div className="mt-1 text-xs text-muted">{subtitle}</div>
        </div>
        <div className="shrink-0 rounded-xl border border-line bg-white px-3 py-2 text-center">
          <div className="text-xl font-semibold leading-none text-ink">
            {questionCount}
          </div>
          <div className="mt-1 text-[10px] text-muted">题</div>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x divide-line text-center">
        <div className="px-2 py-3">
          <Clock3 className="mx-auto h-4 w-4 text-muted" />
          <div className="mt-1 text-xs font-medium text-ink">
            {minutes} 分钟
          </div>
          <div className="mt-0.5 text-[10px] text-muted">限时</div>
        </div>
        <div className="px-2 py-3">
          <Layers3 className="mx-auto h-4 w-4 text-muted" />
          <div className="mt-1 text-xs font-medium text-ink">{moduleName}</div>
          <div className="mt-0.5 text-[10px] text-muted">模块</div>
        </div>
        <div className="px-2 py-3">
          <FileText className="mx-auto h-4 w-4 text-muted" />
          <div className="mt-1 text-xs font-medium text-ink">
            {DIFFICULTY_LABELS[difficulty] ?? "中等"}
          </div>
          <div className="mt-0.5 text-[10px] text-muted">难度</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3">
        <span className="text-xs text-muted">
          {isReal
            ? "答题、计时、交卷判分已接入"
            : "完整答题与判分将在 P2 开放"}
        </span>
        {isReal ? (
          <Link
            href={`/exams/${encodeURIComponent(examId)}`}
            className="rounded-lg bg-accent px-3.5 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
          >
            开始考试
          </Link>
        ) : (
          <button
            type="button"
            disabled
            className="cursor-not-allowed rounded-lg bg-[#e9e4da] px-3.5 py-1.5 text-xs font-medium text-[#8a8475]"
          >
            开始考试
          </button>
        )}
      </div>
    </div>
  );
}
