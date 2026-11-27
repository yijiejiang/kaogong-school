"use client";

import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Lightbulb,
  Loader2,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchAttemptReport } from "@/lib/api";
import type {
  AttemptReport,
  ExamOption,
  FeedbackSkill,
  FeedbackVariant,
  QuestionFeedback,
} from "@/lib/types";
import { cn } from "@/lib/utils";

function typeLabel(type: string): string {
  if (type === "multiple") return "多选";
  if (type === "short") return "简答";
  return "单选";
}

function toKeys(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (value === null || value === undefined || value === "") return [];
  return [String(value)];
}

function displayAnswer(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.map(String).join("、") : "未作答";
  }
  if (value === null || value === undefined || value === "") return "未作答";
  return String(value);
}

function formatDateTime(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReportPage() {
  const params = useParams<{ id: string; attemptId: string }>();
  const [report, setReport] = useState<AttemptReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [grading, setGrading] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    // 交卷后后台还在批改，这时接口返回 status=grading。
    // 自动轮询，批完直接显示报告，不用手动刷新。
    const load = async () => {
      try {
        const data = await fetchAttemptReport(params.attemptId);
        if (!active) return;
        const status = (data as { status?: string }).status;
        if (status === "grading") {
          setGrading(true);
          timer = setTimeout(load, 2000);
          return;
        }
        if (status === "failed") {
          setGrading(false);
          setError((data as { message?: string }).message || "批改失败了");
          setLoading(false);
          return;
        }
        setGrading(false);
        setReport(data);
      } catch (caught) {
        if (active) {
          setError(
            caught instanceof Error ? caught.message : "加载批改报告失败",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [params.attemptId]);

  if (loading && !grading) {
    return (
      <div className="flex h-dvh items-center justify-center bg-[var(--background)] text-sm text-muted">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载批改报告…
      </div>
    );
  }

  if (grading) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-3 bg-[var(--background)] px-6 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-ink" />
        <div className="text-sm font-medium text-ink">正在批改</div>
        <p className="max-w-sm text-xs leading-6 text-muted">
          老师正在逐题分析你的作答并生成讲解和举一反三，通常需要几十秒。
          批完后会发通知，也可以留在这个页面等，会自动刷新。
        </p>
        <Link
          href="/exams"
          className="mt-2 rounded-xl border border-line bg-paper px-4 py-2 text-xs text-muted hover:text-ink"
        >
          先去别处，批完再来看
        </Link>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-[var(--background)] px-4">
        <div className="w-full max-w-md rounded-2xl border border-line bg-paper p-6 text-center">
          <AlertTriangle className="mx-auto h-6 w-6 text-amber-600" />
          <h1 className="mt-3 text-base font-semibold">无法加载报告</h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            {error ?? "报告不存在或试卷还没有批改。"}
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

  const correctCount = report.questions.filter((item) => item.is_correct).length;
  const wrongCount = report.questions.length - correctCount;

  return (
    <div className="min-h-dvh bg-[var(--background)] text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-[#f7f4ee]/90 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-4xl items-center justify-between px-4 sm:px-6">
          <Link
            href="/exams"
            className="flex items-center gap-2 text-sm font-medium text-ink"
          >
            <ArrowLeft className="h-4 w-4" />
            考试中心
          </Link>
          <div className="text-sm font-semibold">批改报告</div>
          <Link href="/" className="text-xs text-muted">
            回对话
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl px-4 py-7 sm:px-6">
        <section className="rounded-2xl border border-line bg-paper p-5 sm:p-6">
          <div className="grid gap-5 sm:grid-cols-[auto_1fr] sm:items-center">
            <div className="flex h-28 w-28 flex-col items-center justify-center rounded-2xl bg-[#fbf4ef]">
              <div className="text-3xl font-semibold text-accent">
                {report.score}
              </div>
              <div className="mt-1 text-xs text-muted">
                / {report.total_score} 分
              </div>
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold tracking-tight">
                  {report.exam_title}
                </h1>
                <span className="rounded-full bg-[#e1efe8] px-2.5 py-1 text-[11px] font-medium text-[#2f5d50]">
                  {report.percentage}%
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted">
                {report.summary}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
                <span>正确 {correctCount}</span>
                <span>·</span>
                <span>错题 {wrongCount}</span>
                <span>·</span>
                <span>错题本 {report.error_book_added}</span>
                <span>·</span>
                <span>掌握度变化 {report.mastery_changes.length} 个知识点</span>
                {report.submitted_at && (
                  <>
                    <span>·</span>
                    <span>{formatDateTime(report.submitted_at)}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        {report.mastery_changes.length > 0 && (
          <section className="mt-5 rounded-2xl border border-line bg-paper p-5">
            <h2 className="text-base font-semibold">知识点掌握度</h2>
            <p className="mt-1 text-xs text-muted">
              本地 P2 使用“旧值 70% + 本次表现 30%”的滚动更新，后续会接入更强的
              IRT/Elo 模型。
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {report.mastery_changes.map((change) => {
                const up = change.after >= change.before;
                return (
                  <div
                    key={change.knowledge_point_id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-line bg-white px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-xs font-medium text-ink">
                        {change.knowledge_point_name}
                      </div>
                      <div className="mt-0.5 text-[9px] text-muted">
                        累计作答 {change.attempts} 题
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 text-xs">
                      <span className="text-muted">{change.before}</span>
                      <span className="text-[#b3aa9c]">→</span>
                      <span
                        className={
                          up ? "font-medium text-emerald-700" : "font-medium text-red-700"
                        }
                      >
                        {change.after}
                      </span>
                      {up ? (
                        <TrendingUp className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <TrendingDown className="h-3.5 w-3.5 text-red-600" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {(report.skill_changes?.length ?? 0) > 0 && (
          <section className="mt-5 rounded-2xl border border-line bg-paper p-5">
            <h2 className="text-base font-semibold">技能掌握度</h2>
            <p className="mt-1 text-xs text-muted">
              这次作答已经更新到对应技能；可到技能地图查看完整状态。
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {report.skill_changes?.map((change) => {
                const up = change.after >= change.before;
                return (
                  <div
                    key={change.skill_id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-line bg-white px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-xs font-medium text-ink">
                        {change.skill_name}
                      </div>
                      <div className="mt-0.5 text-[9px] text-muted">
                        累计作答 {change.attempts} 题
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 text-xs">
                      <span className="text-muted">{change.before}</span>
                      <span className="text-[#b3aa9c]">→</span>
                      <span
                        className={
                          up
                            ? "font-medium text-emerald-700"
                            : "font-medium text-red-700"
                        }
                      >
                        {change.after}
                      </span>
                      {up ? (
                        <TrendingUp className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <TrendingDown className="h-3.5 w-3.5 text-red-600" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        <section className="mt-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">逐题报告</h2>
            <span className="text-[10px] text-muted">
              {report.questions.length} 题
            </span>
          </div>
          {report.questions.map((feedback, index) => (
            <FeedbackCard
              key={feedback.question_id}
              feedback={feedback}
              index={index}
            />
          ))}
        </section>

        <div className="mt-5 rounded-2xl border border-dashed border-[#d8d0c4] bg-[#faf7f1] p-4 text-center text-xs leading-6 text-[#6f685b]">
          想让改卷老师再讲一遍？回到对话，直接问“这道题为什么错”或“再给我两道类似的”。
          <div className="mt-3">
            <Link
              href={`/?attempt=${encodeURIComponent(params.attemptId)}&ask=${encodeURIComponent("这套卷子我哪块最薄弱？")}`}
              className="inline-flex rounded-xl bg-ink px-4 py-2 text-xs font-medium text-white"
            >
              回对话问改卷老师
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

function FeedbackCard({
  feedback,
  index,
}: {
  feedback: QuestionFeedback;
  index: number;
}) {
  const correct = Boolean(feedback.is_correct);
  const correctKeys = toKeys(feedback.correct_answer);
  const userKeys = toKeys(feedback.user_answer);
  const isShort = feedback.type === "short";

  return (
    <article className="rounded-2xl border border-line bg-paper p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span className="font-semibold text-ink">第 {index + 1} 题</span>
          <span className="rounded-full bg-[#f1ece2] px-2 py-0.5 text-[10px]">
            {typeLabel(feedback.type)}
          </span>
          {feedback.knowledge_point_name && (
            <span className="rounded-full bg-[#e6edf5] px-2 py-0.5 text-[10px] text-[#3f5f7f]">
              {feedback.knowledge_point_name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              correct
                ? "bg-[#e1efe8] text-[#2f5d50]"
                : "bg-[#fbe9e7] text-[#a33a2a]",
            )}
          >
            {correct ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <XCircle className="h-3 w-3" />
            )}
            {correct ? "正确" : "错误"}
          </span>
          <span className="text-xs font-semibold text-ink">
            {feedback.score}/{feedback.max_score} 分
          </span>
        </div>
      </div>

      <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-ink">
        {feedback.stem}
      </p>

      {isShort ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <AnswerBlock
            label="你的答案"
            text={displayAnswer(feedback.user_answer)}
            tone={correct ? "green" : "red"}
          />
          <AnswerBlock
            label="参考答案"
            text={displayAnswer(feedback.correct_answer)}
            tone="neutral"
          />
        </div>
      ) : (
        <div className="mt-4 space-y-2">
          {feedback.options.map((option) => {
            const isCorrectOption = correctKeys.includes(option.key);
            const isUserOption = userKeys.includes(option.key);
            return (
              <div
                key={option.key}
                className={cn(
                  "flex items-start gap-3 rounded-xl border px-3 py-2.5 text-sm",
                  isCorrectOption
                    ? "border-[#b9d8cc] bg-[#eef7f3] text-[#2f5d50]"
                    : isUserOption
                      ? "border-[#f0c2b8] bg-[#fbf0ed] text-[#a33a2a]"
                      : "border-line bg-white text-ink",
                )}
              >
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/70 text-[10px] font-semibold">
                  {option.key}
                </span>
                <span className="leading-6">{option.text}</span>
                {isCorrectOption && (
                  <span className="ml-auto shrink-0 text-[10px] font-medium">
                    正确答案
                  </span>
                )}
                {!isCorrectOption && isUserOption && (
                  <span className="ml-auto shrink-0 text-[10px] font-medium">
                    你的选择
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {feedback.comment && (
        <p className="mt-3 text-xs leading-5 text-muted">{feedback.comment}</p>
      )}

      {feedback.explanation && (
        <div className="mt-3 rounded-xl bg-[#faf7f1] p-3 text-xs leading-6 text-[#5f5a4d]">
          <span className="inline-flex items-center gap-1 font-medium text-ink">
            <BookOpen className="h-3.5 w-3.5" />
            解析：
          </span>
          {feedback.explanation}
        </div>
      )}

      {isShort && feedback.rubric.length > 0 && (
        <RubricBlock feedback={feedback} />
      )}

      {feedback.skills?.length > 0 && (
        <SkillInsight skills={feedback.skills} />
      )}

      {feedback.skill_usage && (
        <SkillUsage text={feedback.skill_usage} />
      )}

      {feedback.variants.length > 0 && (
        <Variants variants={feedback.variants} />
      )}
    </article>
  );
}

function AnswerBlock({
  label,
  text,
  tone,
}: {
  label: string;
  text: string;
  tone: "green" | "red" | "neutral";
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-3",
        tone === "green"
          ? "border-[#b9d8cc] bg-[#eef7f3]"
          : tone === "red"
            ? "border-[#f0c2b8] bg-[#fbf0ed]"
            : "border-line bg-white",
      )}
    >
      <div className="text-[10px] font-medium text-muted">{label}</div>
      <p className="mt-1 whitespace-pre-wrap text-xs leading-6 text-ink">
        {text}
      </p>
    </div>
  );
}

function RubricBlock({ feedback }: { feedback: QuestionFeedback }) {
  const hitPoints = new Set(feedback.hit_points.map((item) => item.point));

  return (
    <div className="mt-3 rounded-xl border border-line bg-white p-3">
      <div className="text-[11px] font-medium text-ink">评分细则</div>
      <div className="mt-2 space-y-1.5">
        {feedback.rubric.map((point) => {
          const hit = hitPoints.has(point.point);
          return (
            <div
              key={point.point}
              className="flex items-start gap-2 text-[11px] leading-5"
            >
              <span
                className={cn(
                  "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px]",
                  hit
                    ? "bg-[#e1efe8] text-[#2f5d50]"
                    : "bg-[#fbe9e7] text-[#a33a2a]",
                )}
              >
                {hit ? "✓" : "×"}
              </span>
              <span className={hit ? "text-ink" : "text-muted"}>
                {point.point}（{point.score} 分）
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SkillInsight({ skills }: { skills: FeedbackSkill[] }) {
  return (
    <div className="mt-3 rounded-xl border border-[#d9e4e0] bg-[#eef5f2] p-3 text-xs leading-6 text-[#2f5d50]">
      <div className="flex items-center gap-1 font-medium">
        <Lightbulb className="h-3.5 w-3.5" />
        这题对应的技能
      </div>
      <div className="mt-2 space-y-2">
        {skills.map((skill) => (
          <div key={skill.id} className="rounded-lg bg-white/70 px-2.5 py-2">
            <div className="font-medium text-ink">{skill.name}</div>
            {skill.exam_patterns[0] && (
              <div className="mt-0.5">怎么考：{skill.exam_patterns[0]}</div>
            )}
            {skill.signals.length > 0 && (
              <div className="mt-0.5">
                识别信号：{skill.signals.slice(0, 2).join("；")}
              </div>
            )}
            {skill.steps.length > 0 && (
              <div className="mt-0.5">
                步骤：{skill.steps.slice(0, 2).join(" → ")}
              </div>
            )}
          </div>
        ))}
      </div>
      <Link
        href="/skills"
        className="mt-2 inline-flex items-center gap-1 text-[10px] font-medium text-[#2f5d50] underline-offset-2 hover:underline"
      >
        打开技能地图
      </Link>
    </div>
  );
}

function SkillUsage({ text }: { text: string }) {
  return (
    <div className="mt-3 rounded-xl border border-[#d9e3ec] bg-[#f4f8fb] px-4 py-3">
      <div className="text-[11px] font-semibold text-[#3f5f7a]">
        这道题怎么用这个技能
      </div>
      <p className="mt-1.5 whitespace-pre-wrap text-xs leading-6 text-[#4a5561]">
        {text}
      </p>
    </div>
  );
}

function Variants({ variants }: { variants: FeedbackVariant[] }) {
  return (
    <div className="mt-3 rounded-xl border border-[#f0d9a8] bg-[#fffaf0] p-3">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-[#8a6a24]">
        <Lightbulb className="h-3.5 w-3.5" />
        举一反三
      </div>
      <div className="mt-2 space-y-2">
        {variants.map((variant, index) => (
          <div key={`${variant.stem}-${index}`} className="text-[11px] leading-5">
            <div className="font-medium text-ink">
              {index + 1}. {variant.stem}
            </div>
            <div className="text-[#8a6a24]">答案：{variant.answer}</div>
            <div className="text-muted">{variant.explanation}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
