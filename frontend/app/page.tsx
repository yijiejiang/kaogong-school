"use client";

import {
  AlertTriangle,
  ArrowRight,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { ChatHeader } from "@/components/ChatHeader";
import { Composer } from "@/components/Composer";
import { MessageBubble } from "@/components/MessageBubble";
import { Sidebar } from "@/components/Sidebar";
import { StatusPanel } from "@/components/StatusPanel";
import { agentMeta, ROLE_OPTIONS } from "@/lib/agents";
import {
  fetchMessages,
  fetchSessions,
  fetchSettings,
  streamChat,
  uploadMaterial,
  type StreamEvent,
} from "@/lib/api";
import type { ChatMessage, SessionSummary, SettingsBundle } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useUserId } from "@/lib/user";

const QUICK_PROMPTS = [
  {
    title: "看看我的学情",
    detail: "让督导老师根据当前记录给判断",
    prompt: "我最近学得怎么样？帮我看看学情。",
  },
  {
    title: "出一套小卷",
    detail: "30 题资料分析，35 分钟",
    prompt: "帮我出一套资料分析小卷。",
  },
  {
    title: "排本周计划",
    detail: "结合目标考试和每日时间",
    prompt: "根据我目前的情况，帮我安排本周的学习计划。",
  },
  {
    title: "问资料库",
    detail: "查资料分析速算技巧与来源",
    prompt: "资料分析速算技巧有哪些？",
  },
];

export default function ChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatWorkspace />
    </Suspense>
  );
}

