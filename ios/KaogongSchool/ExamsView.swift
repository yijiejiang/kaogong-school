import SwiftUI

struct ExamsView: View {
    @State private var exams: [ExamSummary] = []
    @State private var loading = true
    @State private var error: String?
    @State private var showGenerate = false
    @State private var path: [ExamSummary] = []

    var body: some View {
        NavigationStack(path: $path) {
            Group {
                if loading {
                    ProgressView("正在加载试卷…")
                } else if exams.isEmpty {
                    ContentUnavailableView(
                        "还没有试卷",
                        systemImage: "doc.text",
                        description: Text("点右上角生成一套，或在对话里让出卷老师出卷。")
                    )
                } else {
                    List(exams) { exam in
                        NavigationLink(value: exam) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(exam.title)
                                    .font(.subheadline.bold())
                                HStack(spacing: 6) {
                                    Text("\(exam.questionCount) 题")
                                    Text("·")
                                    Text("\(exam.durationMinutes) 分钟")
                                    if let ai = exam.aiGenerated, ai > 0 {
                                        Text("· AI \(ai) 题")
                                            .foregroundStyle(Theme.accent)
                                    }
                                }
                                .font(.caption2)
                                .foregroundStyle(Theme.muted)
                            }
                            .padding(.vertical, 2)
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("考试中心")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showGenerate = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .navigationDestination(for: ExamSummary.self) { exam in
                ExamPlayerView(exam: exam)
            }
            .sheet(isPresented: $showGenerate) {
                GenerateExamSheet { exam in
                    exams.insert(exam, at: 0)
                    showGenerate = false
                    path.append(exam)
                }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        loading = true
        do {
            exams = try await APIClient.shared.exams()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }
}

private struct GenerateExamSheet: View {
    @Environment(\.dismiss) private var dismiss
    let onCreate: (ExamSummary) -> Void

    @State private var subject = "行测"
    @State private var module = "资料分析"
    @State private var count = 10
    @State private var minutes = 15
    @State private var difficulty = "medium"
    @State private var aiCount = 0
    @State private var busy = false
    @State private var error: String?

    private let modules: [String: [String]] = [
        "行测": ["资料分析", "言语理解与表达", "数量关系", "判断推理", "常识判断"],
        "申论": ["归纳概括", "综合分析", "提出对策", "贯彻执行", "文章写作"],
    ]

    var body: some View {
        NavigationStack {
            Form {
                Picker("科目", selection: $subject) {
                    Text("行测").tag("行测")
                    Text("申论").tag("申论")
                }
                .onChange(of: subject) {
                    module = modules[subject]?.first ?? "资料分析"
                }
                Picker("模块", selection: $module) {
                    ForEach(modules[subject] ?? [], id: \.self) { item in
                        Text(item).tag(item)
                    }
                }
                Stepper("题量：\(count)", value: $count, in: 1...60)
                Stepper("限时：\(minutes) 分钟", value: $minutes, in: 5...180, step: 5)
                Picker("难度", selection: $difficulty) {
                    Text("简单").tag("easy")
                    Text("中等").tag("medium")
                    Text("困难").tag("hard")
                    Text("混合").tag("mixed")
                }
                Stepper("AI 原创题：\(aiCount)", value: $aiCount, in: 0...min(10, count))
                if let error {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }
            .navigationTitle("生成试卷")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task { await create() }
                    } label: {
                        if busy { ProgressView() } else { Text("生成") }
                    }
                    .disabled(busy)
                }
            }
        }
    }

    private func create() async {
        busy = true
        error = nil
        do {
            let exam = try await APIClient.shared.generateExam(
                subject: subject,
                module: module,
                count: count,
                minutes: minutes,
                difficulty: difficulty,
                aiCount: min(aiCount, count)
            )
            if exam.warning?.isEmpty == false {
                error = exam.warning
            } else {
                onCreate(exam)
            }
        } catch {
            self.error = error.localizedDescription
        }
        busy = false
    }
}

private struct ExamPlayerView: View {
    let exam: ExamSummary

    @State private var attempt: AttemptStart?
    @State private var answers: [String: String] = [:]
    @State private var remaining = 0
    @State private var report: AttemptReport?
    @State private var busy = false
    @State private var error: String?
    @State private var ticker: Task<Void, Never>?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if let attempt {
                    HStack {
                        Text(attempt.exam.title)
                            .font(.headline)
                        Spacer()
                        Label(timeText, systemImage: "clock")
                            .font(.caption)
                            .foregroundStyle(remaining < 60 ? .red : Theme.muted)
                    }

                    if let report {
                        reportCard(report)
                    }

                    ForEach(Array(attempt.exam.questions.enumerated()), id: \.element.id) { index, question in
                        questionView(index: index + 1, question: question)
                    }

                    Button {
                        Task { await submit() }
                    } label: {
                        HStack {
                            Spacer()
                            if busy {
                                ProgressView().tint(.white)
                            } else {
                                Text("交卷并判分").bold()
                            }
                            Spacer()
                        }
                        .padding(.vertical, 12)
                        .background(Theme.ink)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(busy)
                } else if let error {
                    Text(error)
                        .font(.subheadline)
                        .foregroundStyle(.red)
                } else {
                    ProgressView("正在开始考试…")
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                }
            }
            .padding()
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle(exam.module)
        .navigationBarTitleDisplayMode(.inline)
        .task { await start() }
        .onDisappear { ticker?.cancel() }
    }

    private var timeText: String {
        String(format: "%02d:%02d", remaining / 60, remaining % 60)
    }

    private func start() async {
        do {
            let started = try await APIClient.shared.startAttempt(examId: exam.id)
            attempt = started
            remaining = started.remainingSeconds
            ticker = Task {
                while !Task.isCancelled && remaining > 0 {
                    try? await Task.sleep(for: .seconds(1))
                    if Task.isCancelled { break }
                    remaining = max(0, remaining - 1)
                }
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func questionView(index: Int, question: ExamQuestion) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("第 \(index) 题")
                    .font(.caption.bold())
                    .foregroundStyle(Theme.accent)
                Text(question.knowledgePointName)
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
                Spacer()
                Text("\(Int(question.score)) 分")
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
            }
            Text(question.stem)
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)

            if question.type == "short" {
                TextEditor(text: binding(for: question.id))
                    .frame(minHeight: 100)
                    .padding(6)
                    .background(Theme.paper)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            } else {
                ForEach(question.options) { option in
                    Button {
                        answers[question.id] = option.key
                    } label: {
                        HStack(alignment: .top, spacing: 8) {
                            Text(option.key)
                                .font(.caption.bold())
                                .frame(width: 22, height: 22)
                                .background(
                                    answers[question.id] == option.key
                                        ? Theme.accent : Theme.line.opacity(0.5)
                                )
                                .foregroundStyle(
                                    answers[question.id] == option.key
                                        ? .white : Theme.ink
                                )
                                .clipShape(Circle())
                            Text(option.text)
                                .font(.subheadline)
                                .multilineTextAlignment(.leading)
                            Spacer()
                        }
                        .padding(8)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(12)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func binding(for id: String) -> Binding<String> {
        Binding(
            get: { answers[id] ?? "" },
            set: { answers[id] = $0 }
        )
    }

    private func submit() async {
        guard let attempt else { return }
        busy = true
        defer { busy = false }
        let payload = attempt.exam.questions.map { question in
            ["question_id": question.id, "response": answers[question.id] ?? ""]
        }
        do {
            report = try await APIClient.shared.submitAttempt(
                attemptId: attempt.attemptId,
                answers: payload
            )
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func reportCard(_ report: AttemptReport) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("得分 \(Int(report.score)) / \(Int(report.totalScore))（\(Int(report.percentage))%）")
                .font(.headline)
            Text(report.summary)
                .font(.caption)
                .foregroundStyle(Theme.muted)
            Text("错题本新增 \(report.errorBookAdded) 题；详细解析可在网页报告页查看。")
                .font(.caption2)
                .foregroundStyle(Theme.muted)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.accentSoft)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
