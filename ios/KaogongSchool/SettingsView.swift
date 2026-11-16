import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppStore
    @AppStorage("apiBaseURL") private var apiBaseURL = "http://127.0.0.1:8000"
    @AppStorage("userId") private var userId = "local-user"

    @State private var profile = SettingsBundle.Profile(
        name: "同学",
        targetExam: "国考",
        examDate: "",
        dailyMinutes: 120
    )
    @State private var llmApiBase = ""
    @State private var defaultModel = ""
    @State private var embeddingModel = ""
    @State private var embeddingApiBase = ""
    @State private var embeddingApiKey = ""
    @State private var embeddingKeySet = false
    @State private var asrModel = ""
    @State private var asrApiBase = ""
    @State private var asrApiKey = ""
    @State private var asrKeySet = false
    @State private var inputPrice = 0.0
    @State private var outputPrice = 0.0
    @State private var apiKey = ""
    @State private var apiKeySet = false
    @State private var roles: [String: SettingsBundle.RoleConfig] = [:]
    @State private var clearedRoles: Set<String> = []
    @State private var modelOptions: [String] = []
    @State private var modelLoading = false
    @State private var server: SettingsBundle.Server?
    @State private var loading = true
    @State private var saving = false
    @State private var notice: String?
    @State private var noticeIsError = false

    private let targets = ["国考", "省考", "事业单位", "选调生", "其他"]
    private let roleKeys = [
        "counselor",
        "supervisor",
        "examiner",
        "collector",
        "organizer",
        "knowledge",
        "grader",
    ]

    private var emptyRole: SettingsBundle.RoleConfig {
        SettingsBundle.RoleConfig(
            model: "",
            temperature: 0.3,
            maxTokens: 0,
            topP: 0,
            apiBase: "",
            apiKey: "",
            apiKeySet: false
        )
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("连接") {
                    TextField("后端 Base URL", text: $apiBaseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    TextField("学习者 ID", text: $userId)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .onSubmit {
                            Task { await load() }
                        }
                    if let server {
                        LabeledContent("后端状态", value: server.mockMode ? "本地演示模式" : "真实模型")
                        LabeledContent("数据库", value: server.database)
                    }
                }

                Section("学习档案") {
                    TextField("称呼", text: $profile.name)
                    Picker("目标考试", selection: $profile.targetExam) {
                        ForEach(targets, id: \.self) { item in
                            Text(item).tag(item)
                        }
                    }
                    TextField("考试日期（YYYY-MM-DD）", text: $profile.examDate)
                        .keyboardType(.numbersAndPunctuation)
                    Stepper(
                        "每天 \(profile.dailyMinutes) 分钟",
                        value: $profile.dailyMinutes,
                        in: 15...720,
                        step: 15
                    )
                }

                Section("模型") {
                    TextField("LLM Base URL（供应商）", text: $llmApiBase)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    TextField("默认模型", text: $defaultModel)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    HStack {
                        Button {
                            Task { await fetchModels() }
                        } label: {
                            Label(
                                modelLoading ? "获取中…" : "获取模型",
                                systemImage: "arrow.clockwise"
                            )
                        }
                        .disabled(modelLoading)
                        if !modelOptions.isEmpty {
                            Menu("从列表选择") {
                                ForEach(modelOptions, id: \.self) { model in
                                    Button(model) { defaultModel = model }
                                }
                            }
                        }
                    }
                    SecureField(
                        apiKeySet ? "已配置，留空保持不变" : "API Key",
                        text: $apiKey
                    )
                    TextField("Embedding 模型（可选）", text: $embeddingModel)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("Embedding Base URL（可选）", text: $embeddingApiBase)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    SecureField(
                        embeddingKeySet ? "Embedding Key 已配置" : "Embedding API Key（可选）",
                        text: $embeddingApiKey
                    )
                    TextField("语音转写模型（可选）", text: $asrModel)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("语音转写 Base URL（可选）", text: $asrApiBase)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    SecureField(
                        asrKeySet ? "语音 Key 已配置" : "语音转写 API Key（可选）",
                        text: $asrApiKey
                    )
                    HStack {
                        Text("输入价 / 百万 token")
                        Spacer()
                        TextField("0", value: $inputPrice, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 80)
                    }
                    HStack {
                        Text("输出价 / 百万 token")
                        Spacer()
                        TextField("0", value: $outputPrice, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 80)
                    }
                }

                Section("角色模型") {
                    ForEach(roleKeys, id: \.self) { key in
                        NavigationLink {
                            RoleEditorView(
                                title: roleName(key),
                                roleKey: key,
                                role: Binding(
                                    get: { roles[key] ?? emptyRole },
                                    set: { roles[key] = $0 }
                                ),
                                onClearKey: { clearedRoles.insert(key) }
                            )
                        } label: {
                            HStack {
                                Text(roleName(key))
                                Spacer()
                                Text(roleSummary(key))
                                    .font(.caption)
                                    .foregroundStyle(Theme.muted)
                            }
                        }
                    }
                }

                if let notice {
                    Section {
                        Text(notice)
                            .font(.caption)
                            .foregroundStyle(noticeIsError ? .red : Theme.accent)
                    }
                }

                Section {
                    Text("iOS 客户端复用与网页相同的 REST + SSE 接口。本地多用户没有登录鉴权，仅适合个人使用。")
                        .font(.caption2)
                        .foregroundStyle(Theme.muted)
                }
            }
            .navigationTitle("设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await save() }
                    } label: {
                        if saving { ProgressView() } else { Text("保存") }
                    }
                    .disabled(saving)
                }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        loading = true
        defer { loading = false }
        do {
            let bundle = try await APIClient.shared.settings()
            profile = bundle.profile
            llmApiBase = bundle.llm.apiBase
            defaultModel = bundle.llm.defaultModel
            embeddingModel = bundle.llm.embeddingModel
            embeddingApiBase = bundle.llm.embeddingApiBase
            embeddingApiKey = ""
            embeddingKeySet = bundle.llm.embeddingApiKeySet
            asrModel = bundle.llm.asrModel
            asrApiBase = bundle.llm.asrApiBase
            asrApiKey = ""
            asrKeySet = bundle.llm.asrApiKeySet
            inputPrice = bundle.llm.inputPricePerM
            outputPrice = bundle.llm.outputPricePerM
            apiKeySet = bundle.llm.apiKeySet
            apiKey = ""
            roles = bundle.llm.roles
            server = bundle.server
            store.settings = bundle
        } catch {
            notice = error.localizedDescription
            noticeIsError = true
        }
    }

    private func fetchModels() async {
        modelLoading = true
        defer { modelLoading = false }
        do {
            modelOptions = try await APIClient.shared.availableModels(
                apiBase: llmApiBase,
                apiKey: apiKey,
                role: nil
            )
            notice = "已获取 \(modelOptions.count) 个模型。"
            noticeIsError = false
        } catch {
            notice = error.localizedDescription
            noticeIsError = true
        }
    }

    private func save() async {
        saving = true
        defer { saving = false }
        do {
            let payload = SettingsPayload(
                llm: SettingsPayload.LLMPayload(
                    apiBase: llmApiBase,
                    apiKey: apiKey,
                    defaultModel: defaultModel,
                    embeddingModel: embeddingModel,
                    embeddingApiBase: embeddingApiBase,
                    embeddingApiKey: embeddingApiKey,
                    asrModel: asrModel,
                    asrApiBase: asrApiBase,
                    asrApiKey: asrApiKey,
                    inputPricePerM: inputPrice,
                    outputPricePerM: outputPrice,
                    roles: Dictionary(
                        uniqueKeysWithValues: roles.map { key, role in
                            (
                                key,
                                SettingsPayload.RolePayload(
                                    model: role.model,
                                    temperature: role.temperature,
                                    maxTokens: role.maxTokens,
                                    topP: role.topP,
                                    apiBase: role.apiBase,
                                    apiKey: role.apiKey,
                                    clearApiKey: clearedRoles.contains(key)
                                )
                            )
                        }
                    )
                ),
                profile: profile
            )
            let bundle = try await APIClient.shared.saveSettings(payload)
            apiKey = ""
            embeddingApiKey = ""
            asrApiKey = ""
            apiKeySet = bundle.llm.apiKeySet
            embeddingKeySet = bundle.llm.embeddingApiKeySet
            asrKeySet = bundle.llm.asrApiKeySet
            roles = bundle.llm.roles
            clearedRoles.removeAll()
            server = bundle.server
            store.settings = bundle
            notice = "已保存。"
            noticeIsError = false
        } catch {
            notice = error.localizedDescription
            noticeIsError = true
        }
    }

    private func roleName(_ key: String) -> String {
        switch key {
        case "counselor": return "辅导员"
        case "supervisor": return "学习督导"
        case "examiner": return "出卷老师"
        case "collector": return "资料搜集"
        case "organizer": return "资料整理"
        case "knowledge": return "知识点整理"
        case "grader": return "改卷老师"
        default: return key
        }
    }

    private func roleSummary(_ key: String) -> String {
        guard let role = roles[key] else { return "沿用默认" }
        if role.apiBase.isEmpty == false
            || role.apiKeySet
            || role.maxTokens > 0
            || role.topP > 0
            || role.temperature != 0.3 {
            return "已独立配置"
        }
        return role.model.isEmpty ? "沿用默认" : role.model
    }
}