function ChatWorkspace() {
  const userId = useUserId();
  const searchParams = useSearchParams();
  const attemptId = searchParams.get("attempt") || "";
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<SettingsBundle | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [headerAuthor, setHeaderAuthor] = useState("counselor");
  // 点了「继续问这位老师」但还没发出去时，记住下一条消息要绕过辅导员
  const [continueWith, setContinueWith] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const activeAssistantIdRef = useRef<string | null>(null);
  const activeAuthorRef = useRef<string | null>(null);
  const pendingUiRef = useRef<
    Record<string, NonNullable<ChatMessage["ui"]>>
  >({});

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await fetchSessions(userId));
    } catch {
      // The session list is useful but not required to keep chatting.
    }
  }, [userId]);

  useEffect(() => {
    setActiveSessionId(null);
    setMessages([]);
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    fetchSettings(userId)
      .then(setSettings)
      .catch(() => {
        // The Settings page will surface the details.
      });
  }, [userId]);

  // 流式回答时每来一段内容 messages 都会变，若无条件滚到底，
  // 用户往上翻历史会被一直拽回去，看不到上面的内容。
  // 只在用户本来就贴着底部时才自动跟随。
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distance < 120;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (messages.length === 0) {
      scrollRef.current?.scrollTo({ top: 0 });
      return;
    }
    if (!stickToBottomRef.current) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  const ensureAssistant = useCallback((author: string) => {
    if (activeAssistantIdRef.current && activeAuthorRef.current === author) {
      return activeAssistantIdRef.current;
    }
    const id = `a_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    activeAssistantIdRef.current = id;
    activeAuthorRef.current = author;
    const pendingUi = pendingUiRef.current[author] ?? null;
    if (pendingUi) delete pendingUiRef.current[author];
    setMessages((prev) => [
      ...prev,
      {
        id,
        role: "assistant",
        author,
        content: "",
        streaming: true,
        ui: pendingUi,
      },
    ]);
    return id;
  }, []);

  const flushPendingUi = useCallback(() => {
    const pending = pendingUiRef.current;
    pendingUiRef.current = {};
    const entries = Object.entries(pending);
    if (entries.length === 0) return;
    setMessages((prev) => [
      ...prev,
      ...entries.map(([author, ui]) => ({
        id: `ui_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        role: "assistant" as const,
        author,
        content: "",
        ui,
      })),
    ]);
  }, []);

  const resetActiveAssistant = useCallback(() => {
    activeAssistantIdRef.current = null;
    activeAuthorRef.current = null;
  }, []);

  const send = useCallback(
    async (raw?: string, explicitTarget?: string) => {
      const text = (raw ?? input).trim();
      if (!text || streaming) return;
      // 显式传入的优先；否则用「点了续问按钮」记下的意图
      const target = explicitTarget ?? continueWith ?? undefined;

      setInput("");
      setError(null);
      setStreaming(true);
      resetActiveAssistant();
      pendingUiRef.current = {};
      setHeaderAuthor(target ?? "counselor");
      // 自己发消息时总要看得到，哪怕之前翻到了上面
      stickToBottomRef.current = true;
      setMessages((prev) => [
        ...prev,
        { id: `u_${Date.now()}`, role: "user", author: "user", content: text },
      ]);

      setContinueWith(null);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(
          {
            message: text,
            session_id: activeSessionId,
            user_id: userId,
            ...(attemptId ? { attempt_id: attemptId } : {}),
            ...(target ? { continue_with: target } : {}),
          },
          (event: StreamEvent) => {
            switch (event.type) {
              case "session": {
                if (typeof event.session_id === "string") {
                  setActiveSessionId(event.session_id);
                }
                break;
              }
              case "delta": {
                const author = String(event.author ?? "counselor");
                const chunk = String(event.text ?? "");
                if (!chunk) break;
                setHeaderAuthor(author);
                const id = ensureAssistant(author);
                setMessages((prev) =>
                  prev.map((message) =>
                    message.id === id
                      ? { ...message, content: message.content + chunk }
                      : message,
                  ),
                );
                break;
              }
              case "message": {
                const author = String(event.author ?? "counselor");
                const content = String(event.text ?? "");
                setHeaderAuthor(author);
                const id = ensureAssistant(author);
                setMessages((prev) =>
                  prev.map((message) =>
                    message.id === id
                      ? { ...message, content, streaming: false }
                      : message,
                  ),
                );
                resetActiveAssistant();
                break;
              }
              case "transfer": {
                const to = String(event.to ?? "specialist");
                const meta = agentMeta(to);
                resetActiveAssistant();
                setHeaderAuthor(to);
                setMessages((prev) => [
                  ...prev,
                  {
                    id: `s_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
                    role: "system",
                    author: "system",
                    content: `已转接给 ${meta.name}`,
                  },
                ]);
                break;
              }
              case "ui": {
                const author = String(event.author ?? "counselor");
                const component = event.component as NonNullable<
                  ChatMessage["ui"]
                >;
                if (component) {
                  setHeaderAuthor(author);
                  pendingUiRef.current[author] = component;
                }
                break;
              }
              case "error": {
                setError(String(event.message ?? "对话失败，请稍后重试。"));
                resetActiveAssistant();
                break;
              }
              default:
                break;
            }
          },
          controller.signal,
        );

        setMessages((prev) =>
          prev.map((message) =>
            message.streaming ? { ...message, streaming: false } : message,
          ),
        );
        flushPendingUi();
        await refreshSessions();
      } catch (caught) {
        if ((caught as Error).name !== "AbortError") {
          setError(
            caught instanceof Error ? caught.message : "对话失败，请稍后重试。",
          );
        }
        setMessages((prev) =>
          prev.map((message) =>
            message.streaming ? { ...message, streaming: false } : message,
          ),
        );
      } finally {
        setStreaming(false);
        resetActiveAssistant();
        abortRef.current = null;
      }
    },
    [
      activeSessionId,
      attemptId,
      continueWith,
      ensureAssistant,
      flushPendingUi,
      input,
      refreshSessions,
      resetActiveAssistant,
      streaming,
    ],
  );

  // 从报告页跳过来时带着问题，进来就直接问，不用学生再打一遍。
  const askedRef = useRef("");
  useEffect(() => {
    const ask = searchParams.get("ask") || "";
    if (!ask || askedRef.current === ask + attemptId) return;
    askedRef.current = ask + attemptId;
    void send(ask);
  }, [attemptId, searchParams, send]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
    setMessages((prev) =>
      prev.map((message) =>
        message.streaming ? { ...message, streaming: false } : message,
      ),
    );
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      try {
        const material = await uploadMaterial(file);
        void send(
          `我上传了资料《${material.title}》，请资料搜集老师帮我确认入库结果。`,
        );
        setMessages((prev) => [
          ...prev,
          {
            id: `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            role: "assistant",
            author: "collector",
            content: "",
            ui: { type: "material_card", ...material },
          },
        ]);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "上传失败");
      }
    },
    [send],
  );

  const selectSession = useCallback(
    async (id: string) => {
      if (streaming) return;
      setSidebarOpen(false);
      setError(null);
      setActiveSessionId(id);
      pendingUiRef.current = {};
      try {
        const history = await fetchMessages(id, userId);
        setMessages(history);
        const lastAssistant = [...history]
          .reverse()
          .find((message) => message.role === "assistant");
        setHeaderAuthor(lastAssistant?.author ?? "counselor");
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "加载会话失败");
      }
    },
    [streaming, userId],
  );

  const newChat = useCallback(() => {
    if (streaming) return;
    setSidebarOpen(false);
    setActiveSessionId(null);
    setMessages([]);
    setError(null);
    setInput("");
    setHeaderAuthor("counselor");
    pendingUiRef.current = {};
  }, [streaming]);

  const handleQuote = useCallback((text: string) => {
    const quoted = text
      .split("\n")
      .filter((line) => line.trim())
      .slice(0, 6)
      .join("\n")
      .slice(0, 400);
    setInput((prev) =>
      prev.trim()
        ? `${prev}\n\n> ${quoted.replace(/\n/g, "\n> ")}\n\n`
        : `> ${quoted.replace(/\n/g, "\n> ")}\n\n`,
    );
  }, []);

  const composerDisabled = settings ? !settings.server.llm_configured : false;

  const prompt = useCallback(
    (text: string) => {
      if (composerDisabled) {
        setError("请先在设置页配置 LLM 模型，再开始对话。");
        return;
      }
      void send(text);
    },
    [composerDisabled, send],
  );

  const hasStreamingMessage = messages.some((message) => message.streaming);

  // 只有专家回答才需要「继续问」：默认本来就回辅导员，给它的回答加按钮没意义
  const lastTeacher = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i];
      if (m.role !== "assistant" || !m.content) continue;
      if (m.streaming) return null;
      if (m.author === "counselor" || !m.author) return null;
      return m.author;
    }
    return null;
  })();

  return (
    <div className="flex h-dvh overflow-hidden bg-[var(--background)] text-ink">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={(id) => void selectSession(id)}
        onNew={newChat}
        settings={settings}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <ChatHeader
          author={headerAuthor}
          onMenu={() => setSidebarOpen(true)}
        />

        {settings && !settings.server.llm_configured && <SetupBanner />}
        {settings?.server.mock_mode && <MockBanner />}
        {error && (
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        )}

        <div ref={scrollRef} className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6 sm:px-6 sm:py-8">
            {messages.length === 0 ? (
              <Welcome onPrompt={prompt} />
            ) : (
              messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  onQuote={handleQuote}
                />
              ))
            )}

            {streaming && !hasStreamingMessage && <Thinking />}

            {lastTeacher && !streaming && (
              <div className="flex justify-center">
                <button
                  type="button"
                  onClick={() => {
                    const text = input.trim();
                    if (text) {
                      setInput("");
                      setContinueWith(null);
                      void send(text, lastTeacher);
                      return;
                    }
                    // 输入框还空着，就记下续接意图，等学生打完这句话自动带上
                    setContinueWith(
                      continueWith === lastTeacher ? null : lastTeacher,
                    );
                  }}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] transition",
                    continueWith === lastTeacher
                      ? "border-[#3f5f7f] bg-[#e6edf5] text-[#3f5f7f]"
                      : "border-line bg-paper text-muted hover:border-[#cfc4b5] hover:text-ink",
                  )}
                  title="跳过辅导员，直接由这位老师接着答"
                >
                  {continueWith === lastTeacher ? "将直接问" : "继续问"}
                  {agentMeta(lastTeacher).name}
                </button>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        <Composer
          value={input}
          onChange={setInput}
          onSend={() => void send()}
          onStop={stop}
          onFile={(file) => void handleFile(file)}
          streaming={streaming}
          disabled={composerDisabled}
        />
      </main>

      <StatusPanel settings={settings} onPrompt={prompt} />
    </div>
  );
}

