import Foundation

struct SettingsBundle: Decodable {
    struct RoleConfig: Decodable {
        var model: String
        var temperature: Double
        var maxTokens: Int
        var topP: Double
        var apiBase: String
        var apiKey: String
        var apiKeySet: Bool

        enum CodingKeys: String, CodingKey {
            case model
            case temperature
            case maxTokens = "max_tokens"
            case topP = "top_p"
            case apiBase = "api_base"
            case apiKey = "api_key"
            case apiKeySet = "api_key_set"
        }
    }

    struct LLM: Decodable {
        let apiBase: String
        let apiKey: String
        let apiKeySet: Bool
        let defaultModel: String
        let embeddingModel: String
        let embeddingApiBase: String
        let embeddingApiKey: String
        let embeddingApiKeySet: Bool
        let asrModel: String
        let asrApiBase: String
        let asrApiKey: String
        let asrApiKeySet: Bool
        let deepseekApiBase: String
        let deepseekApiKey: String
        let deepseekApiKeySet: Bool
        let inputPricePerM: Double
        let outputPricePerM: Double
        let roles: [String: RoleConfig]

        enum CodingKeys: String, CodingKey {
            case apiBase = "api_base"
            case apiKey = "api_key"
            case apiKeySet = "api_key_set"
            case defaultModel = "default_model"
            case embeddingModel = "embedding_model"
            case embeddingApiBase = "embedding_api_base"
            case embeddingApiKey = "embedding_api_key"
            case embeddingApiKeySet = "embedding_api_key_set"
            case asrModel = "asr_model"
            case asrApiBase = "asr_api_base"
            case asrApiKey = "asr_api_key"
            case asrApiKeySet = "asr_api_key_set"
            case deepseekApiBase = "deepseek_api_base"
            case deepseekApiKey = "deepseek_api_key"
            case deepseekApiKeySet = "deepseek_api_key_set"
            case inputPricePerM = "input_price_per_m"
            case outputPricePerM = "output_price_per_m"
            case roles
        }
    }

    struct Profile: Codable {
        var name: String
        var targetExam: String
        var examDate: String
        var dailyMinutes: Int

        enum CodingKeys: String, CodingKey {
            case name
            case targetExam = "target_exam"
            case examDate = "exam_date"
            case dailyMinutes = "daily_minutes"
        }
    }

    struct Server: Decodable {
        let llmConfigured: Bool
        let database: String
        let appVersion: String
        let mockMode: Bool

        enum CodingKeys: String, CodingKey {
            case llmConfigured = "llm_configured"
            case database
            case appVersion = "app_version"
            case mockMode = "mock_mode"
        }
    }

    let llm: LLM
    let profile: Profile
    let server: Server
}

struct SettingsPayload: Encodable {
    struct LLMPayload: Encodable {
        let apiBase: String
        let apiKey: String
        let defaultModel: String
        let embeddingModel: String
        let embeddingApiBase: String
        let embeddingApiKey: String
        let asrModel: String
        let asrApiBase: String
        let asrApiKey: String
        let deepseekApiBase: String
        let deepseekApiKey: String
        let inputPricePerM: Double
        let outputPricePerM: Double
        let roles: [String: RolePayload]

        enum CodingKeys: String, CodingKey {
            case apiBase = "api_base"
            case apiKey = "api_key"
            case defaultModel = "default_model"
            case embeddingModel = "embedding_model"
            case embeddingApiBase = "embedding_api_base"
            case embeddingApiKey = "embedding_api_key"
            case asrModel = "asr_model"
            case asrApiBase = "asr_api_base"
            case asrApiKey = "asr_api_key"
            case deepseekApiBase = "deepseek_api_base"
            case deepseekApiKey = "deepseek_api_key"
            case inputPricePerM = "input_price_per_m"
            case outputPricePerM = "output_price_per_m"
            case roles
        }
    }

    struct RolePayload: Encodable {
        let model: String
        let temperature: Double
        let maxTokens: Int
        let topP: Double
        let apiBase: String
        let apiKey: String
        let clearApiKey: Bool

        enum CodingKeys: String, CodingKey {
            case model
            case temperature
            case maxTokens = "max_tokens"
            case topP = "top_p"
            case apiBase = "api_base"
            case apiKey = "api_key"
            case clearApiKey = "clear_api_key"
        }
    }

