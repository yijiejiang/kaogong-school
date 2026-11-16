"use client";

import { Bell, CheckCheck, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api";
import type { NotificationItem } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

export function NotificationBell() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchNotifications();
      setItems(data.items);
      setUnread(data.unread);
    } catch {
      // The backend may be restarting; keep the last known state.
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 60000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) void refresh();
  };

  const handleRead = async (item: NotificationItem) => {
    if (item.read) return;
    setLoading(true);
    try {
      await markNotificationRead(item.id);
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  const handleAll = async () => {
    setLoading(true);
    try {
      await markAllNotificationsRead();
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative" ref={wrapperRef}>
      <button
        type="button"
        onClick={toggle}
        className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-paper text-ink transition hover:border-[#cfc4b5] hover:bg-white"
        aria-label="通知"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Bell className="h-4 w-4" />
        )}
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[9px] font-semibold leading-none text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-80 overflow-hidden rounded-2xl border border-line bg-paper shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div className="text-xs font-semibold text-ink">通知</div>
            <button
              type="button"
              onClick={() => void handleAll()}
              className="inline-flex items-center gap-1 text-[10px] text-muted transition hover:text-ink"
            >
              <CheckCheck className="h-3 w-3" />
              全部已读
            </button>
          </div>
          <div className="scrollbar-thin max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-7 text-center text-xs text-muted">
                暂无通知。到点后督导老师会提醒今天的学习任务。
              </div>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => void handleRead(item)}
                  className={cn(
                    "block w-full border-b border-line px-4 py-3 text-left transition last:border-b-0 hover:bg-[#faf7f1]",
                    !item.read && "bg-[#fbf4ef]",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-medium text-ink">
                      {item.title}
                    </span>
                    {!item.read && (
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    )}
                  </div>
                  <p className="mt-1 text-[10px] leading-5 text-muted">
                    {item.body}
                  </p>
                  <div className="mt-1 text-[9px] text-[#a59d90]">
                    {formatRelative(item.created_at) || "刚刚"}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
