import SwiftUI

struct KnowledgeMiningView: View {
    private enum Tab: String, CaseIterable {
        case units = "知识单元"
        case skills = "技能"
    }

    @State private var tab: Tab = .units
    @State private var filter = "draft"
    @State private var units: [KnowledgeUnitItem] = []
    @State private var skills: [SkillItem] = []
    @State private var materials: [MaterialItem] = []
    @State private var loading = true
    @State private var busy = false
    @State private var error: String?
    @State private var notice: String?
    @State private var selectedUnit: KnowledgeUnitItem?
    @State private var selectedSkill: SkillItem?

    private struct MiningFilter: Identifiable {
        let value: String
        let label: String
        var id: String { value }
    }

    private let filters = [
        MiningFilter(value: "draft", label: "待审核"),
        MiningFilter(value: "proposal", label: "新知识点"),
        MiningFilter(value: "approved", label: "已通过"),
        MiningFilter(value: "rejected", label: "已驳回"),
        MiningFilter(value: "", label: "全部"),
    ]

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("类型", selection: $tab) {
                        ForEach(Tab.allCases, id: \.self) { item in
                            Text(item.rawValue).tag(item)
                        }
                    }
                    .pickerStyle(.segmented)
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(filters) { item in
                                Button {
                                    filter = item.value
                                    Task { await load() }
                                } label: {
                                    Text(item.label)
                                        .font(.caption.weight(.medium))
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, 5)
                                        .background(filter == item.value ? Theme.solid : Theme.paper)
                                        .foregroundStyle(filter == item.value ? Theme.onSolid : Theme.muted)
                                        .clipShape(Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }

                if let error {
                    Section {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }
                }

                if busy {
                    Section {
                        HStack(spacing: 8) {
                            ProgressView()
                            Text("正在抽取，可能需要几分钟…").font(.caption)
                        }
                    }
                }

                if loading {
                    ProgressView("加载中…")
                } else if tab == .units {
                    if units.isEmpty {
                        ContentUnavailableView(
                            "暂无知识单元",
                            systemImage: "sparkles",
                            description: Text("先上传资料，或在资料库重新索引。")
                        )
                    } else {
                        ForEach(units) { unit in
                            Button {
                                selectedUnit = unit
                            } label: {
                                unitRow(unit)
                            }
                            .buttonStyle(.plain)
                            .swipeActions(edge: .leading) {
                                if unit.status != "approved" {
                                    Button("通过") { Task { await setUnit(unit, "approved") } }
                                        .tint(.green)
                                }
                            }
                            .swipeActions(edge: .trailing) {
                                if unit.status != "rejected" {
                                    Button("驳回", role: .destructive) {
                                        Task { await setUnit(unit, "rejected") }
                                    }
                                }
                            }
                        }
                    }
                } else {
                    if skills.isEmpty {
                        ContentUnavailableView(
                            "暂无技能",
                            systemImage: "target",
                            description: Text("知识单元抽取后会自动聚类出技能。")
                        )
                    } else {
                        ForEach(skills) { skill in
                            Button {
                                selectedSkill = skill
                            } label: {
                                skillRow(skill)
                            }
                            .buttonStyle(.plain)
                            .swipeActions(edge: .leading) {
                                if skill.status != "approved" {
                                    Button("通过") { Task { await setSkill(skill, "approved") } }
                                        .tint(.green)
                                }
                            }
                            .swipeActions(edge: .trailing) {
                                if skill.status != "rejected" {
                                    Button("驳回", role: .destructive) {
                                        Task { await setSkill(skill, "rejected") }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("知识挖掘")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        if materials.isEmpty {
                            Text("没有可抽取的资料")
                        }
                        ForEach(materials) { material in
                            Button(material.title) {
                                Task { await extract(material) }
                            }
                        }
                    } label: {
                        Image(systemName: "arrow.triangle.2.circlepath")
                    }
                    .disabled(busy)
                }
            }
            .task { await load() }
            .refreshable { await load() }
            .sheet(item: $selectedUnit) { unit in
                UnitDetailSheet(unit: unit) {
                    selectedUnit = nil
                    Task { await load() }
                }
            }
            .sheet(item: $selectedSkill) { skill in
                SkillDetailSheet(skill: skill) {
                    selectedSkill = nil
                    Task { await load() }
                }
            }
            .alert("完成", isPresented: Binding(
                get: { notice != nil },
                set: { if !$0 { notice = nil } }
            )) {
                Button("好", role: .cancel) {}
            } message: {
                Text(notice ?? "")
            }
        }
    }

    private func unitRow(_ unit: KnowledgeUnitItem) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Text(unit.title)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Theme.ink)
                    .lineLimit(2)
                Spacer()
                Text(unit.status == "approved" ? "已通过" : unit.status == "rejected" ? "已驳回" : "待审核")
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(statusColor(unit.status).opacity(0.15))
                    .foregroundStyle(statusColor(unit.status))
                    .clipShape(Capsule())
            }
            if !unit.proposedKnowledgePoint.isEmpty {
                Text("新知识点候选：\(unit.proposedKnowledgePoint)")
                    .font(.caption2)
                    .foregroundStyle(.blue)
            }
            HStack(spacing: 8) {
                if !unit.knowledgePointName.isEmpty {
                    Text(unit.knowledgePointName)
                }
                if !unit.skillName.isEmpty {
                    Text(unit.skillName)
                }
                Text(unit.extractionModel)
            }
            .font(.caption2)
            .foregroundStyle(Theme.muted)
            if !unit.summary.isEmpty {
                Text(unit.summary)
                    .font(.caption)
                    .foregroundStyle(Theme.muted)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 2)
    }

    private func skillRow(_ skill: SkillItem) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(skill.name)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Theme.ink)
                Spacer()
                Text(skill.status == "approved" ? "已通过" : skill.status == "rejected" ? "已驳回" : "待审核")
                    .font(.caption2)
                    .foregroundStyle(statusColor(skill.status))
            }
            HStack(spacing: 8) {
                if !skill.knowledgePointName.isEmpty {
                    Text(skill.knowledgePointName)
                }
                if !skill.module.isEmpty {
                    Text(skill.module)
                }
                Text("来源 \(skill.sourceUnitIds.count)")
            }
            .font(.caption2)
            .foregroundStyle(Theme.muted)
            if let pattern = skill.examPatterns.first, !pattern.isEmpty {
                Text("怎么考：\(pattern)")
                    .font(.caption)
                    .foregroundStyle(Theme.muted)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 2)
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "approved": return .green
        case "rejected": return .red
        default: return .orange
        }
    }

    private func load() async {
        loading = true
        defer { loading = false }
        do {
            async let unitTask = APIClient.shared.knowledgeUnits(
                status: filter == "proposal" ? nil : filter,
                hasProposal: filter == "proposal"
            )
            async let skillTask = APIClient.shared.skills(
                status: filter == "proposal" ? nil : filter
            )
            async let materialTask = APIClient.shared.materials()
            units = try await unitTask
            skills = try await skillTask
            materials = try await materialTask
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func setUnit(_ unit: KnowledgeUnitItem, _ status: String) async {
        do {
            _ = try await APIClient.shared.updateKnowledgeUnitStatus(
                id: unit.id,
                status: status
            )
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func setSkill(_ skill: SkillItem, _ status: String) async {
        do {
            _ = try await APIClient.shared.updateSkillStatus(
                id: skill.id,
                status: status
            )
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func extract(_ material: MaterialItem) async {
        busy = true
        defer { busy = false }
        do {
            let result = try await APIClient.shared.extractMaterialUnits(
                materialId: material.id
            )
            notice = "抽取完成：\(result.units) 个知识单元、\(result.skills) 个技能、\(result.proposals) 个新知识点候选。"
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct UnitDetailSheet: View {
    let unit: KnowledgeUnitItem
    let onChanged: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var busy = false
    @State private var error: String?
    @State private var editing = false
    @State private var title: String
    @State private var summary: String

    init(unit: KnowledgeUnitItem, onChanged: @escaping () -> Void) {
        self.unit = unit
        self.onChanged = onChanged
        _title = State(initialValue: unit.title)
        _summary = State(initialValue: unit.summary)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if editing {
                        TextField("标题", text: $title)
                            .textFieldStyle(.roundedBorder)
                            .font(.title3.bold())
                        TextEditor(text: $summary)
                            .frame(minHeight: 100)
                            .padding(6)
                            .background(Theme.paper)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8).stroke(Theme.line)
                            )
                    } else {
                        Text(title).font(.title3.bold())
                        if !summary.isEmpty {
                            Text(summary).font(.subheadline)
                        }
                    }
                    if !unit.proposedKnowledgePoint.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("新知识点候选").font(.caption.bold())
                            Text(unit.proposedKnowledgePoint).font(.subheadline)
                            if !unit.proposedReason.isEmpty {
                                Text(unit.proposedReason)
                                    .font(.caption)
                                    .foregroundStyle(Theme.muted)
                            }
                            Button {
                                Task { await createPoint() }
                            } label: {
                                Label("创建知识点", systemImage: "plus.circle")
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(busy)
                        }
                        .padding(12)
                        .background(Color.blue.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    detailSection("怎么考", [unit.examPattern])
                    detailSection("题目识别信号", unit.signals)
                    detailSection("步骤", unit.steps, ordered: true)
                    detailSection("易错点", unit.pitfalls)
                    detailSection("常见变式", unit.variants)
                    detailSection("出题人怎么设干扰", unit.questionDesign)
                    if !unit.connections.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("关联知识点").font(.caption.bold())
                            ForEach(unit.connections) { item in
                                Text("\(item.relation)：\(item.name)").font(.caption)
                            }
                        }
                    }
                    if let error {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }
                }
                .padding()
            }
            .navigationTitle("知识单元")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if editing {
                        Button("保存") { Task { await save() } }
                            .disabled(busy)
                    } else {
                        Button("编辑") { editing = true }
                    }
                }
            }
        }
    }

    private func detailSection(_ title: String, _ items: [String], ordered: Bool = false) -> some View {
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

    private func save() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await APIClient.shared.updateKnowledgeUnit(
                id: unit.id,
                title: title,
                summary: summary
            )
            editing = false
            error = nil
            onChanged()
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func createPoint() async {
        busy = true
        defer { busy = false }
        do {
            let result = try await APIClient.shared.createPointFromUnit(id: unit.id)
            error = nil
            onChanged()
            dismiss()
            _ = result
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct SkillDetailSheet: View {
    let skill: SkillItem
    let onChanged: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var detail: SkillDetailResponse?
    @State private var editing = false
    @State private var name: String
    @State private var summary: String
    @State private var busy = false
    @State private var error: String?

    init(skill: SkillItem, onChanged: @escaping () -> Void) {
        self.skill = skill
        self.onChanged = onChanged
        _name = State(initialValue: skill.name)
        _summary = State(initialValue: skill.summary)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if editing {
                        TextField("技能名称", text: $name)
                            .textFieldStyle(.roundedBorder)
                            .font(.title3.bold())
                        TextEditor(text: $summary)
                            .frame(minHeight: 90)
                            .padding(6)
                            .background(Theme.paper)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8).stroke(Theme.line)
                            )
                    } else {
                        Text(name).font(.title3.bold())
                        if !summary.isEmpty {
                            Text(summary).font(.subheadline)
                        }
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
                    if let error {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }
                }
                .padding()
            }
            .navigationTitle("技能详情")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if editing {
                        Button("保存") { Task { await save() } }
                            .disabled(busy)
                    } else {
                        Button("编辑") { editing = true }
                    }
                }
            }
            .task {
                detail = try? await APIClient.shared.skillDetail(id: skill.id)
            }
        }
    }

    private func save() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await APIClient.shared.updateSkill(
                id: skill.id,
                name: name,
                summary: summary
            )
            editing = false
            error = nil
            onChanged()
            dismiss()
        } catch {
            self.error = error.localizedDescription
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
