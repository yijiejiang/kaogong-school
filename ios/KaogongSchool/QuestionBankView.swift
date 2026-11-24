import SwiftUI

struct QuestionBankView: View {
    @State private var questions: [BankQuestion] = []
    @State private var tags: QuestionTagSummary?
    @State private var loading = true
    @State private var error: String?
    @State private var query = ""
    @State private var activeTag = ""
    @State private var activeModule = ""
    @State private var selected: BankQuestion?

    private var modules: [QuestionTagSummary.ModuleCount] {
        tags?.modules ?? []
    }

    private var tagList: [QuestionTagSummary.TagCount] {
        Array((tags?.tags ?? []).prefix(30))
    }

    var body: some View {
        NavigationStack {
            Group {
                if loading {
                    ProgressView("正在加载题库…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error {
                    ContentUnavailableView(
                        "题库不可用",
                        systemImage: "doc.questionmark",
                        description: Text(error)
                    )
                } else {
                    List {
                        Section {
                            HStack(spacing: 8) {
                                Image(systemName: "magnifyingglass")
                                    .foregroundStyle(Theme.muted)
                                TextField("搜索题干", text: $query)
                                    .textInputAutocapitalization(.never)
                                    .autocorrectionDisabled()
                                    .onSubmit { Task { await load() } }
                            }
                            Picker("模块", selection: $activeModule) {
                                Text("全部模块").tag("")
                                ForEach(modules) { item in
                                    Text("\(item.module)（\(item.count)）")
                                        .tag(item.module)
                                }
                            }
                            .pickerStyle(.menu)
                            .onChange(of: activeModule) {
                                Task { await load() }
                            }
                        }

                        if !tagList.isEmpty {
                            Section("按标签筛选") {
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 6) {
                                        Button {
                                            activeTag = ""
                                            Task { await load() }
                                        } label: {
                                            Text("全部")
                                                .font(.caption2.weight(.medium))
                                                .padding(.horizontal, 10)
                                                .padding(.vertical, 5)
                                                .background(
                                                    activeTag.isEmpty
                                                        ? Theme.accent
                                                        : Theme.paper
                                                )
                                                .foregroundStyle(
                                                    activeTag.isEmpty
                                                        ? Theme.onAccent
                                                        : Theme.muted
                                                )
                                                .clipShape(Capsule())
                                        }
                                        .buttonStyle(.plain)
                                        ForEach(tagList) { item in
                                            Button {
                                                activeTag = activeTag == item.tag ? "" : item.tag
                                                Task { await load() }
                                            } label: {
                                                Text("\(item.tag) \(item.count)")
                                                    .font(.caption2.weight(.medium))
                                                    .padding(.horizontal, 10)
                                                    .padding(.vertical, 5)
                                                    .background(
                                                        activeTag == item.tag
                                                            ? Theme.accent
                                                            : Theme.paper
                                                    )
                                                    .foregroundStyle(
                                                        activeTag == item.tag
                                                            ? Theme.onAccent
                                                            : Theme.muted
                                                    )
                                                    .clipShape(Capsule())
                                            }
                                            .buttonStyle(.plain)
                                        }
                                    }
                                    .padding(.vertical, 2)
                                }
                                .listRowInsets(
                                    EdgeInsets(top: 6, leading: 12, bottom: 6, trailing: 12)
                                )
                            }
                        }

                        Section("题目（\(questions.count)）") {
                            if questions.isEmpty {
                                Text("题库还是空的。上传带题目的资料后会自动识别。")
                                    .font(.caption)
                                    .foregroundStyle(Theme.muted)
                            } else {
                                ForEach(questions) { question in
                                    Button {
                                        selected = question
                                    } label: {
                                        questionRow(question)
                                    }
                                    .buttonStyle(.plain)
                                    .swipeActions(edge: .trailing) {
                                        Button("删除", role: .destructive) {
                                            Task { await remove(question) }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("题库")
            .navigationBarTitleDisplayMode(.inline)
            .task { await load() }
            .refreshable { await load() }
            .sheet(item: $selected) { question in
                QuestionEditSheet(question: question) {
                    selected = nil
                    Task { await load() }
                }
            }
        }
    }

    private func questionRow(_ question: BankQuestion) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Text(question.module)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Theme.accentSoft)
                    .foregroundStyle(Theme.accent)
                    .clipShape(Capsule())
                Text("难度 \(question.difficulty)")
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
                if !question.answer.isEmpty {
                    Text("答案 \(question.answer)")
                        .font(.caption2)
                        .foregroundStyle(Theme.muted)
                }
                Spacer()
            }
            Text(question.stem)
                .font(.caption)
                .foregroundStyle(Theme.ink)
                .lineLimit(3)
            if !question.tags.isEmpty {
                HStack(spacing: 4) {
                    ForEach(question.tags.prefix(4), id: \.self) { tag in
                        Text(tag)
                            .font(.caption2)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1)
                            .background(Theme.line.opacity(0.35))
                            .clipShape(Capsule())
                    }
                }
            }
        }
        .padding(.vertical, 2)
    }

    private func load() async {
        do {
            async let listTask = APIClient.shared.questions(
                tag: activeTag,
                module: activeModule,
                search: query
            )
            async let tagTask = APIClient.shared.questionTags()
            questions = try await listTask
            tags = try await tagTask
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func remove(_ question: BankQuestion) async {
        do {
            try await APIClient.shared.deleteQuestion(id: question.id)
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct QuestionEditSheet: View {
    let question: BankQuestion
    let onChanged: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var tags: String
    @State private var module: String
    @State private var answer: String
    @State private var difficulty: Int
    @State private var busy = false
    @State private var error: String?

    init(question: BankQuestion, onChanged: @escaping () -> Void) {
        self.question = question
        self.onChanged = onChanged
        _tags = State(initialValue: question.tags.joined(separator: "、"))
        _module = State(initialValue: question.module)
        _answer = State(initialValue: question.answer)
        _difficulty = State(initialValue: question.difficulty)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(question.stem)
                        .font(.subheadline)
                }
                Section("分类") {
                    TextField("模块", text: $module)
                    TextField("标签（用顿号分隔）", text: $tags)
                    TextField("答案", text: $answer)
                    Picker("难度", selection: $difficulty) {
                        ForEach(1...5, id: \.self) { value in
                            Text("\(value)").tag(value)
                        }
                    }
                }
                if let error {
                    Section {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("编辑题目")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") { Task { await save() } }
                        .disabled(busy)
                }
            }
        }
    }

    private func save() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await APIClient.shared.updateQuestion(
                id: question.id,
                tags: tags
                    .split(whereSeparator: { "、,，;； ".contains($0) })
                    .map(String.init)
                    .filter { !$0.isEmpty },
                module: module,
                answer: answer,
                difficulty: difficulty
            )
            onChanged()
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
