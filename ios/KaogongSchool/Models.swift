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

    enum CodingKeys: String, CodingKey {
        case attemptId = "attempt_id"
        case remainingSeconds = "remaining_seconds"
        case exam
    }
}

struct AttemptReport: Decodable {
    let attemptId: String
    let examTitle: String
    let score: Double
    let totalScore: Double
    let percentage: Double
    let summary: String
    let errorBookAdded: Int

    enum CodingKeys: String, CodingKey {
        case attemptId = "attempt_id"
        case examTitle = "exam_title"
        case score
        case totalScore = "total_score"
        case percentage
        case summary
        case errorBookAdded = "error_book_added"
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

        enum CodingKeys: String, CodingKey {
            case requests
            case totalTokens = "total_tokens"
            case cost
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

    let totals: Totals
    let byRole: [Role]

    enum CodingKeys: String, CodingKey {
        case totals
        case byRole = "by_role"
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

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case kind
        case status
        case subject
        case module
        case chunkCount = "chunk_count"
        case error
    }
}
