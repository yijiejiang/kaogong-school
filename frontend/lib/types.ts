export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  author: string;
  content: string;
  streaming?: boolean;
  ui?: UiPayload | null;
  createdAt?: string;
};

export type UiPayload = {
  type: string;
  title?: string;
  subtitle?: string;
  questions?: number;
  duration_minutes?: number;
  exam_id?: string;
  [key: string]: unknown;
};

export type SessionSummary = {
  id: string;
  title: string;
  updated_at?: string | number | null;
};

export type RoleModelConfig = {
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  api_base: string;
  api_key: string;
  api_key_set?: boolean;
  clear_api_key?: boolean;
};

export type SettingsBundle = {
  llm: {
    api_base: string;
    api_key: string;
    api_key_set: boolean;
    default_model: string;
    embedding_model: string;
    embedding_api_base: string;
    embedding_api_key: string;
    embedding_api_key_set: boolean;
    asr_model: string;
    asr_api_base: string;
    asr_api_key: string;
    asr_api_key_set: boolean;
    deepseek_api_base: string;
    deepseek_api_key: string;
    deepseek_api_key_set: boolean;
    input_price_per_m: number;
    output_price_per_m: number;
    roles: Record<string, RoleModelConfig>;
  };
  profile: {
    name: string;
    target_exam: string;
    exam_date: string;
    daily_minutes: number;
  };
  server: {
    llm_configured: boolean;
    database: string;
    app_version: string;
    mock_mode: boolean;
  };
};

export type SettingsPayload = {
  llm: {
    api_base: string;
    api_key: string;
    default_model: string;
    embedding_model: string;
    embedding_api_base: string;
    embedding_api_key: string;
    asr_model: string;
    asr_api_base: string;
    asr_api_key: string;
    deepseek_api_base: string;
    deepseek_api_key: string;
    input_price_per_m: number;
    output_price_per_m: number;
    roles: Record<string, RoleModelConfig>;
  };
  profile: {
    name: string;
    target_exam: string;
    exam_date: string;
    daily_minutes: number;
  };
};

export type MaterialStatus = "pending" | "processing" | "ready" | "failed";

export type Material = {
  id: string;
  title: string;
  kind: string;
  status: MaterialStatus;
  subject: string;
  module: string;
  chunk_count: number;
  error: string;
  filename: string;
  source_url: string;
  size_bytes: number;
  embedding_model: string;
  created_at: string;
  updated_at: string;
};

export type ChunkLabel = {
  knowledge_point_id: string;
  knowledge_point_name: string;
  subject: string;
  module: string;
  score: number;
  confidence: number;
  tags: string[];
};

export type MaterialChunk = {
  id: string;
  chunk_index: number;
  content: string;
  page: number | null;
  time_start: number | null;
  time_end: number | null;
  frame_url: string;
  heading: string;
  heading_path: string;
  chunk_type: string;
  subject: string;
  module: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  tags: string[];
  labels: ChunkLabel[];
};

export type MaterialDetail = {
  material: Material;
  chunks: MaterialChunk[];
};

export type SearchHit = {
  chunk_id: string;
  material_id: string;
  material_title: string;
  page: number | null;
  time_start: number | null;
  time_end: number | null;
  frame_url: string;
  heading: string;
  heading_path: string;
  chunk_type: string;
  content: string;
  score: number;
  subject: string;
  module: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  tags: string[];
  labels: ChunkLabel[];
};

export type KnowledgeCardHit = {
  kp_id: string;
  title: string;
  summary: string;
  methods: string;
  traps: string;
};

export type SearchResponse = {
  query: string;
  results: SearchHit[];
  cards: KnowledgeCardHit[];
};

export type KnowledgeNode = {
  id: string;
  parent_id: string | null;
  name: string;
  subject: string;
  module: string;
  level: number;
  description: string;
  keywords: string[];
  chunk_count: number;
};

export type KnowledgeEvidence = {
  page?: number | null;
  quote?: string;
};

export type SkillConnection = {
  name: string;
  relation: string;
  knowledge_point_id: string;
};

export type KnowledgeUnit = {
  id: string;
  material_id: string | null;
  chunk_id: string | null;
  chunk_type: string;
  title: string;
  summary: string;
  definition: string;
  conditions: string[];
  steps: string[];
  pitfalls: string[];
  examples: string[];
  exam_pattern: string;
  signals: string[];
  variants: string[];
  connections: SkillConnection[];
  question_design: string[];
  knowledge_point_id: string;
  knowledge_point_name: string;
  skill_name: string;
  skill_id: string;
  proposed_knowledge_point: string;
  proposed_parent_id: string;
  proposed_reason: string;
  confidence: number;
  status: string;
  evidence: KnowledgeEvidence[];
  extraction_model: string;
  created_at: string;
  updated_at: string;
};

