"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Save,
  ShieldCheck,
  UserRound,
  Wifi,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ROLE_OPTIONS } from "@/lib/agents";
import { fetchSettings, saveSettings, testLlm } from "@/lib/api";
import type { SettingsBundle, SettingsPayload } from "@/lib/types";
import { normalizeUserId, setUserId, useUserId } from "@/lib/user";

const emptyRoles = Object.fromEntries(
  ROLE_OPTIONS.map((role) => [role.key, { model: "", temperature: 0.3 }]),
) as SettingsPayload["llm"]["roles"];

const fieldClass =
  "w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm text-ink outline-none transition placeholder:text-[#b3aa9c] focus:border-[#cfc4b5] focus:ring-2 focus:ring-[#efe7da]";

export default function SettingsPage() {
  const userId = useUserId();
  const [bundle, setBundle] = useState<SettingsBundle | null>(null);
  const [llm, setLlm] = useState<SettingsPayload["llm"]>({
    api_base: "",
    api_key: "",
    default_model: "",
    embedding_model: "",
    asr_model: "",
    input_price_per_m: 0,
    output_price_per_m: 0,
    roles: emptyRoles,
  });
  const [profile, setProfile] = useState<SettingsPayload["profile"]>({
    name: "同学",
    target_exam: "国考",
    exam_date: "",
    daily_minutes: 120,
  });
  const [userIdDraft, setUserIdDraft] = useState(userId);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const applyBundle = useCallback((data: SettingsBundle) => {
    setBundle(data);
    setLlm({
      api_base: data.llm.api_base,
      api_key: "",
      default_model: data.llm.default_model,
      embedding_model: data.llm.embedding_model,
      asr_model: data.llm.asr_model ?? "",
      input_price_per_m: data.llm.input_price_per_m ?? 0,
      output_price_per_m: data.llm.output_price_per_m ?? 0,
      roles: { ...emptyRoles, ...data.llm.roles },
    });
    setProfile(data.profile);
  }, []);

  useEffect(() => {
    fetchSettings(userId)
      .then(applyBundle)
      .catch((error) =>
        setLoadError(error instanceof Error ? error.message : "加载设置失败"),
      )
      .finally(() => setLoading(false));
  }, [applyBundle, userId]);

  useEffect(() => {
    setUserIdDraft(userId);
  }, [userId]);

  const handleSwitchUser = async () => {
    const nextId = normalizeUserId(userIdDraft);
    setNotice(null);
    try {
      setUserId(nextId);
      const data = await fetchSettings(nextId);
      applyBundle(data);
      setNotice({
        kind: "success",
        text:
          nextId === "local-user"
            ? "已切换到默认学习者。"
            : `已切换到学习者 ${nextId}，资料库共享，学情和计划独立。`,
      });
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "切换学习者失败",
      });
    }
  };

  const updateRole = (key: string, model: string) => {
    setLlm((prev) => ({
      ...prev,
      roles: {
        ...prev.roles,
        [key]: {
          ...(prev.roles[key] ?? { temperature: 0.3 }),
          model,
        },
      },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const result = await saveSettings({ llm, profile }, userId);
      setBundle(result);
      setLlm((prev) => ({ ...prev, api_key: "" }));
      setNotice({ kind: "success", text: "已保存。回到对话页即可使用。" });
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "保存失败",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setNotice(null);
    try {
      const result = await testLlm(llm);
      if (result.ok) {
        setNotice({
          kind: "success",
          text: `连接成功 · ${result.model ?? "模型"} · ${result.latency_ms ?? 0} ms`,
        });
      } else {
        setNotice({ kind: "error", text: result.error ?? "连接失败" });
      }
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "测试失败",
      });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-dvh items-center justify-center bg-[var(--background)] text-sm text-muted">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在读取设置…
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-[var(--background)] text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-[#f7f4ee]/90 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-4xl items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-medium text-ink"
          >
            <ArrowLeft className="h-4 w-4" />
            返回对话
          </Link>
          <div className="text-sm font-semibold">设置</div>
          <div className="w-20" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
        <div className="mb-7">
          <h1 className="text-2xl font-semibold tracking-tight">
            把私塾配成你的样子
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            学习档案会影响督导老师的判断；LLM 配置决定每位老师用哪个模型、连哪个
            API。
          </p>
        </div>

        {loadError && (
          <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {loadError}
          </div>
        )}

        {notice && (
          <div
            className={`mb-5 flex items-start gap-2 rounded-xl border px-4 py-3 text-sm ${
              notice.kind === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-red-800"
            }`}
          >
            {notice.kind === "success" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
            )}
            <span>{notice.text}</span>
          </div>
        )}

        <div className="space-y-5">
          <section className="rounded-2xl border border-line bg-paper p-5 sm:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">当前学习者</h2>
                <p className="mt-1 text-xs text-muted">
                  本地多用户：资料库共享，做题记录、掌握度和计划按学习者隔离。
                </p>
              </div>
              <span className="rounded-full bg-[#f1ece2] px-2.5 py-1 text-[10px] text-muted">
                {userId}
              </span>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="block flex-1">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  学习者 ID
                </span>
                <input
                  className={fieldClass}
                  value={userIdDraft}
                  onChange={(event) => setUserIdDraft(event.target.value)}
                  placeholder="local-user 或 alice"
                />
                <span className="mt-1 block text-[10px] text-muted">
                  只能使用小写字母、数字、短横线；输入新 ID 即创建新学习者。
                </span>
              </label>
              <button
                type="button"
                onClick={() => void handleSwitchUser()}
                disabled={normalizeUserId(userIdDraft) === userId}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-line bg-white px-4 py-2.5 text-xs font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-50"
              >
                <UserRound className="h-3.5 w-3.5" />
                切换学习者
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-line bg-paper p-5 sm:p-6">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">学习档案</h2>
                <p className="mt-1 text-xs text-muted">
                  让辅导员和督导老师知道你的目标与时间。
                </p>
              </div>
              <span className="rounded-full bg-[#f1ece2] px-2.5 py-1 text-[10px] text-muted">
                P0
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  怎么称呼你
                </span>
                <input
                  className={fieldClass}
                  value={profile.name}
                  onChange={(event) =>
                    setProfile({ ...profile, name: event.target.value })
                  }
                  placeholder="同学"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  目标考试
                </span>
                <select
                  className={fieldClass}
                  value={profile.target_exam}
                  onChange={(event) =>
                    setProfile({ ...profile, target_exam: event.target.value })
                  }
                >
                  <option value="国考">国考</option>
                  <option value="省考">省考</option>
                  <option value="事业单位">事业单位</option>
                  <option value="选调生">选调生</option>
                  <option value="其他">其他</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  考试日期
                </span>
                <input
                  type="date"
                  className={fieldClass}
                  value={profile.exam_date}
                  onChange={(event) =>
                    setProfile({ ...profile, exam_date: event.target.value })
                  }
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  每天可用时间（分钟）
                </span>
                <input
                  type="number"
                  min={15}
                  max={720}
                  step={15}
                  className={fieldClass}
                  value={profile.daily_minutes}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      daily_minutes: Number(event.target.value) || 0,
                    })
                  }
                />
              </label>
            </div>
          </section>

          <section className="rounded-2xl border border-line bg-paper p-5 sm:p-6">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">LLM 接入</h2>
                <p className="mt-1 text-xs text-muted">
                  支持任意 OpenAI 兼容 API，也可以填 LiteLLM 的供应商前缀。
                </p>
              </div>
              <span className="rounded-full bg-accent-soft px-2.5 py-1 text-[10px] font-medium text-accent">
                按角色分配
              </span>
            </div>

            {bundle?.server.mock_mode && (
              <div className="mb-4 rounded-xl border border-[#d9e4e0] bg-[#eef5f2] px-3 py-2.5 text-[11px] leading-5 text-[#2f5d50]">
                当前后端以 MOCK_LLM=1 启动，对话使用本地演示模型。这里保存的模型配置会在关闭演示模式后生效。
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  Base URL
                </span>
                <input
                  className={fieldClass}
                  value={llm.api_base}
                  onChange={(event) =>
                    setLlm({ ...llm, api_base: event.target.value })
                  }
                  placeholder="https://api.openai.com/v1 或你的兼容端点"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  API Key
                </span>
                <input
                  type="password"
                  className={fieldClass}
                  value={llm.api_key}
                  onChange={(event) =>
                    setLlm({ ...llm, api_key: event.target.value })
                  }
                  placeholder={
                    bundle?.llm.api_key_set
                      ? "已配置，留空保持不变"
                      : "sk-..."
                  }
                  autoComplete="off"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  默认模型
                </span>
                <input
                  className={fieldClass}
                  value={llm.default_model}
                  onChange={(event) =>
                    setLlm({ ...llm, default_model: event.target.value })
                  }
                  placeholder="gpt-4o-mini / deepseek/deepseek-chat"
                />
              </label>
            </div>

            <label className="mt-4 block">
              <span className="mb-1.5 block text-xs font-medium text-ink">
                Embedding 模型（可选）
              </span>
              <input
                className={fieldClass}
                value={llm.embedding_model}
                onChange={(event) =>
                  setLlm({ ...llm, embedding_model: event.target.value })
                }
                placeholder="留空使用本地哈希向量；可填 text-embedding-3-small / bge-m3"
              />
              <span className="mt-1 block text-[10px] leading-4 text-muted">
                留空 = 本地哈希向量（演示，无需 Key）；填写后复用上面的 Base URL /
                API Key 调用 Embedding API。更换模型后请到资料库重新索引。
              </span>
            </label>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  语音转写模型（可选）
                </span>
                <input
                  className={fieldClass}
                  value={llm.asr_model}
                  onChange={(event) =>
                    setLlm({ ...llm, asr_model: event.target.value })
                  }
                  placeholder="whisper-1 / FunAudioLLM/SenseVoiceSmall"
                />
                <span className="mt-1 block text-[10px] leading-4 text-muted">
                  复用上面的 Base URL / API Key，调用 /audio/transcriptions；
                  留空时如果有 faster-whisper 会退回本地转写。
                </span>
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink">
                    输入价 / 百万 token
                  </span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    className={fieldClass}
                    value={llm.input_price_per_m}
                    onChange={(event) =>
                      setLlm({
                        ...llm,
                        input_price_per_m: Number(event.target.value) || 0,
                      })
                    }
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink">
                    输出价 / 百万 token
                  </span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    className={fieldClass}
                    value={llm.output_price_per_m}
                    onChange={(event) =>
                      setLlm({
                        ...llm,
                        output_price_per_m: Number(event.target.value) || 0,
                      })
                    }
                  />
                </label>
                <span className="text-[10px] leading-4 text-muted sm:col-span-2">
                  用于看板的成本估算；填 0 时只统计 token，不计算金额。
                </span>
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-line bg-[#faf7f1] p-4">
              <div className="mb-3 text-xs font-medium text-ink">
                角色模型覆盖
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {ROLE_OPTIONS.map((role) => (
                  <label key={role.key} className="block">
                    <span className="mb-1 flex items-center justify-between gap-2 text-[11px] text-muted">
                      <span className="font-medium text-ink">{role.label}</span>
                      <span>{role.hint}</span>
                    </span>
                    <input
                      className={fieldClass}
                      value={llm.roles[role.key]?.model ?? ""}
                      onChange={(event) =>
                        updateRole(role.key, event.target.value)
                      }
                      placeholder="留空则使用默认模型"
                    />
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-4 flex items-start gap-2 rounded-xl bg-[#f1ece2] px-3 py-2.5 text-[11px] leading-5 text-[#6f685b]">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              API Key 会加密存储在本地数据库；接口只返回脱敏值。留空表示不修改已有
              Key。
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void handleTest()}
                disabled={testing || saving}
                className="inline-flex items-center gap-2 rounded-xl border border-line bg-white px-4 py-2.5 text-xs font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
              >
                {testing ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Wifi className="h-3.5 w-3.5" />
                )}
                测试连接
              </button>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving || testing}
                className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-60"
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5" />
                )}
                保存设置
              </button>
              {bundle?.server.mock_mode && (
                <span className="rounded-full bg-[#e1efe8] px-2.5 py-1 text-[10px] font-medium text-[#2f5d50]">
                  当前：本地演示模式
                </span>
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-line bg-paper p-5 text-xs text-muted sm:p-6">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <span>数据库：{bundle?.server.database ?? "unknown"}</span>
              <span>版本：{bundle?.server.app_version ?? "0.1.0"}</span>
              <span>
                LLM：{bundle?.server.llm_configured ? "已配置" : "未配置"}
              </span>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
