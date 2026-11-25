import { getUserId } from "./user";
import type {
  AnalyticsOverview,
  AnswerItem,
  AttemptReport,
  AttemptStart,
  AttemptState,
  AttemptSummary,
  BankQuestion,
  BankTagsResponse,
  ExtractJob,
  BillingOverview,
  ChatMessage,
  ConnectInfo,
  ExamConfig,
  ExamSummary,
  ExamTake,
  ExtractionResult,
  KnowledgeNode,
  KnowledgeUnit,
  Material,
  MaterialDetail,
  ModelListResult,
  NotificationItem,
  NotificationList,
  PlanTask,
  SearchResponse,
  SessionSummary,
  SettingsBundle,
  SettingsPayload,
  Skill,
  SkillDetail,
  SkillMap,
  SkillSourcesResponse,
  UsageSummary,
  WeekPlan,
  WeeklyReport,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export { API_BASE };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `请求失败（${response.status}）`);
  }

  return (await response.json()) as T;
}

export async function fetchSessions(
  userId = getUserId(),
): Promise<SessionSummary[]> {
  return request(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`);
}

export async function fetchMessages(
  sessionId: string,
  userId = getUserId(),
): Promise<ChatMessage[]> {
  const data = await request<{ messages: ChatMessage[] }>(
    `/api/chat/sessions/${encodeURIComponent(sessionId)}/messages?user_id=${encodeURIComponent(userId)}`,
  );
  return data.messages;
}

export async function fetchSettings(
  userId = getUserId(),
): Promise<SettingsBundle> {
  return request(`/api/settings?user_id=${encodeURIComponent(userId)}`);
}

export async function saveSettings(
  payload: SettingsPayload,
  userId = getUserId(),
): Promise<SettingsBundle> {
  return request(`/api/settings?user_id=${encodeURIComponent(userId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export type TestResult = {
  ok: boolean;
  model?: string;
  latency_ms?: number;
  sample?: string;
  error?: string;
};

export async function testLlm(
  llm: SettingsPayload["llm"],
  role?: string,
): Promise<TestResult> {
  return request("/api/settings/test", {
    method: "POST",
    body: JSON.stringify({ llm, role: role ?? null }),
  });
}

export async function fetchModels(payload: {
  api_base?: string;
  api_key?: string;
  role?: string;
}): Promise<ModelListResult> {
  return request("/api/settings/models", {
    method: "POST",
    body: JSON.stringify({
      api_base: payload.api_base ?? "",
      api_key: payload.api_key ?? "",
      role: payload.role ?? null,
    }),
  });
}

export async function fetchConnectInfo(): Promise<ConnectInfo> {
  return request("/api/connect/info");
}

export function connectQrUrl(base?: string): string {
  const query = base ? `?base=${encodeURIComponent(base)}` : "";
  return `${API_BASE}/api/connect/qr.png${query}`;
}

export async function fetchMaterials(): Promise<Material[]> {
  return request("/api/materials");
}

export async function fetchMaterial(id: string): Promise<MaterialDetail> {
  return request(`/api/materials/${encodeURIComponent(id)}`);
}

export async function uploadMaterial(file: File): Promise<Material> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/materials/upload`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `上传失败（${response.status}）`);
  }
  return (await response.json()) as Material;
}

export async function importUrl(url: string): Promise<Material> {
  return request("/api/materials/import-url", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function seedSampleMaterial(): Promise<Material> {
  return request("/api/materials/seed-sample", { method: "POST" });
}

export async function reindexMaterial(id: string): Promise<Material> {
  return request(`/api/materials/${encodeURIComponent(id)}/reindex`, {
    method: "POST",
  });
}

export async function deleteMaterial(id: string): Promise<{ ok: boolean }> {
  return request(`/api/materials/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function searchMaterials(
  query: string,
  options?: { subject?: string; module?: string; topK?: number },
): Promise<SearchResponse> {
  return request("/api/search", {
    method: "POST",
    body: JSON.stringify({
      query,
      subject: options?.subject ?? "",
      module: options?.module ?? "",
      top_k: options?.topK ?? 8,
    }),
  });
}

export async function fetchKnowledgeTree(): Promise<KnowledgeNode[]> {
  return request("/api/knowledge/tree");
}

export async function fetchKnowledgeUnits(options?: {
  status?: string;
  materialId?: string;
  knowledgePointId?: string;
  hasProposal?: boolean;
  limit?: number;
}): Promise<KnowledgeUnit[]> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.materialId) params.set("material_id", options.materialId);
  if (options?.knowledgePointId) {
    params.set("knowledge_point_id", options.knowledgePointId);
  }
  if (options?.hasProposal) params.set("has_proposal", "true");
  params.set("limit", String(options?.limit ?? 100));
  return request(`/api/knowledge/units?${params.toString()}`);
}

export async function createKnowledgeUnit(payload: {
  title: string;
  summary?: string;
  definition?: string;
  conditions?: string[];
  steps?: string[];
  pitfalls?: string[];
  examples?: string[];
  exam_pattern?: string;
  signals?: string[];
  variants?: string[];
  knowledge_point_id?: string;
  knowledge_point_name?: string;
}): Promise<KnowledgeUnit> {
  return request("/api/knowledge/units", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateKnowledgeUnit(
  id: string,
  payload: Partial<
    Pick<
      KnowledgeUnit,
      | "title"
      | "summary"
      | "definition"
      | "conditions"
      | "steps"
      | "pitfalls"
      | "examples"
      | "knowledge_point_id"
      | "knowledge_point_name"
      | "status"
    >
  >,
): Promise<KnowledgeUnit> {
  return request(`/api/knowledge/units/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchSkills(options?: {
  status?: string;
  knowledgePointId?: string;
  limit?: number;
}): Promise<Skill[]> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.knowledgePointId) {
    params.set("knowledge_point_id", options.knowledgePointId);
  }
  params.set("limit", String(options?.limit ?? 100));
  return request(`/api/knowledge/skills?${params.toString()}`);
}

export async function updateSkill(
  id: string,
  payload: Partial<Pick<Skill, "name" | "summary" | "status">>,
): Promise<Skill> {
  return request(`/api/knowledge/skills/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchSkillSources(): Promise<SkillSourcesResponse> {
  return request("/api/knowledge/skill-sources");
}

export async function importSkillPack(payload: {
  repo?: string;
  useBuiltin?: boolean;
  sourceKey?: string;
}): Promise<{ status: string; source: string; created: number; total: number }> {
  return request("/api/knowledge/skill-sources/import", {
    method: "POST",
    body: JSON.stringify({
      repo: payload.repo ?? "",
      use_builtin: payload.useBuiltin ?? false,
      source_key: payload.sourceKey ?? "huasheng13",
    }),
  });
}

export async function fetchSkillMap(userId = getUserId()): Promise<SkillMap> {
  return request(
    `/api/knowledge/skill-map?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function fetchSkillDetail(id: string): Promise<SkillDetail> {
  return request(`/api/knowledge/skills/${encodeURIComponent(id)}`);
}

export async function createPointFromUnit(unitId: string): Promise<{
  status: string;
  knowledge_point: {
    id: string;
    name: string;
    parent_id: string;
    subject: string;
    module: string;
  };
  unit: KnowledgeUnit;
}> {
  return request(
    `/api/knowledge/units/${encodeURIComponent(unitId)}/create-point`,
    { method: "POST" },
  );
}

export async function extractMaterialUnits(
  materialId: string,
): Promise<ExtractionResult> {
  return request(`/api/knowledge/extract/${encodeURIComponent(materialId)}`, {
    method: "POST",
  });
}

export async function generateExam(config: ExamConfig): Promise<ExamSummary> {
  return request("/api/exams/generate", {
    method: "POST",
    body: JSON.stringify({
      ...config,
      user_id: config.user_id ?? getUserId(),
    }),
  });
}

export async function fetchExams(): Promise<ExamSummary[]> {
  return request("/api/exams");
}

export async function fetchQuestions(options?: {
  tag?: string;
  module?: string;
  subject?: string;
  materialId?: string;
  search?: string;
  limit?: number;
}): Promise<BankQuestion[]> {
  const params = new URLSearchParams();
  if (options?.tag) params.set("tag", options.tag);
  if (options?.module) params.set("module", options.module);
  if (options?.subject) params.set("subject", options.subject);
  if (options?.materialId) params.set("material_id", options.materialId);
  if (options?.search) params.set("search", options.search);
  params.set("limit", String(options?.limit ?? 200));
  return request(`/api/questions?${params.toString()}`);
}

export async function fetchQuestionTags(): Promise<BankTagsResponse> {
  return request("/api/questions/tags");
}

export async function updateQuestion(
  id: string,
  payload: Partial<
    Pick<
      BankQuestion,
      | "type"
      | "subject"
      | "module"
      | "stem"
      | "options"
      | "answer"
      | "explanation"
      | "difficulty"
      | "tags"
    >
  >,
): Promise<BankQuestion> {
  return request(`/api/questions/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteQuestion(id: string): Promise<{ ok: boolean }> {
  return request(`/api/questions/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function extractQuestions(
  materialId: string,
  force = false,
): Promise<{ status: string; job_id: string; message: string }> {
  const query = force ? "?force=true" : "";
  return request(
    `/api/questions/extract/${encodeURIComponent(materialId)}${query}`,
    { method: "POST" },
  );
}

export async function fetchExtractJob(jobId: string): Promise<ExtractJob> {
  return request(`/api/questions/extract/jobs/${encodeURIComponent(jobId)}`);
}

export async function fetchExam(id: string): Promise<ExamTake> {
  return request(`/api/exams/${encodeURIComponent(id)}`);
}

export async function startAttempt(
  examId: string,
  userId = getUserId(),
): Promise<AttemptStart> {
  return request(
    `/api/exams/${encodeURIComponent(examId)}/start?user_id=${encodeURIComponent(userId)}`,
    { method: "POST" },
  );
}

export async function saveAttemptAnswers(
  attemptId: string,
  answers: AnswerItem[],
): Promise<{ ok: boolean; saved: number }> {
  return request(`/api/attempts/${encodeURIComponent(attemptId)}/answers`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export async function submitAttempt(
  attemptId: string,
  answers: AnswerItem[],
): Promise<AttemptReport> {
  return request(`/api/attempts/${encodeURIComponent(attemptId)}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export async function fetchAttemptReport(
  attemptId: string,
): Promise<AttemptReport> {
  return request(`/api/attempts/${encodeURIComponent(attemptId)}/report`);
}

export async function fetchAttemptState(
  attemptId: string,
): Promise<AttemptState> {
  return request(`/api/attempts/${encodeURIComponent(attemptId)}`);
}

export async function fetchAttempts(
  userId = getUserId(),
): Promise<AttemptSummary[]> {
  return request(`/api/attempts?user_id=${encodeURIComponent(userId)}`);
}

export async function fetchAnalyticsOverview(
  userId = getUserId(),
): Promise<AnalyticsOverview> {
  return request(
    `/api/analytics/overview?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function fetchWeeklyReport(
  userId = getUserId(),
): Promise<WeeklyReport> {
  return request(
    `/api/analytics/weekly-report?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function fetchUsage(
  userId = getUserId(),
  days = 14,
): Promise<UsageSummary> {
  return request(
    `/api/analytics/usage?user_id=${encodeURIComponent(userId)}&days=${days}`,
  );
}

export async function fetchBilling(
  userId = getUserId(),
): Promise<BillingOverview> {
  return request(
    `/api/analytics/billing?user_id=${encodeURIComponent(userId)}`,
  );
}

export type AsrStatus = {
  ready: boolean;
  api_configured: boolean;
  local_available: boolean;
  model: string;
};

export async function fetchAsrStatus(): Promise<AsrStatus> {
  return request("/api/asr/status");
}

export async function transcribeAudio(
  file: File,
): Promise<{ text: string; provider: string; model: string; chars: number }> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/asr/transcribe`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `语音转写失败（${response.status}）`);
  }
  return (await response.json()) as {
    text: string;
    provider: string;
    model: string;
    chars: number;
  };
}

export async function fetchWeekPlan(
  userId = getUserId(),
): Promise<WeekPlan> {
  return request(`/api/plan/week?user_id=${encodeURIComponent(userId)}`);
}

export async function generateWeekPlan(
  userId = getUserId(),
): Promise<WeekPlan> {
  return request(`/api/plan/generate?user_id=${encodeURIComponent(userId)}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function togglePlanTask(
  taskId: string,
  done: boolean,
  userId = getUserId(),
): Promise<PlanTask> {
  return request(
    `/api/plan/tasks/${encodeURIComponent(taskId)}?user_id=${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ done }),
    },
  );
}

export async function fetchNotifications(
  userId = getUserId(),
): Promise<NotificationList> {
  return request(
    `/api/notifications?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function markNotificationRead(
  notificationId: string,
  userId = getUserId(),
): Promise<NotificationItem> {
  return request(
    `/api/notifications/${encodeURIComponent(notificationId)}/read?user_id=${encodeURIComponent(userId)}`,
    { method: "PATCH" },
  );
}

export async function markAllNotificationsRead(
  userId = getUserId(),
): Promise<{ ok: boolean; updated: number }> {
  return request(
    `/api/notifications/read-all?user_id=${encodeURIComponent(userId)}`,
    { method: "POST" },
  );
}

export type StreamEvent = {
  type: string;
  [key: string]: unknown;
};

export async function streamChat(
  payload: {
    message: string;
    session_id?: string | null;
    user_id?: string;
    attempt_id?: string | null;
  },
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = data.detail ?? "";
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `对话请求失败（${response.status}）`);
  }

  if (!response.body) {
    throw new Error("服务端没有返回流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const dataLines = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim());
        if (dataLines.length === 0) continue;

        const raw = dataLines.join("\n");
        if (!raw || raw === "[DONE]") continue;

        try {
          onEvent(JSON.parse(raw) as StreamEvent);
        } catch {
          // Ignore malformed frames; the stream should stay usable.
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
