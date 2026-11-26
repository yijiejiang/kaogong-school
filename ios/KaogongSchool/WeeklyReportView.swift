import SwiftUI

/// 周报：这一周做了多少、正确率怎么样、计划完成到哪。
struct WeeklyReportView: View {
    @State private var report: WeeklyReport?
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if loading {
                    ProgressView("正在统计…")
                        .frame(maxWidth: .infinity)
                        .padding(.top, 60)
                } else if let report {
                    summaryCard(report)
                    statGrid(report)
                    if !report.weak_points.isEmpty {
                        weakCard(report.weak_points)
                    }
                    Text(report.summary)
                        .font(.subheadline)
                        .foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Theme.paper)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                } else if let error {
                    Text(error).font(.subheadline).foregroundStyle(.red).padding()
                }
            }
            .padding()
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("周报")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
    }

    private func summaryCard(_ report: WeeklyReport) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("\(report.period_start) ~ \(report.period_end)")
                .font(.caption)
                .foregroundStyle(Theme.muted)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("\(report.questions)")
                    .font(.system(size: 34, weight: .bold))
                    .foregroundStyle(Theme.ink)
                Text("题")
                    .font(.subheadline)
                    .foregroundStyle(Theme.muted)
                Spacer()
                Text(String(format: "%.0f%%", report.accuracy * 100))
                    .font(.title3.bold())
                    .foregroundStyle(Theme.accent)
                Text("正确率")
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.paper)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func statGrid(_ report: WeeklyReport) -> some View {
        HStack(spacing: 10) {
            statTile("练习次数", "\(report.attempts)")
            statTile("学习时长", "\(report.study_minutes) 分")
            statTile("错题", "\(report.wrong_count)")
            statTile("计划完成", "\(report.plan_done)/\(report.plan_total)")
        }
    }

    private func statTile(_ label: String, _ value: String) -> some View {
        VStack(spacing: 4) {
            Text(value).font(.subheadline.bold()).foregroundStyle(Theme.ink)
            Text(label).font(.caption2).foregroundStyle(Theme.muted)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(Theme.paper)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func weakCard(_ points: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("薄弱点").font(.subheadline.bold())
            ForEach(points, id: \.self) { point in
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.circle.fill")
                        .font(.caption2)
                        .foregroundStyle(.orange)
                    Text(point).font(.caption).foregroundStyle(Theme.ink)
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.paper)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func load() async {
        do {
            report = try await APIClient.shared.weeklyReport()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }
}
