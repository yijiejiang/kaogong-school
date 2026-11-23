"use client";

import {
  AlertTriangle,
  ArrowLeft,
  AudioLines,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileText,
  Globe2,
  Image as ImageIcon,
  Layers3,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Upload,
  Video,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  API_BASE,
  deleteMaterial,
  fetchKnowledgeTree,
  fetchMaterial,
  fetchMaterials,
  importUrl,
  reindexMaterial,
  searchMaterials,
  seedSampleMaterial,
  uploadMaterial,
} from "@/lib/api";
import type {
  KnowledgeNode,
  Material,
  MaterialChunk,
  MaterialDetail,
  SearchResponse,
} from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

const STATUS_META: Record<
  string,
  { label: string; className: string; icon: LucideIcon }
> = {
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

export default function LibraryPage() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [tree, setTree] = useState<KnowledgeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState("");
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [materialList, knowledgeTree] = await Promise.all([
        fetchMaterials(),
        fetchKnowledgeTree(),
      ]);
      setMaterials(materialList);
      setTree(knowledgeTree);
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "加载资料库失败",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const active = materials.some(
      (material) =>
        material.status === "pending" || material.status === "processing",
    );
    if (!active) return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [materials, refresh]);

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    setNotice(null);
    try {
      const uploaded: Material[] = [];
      for (const file of Array.from(files)) {
        uploaded.push(await uploadMaterial(file));
      }
      setNotice({
        kind: "success",
        text: `已上传 ${uploaded.length} 份资料，正在后台入库。`,
      });
      await refresh();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "上传失败",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleUrl = async () => {
    const target = url.trim();
    if (!target) return;
    setBusy(true);
    setNotice(null);
    try {
      const material = await importUrl(target);
      setUrl("");
      setNotice({
        kind: "success",
        text: `已提交网页入库：${material.title}`,
      });
      await refresh();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "导入网页失败",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleSeed = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const material = await seedSampleMaterial();
      setNotice({
        kind: "success",
        text: `已导入示例资料：${material.title}`,
      });
      await refresh();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "导入示例失败",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleReindex = async (material: Material) => {
    setBusy(true);
    setNotice(null);
    try {
      await reindexMaterial(material.id);
      setNotice({ kind: "success", text: `已提交重新索引：${material.title}` });
      await refresh();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "重新索引失败",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (material: Material) => {
    if (
      !window.confirm(
        `删除资料《${material.title}》？分块和索引会一起删除，且不可恢复。`,
      )
    ) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await deleteMaterial(material.id);
      if (expandedId === material.id) {
        setExpandedId(null);
        setDetail(null);
      }
      setNotice({ kind: "success", text: `已删除：${material.title}` });
      await refresh();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "删除失败",
      });
    } finally {
      setBusy(false);
    }
  };

  const toggleDetail = async (material: Material) => {
    if (expandedId === material.id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(material.id);
    setDetail(null);
    try {
      setDetail(await fetchMaterial(material.id));
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "加载分块失败",
      });
    }
  };

  const runSearch = async (query?: string) => {
    const target = (query ?? searchQuery).trim();
    if (!target) return;
    setSearching(true);
    setNotice(null);
    try {
      setSearchResult(await searchMaterials(target));
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "搜索失败",
      });
    } finally {
      setSearching(false);
    }
  };

  const readyCount = materials.filter(
    (material) => material.status === "ready",
  ).length;
  const activeCount = materials.filter(
    (material) =>
      material.status === "pending" || material.status === "processing",
  ).length;
  const totalChunks = materials.reduce(
    (sum, material) => sum + material.chunk_count,
    0,
  );

  const treeBySubject = useMemo(() => {
    const groups: Record<string, KnowledgeNode[]> = {};
    for (const node of tree) {
      if (node.level > 2 && node.chunk_count === 0) continue;
      const key = node.subject || "未分类";
      (groups[key] ??= []).push(node);
    }
    return groups;
  }, [tree]);

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
          <div className="text-sm font-semibold">资料库</div>
          <div className="flex items-center gap-4 text-xs text-muted">
            <Link
              href="/knowledge"
              className="inline-flex items-center gap-1 font-medium text-ink"
            >
              <Sparkles className="h-3.5 w-3.5" />
              知识挖掘
            </Link>
            <Link href="/settings">设置</Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-6">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">资料库</h1>
            <p className="mt-1 text-sm text-muted">
              上传 PDF / Word / Markdown 或导入网页，系统会自动分块、打标签并建立检索索引。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Stat label="资料" value={materials.length} />
            <Stat label="已就绪" value={readyCount} />
            <Stat label="分块" value={totalChunks} />
            {activeCount > 0 && (
              <Stat label="处理中" value={activeCount} accent />
            )}
          </div>
        </div>

        {notice && <Notice kind={notice.kind} text={notice.text} />}

        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-5">
            <section className="rounded-2xl border border-line bg-paper p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">添加资料</h2>
                  <p className="mt-1 text-xs text-muted">
                    单个文件上限 200 MB（可在后端 .env 调整）；支持 PDF/Word/Markdown/图片，图片走 OCR。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleSeed()}
                  disabled={busy}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 py-1.5 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
                >
                  <Sparkles className="h-3.5 w-3.5 text-accent" />
                  导入示例资料
                </button>
              </div>

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={busy}
                className="mt-4 flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[#d8d0c4] bg-[#faf7f1] px-4 py-8 text-center transition hover:border-[#b5462f]/40 hover:bg-[#fbf4ef] disabled:opacity-60"
              >
                {busy ? (
                  <Loader2 className="h-5 w-5 animate-spin text-accent" />
                ) : (
                  <Upload className="h-5 w-5 text-accent" />
                )}
                <span className="text-sm font-medium">
                  点击上传 PDF / DOCX / TXT / Markdown / 图片
                </span>
                <span className="text-[11px] text-muted">
                  也可以一次选择多个文件
                </span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.mp3,.m4a,.wav,.aac,.flac,.ogg,.webm,.mp4"
                className="hidden"
                onChange={(event) => {
                  void handleFiles(event.target.files);
                  event.target.value = "";
                }}
              />

              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <div className="flex flex-1 items-center gap-2 rounded-xl border border-line bg-white px-3">
                  <Globe2 className="h-4 w-4 shrink-0 text-muted" />
                  <input
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder="导入网页 / B站 / YouTube 链接"
                    className="h-10 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#b3aa9c]"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => void handleUrl()}
                  disabled={busy || !url.trim()}
                  className="rounded-xl bg-ink px-4 py-2.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
                >
                  导入网页
                </button>
              </div>
            </section>

            <section className="rounded-2xl border border-line bg-paper p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-semibold">资料列表</h2>
                <span className="text-[10px] text-muted">
                  {materials.length} 份
                </span>
              </div>
              {loading ? (
                <div className="flex items-center gap-2 rounded-xl border border-dashed border-line px-3 py-4 text-xs text-muted">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  正在加载资料…
                </div>
              ) : materials.length === 0 ? (
                <div className="rounded-xl border border-dashed border-line px-3 py-5 text-xs leading-5 text-muted">
                  还没有资料。上传一份文件，或点上面的“导入示例资料”先跑一遍。
                </div>
              ) : (
                <div className="space-y-2">
                  {materials.map((material) => (
                    <MaterialRow
                      key={material.id}
                      material={material}
                      busy={busy}
                      expanded={expandedId === material.id}
                      detail={expandedId === material.id ? detail : null}
                      onToggle={() => void toggleDetail(material)}
                      onReindex={() => void handleReindex(material)}
                      onDelete={() => void handleDelete(material)}
                    />
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="space-y-5">
            <section className="rounded-2xl border border-line bg-paper p-5">
              <h2 className="text-base font-semibold">在资料库中搜索</h2>
              <p className="mt-1 text-xs text-muted">
                直接走 RAG 检索，结果带来源，可用于验证入库质量。
              </p>
              <div className="mt-3 flex gap-2">
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void runSearch();
                  }}
                  placeholder="例如：截位直除怎么用？"
                  className="h-10 min-w-0 flex-1 rounded-xl border border-line bg-white px-3 text-sm outline-none transition placeholder:text-[#b3aa9c] focus:border-[#cfc4b5]"
                />
                <button
                  type="button"
                  onClick={() => void runSearch()}
                  disabled={searching || !searchQuery.trim()}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-white transition hover:opacity-90 disabled:bg-[#d8d0c4]"
                  aria-label="搜索资料"
                >
                  {searching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </button>
              </div>
              {searchResult && <SearchResults result={searchResult} />}
            </section>

            <section className="rounded-2xl border border-line bg-paper p-5">
              <h2 className="text-base font-semibold">知识树</h2>
              <p className="mt-1 text-xs text-muted">
                行测 / 申论的知识点骨架；分块数会随着资料入库增长。
              </p>
              <div className="mt-3 space-y-3">
                {Object.entries(treeBySubject).map(([subject, nodes]) => (
                  <div key={subject}>
                    <div className="text-xs font-semibold text-ink">
                      {subject || "未分类"}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {nodes.map((node) => (
                        <button
                          key={node.id}
                          type="button"
                          onClick={() => {
                            setSearchQuery(node.name);
                            void runSearch(node.name);
                          }}
                          className={cn(
                            "rounded-full border border-line px-2 py-1 transition hover:border-[#cfc4b5]",
                            node.level >= 3
                              ? "bg-white text-[9px] text-muted"
                              : "bg-[#faf7f1] text-[10px] text-ink",
                          )}
                        >
                          {node.name} · {node.chunk_count}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-3 py-2",
        accent
          ? "border-[#f0d9a8] bg-[#fff4dd]"
          : "border-line bg-paper",
      )}
    >
      <div className="text-lg font-semibold leading-none text-ink">{value}</div>
      <div className="mt-1 text-[9px] uppercase tracking-[0.12em] text-muted">
        {label}
      </div>
    </div>
  );
}

function Notice({
  kind,
  text,
}: {
  kind: "success" | "error";
  text: string;
}) {
  return (
    <div
      className={cn(
        "mb-5 flex items-start gap-2 rounded-xl border px-4 py-3 text-sm",
        kind === "success"
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-red-200 bg-red-50 text-red-800",
      )}
    >
      {kind === "success" ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
      ) : (
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      )}
      <span>{text}</span>
    </div>
  );
}

function MaterialRow({
  material,
  busy,
  expanded,
  detail,
  onToggle,
  onReindex,
  onDelete,
}: {
  material: Material;
  busy: boolean;
  expanded: boolean;
  detail: MaterialDetail | null;
  onToggle: () => void;
  onReindex: () => void;
  onDelete: () => void;
}) {
  const meta = STATUS_META[material.status] ?? STATUS_META.pending;
  const Icon = meta.icon;
  const spinning =
    material.status === "processing" || material.status === "pending";

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-white">
      <div className="flex items-start gap-2 p-3">
        <button
          type="button"
          onClick={onToggle}
          className="flex min-w-0 flex-1 items-start gap-3 text-left"
        >
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#f2ead6] text-[#8a6a24]">
            {material.kind === "video" ? (
              <Video className="h-4 w-4" />
            ) : material.kind === "audio" ? (
              <AudioLines className="h-4 w-4" />
            ) : material.kind === "image" ? (
              <ImageIcon className="h-4 w-4" />
            ) : material.kind === "url" ? (
              <Globe2 className="h-4 w-4" />
            ) : (
              <FileText className="h-4 w-4" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-medium text-ink">
                {material.title || "未命名资料"}
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${meta.className}`}
              >
                <Icon
                  className={`h-3 w-3 ${spinning ? "animate-spin" : ""}`}
                />
                {meta.label}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-muted">
              <span>{kindLabel(material.kind)}</span>
              <span>·</span>
              <span>{material.chunk_count} 个分块</span>
              {material.subject && (
                <>
                  <span>·</span>
                  <span>{material.subject}</span>
                </>
              )}
              {material.module && (
                <>
                  <span>·</span>
                  <span>{material.module}</span>
                </>
              )}
              <span>·</span>
              <span>{formatRelative(material.created_at) || "刚刚"}</span>
              <span>·</span>
              <span>{formatSize(material.size_bytes)}</span>
            </div>
            {material.error && (
              <div className="mt-1 text-[11px] text-red-700">
                {material.error}
              </div>
            )}
          </div>
          {expanded ? (
            <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted" />
          ) : (
            <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted" />
          )}
        </button>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={onReindex}
            disabled={busy || material.status === "processing"}
            title="重新索引"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[#8a8475] transition hover:bg-[#f3efe7] disabled:opacity-40"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={busy}
            title="删除资料"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[#a33a2a] transition hover:bg-[#fbe9e7] disabled:opacity-40"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {expanded && <MaterialChunks detail={detail} />}
    </div>
  );
}

function MaterialChunks({ detail }: { detail: MaterialDetail | null }) {
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<MaterialChunk | null>(null);
  if (!detail) {
    return (
      <div className="flex items-center gap-2 border-t border-line bg-[#faf7f1] px-4 py-3 text-xs text-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        正在加载分块…
      </div>
    );
  }

  return (
    <div className="border-t border-line bg-[#faf7f1] px-4 py-3">
      <div className="mb-2 flex items-center justify-between text-[10px] text-muted">
        <span>分块预览</span>
        <span>{detail.chunks.length} 个</span>
      </div>
      <div className="space-y-2">
        {(showAll ? detail.chunks : detail.chunks.slice(0, 6)).map((chunk) => (
          <button
            key={chunk.id}
            type="button"
            onClick={() => setSelected(chunk)}
            className="w-full rounded-lg border border-line bg-white p-3 text-left transition hover:border-[#cfc4b5] hover:shadow-sm"
          >
            <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted">
              <span>#{chunk.chunk_index + 1}</span>
              {chunk.page && (
                <span>
                  {detail.material.kind === "video"
                    ? `幻灯片 ${chunk.page}`
                    : `第 ${chunk.page} 页`}
                </span>
              )}
              {chunk.time_start != null && (
                <span className="rounded-full bg-[#eef5f2] px-1.5 py-0.5 text-[#2f5d50]">
                  {formatVideoTime(chunk.time_start)}
                  {chunk.time_end != null
                    ? `–${formatVideoTime(chunk.time_end)}`
                    : ""}
                </span>
              )}
              <span className="rounded-full bg-[#f1ece2] px-1.5 py-0.5">
                {chunkTypeLabel(chunk.chunk_type)}
              </span>
              {chunk.knowledge_point_name && (
                <span className="rounded-full bg-[#e6edf5] px-1.5 py-0.5 text-[#3f5f7f]">
                  {chunk.knowledge_point_name}
                </span>
              )}
              {chunk.tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-[#f1ece2] px-1.5 py-0.5"
                >
                  {tag}
                </span>
              ))}
              {chunk.labels.length > 1 && (
                <span className="text-[9px] text-[#a59d90]">
                  +{chunk.labels.length - 1} 个候选标签
                </span>
              )}
            </div>
            <div className="mt-1 flex gap-3">
              {chunk.frame_url && (
                <img
                  src={`${API_BASE}${chunk.frame_url}`}
                  alt="视频关键帧"
                  loading="lazy"
                  className="h-16 w-28 shrink-0 rounded-md border border-line object-cover"
                />
              )}
              <div className="min-w-0 flex-1">
                {chunk.heading_path && (
                  <div className="text-[9px] text-[#a59d90]">
                    {chunk.heading_path}
                  </div>
                )}
                <p className="mt-1 line-clamp-3 text-[11px] leading-5 text-[#5f5a4d]">
                  {chunk.content}
                </p>
                <span className="mt-1 inline-block text-[9px] text-[#a59d90]">
                  点击查看全文
                </span>
              </div>
            </div>
          </button>
        ))}
      </div>
      {detail.chunks.length > 6 && (
        <button
          type="button"
          onClick={() => setShowAll((value) => !value)}
          className="mt-3 w-full rounded-lg border border-line bg-white px-3 py-2 text-[10px] font-medium text-[#6b6459] transition hover:border-[#cfc4b5]"
        >
          {showAll
            ? "收起分块"
            : `展开全部 ${detail.chunks.length} 个分块`}
        </button>
      )}
      {selected && (
        <ChunkDetailModal
          chunk={selected}
          material={detail.material}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function ChunkDetailModal({
  chunk,
  material,
  onClose,
}: {
  chunk: MaterialChunk;
  material: Material;
  onClose: () => void;
}) {
  const isVideo = material.kind === "video";
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 p-0 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label="分块详情"
    >
      <button
        type="button"
        aria-label="关闭"
        onClick={onClose}
        className="absolute inset-0 cursor-default"
      />
      <div className="relative z-10 max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-t-2xl border border-line bg-[#fdfbf7] p-5 shadow-2xl sm:rounded-2xl">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted">
              <span>#{chunk.chunk_index + 1}</span>
              {chunk.page && (
                <span>{isVideo ? `幻灯片 ${chunk.page}` : `第 ${chunk.page} 页`}</span>
              )}
              {chunk.time_start != null && (
                <span className="rounded-full bg-[#eef5f2] px-2 py-0.5 text-[#2f5d50]">
                  {formatVideoTime(chunk.time_start)}
                  {chunk.time_end != null
                    ? `–${formatVideoTime(chunk.time_end)}`
                    : ""}
                </span>
              )}
              <span className="rounded-full bg-[#f1ece2] px-2 py-0.5">
                {chunkTypeLabel(chunk.chunk_type)}
              </span>
            </div>
            <h2 className="mt-2 truncate font-serif text-lg font-semibold">
              {chunk.heading || material.title}
            </h2>
            <div className="mt-1 truncate text-[11px] text-muted">
              {chunk.heading_path || material.title}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭分块详情"
            className="rounded-lg border border-line bg-white p-1.5 text-[#6b6459]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,1fr)_220px]">
          <div className="min-w-0">
            <div className="whitespace-pre-wrap rounded-xl border border-[#ece6da] bg-white px-4 py-3 text-sm leading-7 text-[#3f3a32]">
              {chunk.content}
            </div>

            {chunk.labels.length > 0 && (
              <div className="mt-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8a8475]">
                  候选知识点
                </div>
                <div className="mt-2 space-y-2">
                  {chunk.labels.map((label) => (
                    <div
                      key={`${label.knowledge_point_id}-${label.score}`}
                      className="rounded-lg border border-[#ece6da] bg-white px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-ink">
                          {label.knowledge_point_name || "未命名知识点"}
                        </span>
                        <span className="text-[10px] text-muted">
                          {label.subject}
                          {label.module ? ` · ${label.module}` : ""}
                        </span>
                        <span className="ml-auto rounded-full bg-[#e6edf5] px-2 py-0.5 text-[10px] text-[#3f5f7f]">
                          置信度 {Math.round(label.confidence * 100)}%
                        </span>
                      </div>
                      {label.tags.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {label.tags.map((tag) => (
                            <span
                              key={tag}
                              className="rounded-full bg-[#f1ece2] px-2 py-0.5 text-[9px] text-[#6b6459]"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <aside className="space-y-3">
            {chunk.frame_url && (
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8a8475]">
                  关键帧
                </div>
                <img
                  src={`${API_BASE}${chunk.frame_url}`}
                  alt="视频关键帧"
                  className="mt-1.5 w-full rounded-lg border border-line object-cover"
                />
              </div>
            )}
            <div className="rounded-xl border border-[#ece6da] bg-white px-3 py-2.5 text-[11px] leading-6 text-[#5f5a4d]">
              <div className="flex justify-between gap-2">
                <span className="text-muted">资料</span>
                <span className="truncate text-right">{material.title}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-muted">知识点</span>
                <span className="truncate text-right">
                  {chunk.knowledge_point_name || "未归类"}
                </span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-muted">类型</span>
                <span>{chunkTypeLabel(chunk.chunk_type)}</span>
              </div>
              {chunk.tags.length > 0 && (
                <div className="mt-1 border-t border-[#f0ebe1] pt-1">
                  <div className="text-muted">标签</div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {chunk.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-[#f1ece2] px-2 py-0.5 text-[9px]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function SearchResults({ result }: { result: SearchResponse }) {
  return (
    <div className="mt-4 space-y-3">
      {result.cards.map((card) => (
        <div
          key={card.kp_id}
          className="rounded-xl border border-[#d9e4e0] bg-[#eef5f2] p-3"
        >
          <div className="flex items-center gap-2 text-xs font-medium text-[#2f5d50]">
            <Layers3 className="h-3.5 w-3.5" />
            {card.title}
          </div>
          <p className="mt-1 text-[11px] leading-5 text-[#3f5d54]">
            {card.summary}
          </p>
        </div>
      ))}

      {result.results.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line px-3 py-4 text-xs text-muted">
          没有找到结果。先导入示例资料或上传一份资料。
        </div>
      ) : (
        result.results.map((hit) => (
          <div
            key={hit.chunk_id}
            className="rounded-xl border border-line bg-[#faf7f1] p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted">
              <span className="font-medium text-ink">
                {hit.material_title}
              </span>
              <span>score {hit.score.toFixed(3)}</span>
            </div>
            <p className="mt-1 line-clamp-4 text-[11px] leading-5 text-[#5f5a4d]">
              {hit.content}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted">
              {hit.page && <span>第 {hit.page} 页</span>}
              {hit.time_start != null && (
                <span className="rounded-full bg-[#eef5f2] px-1.5 py-0.5 text-[#2f5d50]">
                  {formatVideoTime(hit.time_start)}
                  {hit.time_end != null
                    ? `–${formatVideoTime(hit.time_end)}`
                    : ""}
                </span>
              )}
              {hit.knowledge_point_name && (
                <span className="rounded-full bg-[#e6edf5] px-1.5 py-0.5 text-[#3f5f7f]">
                  {hit.knowledge_point_name}
                </span>
              )}
              <span>《{hit.material_title}》</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function formatVideoTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return hours
    ? `${hours}:${pad(minutes)}:${pad(secs)}`
    : `${pad(minutes)}:${pad(secs)}`;
}

function chunkTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    method: "方法",
    formula: "公式",
    definition: "定义",
    trap: "易错",
    example: "例题",
    question: "题目",
    summary: "概述",
  };
  return labels[type] ?? "概述";
}

function kindLabel(kind: string): string {
  if (kind === "url") return "网页";
  if (kind === "sample") return "示例";
  if (kind === "image") return "图片";
  if (kind === "video") return "视频";
  if (kind === "audio") return "音频";
  return "文件";
}

function formatSize(bytes: number): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
