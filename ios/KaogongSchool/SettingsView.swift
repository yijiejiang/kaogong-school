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
    @State private var asrModel = ""
    @State private var inputPrice = 0.0
    @State private var outputPrice = 0.0
    @State private var apiKey = ""
    @State private var apiKeySet = false
    @State private var roles: [String: SettingsBundle.RoleConfig] = [:]
    @State private var server: SettingsBundle.Server?
    @State private var loading = true
    @State private var saving = false
    @State private var notice: String?
    @State private var noticeIsError = false

    private let targets = ["国考", "省考", "事业单位", "选调生", "其他"]

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
                    SecureField(
                        apiKeySet ? "已配置，留空保持不变" : "API Key",
                        text: $apiKey
                    )
                    TextField("Embedding 模型（可选）", text: $embeddingModel)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("语音转写模型（可选）", text: $asrModel)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
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

                if !roles.isEmpty {
                    Section("角色模型") {
                        ForEach(roles.keys.sorted(), id: \.self) { key in
                            if let role = roles[key], !role.model.isEmpty {
                                LabeledContent(roleName(key), value: role.model)
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
            asrModel = bundle.llm.asrModel
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
                    asrModel: asrModel,
                    inputPricePerM: inputPrice,
                    outputPricePerM: outputPrice,
                    roles: roles.mapValues {
                        SettingsPayload.RolePayload(
                            model: $0.model,
                            temperature: $0.temperature
                        )
                    }
                ),
                profile: profile
            )
            let bundle = try await APIClient.shared.saveSettings(payload)
            apiKey = ""
            apiKeySet = bundle.llm.apiKeySet
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
}
