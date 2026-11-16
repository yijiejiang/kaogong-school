"use client";

import { Volume2, VolumeX } from "lucide-react";
import { useState } from "react";

import { agentMeta } from "@/lib/agents";
import type { ChatMessage } from "@/lib/types";

import { ExamCard } from "./ExamCard";
import { Markdown } from "./Markdown";
import { MaterialCard } from "./MaterialCard";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const [speaking, setSpeaking] = useState(false);

  if (message.role === "system") {
    return (
      <div className="flex justify-center">
        <span className="rounded-full border border-line bg-[#f1ece2] px-3 py-1 text-[11px] text-muted">
          {message.content}
        </span>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[88%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-ink px-4 py-3 text-sm leading-6 text-white shadow-[0_1px_0_rgba(31,35,40,0.04)]">
          {message.content}
        </div>
      </div>
    );
  }

  const meta = agentMeta(message.author);
  const showTyping = message.streaming && !message.content;

  const toggleSpeak = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      return;
    }
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(message.content);
    utterance.lang = "zh-CN";
    utterance.rate = 1.02;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  return (
    <div className="flex gap-3">
      <div
        className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${meta.avatarClass}`}
      >
        {meta.short}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[11px] text-muted">
          <span className="font-medium text-ink">{meta.name}</span>
          {message.streaming && (
            <span className="text-accent">正在输入…</span>
          )}
          {!message.streaming && message.content && (
            <button
              type="button"
              onClick={toggleSpeak}
              title={speaking ? "停止朗读" : "朗读这条回答"}
              className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] text-muted transition hover:bg-[#f1ece2] hover:text-ink"
            >
              {speaking ? (
                <VolumeX className="h-3 w-3" />
              ) : (
                <Volume2 className="h-3 w-3" />
              )}
              朗读
            </button>
          )}
        </div>

        {showTyping ? (
          <div className="flex items-center gap-1 rounded-2xl rounded-tl-md border border-line bg-paper px-4 py-3">
            <span className="h-1.5 w-1.5 rounded-full bg-accent typing-dot" />
            <span
              className="h-1.5 w-1.5 rounded-full bg-accent typing-dot"
              style={{ animationDelay: "0.15s" }}
            />
            <span
              className="h-1.5 w-1.5 rounded-full bg-accent typing-dot"
              style={{ animationDelay: "0.3s" }}
            />
          </div>
        ) : (
          message.content && (
            <div className="rounded-2xl rounded-tl-md border border-line bg-paper px-4 py-3 shadow-[0_1px_0_rgba(31,35,40,0.03)]">
              <Markdown>{message.content}</Markdown>
            </div>
          )
        )}

        {message.ui?.type === "exam_card" ? (
          <ExamCard payload={message.ui} />
        ) : message.ui?.type === "material_card" ? (
          <MaterialCard payload={message.ui} />
        ) : null}
      </div>
    </div>
  );
}