    let llm: LLMPayload
    let profile: SettingsBundle.Profile
}

struct SessionSummary: Decodable, Identifiable {
    let id: String
    let title: String
}

struct ChatMessage: Identifiable, Equatable {
    enum Role: String {
        case user
        case assistant
        case system
    }

    var id = UUID().uuidString
    var role: Role
    var author: String
    var content: String
    var streaming = false
    var ui: UIComponent?
}

struct ChatEvent: Decodable {
    let type: String
    let text: String?
    let author: String?
    let sessionId: String?
    let to: String?
    let message: String?
    let component: UIComponent?

    enum CodingKeys: String, CodingKey {
        case type
        case text
        case author
        case sessionId = "session_id"
        case to
        case message
        case component
    }
}

struct UIComponent: Decodable, Equatable {
    let type: String
    let title: String?
    let subtitle: String?
    let examId: String?
    let questions: Int?
    let durationMinutes: Int?
    let aiGenerated: Int?
    let warning: String?

    enum CodingKeys: String, CodingKey {
        case type
        case title
        case subtitle
        case examId = "exam_id"
        case questions
        case durationMinutes = "duration_minutes"
        case aiGenerated = "ai_generated"
        case warning
    }
}

struct ExamSummary: Decodable, Identifiable, Hashable {
    let id: String
    let title: String
    let subject: String
    let module: String
    let questionCount: Int
    let durationMinutes: Int
    let difficulty: String
    let aiGenerated: Int?
    let warning: String?
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case subject
        case module
        case questionCount = "question_count"
        case durationMinutes = "duration_minutes"
        case difficulty
        case aiGenerated = "ai_generated"
        case warning
        case createdAt = "created_at"
    }
}

struct ExamOption: Decodable, Identifiable, Equatable {
    let key: String
    let text: String

    var id: String { key }
}

struct ExamQuestion: Decodable, Identifiable {
    let id: String
    let orderIndex: Int
    let type: String
    let stem: String
    let options: [ExamOption]
    let score: Double
    let knowledgePointName: String

    enum CodingKeys: String, CodingKey {
        case id
        case orderIndex = "order_index"
        case type
        case stem
        case options
        case score
        case knowledgePointName = "knowledge_point_name"
    }
}

struct ExamTake: Decodable {
    let id: String
    let title: String
    let durationMinutes: Int
    let questions: [ExamQuestion]

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case durationMinutes = "duration_minutes"
        case questions
    }
}

struct AttemptStart: Decodable {
    let attemptId: String
    let remainingSeconds: Int
    let exam: ExamTake
    let answers: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case attemptId = "attempt_id"
        case remainingSeconds = "remaining_seconds"
        case exam
        case answers
    }
}

enum JSONValue: Decodable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else {
            self = .null
        }
    }

    var display: String {
        switch self {
        case .string(let value):
            return value.isEmpty ? "未作答" : value
        case .number(let value):
            return value.rounded() == value
                ? String(Int(value)) : String(value)
        case .bool(let value):
            return value ? "是" : "否"
        case .array(let values):
            let text = values.map(\.display).joined(separator: "、")
            return text.isEmpty ? "未作答" : text
        case .object:
            return "已作答"
        case .null:
            return "未作答"
        }
    }

    var keys: [String] {
        switch self {
        case .string(let value):
            return value.isEmpty ? [] : [value]
        case .array(let values):
            return values.flatMap(\.keys)
        default:
            return []
        }
    }
}

struct RubricPoint: Decodable, Identifiable {
    let point: String
    let keywords: [String]?
    let score: Double

    var id: String { point }
}

struct RubricHit: Decodable, Identifiable {
    let point: String
    let evidence: String?

    var id: String { point }
}

struct FeedbackVariant: Decodable, Identifiable {
    let stem: String
    let answer: String?
    let explanation: String?

    var id: String { stem + (answer ?? "") }
}

struct FeedbackSkill: Decodable, Identifiable {
    let id: String
    let name: String
    let summary: String
    let examPatterns: [String]
    let signals: [String]
    let steps: [String]
    let pitfalls: [String]
    let variants: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case summary
        case examPatterns = "exam_patterns"
        case signals
        case steps
        case pitfalls
        case variants
    }
}

