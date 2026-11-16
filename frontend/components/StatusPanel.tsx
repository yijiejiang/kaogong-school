import { ArrowRight, CalendarDays, Target } from "lucide-react";

import type { SettingsBundle } from "@/lib/types";
import { examCountdown } from "@/lib/utils";

type StatusPanelProps = {
  settings: SettingsBundle | null;
  onPrompt: (text: string) => void;
};

export function StatusPanel({ settings, onPrompt }: StatusPanelProps) {
  const profile = settings?.profile;
  const countdown = examCountdown(profile?.exam_date);

  return (
    <aside className="hidden w-72 shrink-0 flex-col border-l border-line bg-[#faf7f1] xl:flex">
      <div className="border-b border-line px-5 py-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#8a8475]">
          备考状态
        </div>
        <div className="mt-3 text-lg font-semibold text-ink">
          {profile?.name || "同学"}
        </div>
        <div className="mt-1 flex items-center gap-1.5 text-xs text-muted">
          <Target className="h-3.5 w-3.5" />
          {profile?.target_exam || "国考"}
          {countdown && (
            <>
              <span className="text-[#c9c0b2]">·</span>
              <span>{countdown}</span>
            </>
          )}
        </div>
        {profile?.exam_date && (
          <div className="mt-1 flex items-center gap-1.5 text-[10px] text-[#a59d90]">
            <CalendarDays className="h-3 w-3" />
            {profile.exam_date}
          </div>
        )}
        {settings?.server.mock_mode && (
          <span className="mt-3 inline-flex rounded-full bg-[#e1efe8] px-2 py-0.5 text-[10px] font-medium text-[#2f5d50]">
            本地演示模式
          </span>
        )}
      </div>

      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto p-4">
        <div className="rounded-xl border border-line bg-paper p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium text-ink">学情档案</div>
            <span className="rounded-full bg-[#f1ece2] px-2 py-0.5 text-[9px] text-muted">
              待建立
            </span>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-muted">
            完成一次诊断练习后，督导老师会在这里生成知识点掌握度和薄弱项。
          </p>
          <button
            type="button"
            onClick={() =>
              onPrompt("根据我目前的情况，帮我安排本周的学习计划。")
            }
            className="mt-3 flex w-full items-center justify-between rounded-lg bg-ink px-3 py-2 text-[11px] font-medium text-white transition hover:opacity-90"
          >
            让督导老师看看
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="rounded-xl border border-line bg-paper p-4">
          <div className="text-sm font-medium text-ink">今日建议</div>
          <p className="mt-2 text-[11px] leading-5 text-muted">
            {profile?.daily_minutes || 120} 分钟 · 先做一次诊断，再按薄弱点分配模块。
          </p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#eee8dd]">
            <div className="h-full w-0 rounded-full bg-accent" />
          </div>
          <div className="mt-1.5 text-[9px] text-[#a59d90]">今日完成度 0%</div>
        </div>

        <div className="rounded-xl border border-line bg-paper p-4">
          <div className="text-sm font-medium text-ink">快捷问题</div>
          <div className="mt-2 space-y-1.5">
            {[
              "我最近学得怎么样？",
              "资料分析速算技巧有哪些？",
              "出一套资料分析小卷",
            ].map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => onPrompt(question)}
                className="w-full rounded-lg border border-line px-3 py-2 text-left text-[11px] text-ink transition hover:bg-[#f3efe7]"
              >
                {question}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-dashed border-[#d8d0c4] p-4 text-[10px] leading-5 text-[#8a8475]">
          P4.5 已接入五模块题库、AI 原创题、语音转写、用量成本看板、本地多用户与 iOS 客户端。
        </div>
      </div>
    </aside>
  );
}
