"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Loader2,
  Send,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { saveAttemptAnswers, startAttempt, submitAttempt } from "@/lib/api";
import type { AnswerItem, ExamQuestion, ExamTake } from "@/lib/types";
import { cn } from "@/lib/utils";

function hasAnswer(value: unknown): boolean {
  if (value === undefined || value === null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

function serializeAnswers(answers: Record<string, unknown>): AnswerItem[] {
  return Object.entries(answers)
    .filter(
      ([, value]) =>
        value !== undefined &&
        value !== null &&
        value !== "" &&
        !(Array.isArray(value) && value.length === 0),
    )
    .map(([question_id, response]) => ({ question_id, response }));
}

function formatTime(totalSeconds: number): string {
  const safe = Math.max(0, totalSeconds);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function typeLabel(type: string): string {
  if (type === "multiple") return "多选";
  if (type === "short") return "简答";
  return "单选";
}

export default function ExamPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const examId = params.id;

  const [exam, setExam] = useState<ExamTake | null>(null);
  const [attemptId, setAttemptId] = useState("");
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const answersRef = useRef<Record<string, unknown>>({});
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const submittedRef = useRef(false);
  const autoSubmittedRef = useRef(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await startAttempt(examId);
        if (!active) return;
        setExam(data.exam);
        setAttemptId(data.attempt_id);

        let local: Record<string, unknown> = {};
        try {
          local = JSON.parse(
            localStorage.getItem(`kaogong-exam-${data.attempt_id}`) ?? "{}",
          ) as Record<string, unknown>;
        } catch {
          local = {};
        }
        const merged = { ...(data.answers ?? {}), ...local };
        setAnswers(merged);
        answersRef.current = merged;
        setRemaining(data.remaining_seconds);
        if (data.exam.questions.length === 0) {
          setError("这套试卷还没有题目，请回到考试中心重新生成。");
        }
      } catch (caught) {
        if (active) {
          setError(caught instanceof Error ? caught.message : "开始考试失败");
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [examId]);

  useEffect(
    () => () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    },
    [],
  );

  const handleSubmit = useCallback(
    async (auto = false) => {
      if (!attemptId || submittedRef.current) return;
      if (!auto && !window.confirm("确定交卷吗？交卷后不能修改答案。")) {
        return;
      }
      submittedRef.current = true;
      setSubmitting(true);
      setError(null);
      if (saveTimer.current) clearTimeout(saveTimer.current);
      try {
        await submitAttempt(attemptId, serializeAnswers(answersRef.current));
        try {
          localStorage.removeItem(`kaogong-exam-${attemptId}`);
        } catch {
          // localStorage can be unavailable in private mode.
        }
        router.replace(
          `/exams/${encodeURIComponent(examId)}/report/${encodeURIComponent(attemptId)}`,
        );
      } catch (caught) {
        submittedRef.current = false;
        setSubmitting(false);
        setError(caught instanceof Error ? caught.message : "交卷失败");
      }
    },
    [attemptId, examId, router],
  );

  useEffect(() => {
    if (loading || !attemptId || submitting) return;
    const timer = setInterval(() => {
      setRemaining((previous) => {
        if (previous <= 1) {
          clearInterval(timer);
          if (!autoSubmittedRef.current) {
            autoSubmittedRef.current = true;
            setNotice("时间到，正在自动交卷…");
            void handleSubmit(true);
          }
          return 0;
        }
        return previous - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [attemptId, handleSubmit, loading, submitting]);

  const updateAnswer = useCallback(
    (questionId: string, value: unknown) => {
      setAnswers((previous) => {
        const next = { ...previous, [questionId]: value };
        answersRef.current = next;
        if (attemptId) {
          try {
            localStorage.setItem(
              `kaogong-exam-${attemptId}`,
              JSON.stringify(next),
            );
          } catch {
            // localStorage can be unavailable in private mode.
          }
          if (saveTimer.current) clearTimeout(saveTimer.current);
          saveTimer.current = setTimeout(() => {
            if (submittedRef.current) return;
            void saveAttemptAnswers(
              attemptId,
              serializeAnswers(next),
            ).catch(() => {
              // Autosave failures are non-fatal; submit still sends everything.
            });
          }, 800);
        }
        return next;
      });
    },
    [attemptId],
  );

  const questions = exam?.questions ?? [];
  const currentQuestion: ExamQuestion | undefined = questions[currentIndex];
  const answeredCount = useMemo(
    () => questions.filter((question) => hasAnswer(answers[question.id])).length,
    [answers, questions],
  );

  if (loading) {
    return (
      <div className="flex h-dvh items-center justify-center bg-[var(--background)] text-sm text-muted">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在准备试卷…
      </div>
    );
  }

  if (error || !exam || questions.length === 0) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-[var(--background)] px-4">
        <div className="w-full max-w-md rounded-2xl border border-line bg-paper p-6 text-center">
          <AlertTriangle className="mx-auto h-6 w-6 text-amber-600" />
          <h1 className="mt-3 text-base font-semibold">无法开始考试</h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            {error ?? "试卷不存在或没有题目。"}
          </p>
          <Link
            href="/exams"
            className="mt-4 inline-flex rounded-xl bg-ink px-4 py-2.5 text-xs font-medium text-white"
          >
            返回考试中心
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-[var(--background)] text-ink">
      <header className="sticky top-0 z-20 border-b border-line bg-[#f7f4ee]/95 backdrop-blur">
        <div className="mx-auto flex min-h-16 w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/exams"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-line bg-paper text-ink"
              aria-label="返回考试中心"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{exam.title}</div>
              <div className="text-[10px] text-muted">
                {exam.question_count} 题 · {exam.duration_minutes} 分钟
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm font-semibold tabular-nums",
                remaining <= 300
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-line bg-paper text-ink",
              )}
            >
              <Clock3 className="h-4 w-4" />
              {formatTime(remaining)}
            </div>
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-60"
            >
              {submitting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Send className="h-3.5 w-3.5" />
              )}
              交卷
            </button>
          </div>
        </div>
      </header>

      {notice && (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900">
          {notice}
        </div>
      )}

      <main className="mx-auto grid w-full max-w-6xl gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_280px]">
        <section className="rounded-2xl border border-line bg-paper p-5 sm:p-7">
          {currentQuestion && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs text-muted">
                  <span className="font-semibold text-ink">
                    第 {currentIndex + 1} / {questions.length} 题
                  </span>
                  <span className="rounded-full bg-[#f1ece2] px-2 py-0.5 text-[10px]">
                    {typeLabel(currentQuestion.type)}
                  </span>
                  <span className="rounded-full bg-[#e6edf5] px-2 py-0.5 text-[10px] text-[#3f5f7f]">
                    {currentQuestion.knowledge_point_name || "资料分析"}
                  </span>
                </div>
                <span className="text-[10px] text-muted">
                  本题 {currentQuestion.score} 分
                </span>
              </div>

              <h1 className="mt-5 whitespace-pre-wrap text-base font-medium leading-7 text-ink">
                {currentQuestion.stem}
              </h1>

              <div className="mt-6">
                {currentQuestion.type === "short" ? (
                  <textarea
                    value={
                      typeof answers[currentQuestion.id] === "string"
                        ? (answers[currentQuestion.id] as string)
                        : ""
                    }
                    onChange={(event) =>
                      updateAnswer(currentQuestion.id, event.target.value)
                    }
                    rows={8}
                    placeholder="写下你的答案，尽量分点作答。"
                    className="w-full resize-y rounded-xl border border-line bg-white px-4 py-3 text-sm leading-7 text-ink outline-none transition placeholder:text-[#b3aa9c] focus:border-[#cfc4b5] focus:ring-2 focus:ring-[#efe7da]"
                  />
                ) : (
                  <div className="space-y-2.5">
                    {currentQuestion.options.map((option) => {
                      const selected =
                        currentQuestion.type === "multiple"
                          ? Array.isArray(answers[currentQuestion.id]) &&
                            (answers[currentQuestion.id] as string[]).includes(
                              option.key,
                            )
                          : answers[currentQuestion.id] === option.key;
                      return (
                        <button
                          key={option.key}
                          type="button"
                          onClick={() => {
                            if (currentQuestion.type === "multiple") {
                              const current = Array.isArray(
                                answers[currentQuestion.id],
                              )
                                ? (answers[currentQuestion.id] as string[])
                                : [];
                              const next = current.includes(option.key)
                                ? current.filter((key) => key !== option.key)
                                : [...current, option.key].sort();
                              updateAnswer(currentQuestion.id, next);
                            } else {
                              updateAnswer(currentQuestion.id, option.key);
                            }
                          }}
                          className={cn(
                            "flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left text-sm transition",
                            selected
                              ? "border-accent bg-[#fbf4ef] text-ink"
                              : "border-line bg-white text-ink hover:border-[#cfc4b5]",
                          )}
                        >
                          <span
                            className={cn(
                              "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                              selected
                                ? "bg-accent text-white"
                                : "bg-[#f1ece2] text-[#5f5a4d]",
                            )}
                          >
                            {option.key}
                          </span>
                          <span className="leading-6">{option.text}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="mt-7 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setCurrentIndex((index) => Math.max(0, index - 1))
                  }
                  disabled={currentIndex === 0}
                  className="inline-flex items-center gap-1 rounded-xl border border-line bg-white px-3 py-2 text-xs font-medium text-ink disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                  上一题
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setCurrentIndex((index) =>
                      Math.min(questions.length - 1, index + 1),
                    )
                  }
                  disabled={currentIndex >= questions.length - 1}
                  className="inline-flex items-center gap-1 rounded-xl bg-ink px-3 py-2 text-xs font-medium text-white disabled:opacity-40"
                >
                  下一题
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </>
          )}
        </section>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <div className="rounded-2xl border border-line bg-paper p-4">
            <div className="flex items-center justify-between text-xs text-muted">
              <span>答题卡</span>
              <span>
                {answeredCount}/{questions.length} 已答
              </span>
            </div>
            <div className="mt-3 grid grid-cols-5 gap-1.5">
              {questions.map((question, index) => {
                const answered = hasAnswer(answers[question.id]);
                return (
                  <button
                    key={question.id}
                    type="button"
                    onClick={() => setCurrentIndex(index)}
                    className={cn(
                      "flex h-8 items-center justify-center rounded-lg border text-[11px] font-medium transition",
                      index === currentIndex
                        ? "border-accent bg-accent text-white"
                        : answered
                          ? "border-[#b9d8cc] bg-[#e1efe8] text-[#2f5d50]"
                          : "border-line bg-white text-muted hover:border-[#cfc4b5]",
                    )}
                  >
                    {index + 1}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-[10px] text-muted">
              <span className="inline-flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-sm bg-accent" />
                当前
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-sm bg-[#e1efe8]" />
                已答
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-sm border border-line bg-white" />
                未答
              </span>
            </div>
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={submitting}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-60"
            >
              {submitting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              交卷并看报告
            </button>
            <p className="mt-2 text-center text-[10px] leading-4 text-muted">
              答案会自动保存；时间到会自动交卷。
            </p>
          </div>

          <div className="rounded-xl border border-dashed border-[#d8d0c4] p-3 text-[10px] leading-4 text-[#8a8475]">
            主观题按评分细则踩点给分；交卷后报告会显示得分点、错题和举一反三。
          </div>
        </aside>
      </main>
    </div>
  );
}
