import SwiftUI

struct SkillMapView: View {
    @State private var data: SkillMapResponse?
    @State private var loading = true
    @State private var error: String?
    @State private var selectedSubject = ""
    @State private var selectedModule = ""
    @State private var selectedSkill: SkillMapSkill?

    private var groups: [SkillMapModule] {
        (data?.subjects ?? []).filter {
            (selectedSubject.isEmpty || $0.subject == selectedSubject) &&
                (selectedModule.isEmpty || $0.module == selectedModule)
        }
    }

    private var subjects: [String] {
        Array(Set((data?.subjects ?? []).map(\.subject))).sorted()
    }

    private var modules: [String] {
        Array(
            Set(
                (data?.subjects ?? [])
                    .filter { selectedSubject.isEmpty || $0.subject == selectedSubject }
                    .map(\.module)
            )
        ).sorted()
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let data {
                        summary(data)
                        Picker("科目", selection: $selectedSubject) {
                            Text("全部").tag("")
                            ForEach(subjects, id: \.self) { subject in
                                Text(subject).tag(subject)
                            }
                        }
                        .pickerStyle(.segmented)
                        .onChange(of: selectedSubject) {
                            selectedModule = ""
                        }

                        Picker("模块", selection: $selectedModule) {
                            Text("全部模块").tag("")
                            ForEach(modules, id: \.self) { module in
                                Text(module).tag(module)
                            }
                        }
                        .pickerStyle(.menu)

                        ForEach(groups) { group in
                            moduleCard(group)
                        }
                    } else if loading {
                        ProgressView("正在生成技能地图…")
                            .frame(maxWidth: .infinity, minHeight: 240)
                    } else {
                        ContentUnavailableView(
                            "暂无技能",
                            systemImage: "target",
                            description: Text(error ?? "先在资料库上传资料，入库后会自动挖掘技能。")
                        )
                    }
                }
                .padding()
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("技能地图")
            .task { await load() }
            .refreshable { await load() }
            .sheet(item: $selectedSkill) { skill in
                SkillMapDetailSheet(skill: skill)
            }
        }
    }

    private struct MasteryStat: Identifiable {
        let label: String
        let count: Int
        let color: Color
        var id: String { label }
    }

    private func stats(_ data: SkillMapResponse) -> [MasteryStat] {
        [
            MasteryStat(label: "熟练", count: data.summary["strong"] ?? 0, color: .green),
            MasteryStat(label: "会用", count: data.summary["practicing"] ?? 0, color: .blue),
            MasteryStat(label: "了解", count: data.summary["learning"] ?? 0, color: .orange),
            MasteryStat(label: "不清楚", count: data.summary["unpracticed"] ?? 0, color: Theme.muted),
            MasteryStat(label: "待复习", count: data.summary["due"] ?? 0, color: .red),
        ]
    }

    private func summary(_ data: SkillMapResponse) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
            ForEach(stats(data)) { item in
                VStack(alignment: .leading, spacing: 3) {
                    Text(item.label).font(.caption2).foregroundStyle(Theme.muted)
                    Text("\(item.count)").font(.title3.bold()).foregroundStyle(item.color)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(Theme.paper)
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
    }

    private func moduleCard(_ group: SkillMapModule) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("\(group.subject) · \(group.module)")
                    .font(.headline)
                Spacer()
                Text("\(group.skills.count) 项")
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
            }
            if let average = group.averageScore {
                Text("平均掌握 \(Int(average))")
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
            }
            ForEach(group.skills) { skill in
                Button {
                    selectedSkill = skill
                } label: {
                    HStack(spacing: 10) {
                        Circle()
                            .fill(masteryColor(skill.masteryStatus))
                            .frame(width: 8, height: 8)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(skill.name)
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(Theme.ink)
                            HStack(spacing: 6) {
                                Text(skill.masteryLabel)
                                    .font(.caption2)
                                    .foregroundStyle(masteryColor(skill.masteryStatus))
                                if skill.masterySource == "knowledge_point" {
                                    Text("知识点估算").font(.caption2).foregroundStyle(Theme.muted)
                                }
                                if let score = skill.score {
                                    Text("\(Int(score)) 分").font(.caption2).foregroundStyle(Theme.muted)
                                }
                                Text("来源 \(skill.sourceUnitCount)").font(.caption2).foregroundStyle(Theme.muted)
                            }
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption2)
                            .foregroundStyle(Theme.muted)
                    }
                    .padding(.vertical, 4)
                }
                .buttonStyle(.plain)
                if skill.id != group.skills.last?.id {
                    Divider()
                }
            }
        }
        .padding(14)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func masteryColor(_ status: String) -> Color {
        switch status {
        case "strong": return .green
        case "practicing": return .blue
        case "learning": return .orange
        case "due": return .red
        default: return Theme.muted
        }
    }

    private func load() async {
        loading = true
        defer { loading = false }
        do {
            data = try await APIClient.shared.skillMap()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct SkillMapDetailSheet: View {
    let skill: SkillMapSkill
    @State private var detail: SkillDetailResponse?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Text(skill.name).font(.title3.bold())
                        Spacer()
                        Text(skill.masteryLabel)
                            .font(.caption2.weight(.medium))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(Theme.accentSoft)
                            .foregroundStyle(Theme.accent)
                            .clipShape(Capsule())
                    }
                    if !skill.summary.isEmpty {
                        Text(skill.summary).font(.subheadline)
                    }
                    HStack(spacing: 12) {
                        Text("\(skill.knowledgePointName)")
                        Text("练习 \(skill.attempts) 次")
                        if let score = skill.score { Text("掌握 \(Int(score))") }
                    }
                    .font(.caption)
                    .foregroundStyle(Theme.muted)
                    if skill.masterySource == "knowledge_point" {
                        Text("当前分数按知识点练习结果估算，完成更多相关题目后会切换为技能级数据。")
                            .font(.caption2)
                            .foregroundStyle(.orange)
                    }
                    section("怎么考", skill.examPatterns)
                    section("题目识别信号", skill.signals)
                    section("标准步骤", skill.steps, ordered: true)
                    section("易错点", skill.pitfalls)
                    section("常见变式", skill.variants)
                    section("出题人怎么设干扰", skill.questionDesign)
                    if !skill.connections.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("关联知识点").font(.caption.bold())
                            ForEach(skill.connections) { item in
                                Text("\(item.relation)：\(item.name)").font(.caption)
                            }
                        }
                    }
                    if let units = detail?.units, !units.isEmpty {
                        VStack(alignment: .leading, spacing: 5) {
                            Text("来源资料").font(.caption.bold())
                            ForEach(units.prefix(5)) { unit in
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(unit.title).font(.caption)
                                    Text(unit.materialTitle)
                                        .font(.caption2)
                                        .foregroundStyle(Theme.muted)
                                }
                                .padding(7)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Theme.paper)
                                .clipShape(RoundedRectangle(cornerRadius: 7))
                            }
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("技能详情")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                detail = try? await APIClient.shared.skillDetail(id: skill.id)
            }
        }
    }

    private func section(_ title: String, _ items: [String], ordered: Bool = false) -> some View {
        let values = items.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        return Group {
            if !values.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.caption.bold())
                    ForEach(Array(values.enumerated()), id: \.offset) { index, item in
                        Text(ordered ? "\(index + 1). \(item)" : "• \(item)")
                            .font(.caption)
                    }
                }
            }
        }
    }
}
