import SwiftUI

struct DashboardView: View {
    @State private var overview: AnalyticsOverview?
    @State private var plan: WeekPlan?
    @State private var usage: UsageSummary?
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if loading {
                        ProgressView("正在统计学情…")
                            .frame(maxWidth: .infinity)
                            .padding(.top, 60)
                    } else if let overview {
                        stats(overview.stats)
                        weakPoints(overview.weakPoints)
                        planCard
                        usageCard
                    } else if let error {
                        Text(error)
                            .font(.subheadline)
                            .foregroundStyle(.red)
                            .padding()
                    }
                }
                .padding()
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("学情看板")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        WeeklyReportView()
                    } label: {
                        Image(systemName: "doc.text")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        CostView()
                    } label: {
                        Image(systemName: "wallet.pass")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await load() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        loading = true
        do {
            async let overviewTask = APIClient.shared.analytics()
            async let planTask = APIClient.shared.weekPlan()
            async let usageTask = APIClient.shared.usage()
            overview = try await overviewTask
            plan = try await planTask
            usage = try await usageTask
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func stats(_ stats: AnalyticsOverview.Stats) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            statCard("练习次数", "\(stats.gradedAttempts)", "共 \(stats.questions) 题")
            statCard("正确率", "\(Int(stats.accuracy))%", "按已批改试卷")
            statCard("学习时长", "\(stats.studyMinutes) 分钟", "按交卷时间估算")
            statCard(
                "知识点覆盖",
                "\(Int(stats.coverage))%",
                "\(stats.practicedKps)/\(stats.totalKps) 个"
            )
        }
    }

    private func statCard(_ title: String, _ value: String, _ hint: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(Theme.muted)
            Text(value)
                .font(.title3.bold())
                .foregroundStyle(Theme.ink)
            Text(hint)
                .font(.caption2)
                .foregroundStyle(Theme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func weakPoints(_ points: [AnalyticsOverview.WeakPoint]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("薄弱点")
                .font(.headline)
            if points.isEmpty {
                Text("还没有明显的薄弱点，先做一次诊断卷。")
                    .font(.caption)
                    .foregroundStyle(Theme.muted)
            } else {
                ForEach(points.prefix(5)) { point in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(point.knowledgePointName)
                                .font(.subheadline)
                            Text(point.module)
                                .font(.caption2)
                                .foregroundStyle(Theme.muted)
                        }
                        Spacer()
                        Text(point.score.map { "\(Int($0))" } ?? "待评估")
                            .font(.subheadline.bold())
                            .foregroundStyle(Theme.accent)
                    }
                    .padding(10)
                    .background(Theme.paper)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
        }
        .padding(14)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var planCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("本周计划")
                    .font(.headline)
                Spacer()
                if let plan {
                    Text("\(plan.adherence.done)/\(plan.adherence.total)")
                        .font(.caption)
                        .foregroundStyle(Theme.muted)
                }
            }
            if let plan {
                Text(plan.goal)
                    .font(.caption)
                    .foregroundStyle(Theme.muted)
                ForEach(plan.tasks.prefix(8)) { task in
                    Button {
                        Task { await toggle(task) }
                    } label: {
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: task.status == "done"
                                ? "checkmark.circle.fill" : "circle")
                                .foregroundStyle(
                                    task.status == "done" ? Theme.accent : Theme.muted
                                )
                            VStack(alignment: .leading, spacing: 2) {
                                Text(task.title)
                                    .font(.subheadline)
                                    .strikethrough(task.status == "done")
                                Text("\(task.date) · \(task.minutes) 分钟")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.muted)
                            }
                            Spacer()
                        }
                    }
                    .buttonStyle(.plain)
                }
            } else {
                Text("还没有本周计划。可以在对话里让督导老师生成。")
                    .font(.caption)
                    .foregroundStyle(Theme.muted)
            }
        }
        .padding(14)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var usageCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("模型用量")
                .font(.headline)
            if let usage, usage.totals.totalTokens > 0 {
                HStack(spacing: 18) {
                    usageStat("调用", "\(usage.totals.requests)")
                    usageStat("Token", "\(usage.totals.totalTokens)")
                    usageStat("成本", usage.totals.cost > 0
                        ? String(format: "¥%.2f", usage.totals.cost) : "—")
                }
                ForEach(usage.byRole.prefix(4)) { role in
                    HStack {
                        Text(role.roleLabel)
                            .font(.caption)
                        Spacer()
                        Text("\(role.totalTokens) token")
                            .font(.caption2)
                            .foregroundStyle(Theme.muted)
                    }
                }
            } else {
                Text("还没有真实模型用量；演示模式不产生 token。")
                    .font(.caption)
                    .foregroundStyle(Theme.muted)
            }
        }
        .padding(14)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func usageStat(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(Theme.muted)
            Text(value)
                .font(.subheadline.bold())
        }
    }

    private func toggle(_ task: WeekPlan.Task) async {
        do {
            try await APIClient.shared.toggleTask(
                id: task.id,
                done: task.status != "done"
            )
            plan = try await APIClient.shared.weekPlan()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
