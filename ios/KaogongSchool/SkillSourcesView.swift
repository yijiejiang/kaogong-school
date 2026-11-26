import SwiftUI

/// 技能来源：看已装了哪些包、覆盖哪些模块，以及装新包。
struct SkillSourcesView: View {
    @State private var data: SkillSourceList?
    @State private var loading = true
    @State private var error: String?
    @State private var notice: String?
    @State private var busy = false
    @State private var repo = ""
    @State private var showRepoSheet = false

    var body: some View {
        List {
            if let error {
                Section {
                    Text(error).font(.caption).foregroundStyle(.red)
                }
            }
            if let notice {
                Section {
                    Text(notice).font(.caption).foregroundStyle(Theme.muted)
                }
            }
            if loading {
                ProgressView("加载中…")
            } else if let data {
                Section("已安装") {
                    if data.sources.isEmpty {
                        Text("还没有安装任何技能包。")
                            .font(.caption)
                            .foregroundStyle(Theme.muted)
                    } else {
                        ForEach(data.sources) { source in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(source.label).font(.subheadline.bold())
                                    Spacer()
                                    Text("\(source.count) 项")
                                        .font(.caption2)
                                        .foregroundStyle(Theme.muted)
                                }
                                Text(source.modules.joined(separator: " · "))
                                    .font(.caption2)
                                    .foregroundStyle(Theme.muted)
                                Text("更新于 \(source.last_updated.prefix(10))")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.muted)
                            }
                            .padding(.vertical, 2)
                        }
                    }
                }

                Section("可安装") {
                    ForEach(data.packs) { pack in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(pack.label).font(.subheadline.bold())
                                if pack.builtin {
                                    Text("内置")
                                        .font(.caption2)
                                        .padding(.horizontal, 5)
                                        .padding(.vertical, 1)
                                        .background(Theme.accentSoft)
                                        .foregroundStyle(Theme.accent)
                                        .clipShape(Capsule())
                                }
                                Spacer()
                                Button(pack.installed ? "重新安装" : "安装") {
                                    Task { await install(pack) }
                                }
                                .font(.caption)
                                .disabled(busy)
                            }
                            Text(pack.description)
                                .font(.caption2)
                                .foregroundStyle(Theme.muted)
                        }
                        .padding(.vertical, 2)
                    }
                }

                Section {
                    Button("从 Git 仓库导入") { showRepoSheet = true }
                        .disabled(busy)
                } footer: {
                    Text("仓库需要有 references/ 目录，每个 .md 对应一个模块，用「题型 N：」「方法 N：」拆技能。导入会整体替换该来源下的旧数据。")
                }
            }
        }
        .navigationTitle("技能来源")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
        .sheet(isPresented: $showRepoSheet) {
            ImportRepoSheet { value in
                showRepoSheet = false
                Task { await importRepo(value) }
            }
        }
    }

    private func load() async {
        do {
            data = try await APIClient.shared.skillSources()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func install(_ pack: SkillSourceList.Pack) async {
        busy = true
        defer { busy = false }
        do {
            _ = try await APIClient.shared.importSkillPack(repo: "", useBuiltin: true)
            notice = "已安装 \(pack.label)"
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func importRepo(_ value: String) async {
        busy = true
        defer { busy = false }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        do {
            _ = try await APIClient.shared.importSkillPack(repo: trimmed, useBuiltin: false)
            notice = "已从仓库导入"
            repo = ""
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct ImportRepoSheet: View {
    let onImport: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var value = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("仓库地址") {
                    TextField("https://github.com/…", text: $value)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
            }
            .navigationTitle("导入技能包")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("导入") { onImport(value) }
                        .disabled(value.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }
}
