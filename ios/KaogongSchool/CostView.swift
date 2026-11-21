import SwiftUI

struct CostView: View {
    @State private var usage: UsageSummary?
    @State private var billing: BillingOverview?
    @State private var days = 30
    @State private var loading = true
    @State private var error: String?

    private let ranges = [7, 30, 90, 365]

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("范围", selection: $days) {
                        ForEach(ranges, id: \.self) { value in
                            Text("近 \(value) 天").tag(value)
                        }
                    }
                    .pickerStyle(.segmented)
                    .listRowInsets(EdgeInsets(top: 8, leading: 12, bottom: 8, trailing: 12))
                    .onChange(of: days) {
                        Task { await load() }
                    }
                }

                if let error {
                    Section {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }
                }

                if loading && usage == nil {
                    Section {
                        HStack {
                            ProgressView()
                            Text("正在统计").font(.caption)
                        }
                    }
                } else if let usage {
                    Section("概览") {
                        statRow("按量费用", currency(usage.totals.cost), "不含包月订阅")
                        statRow("包月渠道", "\(usage.totals.monthlyServices)", "不计单次费用")
                        statRow("调用次数", "\(usage.totals.requests)", "")
                        statRow("Token", formatTokens(usage.totals.totalTokens), "")
                    }

                    if let billing, !billing.sources.isEmpty {
                        Section("已接入渠道") {
                            ForEach(billing.sources) { source in
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text(source.label).font(.subheadline.weight(.medium))
                                        Spacer()
                                        Text(source.billingLabel)
                                            .font(.caption2)
                                            .padding(.horizontal, 7)
                                            .padding(.vertical, 2)
                                            .background(modeColor(source.billingMode).opacity(0.15))
                                            .foregroundStyle(modeColor(source.billingMode))
                                            .clipShape(Capsule())
                                    }
                                    Text(source.base)
                                        .font(.caption2)
                                        .foregroundStyle(Theme.muted)
                                        .lineLimit(1)
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }

                    if let providers = usage.byProvider, !providers.isEmpty {
                        Section("按渠道") {
                            ForEach(providers) { item in
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.providerLabel).font(.subheadline)
                                        Text("\(item.requests) 次" + (item.totalTokens > 0 ? " · \(formatTokens(item.totalTokens)) tokens" : ""))
                                            .font(.caption2)
                                            .foregroundStyle(Theme.muted)
                                    }
                                    Spacer()
                                    VStack(alignment: .trailing, spacing: 2) {
                                        Text(item.billingMode == "monthly" ? "包月" : currency(item.cost))
                                            .font(.subheadline.weight(.medium))
                                        Text(item.billingLabel)
                                            .font(.caption2)
                                            .foregroundStyle(modeColor(item.billingMode))
                                    }
                                }
                            }
                        }
                    }

                    if let services = usage.byService, !services.isEmpty {
                        Section("按服务") {
                            ForEach(services) { item in
                                HStack {
                                    Text(item.label.isEmpty ? item.service : item.label)
                                    Spacer()
                                    Text(item.requests > 0 ? "\(item.requests) 次 · " : "")
                                        .font(.caption2)
                                        .foregroundStyle(Theme.muted)
                                    Text(currency(item.cost))
                                        .font(.subheadline.weight(.medium))
                                }
                            }
                        }
                    }

                    Section("DeepSeek 官方价目") {
                        priceRow("flash 输入/输出（高峰）", "¥2 / ¥8 每百万")
                        priceRow("flash 输入/输出（空闲）", "¥1 / ¥4 每百万")
                        priceRow("v4-pro 输入/输出（高峰）", "¥9 / ¥27 每百万")
                        priceRow("v4-pro 输入/输出（空闲）", "¥4.5 / ¥13.5 每百万")
                        priceRow("Search / Fetch", "¥5 / 1000 次")
                        priceRow("OCR", "¥1.5 / 1000 页")
                        priceRow("ASR", "¥0.39 / 小时")
                    }

                    Section {
                        Text("金额为估算，以供应商账单为准。高峰时段：北京时间周一至周五 9:00–12:00、14:00–18:00。")
                            .font(.caption2)
                            .foregroundStyle(Theme.muted)
                    }
                }
            }
            .navigationTitle("费用")
            .refreshable { await load() }
            .task { await load() }
        }
    }

    private func statRow(_ label: String, _ value: String, _ hint: String) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.subheadline)
                if !hint.isEmpty {
                    Text(hint).font(.caption2).foregroundStyle(Theme.muted)
                }
            }
            Spacer()
            Text(value).font(.headline)
        }
    }

    private func priceRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).font(.caption)
            Spacer()
            Text(value).font(.caption.weight(.medium))
        }
    }

    private func modeColor(_ mode: String) -> Color {
        switch mode {
        case "monthly": return .blue
        case "payg": return .orange
        case "free": return .green
        default: return Theme.muted
        }
    }

    private func currency(_ value: Double) -> String {
        if value <= 0 { return "¥0.00" }
        if value < 0.01 { return String(format: "¥%.4f", value) }
        return String(format: "¥%.2f", value)
    }

    private func formatTokens(_ value: Int) -> String {
        if value >= 1_000_000 {
            return String(format: "%.2fM", Double(value) / 1_000_000)
        }
        if value >= 1000 {
            return String(format: "%.1fk", Double(value) / 1000)
        }
        return "\(value)"
    }

    private func load() async {
        loading = true
        defer { loading = false }
        do {
            async let usageTask = APIClient.shared.usage(days: days)
            async let billingTask = APIClient.shared.billing()
            usage = try await usageTask
            billing = try await billingTask
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
