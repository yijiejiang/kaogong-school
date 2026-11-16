import AVFoundation
import SwiftUI

final class SpeechReader: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {
    @Published var speakingId: String?
    private let synthesizer = AVSpeechSynthesizer()

    override init() {
        super.init()
        synthesizer.delegate = self
    }

    func toggle(id: String, text: String) {
        if speakingId == id {
            synthesizer.stopSpeaking(at: .immediate)
            speakingId = nil
            return
        }
        synthesizer.stopSpeaking(at: .immediate)
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "zh-CN")
        utterance.rate = 0.5
        speakingId = id
        synthesizer.speak(utterance)
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        speakingId = nil
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        speakingId = nil
    }
}

struct ChatView: View {
    @EnvironmentObject private var store: AppStore
    @StateObject private var speech = SpeechReader()
    @State private var input = ""
    @State private var showSessions = false

    private let quickPrompts = [
        "我最近学得怎么样？帮我看看学情。",
        "帮我出一套资料分析小卷。",
        "根据我目前的情况，帮我安排本周的学习计划。",
        "资料分析速算技巧有哪些？",
    ]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                header
                if let error = store.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(Color.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal)
                        .padding(.vertical, 6)
                        .background(Color.red.opacity(0.08))
                }
                messages
                inputBar
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("考公私塾")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        showSessions = true
                    } label: {
                        Image(systemName: "list.bullet")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        store.newChat()
                    } label: {
                        Image(systemName: "square.and.pencil")
                    }
                }
            }
            .sheet(isPresented: $showSessions) {
                SessionsSheet()
                    .environmentObject(store)
            }
        }
    }

    private var header: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle().fill(Theme.accentSoft)
                Text(String(AppStore.agentName(store.activeAuthor).prefix(1)))
                    .font(.subheadline.bold())
                    .foregroundStyle(Theme.accent)
            }
            .frame(width: 38, height: 38)

            VStack(alignment: .leading, spacing: 2) {
                Text(AppStore.agentName(store.activeAuthor))
                    .font(.subheadline.bold())
                Text("辅导员主入口，会自动转接给合适的老师")
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
            }
            Spacer()
            if let settings = store.settings {
                Text(settings.profile.name)
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
                if settings.server.mockMode {
                    Text("演示")
                        .font(.caption2.bold())
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(Theme.accentSoft)
                        .foregroundStyle(Theme.accent)
                        .clipShape(Capsule())
                }
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Theme.paper)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Theme.line).frame(height: 1)
        }
    }

    private var messages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 14) {
                    if store.messages.isEmpty {
                        emptyState
                    }
                    ForEach(store.messages) { message in
                        MessageRow(message: message, speech: speech)
                            .id(message.id)
                    }
                    Color.clear.frame(height: 1).id("bottom")
                }
                .padding(.horizontal)
                .padding(.vertical, 14)
            }
            .onChange(of: store.messages.count) {
                withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
            }
            .onChange(of: store.messages.last?.content.count) {
                proxy.scrollTo("bottom", anchor: .bottom)
            }
        }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("今天想学点什么？")
                .font(.title3.bold())
            Text("可以直接问学习方法、看学情、出小卷、排计划，或者上传资料后让我基于资料回答。")
                .font(.subheadline)
                .foregroundStyle(Theme.muted)

            ForEach(quickPrompts, id: \.self) { prompt in
                Button {
                    store.send(prompt)
                } label: {
                    HStack {
                        Text(prompt)
                            .font(.subheadline)
                            .multilineTextAlignment(.leading)
                        Spacer()
                        Image(systemName: "arrow.up.right")
                            .font(.caption)
                    }
                    .padding(12)
                    .background(Theme.paper)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12).stroke(Theme.line)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 20)
    }

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField("问辅导员，或者说出你想做的事…", text: $input, axis: .vertical)
                .lineLimit(1...4)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Theme.paper)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16).stroke(Theme.line)
                )

            if store.isStreaming {
                Button {
                    store.stop()
                } label: {
                    Image(systemName: "stop.fill")
                        .frame(width: 40, height: 40)
                        .background(Theme.ink)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
            } else {
                Button {
                    let text = input
                    input = ""
                    store.send(text)
                } label: {
                    Image(systemName: "arrow.up")
                        .frame(width: 40, height: 40)
                        .background(
                            input.trimmingCharacters(in: .whitespaces).isEmpty
                                ? Theme.line : Theme.accent
                        )
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                .disabled(input.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Theme.paper)
    }
}

private struct MessageRow: View {
    let message: ChatMessage
    @ObservedObject var speech: SpeechReader

    var body: some View {
        switch message.role {
        case .system:
            Text(message.content)
                .font(.caption2)
                .foregroundStyle(Theme.muted)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(Theme.line.opacity(0.45))
                .clipShape(Capsule())
                .frame(maxWidth: .infinity)
        case .user:
            HStack {
                Spacer(minLength: 40)
                Text(message.content)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(Theme.ink)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
            }
        case .assistant:
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    Circle().fill(Theme.accentSoft)
                    Text(String(AppStore.agentName(message.author).prefix(1)))
                        .font(.caption.bold())
                        .foregroundStyle(Theme.accent)
                }
                .frame(width: 30, height: 30)

                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        Text(AppStore.agentName(message.author))
                            .font(.caption2.bold())
                            .foregroundStyle(Theme.ink)
                        if message.streaming {
                            Text("正在输入…")
                                .font(.caption2)
                                .foregroundStyle(Theme.accent)
                        } else if !message.content.isEmpty {
                            Button {
                                speech.toggle(id: message.id, text: message.content)
                            } label: {
                                Label(
                                    speech.speakingId == message.id ? "停止" : "朗读",
                                    systemImage: speech.speakingId == message.id
                                        ? "speaker.slash" : "speaker.wave.2"
                                )
                                .font(.caption2)
                                .foregroundStyle(Theme.muted)
                            }
                        }
                    }

                    if message.content.isEmpty && message.streaming {
                        ProgressView()
                            .controlSize(.small)
                    } else if !message.content.isEmpty {
                        Text(message.content)
                            .font(.subheadline)
                            .foregroundStyle(Theme.ink)
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Theme.paper)
                            .overlay(
                                RoundedRectangle(cornerRadius: 14).stroke(Theme.line)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                    }

                    if let ui = message.ui, ui.type == "exam_card" {
                        ExamCardView(ui: ui)
                    }
                }
            }
        }
    }
}

