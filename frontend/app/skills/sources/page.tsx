"use client";

import {
  ArrowLeft,
  Boxes,
  CheckCircle2,
  Download,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { fetchSkillSources, importSkillPack } from "@/lib/api";
import type { SkillSourcesResponse } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

export default function SkillSourcesPage() {
  const [data, setData] = useState<SkillSourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [repo, setRepo] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await fetchSkillSources());
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "加载技能来源失败",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runImport = async (
    key: string,
    payload: { repo?: string; useBuiltin?: boolean },
  ) => {
    setBusy(key);
    setNotice(null);
    try {
      const result = await importSkillPack(payload);
      setNotice({
        kind: "success",
        text: `导入完成：新增 ${result.created} 项，共 ${result.total} 项。`,
      });
      await load();
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "导入失败",
      });
    } finally {
      setBusy("");
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f4ee] text-ink">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <Link
          href="/skills"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#8a8475] hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回技能地图
        </Link>
        <h1 className="mt-3 flex items-center gap-2 font-serif text-2xl font-semibold">
          <Boxes className="h-5 w-5 text-[#b08244]" />
          技能来源
        </h1>
        <p className="mt-1.5 max-w-2xl text-xs leading-5 text-[#6b6459]">
          技能地图里的每一项都有来源。可以装内置花生十三体系，也可以从任意同结构的 git 仓库导入。
          导入会整体替换该来源下的技能，对话中手动新增的技能不受影响。
        </p>

        {notice && (
          <div
            className={cn(
              "mt-4 flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-xs leading-5",
              notice.kind === "success"
                ? "border-[#c8ded4] bg-[#eef7f2] text-[#2f5d50]"
                : "border-[#ecc9c2] bg-[#fbe9e7] text-[#a33a2a]",
            )}
          >
            <span>{notice.text}</span>
            <button
              type="button"
              onClick={() => setNotice(null)}
              aria-label="关闭提示"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {loading ? (
          <div className="mt-10 flex items-center justify-center gap-2 text-xs text-[#8a8475]">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载
          </div>
        ) : (
          <>
            <section className="mt-6">
              <h2 className="text-sm font-semibold">已安装</h2>
              <div className="mt-3 space-y-2">
                {(data?.sources ?? []).length === 0 && (
                  <div className="rounded-xl border border-dashed border-[#d8d0c4] bg-white/50 px-4 py-8 text-center text-xs text-[#8a8475]">
                    还没有任何技能。
                  </div>
                )}
                {(data?.sources ?? []).map((source) => (
                  <div
                    key={source.source}
                    className="rounded-xl border border-[#e5ded1] bg-white/85 px-4 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-[#2f5d50]" />
                      <span className="text-sm font-medium">{source.label}</span>
                      <span className="rounded-full bg-[#f1ece2] px-2 py-0.5 text-[10px] text-[#6b6459]">
                        {source.count} 项
                      </span>
                      {source.file_count > 0 && (
                        <span className="text-[10px] text-[#8a8475]">
                          {source.file_count} 个来源文件
                        </span>
                      )}
                      <span className="ml-auto text-[10px] text-[#a59d90]">
                        {source.last_updated
                          ? formatRelative(source.last_updated)
                          : "—"}
                      </span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {source.modules.map((module) => (
                        <span
                          key={module}
                          className="rounded-full bg-[#e6edf5] px-2 py-0.5 text-[10px] text-[#3f5f7f]"
                        >
                          {module}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-6">
              <h2 className="text-sm font-semibold">可安装的技能包</h2>
              <div className="mt-3 space-y-2">
                {(data?.packs ?? []).map((pack) => (
                  <div
                    key={pack.key}
                    className="rounded-xl border border-[#e5ded1] bg-white/85 px-4 py-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium">
                            {pack.label}
                          </span>
                          {pack.builtin && (
                            <span className="rounded-full bg-[#e1efe8] px-2 py-0.5 text-[10px] text-[#2f5d50]">
                              内置
                            </span>
                          )}
                          {pack.installed && (
                            <span className="text-[10px] text-[#2f5d50]">
                              已安装
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-[11px] leading-5 text-[#6b6459]">
                          {pack.description}
                        </p>
                        <a
                          href={pack.repo}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-block truncate text-[10px] text-[#a59d90] hover:underline"
                        >
                          {pack.repo}
                        </a>
                      </div>
                      <button
                        type="button"
                        disabled={busy === pack.key}
                        onClick={() =>
                          void runImport(pack.key, {
                            useBuiltin: pack.builtin,
                            repo: pack.builtin ? undefined : pack.repo,
                          })
                        }
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-[11px] font-medium text-white disabled:opacity-40"
                      >
                        {busy === pack.key ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                        {pack.installed ? "重新导入" : "安装"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-6 rounded-xl border border-[#e5ded1] bg-white/85 px-4 py-4">
              <h2 className="text-sm font-semibold">从 Git 仓库导入</h2>
              <p className="mt-1 text-[11px] leading-5 text-[#6b6459]">
                仓库需要包含 references/ 目录，每个 .md 文件对应一个模块，
                用「题型 N：xxx」「方法 N：xxx」这类小节拆分技能。
              </p>
              <div className="mt-3 flex gap-2">
                <input
                  value={repo}
                  onChange={(event) => setRepo(event.target.value)}
                  placeholder="https://github.com/owner/skill-repo"
                  className="h-9 min-w-0 flex-1 rounded-lg border border-[#d8d0c4] bg-white px-2.5 text-xs outline-none focus:border-ink"
                />
                <button
                  type="button"
                  disabled={busy === "custom" || !repo.trim()}
                  onClick={() =>
                    void runImport("custom", { repo: repo.trim() })
                  }
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[#d8d0c4] bg-white px-3 text-xs font-medium disabled:opacity-40"
                >
                  {busy === "custom" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  导入
                </button>
              </div>
            </section>

            <p className="mt-4 text-[10px] leading-5 text-[#a59d90]">
              问答老师在答疑时每次都从技能表现查，导入完成后不需要重启服务。
            </p>
          </>
        )}
      </div>
    </main>
  );
}