private struct RoleEditorView: View {
    let title: String
    let roleKey: String
    @Binding var role: SettingsBundle.RoleConfig
    let onClearKey: () -> Void

    @State private var modelOptions: [String] = []
    @State private var modelLoading = false
    @State private var modelError: String?

    var body: some View {
        Form {
            Section("模型") {
                TextField("留空使用默认模型", text: $role.model)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                HStack {
                    Button {
                        Task { await fetchModels() }
                    } label: {
                        Label(
                            modelLoading ? "获取中…" : "获取模型",
                            systemImage: "arrow.clockwise"
                        )
                    }
                    .disabled(modelLoading)
                    if !modelOptions.isEmpty {
                        Menu("从列表选择") {
                            ForEach(modelOptions, id: \.self) { model in
                                Button(model) { role.model = model }
                            }
                        }
                    }
                }
                if let modelError {
                    Text(modelError)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }
            Section("采样参数") {
                HStack {
                    Text("temperature")
                    Spacer()
                    TextField("0.3", value: $role.temperature, format: .number)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .frame(width: 80)
                }
                HStack {
                    Text("max_tokens")
                    Spacer()
                    TextField("0", value: $role.maxTokens, format: .number)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .frame(width: 80)
                }
                HStack {
                    Text("top_p")
                    Spacer()
                    TextField("0", value: $role.topP, format: .number)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .frame(width: 80)
                }
            }
            Section("独立端点") {
                TextField("Base URL（留空沿用全局）", text: $role.apiBase)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                SecureField(
                    role.apiKeySet ? "已配置，留空保持不变" : "API Key（留空沿用全局）",
                    text: $role.apiKey
                )
                if role.apiKeySet {
                    Button("清除独立 Key", role: .destructive) {
                        role.apiKey = ""
                        role.apiKeySet = false
                        onClearKey()
                    }
                }
            }
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func fetchModels() async {
        modelLoading = true
        modelError = nil
        defer { modelLoading = false }
        do {
            modelOptions = try await APIClient.shared.availableModels(
                apiBase: role.apiBase,
                apiKey: role.apiKey,
                role: roleKey
            )
        } catch {
            modelError = error.localizedDescription
        }
    }
}
