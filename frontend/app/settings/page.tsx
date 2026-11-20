"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Copy,
  Loader2,
  QrCode,
  RefreshCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  Wifi,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ROLE_OPTIONS } from "@/lib/agents";
import {
  connectQrUrl,
  fetchConnectInfo,
  fetchModels,
  fetchSettings,
  saveSettings,
  testLlm,
} from "@/lib/api";
import type {
  ConnectInfo,
  RoleModelConfig,
  SettingsBundle,
  SettingsPayload,
} from "@/lib/types";
import { normalizeUserId, setUserId, useUserId } from "@/lib/user";

const emptyRole: RoleModelConfig = {
  model: "",
  temperature: 0.3,
  max_tokens: 0,
  top_p: 0,
  api_base: "",
  api_key: "",
};

const emptyRoles = Object.fromEntries(
  ROLE_OPTIONS.map((role) => [role.key, { ...emptyRole }]),
) as SettingsPayload["llm"]["roles"];

const PROVIDER_PRESETS = [
  {
    label: "OpenDesign / AMR",
    base: "https://amr-link.open-design.ai/v1",
  },
  { label: "OpenAI", base: "https://api.openai.com/v1" },
  { label: "DeepSeek", base: "https://api.deepseek.com/v1" },
  {
    label: "硅基流动 SiliconFlow",
    base: "https://api.siliconflow.cn/v1",
  },
  { label: "Moonshot Kimi", base: "https://api.moonshot.cn/v1" },
  {
    label: "智谱 GLM",
    base: "https://open.bigmodel.cn/api/paas/v4",
  },
  {
    label: "通义千问 DashScope",
    base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  },
  { label: "OpenRouter", base: "https://openrouter.ai/api/v1" },
  { label: "Ollama 本地", base: "http://localhost:11434/v1" },
  { label: "LM Studio 本地", base: "http://localhost:1234/v1" },
];

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
    embedding_api_base: "",
    embedding_api_key: "",
    asr_model: "",
    asr_api_base: "",
    asr_api_key: "",
    deepseek_api_base: "",
    deepseek_api_key: "",
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
  const [expandedRoles, setExpandedRoles] = useState<Record<string, boolean>>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testingRole, setTestingRole] = useState<string | null>(null);
  const [modelOptions, setModelOptions] = useState<Record<string, string[]>>(
    {},
  );
  const [modelLoading, setModelLoading] = useState<string | null>(null);
  const [modelNotice, setModelNotice] = useState<string | null>(null);
  const [connectInfo, setConnectInfo] = useState<ConnectInfo | null>(null);
  const [copied, setCopied] = useState(false);
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
      embedding_api_base: data.llm.embedding_api_base ?? "",
      embedding_api_key: "",
      asr_model: data.llm.asr_model ?? "",
      asr_api_base: data.llm.asr_api_base ?? "",
      asr_api_key: "",
      deepseek_api_base: data.llm.deepseek_api_base ?? "",
      deepseek_api_key: "",
      input_price_per_m: data.llm.input_price_per_m ?? 0,
      output_price_per_m: data.llm.output_price_per_m ?? 0,
      roles: Object.fromEntries(
        ROLE_OPTIONS.map((role) => [
          role.key,
          {
            ...emptyRole,
            ...(data.llm.roles[role.key] ?? {}),
            api_key: "",
            clear_api_key: false,
          },
        ]),
      ),
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

  useEffect(() => {
    fetchConnectInfo()
      .then(setConnectInfo)
      .catch(() => {
        // The QR card falls back to the current API base.
      });
  }, []);

  const copyConnectUrl = async () => {
    if (!connectInfo) return;
    try {
      await navigator.clipboard.writeText(connectInfo.api_base);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

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

  const updateRole = (key: string, patch: Partial<RoleModelConfig>) => {
    setLlm((prev) => ({
      ...prev,
      roles: {
        ...prev.roles,
        [key]: {
          ...(prev.roles[key] ?? emptyRole),
          ...patch,
        },
      },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const result = await saveSettings({ llm, profile }, userId);
      applyBundle(result);
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

  const handleTest = async (role?: string) => {
    setTesting(true);
    if (role) setTestingRole(role);
    setNotice(null);
    const who = role
      ? ROLE_OPTIONS.find((item) => item.key === role)?.label ?? role
      : "全局默认";
    try {
      const result = await testLlm(llm, role);
      if (result.ok) {
        setNotice({
          kind: "success",
          text: `${who}连接成功 · ${result.model ?? "模型"} · ${result.latency_ms ?? 0} ms`,
        });
      } else {
        setNotice({ kind: "error", text: `${who}：${result.error ?? "连接失败"}` });
      }
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "测试失败",
      });
    } finally {
      setTesting(false);
      setTestingRole(null);
    }
  };

  const handleFetchModels = async (
    scope: string,
    payload: { api_base?: string; api_key?: string; role?: string },
  ) => {
    setModelLoading(scope);
    setModelNotice(null);
    try {
      const result = await fetchModels(payload);
      setModelOptions((prev) => ({
        ...prev,
        [scope]: result.models.map((item) => item.id),
      }));
      setModelNotice(
        `已从 ${result.base_url} 获取 ${result.count} 个模型，可在模型输入框下拉选择。`,
      );
    } catch (error) {
      setModelNotice(
        error instanceof Error ? error.message : "获取模型列表失败",
      );
    } finally {
      setModelLoading(null);
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
            <div className="mb-5 flex items-start justify-between gap-3">
              <div>
                <h2 className="flex items-center gap-2 text-base font-semibold">
                  <QrCode className="h-4 w-4 text-accent" />
                  用 iPad / iPhone 扫码连接
                </h2>
                <p className="mt-1 text-xs text-muted">
                  不用在平板上手输 IP。扫码后会打开 App 并自动填好后端地址。
                </p>
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-[200px_1fr] sm:items-start">
              <div className="w-fit rounded-2xl border border-line bg-white p-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={connectQrUrl(connectInfo?.api_base)}
                  alt="扫码连接考公私塾后端"
                  className="h-44 w-44"
                />
              </div>

              <div className="min-w-0 text-xs leading-5 text-muted">
                <div className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#8a8475]">
                  当前连接地址
                  {connectInfo?.source === "public" && (
                    <span className="ml-2 rounded-full bg-[#e1efe8] px-1.5 py-0.5 text-[9px] normal-case tracking-normal text-[#2f5d50]">
                      PUBLIC_BASE_URL
                    </span>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <code className="min-w-0 flex-1 truncate rounded-lg border border-line bg-[#faf7f1] px-3 py-2 text-[11px] text-ink">
                    {connectInfo?.api_base ?? "正在获取 Mac 的局域网地址…"}
                  </code>
                  <button
                    type="button"
                    onClick={() => void copyConnectUrl()}
                    disabled={!connectInfo}
                    className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-line bg-white px-2.5 py-2 text-[10px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-50"
                  >
                    <Copy className="h-3 w-3" />
                    {copied ? "已复制" : "复制"}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void fetchConnectInfo().then(setConnectInfo)
                    }
                    title="刷新局域网地址"
                    className="inline-flex shrink-0 items-center justify-center rounded-lg border border-line bg-white p-2 text-ink transition hover:border-[#cfc4b5]"
                  >
                    <RefreshCw className="h-3 w-3" />
                  </button>
                </div>

                <ol className="mt-3 list-decimal space-y-1 pl-4">
                  <li>
                    {connectInfo?.source === "public"
                      ? "当前二维码使用 PUBLIC_BASE_URL；iPad 需要能访问这个地址，例如已登录同一个 Tailscale，或通过 Cloudflare Access。"
                      : "Mac 与 iPad 连接同一个 Wi-Fi，不要用访客网络。"}
                  </li>
                  <li>
                    {connectInfo?.source === "public"
                      ? "Tailscale / 反向代理需先把该域名转发到本机 8000 端口。"
                      : "后端用 make backend-lan 启动（监听 0.0.0.0），否则平板无法访问。"}
                  </li>
                  <li>
                    iPad 打开 App → 设置 → 扫码连接；也可以直接用系统相机扫码。
                  </li>
                  <li>
                    仍连不上时，检查 macOS 防火墙是否允许 Python/uvicorn
                    接受传入连接。
                  </li>
                </ol>

                {connectInfo && connectInfo.ips.length > 1 && (
                  <div className="mt-2 text-[10px] text-[#a59d90]">
                    检测到的地址：{connectInfo.ips.join(" · ")}
                  </div>
                )}
              </div>
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

            {modelNotice && (
              <div className="mb-4 rounded-xl border border-[#f0d9a8] bg-[#fffaf0] px-3 py-2.5 text-[11px] leading-5 text-[#8a6a24]">
                {modelNotice}
              </div>
            )}

            <label className="mb-4 block">
              <span className="mb-1.5 block text-xs font-medium text-ink">
                平台预设
              </span>
              <select
                className={fieldClass}
                value={
                  PROVIDER_PRESETS.find(
                    (item) => item.base === llm.api_base,
                  )?.base ?? ""
                }
                onChange={(event) => {
                  if (event.target.value) {
                    setLlm({ ...llm, api_base: event.target.value });
                  }
                }}
              >
                <option value="">自定义 / 已填写</option>
                {PROVIDER_PRESETS.map((item) => (
                  <option key={item.label} value={item.base}>
                    {item.label}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-[10px] leading-4 text-muted">
                选择后会填入默认 Base URL；也可以用下面的输入框填写任意
                OpenAI 兼容端点。
              </span>
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  默认 Base URL
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
                  默认 API Key
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
              <div className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  默认模型
                </span>
                <div className="flex gap-2">
                  <input
                    list="models-global"
                    className={fieldClass}
                    value={llm.default_model}
                    onChange={(event) =>
                      setLlm({ ...llm, default_model: event.target.value })
                    }
                    placeholder="gpt-4o-mini / deepseek-chat"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      void handleFetchModels("global", {
                        api_base: llm.api_base,
                        api_key: llm.api_key,
                      })
                    }
                    disabled={modelLoading === "global"}
                    title="从当前 Base URL 获取模型列表"
                    className="inline-flex shrink-0 items-center gap-1 rounded-xl border border-line bg-white px-3 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
                  >
                    {modelLoading === "global" ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                    获取
                  </button>
                </div>
                <datalist id="models-global">
                  {(modelOptions.global ?? []).map((model) => (
                    <option key={model} value={model} />
                  ))}
                </datalist>
              </div>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="block sm:col-span-2">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  Embedding 模型（可选）
                </span>
                <div className="flex gap-2">
                  <input
                    list="models-embedding"
                    className={fieldClass}
                    value={llm.embedding_model}
                    onChange={(event) =>
                      setLlm({ ...llm, embedding_model: event.target.value })
                    }
                    placeholder="留空使用本地哈希向量；可填 text-embedding-3-small / bge-m3"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      void handleFetchModels("embedding", {
                        api_base: llm.embedding_api_base || llm.api_base,
                        api_key: llm.embedding_api_key,
                      })
                    }
                    disabled={modelLoading === "embedding"}
                    title="获取模型列表"
                    className="inline-flex shrink-0 items-center gap-1 rounded-xl border border-line bg-white px-3 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
                  >
                    {modelLoading === "embedding" ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                    获取
                  </button>
                </div>
                <datalist id="models-embedding">
                  {(modelOptions.embedding ?? []).map((model) => (
                    <option key={model} value={model} />
                  ))}
                </datalist>
              </div>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  Embedding Base URL（可选）
                </span>
                <input
                  className={fieldClass}
                  value={llm.embedding_api_base}
                  onChange={(event) =>
                    setLlm({ ...llm, embedding_api_base: event.target.value })
                  }
                  placeholder="留空沿用默认 Base URL"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  Embedding API Key（可选）
                </span>
                <input
                  type="password"
                  className={fieldClass}
                  value={llm.embedding_api_key}
                  onChange={(event) =>
                    setLlm({ ...llm, embedding_api_key: event.target.value })
                  }
                  placeholder={
                    bundle?.llm.embedding_api_key_set
                      ? "已配置，留空保持不变"
                      : "留空沿用默认 API Key"
                  }
                  autoComplete="off"
                />
              </label>
              <span className="text-[10px] leading-4 text-muted sm:col-span-2">
                留空 = 本地哈希向量（演示，无需 Key）；填写模型后可用独立端点与 Key
                调用 Embedding API。更换模型后请到资料库重新索引。
              </span>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="block sm:col-span-2">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  语音转写模型（可选）
                </span>
                <div className="flex gap-2">
                  <input
                    list="models-asr"
                    className={fieldClass}
                    value={llm.asr_model}
                    onChange={(event) =>
                      setLlm({ ...llm, asr_model: event.target.value })
                    }
                    placeholder="whisper-1 / FunAudioLLM/SenseVoiceSmall"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      void handleFetchModels("asr", {
                        api_base: llm.asr_api_base || llm.api_base,
                        api_key: llm.asr_api_key,
                      })
                    }
                    disabled={modelLoading === "asr"}
                    title="获取模型列表"
                    className="inline-flex shrink-0 items-center gap-1 rounded-xl border border-line bg-white px-3 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
                  >
                    {modelLoading === "asr" ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                    获取
                  </button>
                </div>
                <datalist id="models-asr">
                  {(modelOptions.asr ?? []).map((model) => (
                    <option key={model} value={model} />
                  ))}
                </datalist>
              </div>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  语音转写 Base URL（可选）
                </span>
                <input
                  className={fieldClass}
                  value={llm.asr_api_base}
                  onChange={(event) =>
                    setLlm({ ...llm, asr_api_base: event.target.value })
                  }
                  placeholder="留空沿用默认 Base URL"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink">
                  语音转写 API Key（可选）
                </span>
                <input
                  type="password"
                  className={fieldClass}
                  value={llm.asr_api_key}
                  onChange={(event) =>
                    setLlm({ ...llm, asr_api_key: event.target.value })
                  }
                  placeholder={
                    bundle?.llm.asr_api_key_set
                      ? "已配置，留空保持不变"
                      : "留空沿用默认 API Key"
                  }
                  autoComplete="off"
                />
              </label>
              <span className="text-[10px] leading-4 text-muted sm:col-span-2">
                复用独立端点调用 /audio/transcriptions；留空时如果有
                faster-whisper 会退回本地转写。
              </span>
            </div>

            <div className="mt-4 rounded-xl border border-line bg-[#faf7f1] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-medium text-ink">
                  DeepSeek 官方能力（可选）
                </span>
                {bundle?.llm.deepseek_api_key_set && (
                  <span className="rounded-full bg-[#e1efe8] px-2 py-0.5 text-[10px] font-medium text-[#2f5d50]">
                    已启用
                  </span>
                )}
              </div>
              <p className="mt-1 text-[10px] leading-4 text-muted">
                只用于联网搜索、网页抓取、扫描 PDF OCR 和短音频转写，不影响上面的聊天模型。
                官方地址是 https://api.deepseek.com，接口为 /v1/tools/*。
              </p>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink">
                    DeepSeek Base URL
                  </span>
                  <input
                    className={fieldClass}
                    value={llm.deepseek_api_base}
                    onChange={(event) =>
                      setLlm({
                        ...llm,
                        deepseek_api_base: event.target.value,
                      })
                    }
                    placeholder="https://api.deepseek.com"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink">
                    DeepSeek API Key
                  </span>
                  <input
                    type="password"
                    className={fieldClass}
                    value={llm.deepseek_api_key}
                    onChange={(event) =>
                      setLlm({ ...llm, deepseek_api_key: event.target.value })
                    }
                    placeholder={
                      bundle?.llm.deepseek_api_key_set
                        ? "已配置，留空保持不变"
                        : "sk-..."
                    }
                    autoComplete="off"
                  />
                </label>
              </div>
            </div>

            <div className="mt-4 grid gap-3 rounded-xl border border-line bg-[#faf7f1] p-4 sm:grid-cols-2">
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

            <div className="mt-5 rounded-xl border border-line bg-[#faf7f1] p-4">
              <div className="mb-1 text-xs font-medium text-ink">
                角色模型覆盖
              </div>
              <p className="mb-3 text-[10px] leading-4 text-muted">
                每个角色可以单独指定模型、端点、Key 和采样参数；留空沿用全局默认。
              </p>
              <div className="space-y-3">
                {ROLE_OPTIONS.map((role) => {
                  const config = llm.roles[role.key] ?? emptyRole;
                  const expanded = Boolean(expandedRoles[role.key]);
                  const overridden = Boolean(
                    config.api_base ||
                      config.api_key ||
                      config.api_key_set ||
                      config.max_tokens ||
                      config.top_p ||
                      config.temperature !== 0.3,
                  );
                  return (
                    <div
                      key={role.key}
                      className="rounded-xl border border-line bg-white p-3"
                    >
                      <div className="flex flex-wrap items-end gap-2">
                        <div className="flex min-w-0 flex-1 items-end gap-2">
                          <label className="block min-w-0 flex-1">
                            <span className="mb-1 flex items-center justify-between gap-2 text-[11px] text-muted">
                              <span className="font-medium text-ink">
                                {role.label}
                              </span>
                              <span>{role.hint}</span>
                            </span>
                            <input
                              list={`models-role-${role.key}`}
                              className={fieldClass}
                              value={config.model}
                              onChange={(event) =>
                                updateRole(role.key, {
                                  model: event.target.value,
                                })
                              }
                              placeholder="留空则使用默认模型"
                            />
                            <datalist id={`models-role-${role.key}`}>
                              {(modelOptions[role.key] ?? []).map((model) => (
                                <option key={model} value={model} />
                              ))}
                            </datalist>
                          </label>
                          <button
                            type="button"
                            onClick={() =>
                              void handleFetchModels(role.key, {
                                api_base: config.api_base,
                                api_key: config.api_key,
                                role: role.key,
                              })
                            }
                            disabled={modelLoading === role.key}
                            title={`获取 ${role.label} 的模型列表`}
                            className="inline-flex h-[42px] shrink-0 items-center gap-1 rounded-xl border border-line bg-white px-3 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
                          >
                            {modelLoading === role.key ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <RefreshCw className="h-3.5 w-3.5" />
                            )}
                            获取
                          </button>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedRoles((prev) => ({
                              ...prev,
                              [role.key]: !prev[role.key],
                            }))
                          }
                          className="inline-flex h-[42px] items-center gap-1 rounded-xl border border-line bg-white px-3 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5]"
                        >
                          <SlidersHorizontal className="h-3.5 w-3.5" />
                          {expanded ? "收起" : "高级"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleTest(role.key)}
                          disabled={testing || saving}
                          title={`测试 ${role.label}`}
                          className="inline-flex h-[42px] items-center gap-1 rounded-xl border border-line bg-white px-3 text-[11px] font-medium text-ink transition hover:border-[#cfc4b5] disabled:opacity-60"
                        >
                          {testingRole === role.key ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Wifi className="h-3.5 w-3.5" />
                          )}
                          测试
                        </button>
                      </div>

                      {overridden && !expanded && (
                        <div className="mt-2 text-[10px] text-[#8a6a24]">
                          已单独配置
                          {config.api_base ? " · 独立端点" : ""}
                          {config.api_key_set || config.api_key
                            ? " · 独立 Key"
                            : ""}
                          {config.max_tokens
                            ? ` · max_tokens ${config.max_tokens}`
                            : ""}
                          {config.top_p
                            ? ` · top_p ${config.top_p}`
                            : ""}
                        </div>
                      )}

                      {expanded && (
                        <div className="mt-3 grid gap-3 border-t border-line pt-3 sm:grid-cols-2">
                          <label className="block">
                            <span className="mb-1 block text-[10px] text-muted">
                              temperature
                            </span>
                            <input
                              type="number"
                              min={0}
                              max={2}
                              step={0.1}
                              className={fieldClass}
                              value={config.temperature}
                              onChange={(event) =>
                                updateRole(role.key, {
                                  temperature: Number(event.target.value) || 0,
                                })
                              }
                            />
                          </label>
                          <label className="block">
                            <span className="mb-1 block text-[10px] text-muted">
                              max_tokens（0 = 不限制）
                            </span>
                            <input
                              type="number"
                              min={0}
                              step={64}
                              className={fieldClass}
                              value={config.max_tokens}
                              onChange={(event) =>
                                updateRole(role.key, {
                                  max_tokens: Number(event.target.value) || 0,
                                })
                              }
                            />
                          </label>
                          <label className="block">
                            <span className="mb-1 block text-[10px] text-muted">
                              top_p（0 = 使用供应商默认）
                            </span>
                            <input
                              type="number"
                              min={0}
                              max={1}
                              step={0.05}
                              className={fieldClass}
                              value={config.top_p}
                              onChange={(event) =>
                                updateRole(role.key, {
                                  top_p: Number(event.target.value) || 0,
                                })
                              }
                            />
                          </label>
                          <label className="block">
                            <span className="mb-1 block text-[10px] text-muted">
                              Base URL
                            </span>
                            <input
                              className={fieldClass}
                              value={config.api_base}
                              onChange={(event) =>
                                updateRole(role.key, {
                                  api_base: event.target.value,
                                })
                              }
                              placeholder="留空沿用全局 Base URL"
                            />
                          </label>
                          <label className="block sm:col-span-2">
                            <span className="mb-1 flex items-center justify-between gap-2 text-[10px] text-muted">
                              <span>API Key</span>
                              {config.api_key_set && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateRole(role.key, {
                                      api_key: "",
                                      clear_api_key: true,
                                    })
                                  }
                                  className="text-[10px] font-medium text-[#a33a2a] hover:underline"
                                >
                                  清除独立 Key
                                </button>
                              )}
                            </span>
                            <input
                              type="password"
                              className={fieldClass}
                              value={config.api_key}
                              onChange={(event) =>
                                updateRole(role.key, {
                                  api_key: event.target.value,
                                  clear_api_key: false,
                                })
                              }
                              placeholder={
                                config.api_key_set
                                  ? "已配置，留空保持不变"
                                  : "留空沿用全局 API Key"
                              }
                              autoComplete="off"
                            />
                          </label>
                        </div>
                      )}
                    </div>
                  );
                })}
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