struct QuestionFeedback: Decodable, Identifiable {
    let questionId: String
    let orderIndex: Int
    let type: String
    let stem: String
    let options: [ExamOption]
    let userAnswer: JSONValue?
    let correctAnswer: JSONValue?
    let isCorrect: Bool?
    let score: Double
    let maxScore: Double
    let explanation: String
    let knowledgePointId: String
    let knowledgePointName: String
    let rubric: [RubricPoint]
    let hitPoints: [RubricHit]
    let missedPoints: [String]
    let comment: String
    let variants: [FeedbackVariant]
    let skills: [FeedbackSkill]?

    var id: String { questionId }

    enum CodingKeys: String, CodingKey {
        case questionId = "question_id"
        case orderIndex = "order_index"
        case type
        case stem
        case options
        case userAnswer = "user_answer"
        case correctAnswer = "correct_answer"
        case isCorrect = "is_correct"
        case score
        case maxScore = "max_score"
        case explanation
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case rubric
        case hitPoints = "hit_points"
        case missedPoints = "missed_points"
        case comment
        case variants
        case skills
    }
}

struct MasteryChange: Decodable, Identifiable {
    let knowledgePointId: String
    let knowledgePointName: String
    let before: Double
    let after: Double
    let attempts: Int

    var id: String { knowledgePointId }

    enum CodingKeys: String, CodingKey {
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case before
        case after
        case attempts
    }
}

struct SkillChange: Decodable, Identifiable {
    let skillId: String
    let skillName: String
    let before: Double
    let after: Double
    let attempts: Int

    var id: String { skillId }

    enum CodingKeys: String, CodingKey {
        case skillId = "skill_id"
        case skillName = "skill_name"
        case before
        case after
        case attempts
    }
}

struct AttemptReport: Decodable {
    let attemptId: String
    let examId: String
    let examTitle: String
    let score: Double
    let totalScore: Double
    let percentage: Double
    let submittedAt: String?
    let questions: [QuestionFeedback]
    let masteryChanges: [MasteryChange]
    let skillChanges: [SkillChange]?
    let errorBookAdded: Int
    let summary: String

    enum CodingKeys: String, CodingKey {
        case attemptId = "attempt_id"
        case examId = "exam_id"
        case examTitle = "exam_title"
        case score
        case totalScore = "total_score"
        case percentage
        case submittedAt = "submitted_at"
        case questions
        case masteryChanges = "mastery_changes"
        case skillChanges = "skill_changes"
        case errorBookAdded = "error_book_added"
        case summary
    }
}

struct AttemptSummary: Decodable, Identifiable {
    let id: String
    let examId: String
    let examTitle: String
    let status: String
    let score: Double
    let totalScore: Double
    let startedAt: String
    let submittedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case examId = "exam_id"
        case examTitle = "exam_title"
        case status
        case score
        case totalScore = "total_score"
        case startedAt = "started_at"
        case submittedAt = "submitted_at"
    }
}

struct AnalyticsOverview: Decodable {
    struct Stats: Decodable {
        let gradedAttempts: Int
        let questions: Int
        let accuracy: Double
        let studyMinutes: Int
        let coverage: Double
        let practicedKps: Int
        let totalKps: Int

        enum CodingKeys: String, CodingKey {
            case gradedAttempts = "graded_attempts"
            case questions
            case accuracy
            case studyMinutes = "study_minutes"
            case coverage
            case practicedKps = "practiced_kps"
            case totalKps = "total_kps"
        }
    }

    struct WeakPoint: Decodable, Identifiable {
        let knowledgePointId: String
        let knowledgePointName: String
        let module: String
        let score: Double?
        let status: String

        var id: String { knowledgePointId }

        enum CodingKeys: String, CodingKey {
            case knowledgePointId = "knowledge_point_id"
            case knowledgePointName = "knowledge_point_name"
            case module
            case score
            case status
        }
    }

    struct Module: Decodable, Identifiable {
        let subject: String
        let module: String
        let score: Double?

        var id: String { subject + module }
    }

