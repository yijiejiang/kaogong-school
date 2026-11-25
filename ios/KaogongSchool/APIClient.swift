import Foundation

enum APIError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let text): return text
        }
    }
}

actor APIClient {
    static let shared = APIClient()

    nonisolated var baseURLString: String {
        UserDefaults.standard.string(forKey: "apiBaseURL") ?? "http://127.0.0.1:8000"
    }

    nonisolated var userId: String {
        UserDefaults.standard.string(forKey: "userId") ?? "local-user"
    }

    private var decoder: JSONDecoder {
        JSONDecoder()
    }

    private func url(_ path: String, query: [String: String] = [:]) throws -> URL {
        guard var components = URLComponents(string: baseURLString + path) else {
            throw APIError.message("Base URL 格式不正确")
        }
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        guard let url = components.url else {
            throw APIError.message("请求地址不正确")
        }
        return url
    }

    private func check(_ response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = object["detail"] as? String {
                throw APIError.message(detail)
            }
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError.message("请求失败（\(http.statusCode)）\(text.prefix(200))")
        }
    }

    private func perform<T: Decodable>(
        _ path: String,
        method: String = "GET",
        query: [String: String] = [:],
        body: Data? = nil
    ) async throws -> T {
        var request = URLRequest(url: try url(path, query: query))
        request.httpMethod = method
        request.timeoutInterval = 120
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        try check(response, data: data)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.message("返回数据无法解析：\(error.localizedDescription)")
        }
    }

    func get<T: Decodable>(_ path: String, query: [String: String] = [:]) async throws -> T {
        try await perform(path, query: query)
    }

    func send<T: Decodable>(
        _ path: String,
        method: String,
        query: [String: String] = [:],
        json: [String: Any]
    ) async throws -> T {
        let data = try JSONSerialization.data(withJSONObject: json)
        return try await perform(path, method: method, query: query, body: data)
    }

    func send<T: Decodable, B: Encodable>(
        _ path: String,
        method: String,
        query: [String: String] = [:],
        body: B
    ) async throws -> T {
        let data = try JSONEncoder().encode(body)
        return try await perform(path, method: method, query: query, body: data)
    }

    func settings() async throws -> SettingsBundle {
        try await get("/api/settings", query: ["user_id": userId])
    }

    func availableModels(
        apiBase: String,
        apiKey: String,
        role: String?
    ) async throws -> [String] {
        struct ModelItem: Decodable { let id: String }
        struct Response: Decodable {
            let models: [ModelItem]
            let count: Int
        }
        let response: Response = try await send(
            "/api/settings/models",
            method: "POST",
            json: [
                "api_base": apiBase,
                "api_key": apiKey,
                "role": role ?? NSNull(),
            ]
        )
        return response.models.map(\.id)
    }

    func saveSettings(_ payload: SettingsPayload) async throws -> SettingsBundle {
        try await send(
            "/api/settings",
            method: "PUT",
            query: ["user_id": userId],
            body: payload
        )
    }

    func sessions() async throws -> [SessionSummary] {
        try await get("/api/chat/sessions", query: ["user_id": userId])
    }

    func messages(sessionId: String) async throws -> [ChatMessage] {
        struct Response: Decodable {
            struct Item: Decodable {
                let id: String
                let role: String
                let author: String
                let content: String
                let ui: UIComponent?
            }
            let messages: [Item]
        }

        let response: Response = try await get(
            "/api/chat/sessions/\(sessionId)/messages",
            query: ["user_id": userId]
        )
        return response.messages.map {
            ChatMessage(
                id: $0.id,
                role: ChatMessage.Role(rawValue: $0.role) ?? .assistant,
                author: $0.author,
                content: $0.content,
                ui: $0.ui
            )
        }
    }

    func streamChat(message: String, sessionId: String?) -> AsyncThrowingStream<ChatEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    var request = URLRequest(url: try self.url("/api/chat/stream"))
                    request.httpMethod = "POST"
                    request.timeoutInterval = 600
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    var payload: [String: Any] = [
                        "message": message,
                        "user_id": self.userId,
                    ]
                    if let sessionId { payload["session_id"] = sessionId }
                    request.httpBody = try JSONSerialization.data(withJSONObject: payload)

                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    if let http = response as? HTTPURLResponse,
                       !(200..<300).contains(http.statusCode) {
                        throw APIError.message("对话请求失败（\(http.statusCode)）")
                    }
                    for try await line in bytes.lines {
                        guard line.hasPrefix("data:") else { continue }
                        let raw = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                        guard !raw.isEmpty, raw != "[DONE]" else { continue }
                        guard let data = raw.data(using: .utf8) else { continue }
                        if let event = try? self.decoder.decode(ChatEvent.self, from: data) {
                            continuation.yield(event)
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    func exams() async throws -> [ExamSummary] {
        try await get("/api/exams")
    }

    func generateExam(
        subject: String,
        module: String,
        count: Int,
        minutes: Int,
        difficulty: String,
        aiCount: Int
    ) async throws -> ExamSummary {
        try await send(
            "/api/exams/generate",
            method: "POST",
            json: [
                "subject": subject,
                "module": module,
                "question_count": count,
                "duration_minutes": minutes,
                "difficulty": difficulty,
                "ai_count": aiCount,
                "user_id": userId,
            ]
        )
    }

    func startAttempt(examId: String) async throws -> AttemptStart {
        try await send(
            "/api/exams/\(examId)/start",
            method: "POST",
            query: ["user_id": userId],
            json: [:]
        )
    }

    func attempts() async throws -> [AttemptSummary] {
        try await get("/api/attempts", query: ["user_id": userId])
    }

    func attemptReport(attemptId: String) async throws -> AttemptReport {
        try await get("/api/attempts/\(attemptId)/report")
    }

    func saveAnswers(
        attemptId: String,
        answers: [[String: Any]]
    ) async throws {
        struct Response: Decodable {
            let ok: Bool
            let saved: Int
        }
        let _: Response = try await send(
            "/api/attempts/\(attemptId)/answers",
            method: "POST",
            json: ["answers": answers]
        )
    }

    func submitAttempt(attemptId: String, answers: [[String: Any]]) async throws -> AttemptReport {
        try await send(
            "/api/attempts/\(attemptId)/submit",
            method: "POST",
            json: ["answers": answers]
        )
    }

    func analytics() async throws -> AnalyticsOverview {
        try await get("/api/analytics/overview", query: ["user_id": userId])
    }

    func weekPlan() async throws -> WeekPlan {
        try await get("/api/plan/week", query: ["user_id": userId])
    }

    func toggleTask(id: String, done: Bool) async throws {
        struct Response: Decodable { let id: String }
        let _: Response = try await send(
            "/api/plan/tasks/\(id)",
            method: "PATCH",
            query: ["user_id": userId],
            json: ["done": done]
        )
    }

    func usage(days: Int = 14) async throws -> UsageSummary {
        try await get(
            "/api/analytics/usage",
            query: ["user_id": userId, "days": String(days)]
        )
    }

    func billing() async throws -> BillingOverview {
        try await get("/api/analytics/billing", query: ["user_id": userId])
    }

    func materials() async throws -> [MaterialItem] {
        try await get("/api/materials")
    }

    func questions(
        tag: String = "",
        module: String = "",
        materialId: String = "",
        search: String = ""
    ) async throws -> [BankQuestion] {
        var query = ["limit": "300"]
        if !tag.isEmpty { query["tag"] = tag }
        if !module.isEmpty { query["module"] = module }
        if !materialId.isEmpty { query["material_id"] = materialId }
        if !search.isEmpty { query["search"] = search }
        return try await get("/api/questions", query: query)
    }

    func questionTags() async throws -> QuestionTagSummary {
        try await get("/api/questions/tags")
    }

    func updateQuestion(
        id: String,
        tags: [String]?,
        module: String?,
        answer: String?,
        difficulty: Int?
    ) async throws -> BankQuestion {
        var payload: [String: Any] = [:]
        if let tags { payload["tags"] = tags }
        if let module { payload["module"] = module }
        if let answer { payload["answer"] = answer }
        if let difficulty { payload["difficulty"] = difficulty }
        return try await send(
            "/api/questions/\(id)",
            method: "PATCH",
            json: payload
        )
    }

    func deleteQuestion(id: String) async throws {
        let _: [String: Bool] = try await send(
            "/api/questions/\(id)",
            method: "DELETE",
            json: [:]
        )
    }

    func materialDetail(id: String) async throws -> MaterialDetail {
        try await get("/api/materials/\(id)")
    }

    func reindexMaterial(id: String) async throws -> MaterialItem {
        try await send(
            "/api/materials/\(id)/reindex",
            method: "POST",
            json: [:]
        )
    }

    func deleteMaterial(id: String) async throws {
        struct Response: Decodable { let ok: Bool }
        let _: Response = try await perform(
            "/api/materials/\(id)",
            method: "DELETE"
        )
    }

    func seedSample() async throws -> MaterialItem {
        try await send(
            "/api/materials/seed-sample",
            method: "POST",
            json: [:]
        )
    }

    func searchMaterials(
        query: String,
        topK: Int = 8
    ) async throws -> SearchResponse {
        try await send(
            "/api/search",
            method: "POST",
            json: [
                "query": query,
                "subject": "",
                "module": "",
                "top_k": topK,
            ]
        )
    }

    func knowledgeTree() async throws -> [KnowledgeNode] {
        try await get("/api/knowledge/tree")
    }

    func knowledgeCard(kpId: String) async throws -> KnowledgeCardDetail {
        try await get("/api/knowledge/cards/\(kpId)")
    }

    func knowledgeUnits(
        status: String? = nil,
        materialId: String? = nil,
        hasProposal: Bool = false
    ) async throws -> [KnowledgeUnitItem] {
        var query = ["limit": "300"]
        if let status, !status.isEmpty { query["status"] = status }
        if let materialId, !materialId.isEmpty { query["material_id"] = materialId }
        if hasProposal { query["has_proposal"] = "true" }
        return try await get("/api/knowledge/units", query: query)
    }

    func createKnowledgeUnit(
        title: String,
        summary: String,
        steps: [String],
        pitfalls: [String],
        variants: [String],
        knowledgePointName: String
    ) async throws -> KnowledgeUnitItem {
        try await send(
            "/api/knowledge/units",
            method: "POST",
            json: [
                "title": title,
                "summary": summary,
                "steps": steps,
                "pitfalls": pitfalls,
                "variants": variants,
                "knowledge_point_name": knowledgePointName,
            ]
        )
    }

    func updateKnowledgeUnitStatus(id: String, status: String) async throws -> KnowledgeUnitItem {
        try await send(
            "/api/knowledge/units/\(id)",
            method: "PATCH",
            json: ["status": status]
        )
    }

    func updateKnowledgeUnit(
        id: String,
        title: String?,
        summary: String?
    ) async throws -> KnowledgeUnitItem {
        var payload: [String: Any] = [:]
        if let title { payload["title"] = title }
        if let summary { payload["summary"] = summary }
        return try await send(
            "/api/knowledge/units/\(id)",
            method: "PATCH",
            json: payload
        )
    }

    func createPointFromUnit(id: String) async throws -> CreatePointResponse {
        try await send(
            "/api/knowledge/units/\(id)/create-point",
            method: "POST",
            json: [:]
        )
    }

    func skills(status: String? = nil) async throws -> [SkillItem] {
        var query = ["limit": "300"]
        if let status, !status.isEmpty { query["status"] = status }
        return try await get("/api/knowledge/skills", query: query)
    }

    func updateSkillStatus(id: String, status: String) async throws -> SkillItem {
        try await send(
            "/api/knowledge/skills/\(id)",
            method: "PATCH",
            json: ["status": status]
        )
    }

    func updateSkill(
        id: String,
        name: String?,
        summary: String?
    ) async throws -> SkillItem {
        var payload: [String: Any] = [:]
        if let name { payload["name"] = name }
        if let summary { payload["summary"] = summary }
        return try await send(
            "/api/knowledge/skills/\(id)",
            method: "PATCH",
            json: payload
        )
    }

    func extractMaterialUnits(materialId: String) async throws -> ExtractionResult {
        try await send(
            "/api/knowledge/extract/\(materialId)",
            method: "POST",
            json: [:]
        )
    }

    func skillMap() async throws -> SkillMapResponse {
        try await get("/api/knowledge/skill-map", query: ["user_id": userId])
    }

    func skillDetail(id: String) async throws -> SkillDetailResponse {
        try await get("/api/knowledge/skills/\(id)")
    }

    nonisolated func frameURL(_ path: String) -> URL? {
        guard !path.isEmpty else { return nil }
        return URL(string: baseURLString + path)
    }

    func uploadMaterial(data: Data, filename: String, mimeType: String) async throws -> MaterialItem {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: try url("/api/materials/upload"))
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append(
            "Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n"
                .data(using: .utf8)!
        )
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (responseData, response) = try await URLSession.shared.data(for: request)
        try check(response, data: responseData)
        return try decoder.decode(MaterialItem.self, from: responseData)
    }

    func importURL(_ value: String) async throws -> MaterialItem {
        try await send(
            "/api/materials/import-url",
            method: "POST",
            json: ["url": value]
        )
    }
}
