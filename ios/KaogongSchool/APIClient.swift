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

    func usage() async throws -> UsageSummary {
        try await get("/api/analytics/usage", query: ["user_id": userId, "days": "14"])
    }

    func materials() async throws -> [MaterialItem] {
        try await get("/api/materials")
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
