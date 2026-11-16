import { Menu, Settings2 } from "lucide-react";
import Link from "next/link";

import { agentMeta } from "@/lib/agents";

import { NotificationBell } from "./NotificationBell";

type ChatHeaderProps = {
  author: string;
  onMenu: () => void;
};

export function ChatHeader({ author, onMenu }: ChatHeaderProps) {
  const meta = agentMeta(author);
  const isCounselor = author === "counselor";

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-line bg-[#f7f4ee]/85 px-3 backdrop-blur sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenu}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-line bg-paper text-ink lg:hidden"
          aria-label="打开会话列表"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${meta.avatarClass}`}
        >
          {meta.short}
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-ink">
              {meta.name}
            </span>
            <span className="shrink-0 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-medium text-accent">
              {isCounselor ? "主对话" : "专业协作"}
            </span>
          </div>
          <div className="truncate text-[11px] text-muted">{meta.description}</div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <NotificationBell />
        <Link
          href="/settings"
          className="flex h-9 items-center gap-1.5 rounded-xl border border-line bg-paper px-3 text-xs font-medium text-ink transition hover:border-[#cfc4b5] hover:bg-white"
        >
          <Settings2 className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">设置</span>
        </Link>
      </div>
    </header>
  );
}
