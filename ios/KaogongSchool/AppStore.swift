import Foundation
import SwiftUI

@MainActor
final class AppStore: ObservableObject {
    @Published var settings: SettingsBundle?
    @Published var sessions: [SessionSummary] = []
    @Published var messages: [ChatMessage] = []
    @Published var activeSessionId: String?
    @Published var activeAuthor = "counselor"
    @Published var isStreaming = false
    @Published var errorMessage: String?

    private var streamTask: Task<Void, Never>?
    private var pendingUI: [String: UIComponent] = [:]

    func bootstrap() async {
        await loadSettings()
        await loadSessions()
    }

    func loadSettings() async {
        do {
            settings = try await APIClient.shared.settings()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func loadSessions() async {
        do {
            sessions = try await APIClient.shared.sessions()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func newChat() {
        streamTask?.cancel()
        isStreaming = false
        activeSessionId = nil
        messages = []
        activeAuthor = "counselor"
        pendingUI = [:]
        errorMessage = nil
    }

    func open(session: SessionSummary) async {
        guard !isStreaming else { return }
        activeSessionId = session.id
        do {
            messages = try await APIClient.shared.messages(sessionId: session.id)
            activeAuthor = messages.last(where: { $0.role == .assistant })?.author ?? "counselor"
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func stop() {
        streamTask?.cancel()
        streamTask = nil
        isStreaming = false
        for index in messages.indices {
            messages[index].streaming = false
        }
    }

    func send(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isStreaming else { return }
        errorMessage = nil
        pendingUI = [:]
        messages.append(ChatMessage(role: .user, author: "user", content: trimmed))
        isStreaming = true
        activeAuthor = "counselor"

        streamTask = Task {
            do {
                let stream = await APIClient.shared.streamChat(
                    message: trimmed,
                    sessionId: activeSessionId
                )
                for try await event in stream {
                    handle(event)
                }
            } catch {
                if !Task.isCancelled {
                    errorMessage = error.localizedDescription
                }
            }
            isStreaming = false
            for index in messages.indices where messages[index].streaming {
                messages[index].streaming = false
            }
            await loadSessions()
        }
    }

    private func handle(_ event: ChatEvent) {
        switch event.type {
        case "session":
            if let id = event.sessionId { activeSessionId = id }
        case "delta":
            let author = event.author ?? "counselor"
            activeAuthor = author
            let chunk = event.text ?? ""
            guard !chunk.isEmpty else { return }
            let index = ensureAssistant(author: author)
            messages[index].content += chunk
        case "message":
            let author = event.author ?? "counselor"
            activeAuthor = author
            let index = ensureAssistant(author: author)
            messages[index].content = event.text ?? messages[index].content
            messages[index].streaming = false
            if let ui = pendingUI.removeValue(forKey: author) {
                messages[index].ui = ui
            }
        case "transfer":
            if let to = event.to {
                activeAuthor = to
                messages.append(
                    ChatMessage(
                        role: .system,
                        author: "system",
                        content: "已转接给 \(Self.agentName(to))"
                    )
                )
            }
        case "ui":
            if let component = event.component {
                let author = event.author ?? "counselor"
                if let index = messages.lastIndex(where: { $0.role == .assistant && $0.author == author }) {
                    messages[index].ui = component
                } else {
                    pendingUI[author] = component
                }
            }
        case "error":
            errorMessage = event.message ?? "对话失败"
        default:
            break
        }
    }

    private func ensureAssistant(author: String) -> Int {
        if let index = messages.lastIndex(where: { $0.role == .assistant && $0.author == author && $0.streaming }) {
            return index
        }
        var message = ChatMessage(role: .assistant, author: author, content: "", streaming: true)
        message.ui = pendingUI.removeValue(forKey: author)
        messages.append(message)
        return messages.count - 1
    }

    static func agentName(_ key: String) -> String {
        switch key {
        case "supervisor": return "学习督导"
        case "examiner": return "出卷老师"
        case "grader": return "改卷老师"
        case "collector": return "资料搜集"
        case "organizer": return "资料整理"
        case "knowledge": return "知识点整理"
        default: return "辅导员"
        }
    }
}