function Welcome({ onPrompt }: { onPrompt: (text: string) => void }) {
  return (
    <div className="flex flex-col gap-7 py-4">
      <div className="flex flex-col gap-4">
        <div className="inline-flex w-fit items-center gap-2 rounded-full border border-line bg-paper px-3 py-1 text-[11px] text-muted">
          <Sparkles className="h-3.5 w-3.5 text-accent" />
          你的个人考公私塾 · P0
        </div>
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            今天，想先解决什么？
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted">
            辅导员在这儿。可以直接问学习方法，也可以让它帮你看学情、排计划、
            出一套小卷，或者直接问资料库里的知识点。
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {QUICK_PROMPTS.map((item) => (
          <button
            key={item.title}
            type="button"
            onClick={() => onPrompt(item.prompt)}
            className="group flex items-start justify-between gap-3 rounded-2xl border border-line bg-paper p-4 text-left transition hover:border-[#d3c8b8] hover:bg-white"
          >
            <span>
              <span className="block text-sm font-semibold text-ink">
                {item.title}
              </span>
              <span className="mt-1 block text-xs leading-5 text-muted">
                {item.detail}
              </span>
            </span>
            <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-[#b3aa9c] transition group-hover:translate-x-0.5 group-hover:text-accent" />
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <span className="mr-1">当前可协作：</span>
        {ROLE_OPTIONS.map((role) => {
          const meta = agentMeta(role.key);
          return (
            <span
              key={role.key}
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-paper px-2.5 py-1 text-ink"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${meta.dotClass}`} />
              {meta.name}
            </span>
          );
        })}
        <span className="text-[#a59d90]">全部角色已接入</span>
      </div>
    </div>
  );
}

function Thinking() {
  return (
    <div className="flex items-center gap-2 text-xs text-muted">
      <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
      辅导员正在思考…
    </div>
  );
}

function SetupBanner() {
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-900">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
        <span>
          还没有配置 LLM。到设置页填入 Base URL、API Key 和模型后即可开始对话。
        </span>
        <Link
          href="/settings"
          className="shrink-0 rounded-lg border border-amber-300 bg-white px-2.5 py-1 font-medium text-amber-900"
        >
          去设置
        </Link>
      </div>
    </div>
  );
}

function MockBanner() {
  return (
    <div className="border-b border-[#d9e4e0] bg-[#eef5f2] px-4 py-2 text-[11px] text-[#2f5d50]">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
        <span>
          本地演示模式：不会调用外部 LLM，用于验证转接和界面。配置真实模型后自动切换。
        </span>
        <Link
          href="/settings"
          className="shrink-0 font-medium underline underline-offset-2"
        >
          配置模型
        </Link>
      </div>
    </div>
  );
}

function ErrorBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <div className="border-b border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-800">
      <div className="mx-auto flex max-w-3xl items-start justify-between gap-3">
        <span className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {message}
        </span>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded p-1 hover:bg-red-100"
          aria-label="关闭错误提示"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