export type Skill = {
  id: string;
  name: string;
  normalized_name: string;
  subject: string;
  module: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  summary: string;
  conditions: string[];
  steps: string[];
  pitfalls: string[];
  examples: string[];
  exam_patterns: string[];
  signals: string[];
  variants: string[];
  connections: SkillConnection[];
  question_design: string[];
  difficulty: number;
  source: string;
  source_ref: string;
  source_unit_ids: string[];
  confidence: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ExtractionResult = {
  status: string;
  units: number;
  skills: number;
  new_skills: number;
  proposals: number;
  model: string;
  warning: string;
};

export type SkillMapItem = {
  id: string;
  name: string;
  subject: string;
  module: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  summary: string;
  confidence: number;
  difficulty: number;
  status: string;
  mastery_status: string;
  mastery_label: string;
  mastery_source: "skill" | "knowledge_point" | "none";
  score: number | null;
  attempts: number;
  correct: number;
  due_at: string | null;
  source_unit_count: number;
  source_material_count: number;
  exam_patterns: string[];
  signals: string[];
  variants: string[];
  question_design: string[];
  connections: SkillConnection[];
  steps: string[];
  pitfalls: string[];
};

export type SkillMapModule = {
  subject: string;
  module: string;
  counts: Record<string, number>;
  health: number;
  total: number;
  needs_work: number;
  weak_ratio: number;
  average_score: number | null;
  skills: SkillMapItem[];
};

export type SkillSource = {
  source: string;
  label: string;
  count: number;
  modules: string[];
  file_count: number;
  last_updated: string | null;
};

export type SkillPack = {
  key: string;
  label: string;
  repo: string;
  description: string;
  builtin: boolean;
  installed: boolean;
};

export type SkillSourcesResponse = {
  sources: SkillSource[];
  packs: SkillPack[];
};

export type SkillMap = {
  user_id: string;
  summary: Record<string, number>;
  subjects: SkillMapModule[];
  headline: string;
};

export type SkillDetail = {
  skill: Skill;
  units: Array<{
    id: string;
    title: string;
    summary: string;
    material_id: string;
    material_title: string;
    status: string;
  }>;
};

export type BankQuestion = {
  id: string;
  type: string;
  subject: string;
  module: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  stem: string;
  options: ExamOption[];
  answer: string;
  explanation: string;
  difficulty: number;
  source: string;
  material_id: string;
  tags: string[];
  created_at: string;
};

export type BankTag = { tag: string; count: number };
export type BankModule = { module: string; count: number };
export type BankTagsResponse = {
  total: number;
  tags: BankTag[];
  modules: BankModule[];
};

export type ExamQuestionType = "single" | "multiple" | "short";

export type ExamOption = {
  key: string;
  text: string;
};

export type ExamConfig = {
  subject: string;
  module: string;
  question_count: number;
  duration_minutes: number;
  difficulty: "easy" | "medium" | "hard" | "mixed";
  ai_count?: number;
  user_id?: string;
};

export type ExamSummary = {
  id: string;
  title: string;
  subject: string;
  module: string;
  question_count: number;
  duration_minutes: number;
  difficulty: string;
  ai_generated?: number;
  warning?: string;
  created_at: string;
};

export type ExamQuestion = {
  id: string;
  order_index: number;
  type: ExamQuestionType;
  stem: string;
  options: ExamOption[];
  score: number;
  knowledge_point_id: string;
  knowledge_point_name: string;
};

export type ExamTake = ExamSummary & {
  questions: ExamQuestion[];
};

export type AttemptStart = {
  attempt_id: string;
  status: string;
  started_at: string;
  remaining_seconds: number;
  exam: ExamTake;
  answers: Record<string, unknown>;
};

export type AnswerItem = {
  question_id: string;
  response: unknown;
};

export type RubricPoint = {
  point: string;
  keywords?: string[];
  score: number;
};

export type FeedbackVariant = {
  stem: string;
  answer: string;
  explanation: string;
};

export type FeedbackSkill = {
  id: string;
  name: string;
  summary: string;
  exam_patterns: string[];
  signals: string[];
  steps: string[];
  pitfalls: string[];
  variants: string[];
};

export type QuestionFeedback = {
  question_id: string;
  order_index: number;
  type: ExamQuestionType;
  stem: string;
  options: ExamOption[];
  user_answer: unknown;
  correct_answer: unknown;
  is_correct: boolean | null;
  score: number;
  max_score: number;
  explanation: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  rubric: RubricPoint[];
  hit_points: { point: string; evidence?: string }[];
  missed_points: string[];
  comment: string;
  variants: FeedbackVariant[];
  skills: FeedbackSkill[];
  skill_usage?: string;
  teaching_model?: string;
};

export type MasteryChange = {
  knowledge_point_id: string;
  knowledge_point_name: string;
  before: number;
  after: number;
  attempts: number;
};

export type AttemptReport = {
  attempt_id: string;
  exam_id: string;
  exam_title: string;
  score: number;
  total_score: number;
  percentage: number;
  submitted_at: string | null;
  questions: QuestionFeedback[];
  mastery_changes: MasteryChange[];
  skill_changes?: Array<{
    skill_id: string;
    skill_name: string;
    before: number;
    after: number;
    attempts: number;
  }>;
  error_book_added: number;
  summary: string;
};

export type AttemptState = {
  attempt_id: string;
  status: string;
  started_at?: string | null;
  remaining_seconds?: number;
  exam?: ExamTake | null;
  answers?: Record<string, unknown>;
  report?: AttemptReport | null;
};

export type AttemptSummary = {
  id: string;
  exam_id: string;
  exam_title: string;
  status: string;
  score: number;
  total_score: number;
  started_at: string;
  submitted_at: string | null;
};

export type AnalyticsProfile = {
  name: string;
  target_exam: string;
  exam_date: string;
  daily_minutes: number;
};

export type AnalyticsStats = {
  attempts: number;
  graded_attempts: number;
  questions: number;
  accuracy: number;
  study_minutes: number;
  coverage: number;
  practiced_kps: number;
  total_kps: number;
};

export type AnalyticsAlert = {
  level: string;
  text: string;
};

export type ModuleScore = {
  subject: string;
  module: string;
  score: number | null;
  attempts: number;
  kp_count: number;
  practiced: number;
};

export type MasteryItem = {
  knowledge_point_id: string;
  knowledge_point_name: string;
  subject: string;
  module: string;
  level: number;
  score: number | null;
  decayed_score: number | null;
  confidence: number;
  attempts: number;
  correct: number;
  last_practiced: string | null;
  due_at: string | null;
  status: string;
};

export type TrendPoint = {
  date: string;
  label: string;
  attempts: number;
  score: number;
  total_score: number;
  accuracy: number;
};

export type AnalyticsOverview = {
  profile: AnalyticsProfile;
  exam_countdown_days: number | null;
  stats: AnalyticsStats;
  alerts: AnalyticsAlert[];
  modules: ModuleScore[];
  mastery: MasteryItem[];
  weak_points: MasteryItem[];
  trend: TrendPoint[];
};

export type PlanTask = {
  id: string;
  date: string;
  task_type: string;
  title: string;
  knowledge_point_id: string;
  knowledge_point_name: string;
  minutes: number;
  status: string;
};

export type PlanDay = {
  date: string;
  weekday: string;
  tasks: PlanTask[];
};

export type WeekPlan = {
  week_start: string;
  week_end: string;
  goal: string;
  daily_minutes: number;
  tasks: PlanTask[];
  days: PlanDay[];
  adherence: { done: number; total: number; percent: number };
};

export type WeeklyReport = {
  period_start: string;
  period_end: string;
  attempts: number;
  questions: number;
  accuracy: number;
  study_minutes: number;
  wrong_count: number;
  plan_done: number;
  plan_total: number;
  weak_points: MasteryItem[];
  summary: string;
};

export type NotificationItem = {
  id: string;
  type: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  link?: string;
};

export type NotificationList = {
  items: NotificationItem[];
  unread: number;
};

export type UsageRole = {
  role: string;
  role_label: string;
  total_tokens: number;
  cost: number;
};

export type UsageModel = {
  model: string;
  total_tokens: number;
  cost: number;
};

export type UsageDay = {
  date: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
};

export type UsageRecent = {
  id: string;
  role: string;
  role_label: string;
  model: string;
  service: string;
  provider: string;
  provider_label: string;
  units: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
  billing_mode: string;
  note: string;
  created_at: string;
};

export type UsageProvider = {
  provider: string;
  provider_label: string;
  requests: number;
  total_tokens: number;
  cost: number;
  billing_mode: string;
  billing_label: string;
};

export type UsageService = {
  service: string;
  label: string;
  units: number;
  requests: number;
  cost: number;
};

export type BillingSource = {
  provider: string;
  label: string;
  base: string;
  service: string;
  model: string;
  billing_mode: string;
  billing_label: string;
};

export type BillingOverview = {
  user_id: string;
  default_billing: string;
  modes: Array<{ value: string; label: string }>;
  sources: BillingSource[];
  price_catalog: Record<string, Record<string, unknown>>;
};

export type UsageSummary = {
  days: number;
  totals: {
    requests: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost: number;
    monthly_services: number;
  };
  by_role: UsageRole[];
  by_model: UsageModel[];
  by_provider: UsageProvider[];
  by_service: UsageService[];
  daily: UsageDay[];
  recent: UsageRecent[];
};

export type ModelInfo = {
  id: string;
  owned_by: string;
};

export type ModelListResult = {
  models: ModelInfo[];
  count: number;
  base_url: string;
};

export type ConnectInfo = {
  api_base: string;
  source: "public" | "lan" | "custom";
  port: number;
  ips: string[];
  payload: string;
};

export type ExtractJob = {
  id: string;
  status: string;
  progress: number;
  message: string;
  error: string;
  result: {
    questions?: number;
    model?: string;
    warning?: string;
    skipped?: string;
  };
};
