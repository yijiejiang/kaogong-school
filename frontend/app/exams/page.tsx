"use client";

import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Clock3,
  FileText,
  Loader2,
  Play,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { fetchAttempts, fetchExams, generateExam } from "@/lib/api";
import type { AttemptSummary, ExamSummary } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";
import { useUserId } from "@/lib/user";

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "简单",
  medium: "中等",
  hard: "困难",
  mixed: "混合",
};

const MODULE_OPTIONS: Record<string, string[]> = {
  行测: [
    "资料分析",
    "言语理解与表达",
    "数量关系",
    "判断推理",
    "常识判断",
  ],
  申论: ["归纳概括", "综合分析", "提出对策", "贯彻执行", "文章写作"],
};

const fieldClass =
  "w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-[#cfc4b5] focus:ring-2 focus:ring-[#efe7da]";

export default function ExamsPage() {
  const router = useRouter();
  const userId = useUserId();
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [attempts, setAttempts] = useState<AttemptSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);

  const [subject, setSubject] = useState("行测");
  const [module, setModule] = useState("资料分析");
  const [questionCount, setQuestionCount] = useState(30);
  const [minutes, setMinutes] = useState(35);
  const [difficulty, setDifficulty] = useState<
    "easy" | "medium" | "hard" | "mixed"
  >("medium");
  const [aiCount, setAiCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [examList, attemptList] = await Promise.all([
        fetchExams(),
        fetchAttempts(userId),
      ]);
      setExams(examList);
      setAttempts(attemptList);
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "加载考试中心失败",
      });
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleGenerate = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const exam = await generateExam({
        subject,
        module,
        question_count: questionCount,
        duration_minutes: minutes,
        difficulty,
        ai_count: Math.min(aiCount, questionCount, 10),
        user_id: userId,
      });
      if (exam.warning) {
        setNotice({ kind: "error", text: exam.warning });
        await refresh();
        setBusy(false);
        return;
      }
      router.push(`/exams/${encodeURIComponent(exam.id)}`);
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "生成试卷失败",
      });
      setBusy(false);
    }
  };

  const gradedAttempts = attempts.filter((item) => item.status === "graded");
  const inProgress = attempts.filter((item) => item.status === "in_progress");

  return (
    <div className="min-h-dvh bg-[var(--background)] text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-[#f7f4ee]/90 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-medium text-ink"
          >
            <ArrowLeft className="h-4 w-4" />
            返回对话
          </Link>
          <div className="text-sm font-semibold">考试中心</div>
          <Link href="/settings" className="text-xs text-muted">
            设置
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">考试中心</h1>
            <p className="mt-1 text-sm text-muted">
              按条件组卷、限时作答、交卷后自动判分。覆盖行测五模块与申论主观题，
              可按需加入 AI 原创题。
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Stat icon={FileText} label="试卷" value={exams.length} />
            <Stat icon={ClipboardList} label="已批改" value={gradedAttempts.length} />
            {inProgress.length > 0 && (
              <Stat
                icon={Clock3}
                label="进行中"
                value={inProgress.length}
                accent
              />
            )}
          </div>
        </div>

        {notice && (
          <div
            className={cn(
              "mb-5 flex items-start gap-2 rounded-xl border px-4 py-3 text-sm",
              notice.kind === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-red-800",
            )}
          >
            {notice.kind === "success" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            ) : (
              <Target className="mt-0.5 h-4 w-4 shrink-0" />
            )}
            <span>{notice.text}</span>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="rounded-2xl border border-line bg-paper p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">生成一套卷</h2>
                <p className="mt-1 text-xs text-muted">
                  默认按“资料分析、30 题、35 分钟、中等”生成。
                </p>
              </div>
              <Sparkles className="h-5 w-5 text-accent" />
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  科目
                </span>
                <select
                  className={fieldClass}
                  value={subject}
                  onChange={(event) => {
                    const next = event.target.value;
                    setSubject(next);
                    setModule(MODULE_OPTIONS[next][0]);
                  }}
                >
                  <option value="行测">行测</option>
                  <option value="申论">申论</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  模块
                </span>
                <select
                  className={fieldClass}
                  value={module}
                  onChange={(event) => setModule(event.target.value)}
                >
                  {(MODULE_OPTIONS[subject] ?? []).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  题量
                </span>
                <input
                  type="number"
                  min={1}
                  max={60}
                  className={fieldClass}
                  value={questionCount}
                  onChange={(event) =>
                    setQuestionCount(Number(event.target.value) || 1)
                  }
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  限时（分钟）
                </span>
                <input
                  type="number"
                  min={5}
                  max={180}
                  className={fieldClass}
                  value={minutes}
                  onChange={(event) =>
                    setMinutes(Number(event.target.value) || 5)
                  }
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  难度
                </span>
                <select
                  className={fieldClass}
                  value={difficulty}
                  onChange={(event) =>
                    setDifficulty(
                      event.target.value as
                        | "easy"
                        | "medium"
                        | "hard"
                        | "mixed",
                    )
                  }
                >
                  <option value="easy">简单</option>
                  <option value="medium">中等</option>
                  <option value="hard">困难</option>
                  <option value="mixed">混合</option>
                </select>
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-1.5 flex items-center justify-between text-xs font-medium text-ink">
                  <span>AI 原创题数量</span>
                  <span className="text-[10px] font-normal text-muted">
                    0 = 只用题库
                  </span>
                </span>
                <input
                  type="number"
                  min={0}
                  max={10}
                  className={fieldClass}
                  value={aiCount}
                  onChange={(event) =>
                    setAiCount(
                      Math.max(0, Math.min(10, Number(event.target.value) || 0)),
                    )
                  }
                />
                <span className="mt-1 block text-[10px] leading-4 text-muted">
                  需要配置真实 LLM；演示模式或调用失败会自动回退题库并提示。
                </span>
              </label>
            </div>

            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={busy}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-60"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              生成并开始考试
            </button>
            <p className="mt-2 text-center text-[10px] text-muted">
              题量 30 时会包含 2 道主观题，总分 100。
            </p>
          </section>

          <section className="rounded-2xl border border-line bg-paper p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">最近试卷</h2>
              <span className="text-[10px] text-muted">{exams.length} 份</span>
            </div>
            {loading ? (
              <div className="flex items-center gap-2 rounded-xl border border-dashed border-line px-3 py-4 text-xs text-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                正在加载试卷…
              </div>
            ) : exams.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line px-3 py-5 text-xs leading-5 text-muted">
                还没有试卷。左侧生成一套，或在对话里让出卷老师出卷。
              </div>
            ) : (
              <div className="space-y-2">
                {exams.map((exam) => (
                  <div
                    key={exam.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-line bg-white px-3 py-3"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-ink">
                        {exam.title}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-muted">
                        <span>{exam.question_count} 题</span>
                        <span>·</span>
                        <span>{exam.duration_minutes} 分钟</span>
                        <span>·</span>
                        <span>
                          {DIFFICULTY_LABELS[exam.difficulty] ?? exam.difficulty}
                        </span>
                        {(exam.ai_generated ?? 0) > 0 && (
                          <>
                            <span>·</span>
                            <span className="text-accent">
                              AI {exam.ai_generated} 题
                            </span>
                          </>
                        )}
                        <span>·</span>
                        <span>{formatRelative(exam.created_at) || "刚刚"}</span>
                      </div>
                    </div>
                    <Link
                      href={`/exams/${encodeURIComponent(exam.id)}`}
                      className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-[11px] font-medium text-white transition hover:opacity-90"
                    >
                      开始
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="mt-5 rounded-2xl border border-line bg-paper p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold">最近作答</h2>
            <span className="text-[10px] text-muted">{attempts.length} 次</span>
          </div>
          {attempts.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line px-3 py-5 text-xs text-muted">
              还没有作答记录。选一套卷开始，交卷后这里会显示成绩和报告。
            </div>
          ) : (
            <div className="space-y-2">
              {attempts.slice(0, 8).map((attempt) => (
                <div
                  key={attempt.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-3 py-3"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-ink">
                      {attempt.exam_title}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-muted">
                      <span>
                        {attempt.status === "graded" ? "已批改" : "进行中"}
                      </span>
                      {attempt.status === "graded" && (
                        <>
                          <span>·</span>
                          <span>
                            {attempt.score}/{attempt.total_score} 分
                          </span>
                        </>
                      )}
                      <span>·</span>
                      <span>
                        {formatRelative(
                          attempt.submitted_at ?? attempt.started_at,
                        ) || "刚刚"}
                      </span>
                    </div>
                  </div>
                  {attempt.status === "graded" ? (
                    <Link
                      href={`/exams/${encodeURIComponent(attempt.exam_id)}/report/${encodeURIComponent(attempt.id)}`}
                      className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-line bg-white px-3 py-1.5 text-[11px] font-medium text-ink hover:border-[#cfc4b5]"
                    >
                      看报告
                      <ArrowRight className="h-3 w-3" />
                    </Link>
                  ) : (
                    <Link
                      href={`/exams/${encodeURIComponent(attempt.exam_id)}`}
                      className="shrink-0 rounded-lg bg-ink px-3 py-1.5 text-[11px] font-medium text-white"
                    >
                      继续考试
                    </Link>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  accent = false,
}: {
  icon: typeof FileText;
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-3 py-2",
        accent ? "border-[#f0d9a8] bg-[#fff4dd]" : "border-line bg-paper",
      )}
    >
      <div className="flex items-center gap-1.5 text-lg font-semibold leading-none text-ink">
        <Icon className="h-4 w-4 text-muted" />
        {value}
      </div>
      <div className="mt-1 text-[9px] uppercase tracking-[0.12em] text-muted">
        {label}
      </div>
    </div>
  );
}
