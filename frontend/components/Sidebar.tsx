"use client";

import {
  BarChart3,
  FileText,
  Library,
  Map as MapIcon,
  MessageSquare,
  Plus,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";

import type { SessionSummary, SettingsBundle } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

type SidebarProps = {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  settings: SettingsBundle | null;
  open: boolean;
  onClose: () => void;
};

export function Sidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNew,
  settings,
  open,
  onClose,
}: SidebarProps) {
  const profile = settings?.profile;

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/25 backdrop-blur-[1px] lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 shrink-0 flex-col border-r border-line bg-[var(--sidebar)] transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-start justify-between px-4 pb-3 pt-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-lg font-semibold text-white shadow-sm">
              公
            </div>
            <div>
              <div className="text-sm font-semibold tracking-wide text-ink">
                考公私塾
              </div>
              <div className="text-[9px] uppercase tracking-[0.2em] text-muted">
                Personal Academy
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[#8a8475] hover:bg-[#e7e1d6] lg:hidden"
            aria-label="关闭会话列表"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-3">
          <button
            type="button"
            onClick={onNew}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-3 py-2.5 text-xs font-medium text-white transition hover:opacity-90"
          >
            <Plus className="h-3.5 w-3.5" />
            新对话
          </button>
        </div>

        <nav className="mt-5 space-y-1 px-3">
          <NavItem icon={<MessageSquare className="h-4 w-4" />} label="对话" active />
          <Link
            href="/exams"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-[#5f5a4d] transition hover:bg-[#e7e1d6]"
          >
            <FileText className="h-4 w-4" />
            考试中心
          </Link>
          <Link
            href="/library"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-[#5f5a4d] transition hover:bg-[#e7e1d6]"
          >
            <Library className="h-4 w-4" />
            资料库
          </Link>
          <Link
            href="/knowledge"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-[#5f5a4d] transition hover:bg-[#e7e1d6]"
          >
            <Sparkles className="h-4 w-4" />
            知识挖掘
          </Link>
          <Link
            href="/skills"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-[#5f5a4d] transition hover:bg-[#e7e1d6]"
          >
            <MapIcon className="h-4 w-4" />
            技能地图
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-[#5f5a4d] transition hover:bg-[#e7e1d6]"
          >
            <BarChart3 className="h-4 w-4" />
            学情看板
          </Link>
          <Link
            href="/settings"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-[#5f5a4d] transition hover:bg-[#e7e1d6]"
          >
            <Settings className="h-4 w-4" />
            设置
          </Link>
        </nav>

        <div className="mt-6 flex items-center justify-between px-4">
          <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#8a8475]">
            最近对话
          </span>
          <span className="text-[10px] text-[#a59d90]">{sessions.length}</span>
        </div>

        <div className="scrollbar-thin mt-2 flex-1 overflow-y-auto px-3 pb-3">
          {sessions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#d8d0c4] px-3 py-4 text-xs leading-5 text-[#8a8475]">
              还没有对话。问辅导员一个问题，从这里开始。
            </div>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => onSelect(session.id)}
                className={cn(
                  "mb-1 flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left transition",
                  session.id === activeSessionId
                    ? "bg-paper shadow-sm"
                    : "hover:bg-[#e7e1d6]",
                )}
              >
                <MessageSquare
                  className={cn(
                    "mt-0.5 h-3.5 w-3.5 shrink-0",
                    session.id === activeSessionId
                      ? "text-accent"
                      : "text-[#a59d90]",
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs font-medium text-ink">
                    {session.title || "新会话"}
                  </span>
                  <span className="mt-0.5 block text-[10px] text-[#8a8475]">
                    {formatRelative(session.updated_at) || "刚刚"}
                  </span>
                </span>
              </button>
            ))
          )}
        </div>

        <div className="border-t border-[#ddd6c8] p-3">
          <Link
            href="/settings"
            className="flex items-center gap-3 rounded-xl px-2 py-2 transition hover:bg-[#e7e1d6]"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e1d9ca] text-xs font-semibold text-[#5f5a4d]">
              {profile?.name?.slice(0, 1) || "同"}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium text-ink">
                {profile?.name || "同学"}
              </div>
              <div className="truncate text-[10px] text-muted">
                {profile?.target_exam || "国考"} · {profile?.daily_minutes || 120}{" "}
                分钟/天
              </div>
            </div>
            <Settings className="h-3.5 w-3.5 text-[#a59d90]" />
          </Link>
        </div>
      </aside>
    </>
  );
}

function NavItem({
  icon,
  label,
  active = false,
  badge,
  disabled = false,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  badge?: string;
  disabled?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium",
        active ? "bg-paper text-ink shadow-sm" : "text-[#5f5a4d]",
        disabled && "cursor-not-allowed opacity-65",
      )}
    >
      {icon}
      <span className="flex-1">{label}</span>
      {badge && (
        <span className="rounded-full bg-[#e7e1d6] px-1.5 py-0.5 text-[9px] text-[#8a8475]">
          {badge}
        </span>
      )}
    </div>
  );
}