    let stats: Stats
    let weakPoints: [WeakPoint]
    let modules: [Module]

    enum CodingKeys: String, CodingKey {
        case stats
        case weakPoints = "weak_points"
        case modules
    }
}

struct WeekPlan: Decodable {
    struct Task: Decodable, Identifiable {
        let id: String
        let date: String
        let title: String
        let minutes: Int
        let status: String
    }

    let goal: String
    let tasks: [Task]
    let adherence: Adherence

    struct Adherence: Decodable {
        let done: Int
        let total: Int
        let percent: Double
    }
}

struct UsageSummary: Decodable {
    struct Totals: Decodable {
        let requests: Int
        let totalTokens: Int
        let cost: Double
        let monthlyServices: Int

        enum CodingKeys: String, CodingKey {
            case requests
            case totalTokens = "total_tokens"
            case cost
            case monthlyServices = "monthly_services"
        }
    }

    struct Role: Decodable, Identifiable {
        let role: String
        let roleLabel: String
        let totalTokens: Int

        var id: String { role }

        enum CodingKeys: String, CodingKey {
            case role
            case roleLabel = "role_label"
            case totalTokens = "total_tokens"
        }
    }

    struct Provider: Decodable, Identifiable {
        let provider: String
        let providerLabel: String
        let requests: Int
        let totalTokens: Int
        let cost: Double
        let billingMode: String
        let billingLabel: String

        var id: String { provider }

        enum CodingKeys: String, CodingKey {
            case provider
            case providerLabel = "provider_label"
            case requests
            case totalTokens = "total_tokens"
            case cost
            case billingMode = "billing_mode"
            case billingLabel = "billing_label"
        }
    }

    struct Service: Decodable, Identifiable {
        let service: String
        let label: String
        let units: Double
        let requests: Int
        let cost: Double

        var id: String { service }
    }

    let totals: Totals
    let byRole: [Role]
    let byProvider: [Provider]?
    let byService: [Service]?

    enum CodingKeys: String, CodingKey {
        case totals
        case byRole = "by_role"
        case byProvider = "by_provider"
        case byService = "by_service"
    }
}

struct MaterialItem: Decodable, Identifiable {
    let id: String
    let title: String
    let kind: String
    let status: String
    let subject: String
    let module: String
    let chunkCount: Int
    let error: String
    let filename: String?
    let sourceUrl: String?
    let sizeBytes: Int?
    let embeddingModel: String?
    let createdAt: String?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case kind
        case status
        case subject
        case module
        case chunkCount = "chunk_count"
        case error
        case filename
        case sourceUrl = "source_url"
        case sizeBytes = "size_bytes"
        case embeddingModel = "embedding_model"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct ChunkLabel: Decodable, Identifiable {
    let knowledgePointId: String
    let knowledgePointName: String
    let subject: String
    let module: String
    let score: Double
    let confidence: Double
    let tags: [String]

    var id: String { knowledgePointId }

    enum CodingKeys: String, CodingKey {
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case subject
        case module
        case score
        case confidence
        case tags
    }
}

struct MaterialChunk: Decodable, Identifiable {
    let id: String
    let chunkIndex: Int
    let content: String
    let page: Int?
    let timeStart: Double?
    let timeEnd: Double?
    let frameURL: String
    let heading: String
    let headingPath: String
    let chunkType: String
    let subject: String
    let module: String
    let knowledgePointId: String
    let knowledgePointName: String
    let tags: [String]
    let labels: [ChunkLabel]

    enum CodingKeys: String, CodingKey {
        case id
        case chunkIndex = "chunk_index"
        case content
        case page
        case timeStart = "time_start"
        case timeEnd = "time_end"
        case frameURL = "frame_url"
        case heading
        case headingPath = "heading_path"
        case chunkType = "chunk_type"
        case subject
        case module
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case tags
        case labels
    }
}

struct MaterialDetail: Decodable {
    let material: MaterialItem
    let chunks: [MaterialChunk]
}

struct SearchHit: Decodable, Identifiable {
    let chunkId: String
    let materialId: String
    let materialTitle: String
    let page: Int?
    let timeStart: Double?
    let timeEnd: Double?
    let frameURL: String
    let heading: String
    let content: String
    let score: Double
    let subject: String
    let module: String
    let knowledgePointId: String
    let knowledgePointName: String
    let tags: [String]

