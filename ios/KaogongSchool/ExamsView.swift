import SwiftUI

private enum ExamRoute: Hashable {
    case take(String)
    case report(String)
}

struct ExamsView: View {
    @State private var exams: [ExamSummary] = []
    @State private var attempts: [AttemptSummary] = []
    @State private var loading = true
    @State private var error: String?
    @State private var showGenerate = false
    @State private var path: [ExamRoute] = []

    private var graded: [AttemptSummary] {
        attempts.filter { $0.status == "graded" }
    }

    private var inProgress: [AttemptSummary] {
        attempts.filter { $0.status == "in_progress" }
    }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section {
                    HStack(spacing: 10) {
                        examStat("试卷", "\(exams.count)")
                        examStat("已批改", "\(graded.count)")
                        examStat(
                            "进行中",
                            "\(inProgress.count)",
                            accent: inProgress.count > 0
                        )
                    }
                    .listRowInsets(
                        EdgeInsets(top: 6, leading: 12, bottom: 6, trailing: 12)
                    )
                }

                if let error {
                    Section {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                }

                if !attempts.isEmpty {
                    Section("继续考试与报告") {
                        ForEach(attempts.prefix(10)) { attempt in
                            NavigationLink(
                                value: attempt.status == "graded"
                                    ? ExamRoute.report(attempt.id)
                                    : ExamRoute.take(attempt.examId)
                            ) {
                                attemptRow(attempt)
                            }
                        }
                    }
                }

                Section("最近试卷") {
                    if loading {
                        ProgressView("正在加载试卷…")
                    } else if exams.isEmpty {
                        Text("还没有试卷。点右上角生成一套，或在对话里让出卷老师出卷。")
                            .font(.caption)
                            .foregroundStyle(Theme.muted)
                    } else {
                        ForEach(exams) { exam in
                            NavigationLink(value: ExamRoute.take(exam.id)) {
                                examRow(exam)
                            }
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
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
            .navigationDestination(for: ExamRoute.self) { route in
                switch route {
                case .take(let id):
                    ExamPlayerView(examId: id)
                case .report(let id):
                    ReportView(attemptId: id)
                }
            }
            .sheet(isPresented: $showGenerate) {
                GenerateExamSheet { exam in
                    exams.insert(exam, at: 0)
                    showGenerate = false
                    path.append(.take(exam.id))
                }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        loading = true
        do {
            async let examTask = APIClient.shared.exams()
            async let attemptTask = APIClient.shared.attempts()
            exams = try await examTask
            attempts = try await attemptTask
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func examStat(
        _ title: String,
        _ value: String,
        accent: Bool = false
    ) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.title3.bold())
                .foregroundStyle(accent ? Theme.accent : Theme.ink)
            Text(title)
                .font(.caption2)
                .foregroundStyle(Theme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(accent ? Theme.accentSoft : Theme.paper)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func examRow(_ exam: ExamSummary) -> some View {
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

    private func attemptRow(_ attempt: AttemptSummary) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(attempt.examTitle)
                    .font(.subheadline.bold())
                    .lineLimit(1)
                Spacer()
                Text(attempt.status == "graded" ? "已批改" : "进行中")
                    .font(.caption2.bold())
                    .foregroundStyle(
                        attempt.status == "graded" ? Theme.accent : .orange
                    )
            }
            HStack(spacing: 6) {
                if attempt.status == "graded" {
                    Text("\(Int(attempt.score)) / \(Int(attempt.totalScore)) 分")
                } else {
                    Text("继续作答")
                }
                Text("·")
                Text(
                    Self.shortDate(
                        attempt.submittedAt ?? attempt.startedAt
                    )
                )
            }
            .font(.caption2)
            .foregroundStyle(Theme.muted)
        }
        .padding(.vertical, 2)
    }

    static func shortDate(_ value: String?) -> String {
        guard let value, !value.isEmpty else { return "刚刚" }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [
            .withInternetDateTime,
            .withFractionalSeconds,
        ]
        let date = formatter.date(from: value)
            ?? ISO8601DateFormatter().date(from: value)
        guard let date else { return value }
        let output = DateFormatter()
        output.locale = Locale(identifier: "zh_CN")
        output.dateFormat = "M月d日 HH:mm"
        return output.string(from: date)
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
                Stepper(
                    "AI 原创题：\(aiCount)",
                    value: $aiCount,
                    in: 0...min(10, count)
                )
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
    let examId: String

    @State private var attempt: AttemptStart?
    @State private var answers: [String: String] = [:]
    @State private var remaining = 0
    @State private var report: AttemptReport?
    @State private var busy = false
    @State private var error: String?
    @State private var ticker: Task<Void, Never>?
    @State private var saveTask: Task<Void, Never>?
    @State private var showSubmitConfirm = false
    @State private var showScratchPanel = false
    @State private var scratchIndex = 0
    @State private var scratchHeight: CGFloat = 360
    @State private var scratchWidth: CGFloat = 380
    @State private var viewSize: CGSize = .zero

    /// 横屏时左右分屏，竖屏时上下分屏。
    /// iPad 竖屏的 sizeClass 同样是 regular，所以用实际宽高比判断。
    private var isLandscape: Bool {
        viewSize.width > viewSize.height
    }
    @StateObject private var scratchStore = ScratchStore.shared

    private var answeredCount: Int {
        answers.values.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }.count
    }

    var body: some View {
        Group {
            if let attempt {
                ScrollViewReader { proxy in
                    VStack(spacing: 0) {
                        header(attempt)
                        palette(attempt, proxy: proxy)
                        if isLandscape && showScratchPanel {
                            HStack(spacing: 0) {
                                questionScroll(attempt, proxy: proxy)
                                ScratchSplitPanel(
                                    examId: examId,
                                    questions: scratchQuestions(attempt),
                                    currentIndex: $scratchIndex,
                                    height: $scratchHeight,
                                    panelWidth: $scratchWidth,
                                    axis: .horizontal,
                                    onClose: { showScratchPanel = false }
                                )
                                .transition(.move(edge: .trailing))
                            }
                        } else {
                            questionScroll(attempt, proxy: proxy)
                            if showScratchPanel {
                                ScratchSplitPanel(
                                    examId: examId,
                                    questions: scratchQuestions(attempt),
                                    currentIndex: $scratchIndex,
                                    height: $scratchHeight,
                                    panelWidth: $scratchWidth,
                                    axis: .vertical,
                                    onClose: { showScratchPanel = false }
                                )
                                .transition(.move(edge: .bottom))
                            }
                        }
                    }
                    .animation(.easeInOut(duration: 0.22), value: showScratchPanel)
                }
            } else if let error {
                ContentUnavailableView(
                    "无法开始考试",
                    systemImage: "exclamationmark.triangle",
                    description: Text(error)
                )
            } else {
                ProgressView("正在开始考试…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .background(
            GeometryReader { geometry in
                Color.clear
                    .onAppear { viewSize = geometry.size }
                    .onChange(of: geometry.size) { viewSize = geometry.size }
            }
        )
        .navigationTitle(attempt?.exam.title ?? "考试")
        .navigationBarTitleDisplayMode(.inline)
        .task { await start() }
        .onDisappear {
            ticker?.cancel()
            saveTask?.cancel()
        }
        .confirmationDialog(
            "确认交卷？",
            isPresented: $showSubmitConfirm,
            titleVisibility: .visible
        ) {
            Button("交卷并判分", role: .destructive) {
                Task { await submit() }
            }
            Button("继续作答", role: .cancel) {}
        } message: {
            Text("已作答 \(answeredCount) / \(attempt?.exam.questions.count ?? 0) 题")
        }
    }

    private func scratchQuestions(_ attempt: AttemptStart) -> [(id: String, index: Int)] {
        attempt.exam.questions.enumerated().map {
            (id: $0.element.id, index: $0.offset + 1)
        }
    }

    private func questionScroll(
        _ attempt: AttemptStart,
        proxy: ScrollViewProxy
    ) -> some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 14) {
                if let report {
                    submittedCard(report)
                }
                ForEach(
                    Array(attempt.exam.questions.enumerated()),
                    id: \.element.id
                ) { index, question in
                    questionView(index: index + 1, question: question)
                        .id(question.id)
                }
                if report == nil {
                    Button {
                        showSubmitConfirm = true
                    } label: {
                        Text("交卷并判分")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Theme.solid)
                            .foregroundStyle(Theme.onSolid)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(busy)
                    .padding(.top, 4)
                }
            }
            .padding()
        }
    }

    private func header(_ attempt: AttemptStart) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(attempt.exam.title)
                    .font(.subheadline.bold())
                    .lineLimit(1)
                Text("已答 \(answeredCount) / \(attempt.exam.questions.count) 题")
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
            }
            Spacer()
            Button {
                withAnimation(.easeInOut(duration: 0.22)) {
                    showScratchPanel.toggle()
                }
            } label: {
                Image(
                    systemName: showScratchPanel
                        ? "scribble.variable"
                        : "square.and.pencil"
                )
                .font(.subheadline)
                .foregroundStyle(showScratchPanel ? Theme.accent : Theme.ink)
            }
            .accessibilityLabel(showScratchPanel ? "收起草稿" : "打开草稿")
            Label(timeText, systemImage: "clock")
                .font(.subheadline.bold())
                .foregroundStyle(remaining < 60 ? .red : Theme.ink)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Theme.paper)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Theme.line).frame(height: 1)
        }
    }

    private func palette(
        _ attempt: AttemptStart,
        proxy: ScrollViewProxy
    ) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(
                    Array(attempt.exam.questions.enumerated()),
                    id: \.element.id
                ) { index, question in
                    let answered = !(answers[question.id] ?? "")
                        .trimmingCharacters(in: .whitespaces).isEmpty
                    Button {
                        withAnimation {
                            proxy.scrollTo(question.id, anchor: .top)
                        }
                    } label: {
                        Text("\(index + 1)")
                            .font(.caption2.bold())
                            .frame(width: 30, height: 30)
                            .background(
                                answered ? Theme.accent : Theme.paper
                            )
                            .foregroundStyle(
                                answered ? Theme.onAccent : Theme.muted
                            )
                            .overlay(
                                Circle().stroke(Theme.line)
                            )
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(Theme.background)
    }

    private var timeText: String {
        String(format: "%02d:%02d", max(remaining, 0) / 60, max(remaining, 0) % 60)
    }

    private func start() async {
        do {
            let started = try await APIClient.shared.startAttempt(examId: examId)
            attempt = started
            scratchStore.load(examId: examId)
            answers = started.answers.compactMapValues { value in
                let text = value.display
                return text == "未作答" ? nil : text
            }
            remaining = started.remainingSeconds
            ticker = Task {
                while !Task.isCancelled && remaining > 0 {
                    try? await Task.sleep(for: .seconds(1))
                    if Task.isCancelled { break }
                    remaining = max(0, remaining - 1)
                    if remaining == 0 {
                        await submit(auto: true)
                        break
                    }
                }
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func questionView(index: Int, question: ExamQuestion) -> some View {
        let hasDraft = !(scratchStore.drafts[question.id]?.drawing.isEmpty ?? true)
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("第 \(index) 题")
                    .font(.caption.bold())
                    .foregroundStyle(Theme.accent)
                Text(question.knowledgePointName)
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
                Spacer()
                Button {
                    scratchIndex = index - 1
                    if !showScratchPanel {
                        withAnimation(.easeInOut(duration: 0.22)) {
                            showScratchPanel = true
                        }
                    }
                } label: {
                    Label(
                        hasDraft ? "草稿已写" : "草稿",
                        systemImage: hasDraft
                            ? "scribble.variable"
                            : "square.and.pencil"
                    )
                    .font(.caption2)
                    .foregroundStyle(hasDraft ? Theme.accent : Theme.muted)
                }
                .buttonStyle(.plain)
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
                    .scrollContentBackground(.hidden)
                    .foregroundStyle(Theme.ink)
                    .background(Theme.paper)
                    .overlay(
                        RoundedRectangle(cornerRadius: 10).stroke(Theme.line)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            } else {
                ForEach(question.options) { option in
                    Button {
                        answers[question.id] = option.key
                        scheduleAutosave()
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
                                        ? Theme.onAccent : Theme.ink
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
            set: {
                answers[id] = $0
                scheduleAutosave()
            }
        )
    }

    private func scheduleAutosave() {
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(for: .seconds(1))
            guard !Task.isCancelled, let attempt else { return }
            try? await APIClient.shared.saveAnswers(
                attemptId: attempt.attemptId,
                answers: payload(attempt)
            )
        }
    }

    private func payload(_ attempt: AttemptStart) -> [[String: Any]] {
        attempt.exam.questions.map { question in
            ["question_id": question.id, "response": answers[question.id] ?? ""]
        }
    }

    private func submit(auto: Bool = false) async {
        guard let attempt, !busy else { return }
        if report != nil { return }
        busy = true
        defer { busy = false }
        do {
            let result = try await APIClient.shared.submitAttempt(
                attemptId: attempt.attemptId,
                answers: payload(attempt)
            )
            ticker?.cancel()
            report = result
        } catch {
            if !auto {
                self.error = error.localizedDescription
            }
        }
    }

    private func submittedCard(_ report: AttemptReport) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("已交卷")
                    .font(.headline)
                Spacer()
                Text("\(Int(report.score)) / \(Int(report.totalScore)) 分")
                    .font(.headline)
                    .foregroundStyle(Theme.accent)
            }
            Text(report.summary)
                .font(.caption)
                .foregroundStyle(Theme.muted)
            NavigationLink {
                ReportView(attemptId: report.attemptId)
            } label: {
                HStack {
                    Text("查看完整报告")
                        .font(.subheadline.bold())
                    Spacer()
                    Image(systemName: "arrow.right")
                }
                .padding(10)
                .background(Theme.accentSoft)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .padding(12)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

struct ReportView: View {
    let attemptId: String

    @State private var report: AttemptReport?
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        Group {
            if loading {
                ProgressView("正在读取批改报告…")
            } else if let report {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        summaryCard(report)
                        if !report.masteryChanges.isEmpty {
                            masteryCard(report.masteryChanges)
                        }
                        if let changes = report.skillChanges, !changes.isEmpty {
                            skillChangeCard(changes)
                        }
                        ForEach(Array(report.questions.enumerated()), id: \.element.id) {
                            index, feedback in
                            feedbackCard(feedback, index: index)
                        }
                    }
                    .padding()
                }
            } else {
                ContentUnavailableView(
                    "报告不可用",
                    systemImage: "doc.text.magnifyingglass",
                    description: Text(error ?? "没有找到这份报告。")
                )
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("批改报告")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
    }

    private func load() async {
        loading = true
        defer { loading = false }
        do {
            report = try await APIClient.shared.attemptReport(attemptId: attemptId)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func summaryCard(_ report: AttemptReport) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text("\(Int(report.score))")
                    .font(.system(size: 40, weight: .bold))
                    .foregroundStyle(Theme.ink)
                Text("/ \(Int(report.totalScore)) 分")
                    .font(.subheadline)
                    .foregroundStyle(Theme.muted)
                Spacer()
                Text("\(Int(report.percentage))%")
                    .font(.title3.bold())
                    .foregroundStyle(Theme.accent)
            }
            Text(report.examTitle)
                .font(.subheadline)
                .foregroundStyle(Theme.muted)
            Text(report.summary)
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 12) {
                Text("错题本 \(report.errorBookAdded)")
                Text("掌握度变化 \(report.masteryChanges.count) 个")
            }
            .font(.caption2)
            .foregroundStyle(Theme.muted)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func masteryCard(_ changes: [MasteryChange]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("掌握度变化")
                .font(.headline)
            ForEach(changes) { change in
                HStack {
                    Text(change.knowledgePointName)
                        .font(.subheadline)
                    Spacer()
                    Text("\(Int(change.before)) → \(Int(change.after))")
                        .font(.caption)
                        .foregroundStyle(
                            change.after >= change.before ? Theme.accent : .red
                        )
                }
            }
        }
        .padding(14)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func skillChangeCard(_ changes: [SkillChange]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("技能掌握度")
                .font(.headline)
            ForEach(changes) { change in
                HStack {
                    Text(change.skillName).font(.subheadline)
                    Spacer()
                    Text("\(Int(change.before)) → \(Int(change.after))")
                        .font(.caption)
                        .foregroundStyle(
                            change.after >= change.before ? Theme.accent : .red
                        )
                }
            }
            Text("可到「知识 → 技能地图」查看完整状态")
                .font(.caption2)
                .foregroundStyle(Theme.muted)
        }
        .padding(14)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func feedbackCard(_ feedback: QuestionFeedback, index: Int) -> some View {
        let correct = feedback.isCorrect == true
        let correctKeys = feedback.correctAnswer?.keys ?? []
        let userKeys = feedback.userAnswer?.keys ?? []
        return VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 8) {
                Text("第 \(index + 1) 题")
                    .font(.caption.bold())
                    .foregroundStyle(Theme.ink)
                Text(typeLabel(feedback.type))
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Theme.line.opacity(0.4))
                    .clipShape(Capsule())
                if !feedback.knowledgePointName.isEmpty {
                    Text(feedback.knowledgePointName)
                        .font(.caption2)
                        .foregroundStyle(Theme.muted)
                }
                Spacer()
                Text(correct ? "正确" : "错误")
                    .font(.caption2.bold())
                    .foregroundStyle(correct ? Theme.accent : .red)
                Text("\(feedback.score)/\(feedback.maxScore)")
                    .font(.caption.bold())
            }
            Text(feedback.stem)
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)

            if feedback.type == "short" {
                answerBlock("你的答案", feedback.userAnswer?.display ?? "未作答", correct)
                answerBlock(
                    "参考答案",
                    feedback.correctAnswer?.display ?? "未提供",
                    true,
                    neutral: true
                )
                if !feedback.rubric.isEmpty {
                    VStack(alignment: .leading, spacing: 3) {
                        ForEach(feedback.rubric) { point in
                            let hit = feedback.hitPoints.contains {
                                $0.point == point.point
                            }
                            HStack(alignment: .top, spacing: 5) {
                                Image(
                                    systemName: hit
                                        ? "checkmark.circle.fill"
                                        : "circle"
                                )
                                .foregroundStyle(hit ? Theme.accent : Theme.muted)
                                Text("\(point.point)（\(Int(point.score)) 分）")
                                    .font(.caption2)
                                    .foregroundStyle(hit ? Theme.ink : Theme.muted)
                            }
                        }
                        if !feedback.missedPoints.isEmpty {
                            Text("未覆盖：\(feedback.missedPoints.joined(separator: "、"))")
                                .font(.caption2)
                                .foregroundStyle(.red)
                        }
                    }
                    .padding(8)
                    .background(Theme.paper)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            } else {
                ForEach(feedback.options) { option in
                    let isCorrectOption = correctKeys.contains(option.key)
                    let isUserOption = userKeys.contains(option.key)
                    HStack(alignment: .top, spacing: 8) {
                        Text(option.key)
                            .font(.caption.bold())
                            .frame(width: 20, height: 20)
                            .background(
                                isCorrectOption
                                    ? Theme.accent
                                    : isUserOption ? Color.red.opacity(0.7)
                                    : Theme.line.opacity(0.5)
                            )
                            .foregroundStyle(
                                isCorrectOption
                                    ? Theme.onAccent
                                    : isUserOption ? .white : Theme.ink
                            )
                            .clipShape(Circle())
                        Text(option.text)
                            .font(.subheadline)
                        Spacer()
                    }
                    .padding(8)
                    .background(
                        isCorrectOption
                            ? Theme.accentSoft
                            : isUserOption ? Color.red.opacity(0.08)
                            : Theme.paper
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                Text(
                    "你的答案：\(feedback.userAnswer?.display ?? "未作答") · 正确答案：\(feedback.correctAnswer?.display ?? "—")"
                )
                .font(.caption2)
                .foregroundStyle(Theme.muted)
            }

            if !feedback.comment.isEmpty {
                MarkdownText(content: feedback.comment)
                    .font(.caption)
            }
            if !feedback.explanation.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    Text("解析")
                        .font(.caption.bold())
                        .foregroundStyle(Theme.muted)
                    MarkdownText(content: feedback.explanation)
                        .font(.caption)
                }
            }
            if let skills = feedback.skills, !skills.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    Text("这题对应的技能")
                        .font(.caption.bold())
                        .foregroundStyle(Theme.accent)
                    ForEach(skills.prefix(2)) { skill in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(skill.name).font(.caption.weight(.medium))
                            if let pattern = skill.examPatterns.first {
                                Text("怎么考：\(pattern)")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.muted)
                            }
                            if !skill.signals.isEmpty {
                                Text("识别信号：\(skill.signals.prefix(3).joined(separator: "、"))")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.muted)
                            }
                            if !skill.steps.isEmpty {
                                Text("步骤：\(skill.steps.prefix(2).joined(separator: " → "))")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.muted)
                            }
                        }
                        .padding(8)
                        .background(Theme.accentSoft)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }
            }
            if !feedback.variants.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("举一反三")
                        .font(.caption.bold())
                        .foregroundStyle(Theme.accent)
                    ForEach(feedback.variants) { variant in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(variant.stem)
                                .font(.caption)
                            if let answer = variant.answer {
                                Text("答案：\(answer)")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.muted)
                            }
                        }
                        .padding(7)
                        .background(Theme.accentSoft)
                        .clipShape(RoundedRectangle(cornerRadius: 7))
                    }
                }
            }
        }
        .padding(14)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func answerBlock(
        _ title: String,
        _ text: String,
        _ correct: Bool,
        neutral: Bool = false
    ) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.caption2.bold())
                .foregroundStyle(Theme.muted)
            Text(text)
                .font(.caption)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            neutral
                ? Theme.paper
                : correct ? Theme.accentSoft : Color.red.opacity(0.08)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func typeLabel(_ type: String) -> String {
        switch type {
        case "multiple": return "多选"
        case "short": return "简答"
        default: return "单选"
        }
    }
}
