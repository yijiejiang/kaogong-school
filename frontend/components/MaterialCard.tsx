import {
  AlertTriangle,
  AudioLines,
  CheckCircle2,
  FileText,
  Image as ImageIcon,
  Link2,
  Loader2,
  Video,
} from "lucide-react";
import Link from "next/link";

import type { UiPayload } from "@/lib/types";

const STATUS_META = {
  ready: {
    label: "已就绪",
    className: "bg-[#e1efe8] text-[#2f5d50]",
    icon: CheckCircle2,
  },
  processing: {
    label: "入库中",
    className: "bg-[#fff4dd] text-[#8a6a24]",
    icon: Loader2,
  },
  pending: {
    label: "等待中",
    className: "bg-[#ece8df] text-[#6b7280]",
    icon: Loader2,
  },
  failed: {
    label: "失败",
    className: "bg-[#fbe9e7] text-[#a33a2a]",
    icon: AlertTriangle,
  },
};

export function MaterialCard({ payload }: { payload: UiPayload }) {
  if (payload.type !== "material_card") return null;

  const status = String(payload.status ?? "pending");
  const meta =
    STATUS_META[status as keyof typeof STATUS_META] ?? STATUS_META.pending;
  const Icon = meta.icon;
  const isUrl = payload.kind === "url";
  const isImage = payload.kind === "image";
  const isVideo = payload.kind === "video";
  const isAudio = payload.kind === "audio";
  const kindLabel = isUrl
    ? "网页资料"
    : isImage
      ? "图片资料"
      : isVideo
        ? "视频资料"
        : isAudio
          ? "音频资料"
          : "本地资料";
  const chunkCount =
    typeof payload.chunk_count === "number" ? payload.chunk_count : 0;
  const subject = typeof payload.subject === "string" ? payload.subject : "";
  const module = typeof payload.module === "string" ? payload.module : "";
  const error = typeof payload.error === "string" ? payload.error : "";
  const spinning = status === "processing" || status === "pending";

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-line bg-paper">
      <div className="flex items-start gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#f2ead6] text-[#8a6a24]">
          {isVideo ? (
            <Video className="h-4 w-4" />
          ) : isAudio ? (
            <AudioLines className="h-4 w-4" />
          ) : isImage ? (
            <ImageIcon className="h-4 w-4" />
          ) : isUrl ? (
            <Link2 className="h-4 w-4" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-semibold text-ink">
              {payload.title ?? "资料"}
            </span>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${meta.className}`}
            >
              <Icon className={`h-3 w-3 ${spinning ? "animate-spin" : ""}`} />
              {meta.label}
            </span>
          </div>
          <div className="mt-1 text-xs text-muted">
            {kindLabel} · {chunkCount} 个分块
            {subject || module
              ? ` · ${[subject, module].filter(Boolean).join(" / ")}`
              : ""}
          </div>
          {error && (
            <div className="mt-1 text-xs text-red-700">{error}</div>
          )}
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5">
        <span className="text-[10px] text-muted">
          入库后可在资料库查看分块、标签与引用
        </span>
        <Link
          href="/library"
          className="shrink-0 rounded-lg border border-line bg-white px-2.5 py-1 text-[11px] font-medium text-ink hover:border-[#cfc4b5]"
        >
          去资料库
        </Link>
      </div>
    </div>
  );
}