    var id: String { chunkId }

    enum CodingKeys: String, CodingKey {
        case chunkId = "chunk_id"
        case materialId = "material_id"
        case materialTitle = "material_title"
        case page
        case timeStart = "time_start"
        case timeEnd = "time_end"
        case frameURL = "frame_url"
        case heading
        case content
        case score
        case subject
        case module
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case tags
    }
}

struct KnowledgeCardHit: Decodable, Identifiable {
    let kpId: String
    let title: String
    let summary: String
    let methods: String
    let traps: String

    var id: String { kpId }

    enum CodingKeys: String, CodingKey {
        case kpId = "kp_id"
        case title
        case summary
        case methods
        case traps
    }
}

struct SearchResponse: Decodable {
    let query: String
    let results: [SearchHit]
    let cards: [KnowledgeCardHit]
}

struct KnowledgeNode: Decodable, Identifiable {
    let id: String
    let parentId: String?
    let name: String
    let subject: String
    let module: String
    let level: Int
    let description: String
    let keywords: [String]
    let chunkCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case parentId = "parent_id"
        case name
        case subject
        case module
        case level
        case description
        case keywords
        case chunkCount = "chunk_count"
    }
}

struct KnowledgeCardDetail: Decodable {
    let kpId: String
    let title: String
    let summary: String
    let methods: String
    let traps: String
    let sourceChunks: [SearchHit]

    enum CodingKeys: String, CodingKey {
        case kpId = "kp_id"
        case title
        case summary
        case methods
        case traps
        case sourceChunks = "source_chunks"
    }
}

struct SkillConnection: Decodable, Identifiable {
    let name: String
    let relation: String
    let knowledgePointId: String

    var id: String { "\(relation)-\(name)" }

    enum CodingKeys: String, CodingKey {
        case name
        case relation
        case knowledgePointId = "knowledge_point_id"
    }
}

struct KnowledgeUnitItem: Decodable, Identifiable {
    let id: String
    let materialId: String
    let chunkType: String
    let title: String
    let summary: String
    let definition: String
    let conditions: [String]
    let steps: [String]
    let pitfalls: [String]
    let examples: [String]
    let examPattern: String
    let signals: [String]
    let variants: [String]
    let connections: [SkillConnection]
    let questionDesign: [String]
    let knowledgePointId: String
    let knowledgePointName: String
    let skillName: String
    let skillId: String
    let proposedKnowledgePoint: String
    let proposedParentId: String
    let proposedReason: String
    let confidence: Double
    let status: String
    let extractionModel: String

    enum CodingKeys: String, CodingKey {
        case id
        case materialId = "material_id"
        case chunkType = "chunk_type"
        case title
        case summary
        case definition
        case conditions
        case steps
        case pitfalls
        case examples
        case examPattern = "exam_pattern"
        case signals
        case variants
        case connections
        case questionDesign = "question_design"
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case skillName = "skill_name"
        case skillId = "skill_id"
        case proposedKnowledgePoint = "proposed_knowledge_point"
        case proposedParentId = "proposed_parent_id"
        case proposedReason = "proposed_reason"
        case confidence
        case status
        case extractionModel = "extraction_model"
    }
}

struct SkillItem: Decodable, Identifiable {
    let id: String
    let name: String
    let normalizedName: String
    let subject: String
    let module: String
    let knowledgePointId: String
    let knowledgePointName: String
    let summary: String
    let conditions: [String]
    let steps: [String]
    let pitfalls: [String]
    let examples: [String]
    let examPatterns: [String]
    let signals: [String]
    let variants: [String]
    let connections: [SkillConnection]
    let questionDesign: [String]
    let difficulty: Int
    let sourceUnitIds: [String]
    let source: String?
    let sourceRef: String?
    let confidence: Double
    let status: String

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case normalizedName = "normalized_name"
        case subject
        case module
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case summary
        case conditions
        case steps
        case pitfalls
        case examples
        case examPatterns = "exam_patterns"
        case signals
        case variants
        case connections
        case questionDesign = "question_design"
        case difficulty
        case sourceUnitIds = "source_unit_ids"
        case source
        case sourceRef = "source_ref"
        case confidence
        case status
    }
}