private struct ExamCardView: View {
    let ui: UIComponent

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "doc.text")
                    .foregroundStyle(Theme.accent)
                Text(ui.title ?? "试卷已生成")
                    .font(.subheadline.bold())
                Spacer()
                if let count = ui.aiGenerated, count > 0 {
                    Text("AI \(count) 题")
                        .font(.caption2)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Theme.accentSoft)
                        .clipShape(Capsule())
                }
            }
            Text(ui.subtitle ?? "去考试中心开始作答")
                .font(.caption)
                .foregroundStyle(Theme.muted)
            Text("打开「考试」标签即可开始；交卷后改卷老师会给出报告。")
                .font(.caption2)
                .foregroundStyle(Theme.muted)
        }
        .padding(12)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

private struct SessionsSheet: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Button {
                    store.newChat()
                    dismiss()
                } label: {
                    Label("新对话", systemImage: "plus.circle.fill")
                }
                ForEach(store.sessions) { session in
                    Button {
                        Task {
                            await store.open(session: session)
                            dismiss()
                        }
                    } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(session.title.isEmpty ? "新会话" : session.title)
                                .font(.subheadline)
                            Text(session.id)
                                .font(.caption2)
                                .foregroundStyle(Theme.muted)
                        }
                    }
                }
            }
            .navigationTitle("最近对话")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("关闭") { dismiss() }
                }
            }
        }
    }
}