struct SkillMapSkill: Decodable, Identifiable {
    let id: String
    let name: String
    let subject: String
    let module: String
    let knowledgePointId: String
    let knowledgePointName: String
    let summary: String
    let confidence: Double
    let difficulty: Int
    let status: String
    let masteryStatus: String
    let masteryLabel: String
    let masterySource: String
    let score: Double?
    let attempts: Int
    let correct: Int
    let dueAt: String?
    let sourceUnitCount: Int
    let sourceMaterialCount: Int
    let examPatterns: [String]
    let signals: [String]
    let variants: [String]
    let questionDesign: [String]
    let connections: [SkillConnection]
    let steps: [String]
    let pitfalls: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case subject
        case module
        case knowledgePointId = "knowledge_point_id"
        case knowledgePointName = "knowledge_point_name"
        case summary
        case confidence
        case difficulty
        case status
        case masteryStatus = "mastery_status"
        case masteryLabel = "mastery_label"
        case masterySource = "mastery_source"
        case score
        case attempts
        case correct
        case dueAt = "due_at"
        case sourceUnitCount = "source_unit_count"
        case sourceMaterialCount = "source_material_count"
        case examPatterns = "exam_patterns"
        case signals
        case variants
        case questionDesign = "question_design"
        case connections
        case steps
        case pitfalls
    }
}

struct SkillMapModule: Decodable, Identifiable {
    let subject: String
    let module: String
    let counts: [String: Int]
    let health: Double?
    let total: Int?
    let needsWork: Int?
    let weakRatio: Double?
    let averageScore: Double?
    let skills: [SkillMapSkill]

    var id: String { "\(subject)-\(module)" }

    enum CodingKeys: String, CodingKey {
        case subject
        case module
        case counts
        case health
        case total
        case needsWork = "needs_work"
        case weakRatio = "weak_ratio"
        case averageScore = "average_score"
        case skills
    }
}

struct SkillMapResponse: Decodable {
    let userId: String
    let summary: [String: Int]
    let subjects: [SkillMapModule]
    let headline: String?

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case summary
        case subjects
        case headline
    }
}

struct SkillDetailResponse: Decodable {
    struct SourceUnit: Decodable, Identifiable {
        let id: String
        let title: String
        let summary: String
        let materialId: String
        let materialTitle: String
        let status: String

        enum CodingKeys: String, CodingKey {
            case id
            case title
            case summary
            case materialId = "material_id"
            case materialTitle = "material_title"
            case status
        }
    }

    let skill: SkillItem
    let units: [SourceUnit]
}

struct ExtractionResult: Decodable {
    let status: String
    let units: Int
    let skills: Int
    let newSkills: Int
    let proposals: Int
    let model: String
    let warning: String

    enum CodingKeys: String, CodingKey {
        case status
        case units
        case skills
        case newSkills = "new_skills"
        case proposals
        case model
        case warning
    }
}

struct CreatePointResponse: Decodable {
    struct Point: Decodable {
        let id: String
        let name: String
        let parentId: String
        let subject: String
        let module: String

        enum CodingKeys: String, CodingKey {
            case id
            case name
            case parentId = "parent_id"
            case subject
            case module
        }
    }

    let status: String
    let knowledgePoint: Point

    enum CodingKeys: String, CodingKey {
        case status
        case knowledgePoint = "knowledge_point"
    }
}

struct BillingOverview: Decodable {
    struct Source: Decodable, Identifiable {
        let provider: String
        let label: String
        let base: String
        let service: String
        let model: String
        let billingMode: String
        let billingLabel: String

        var id: String { "\(provider)-\(service)" }

        enum CodingKeys: String, CodingKey {
            case provider
            case label
            case base
            case service
            case model
            case billingMode = "billing_mode"
            case billingLabel = "billing_label"
        }
    }

    struct Mode: Decodable, Identifiable {
        let value: String
        let label: String

        var id: String { value }
    }

    let userId: String
    let defaultBilling: String
    let modes: [Mode]
    let sources: [Source]

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case defaultBilling = "default_billing"
        case modes
        case sources
    }
}
