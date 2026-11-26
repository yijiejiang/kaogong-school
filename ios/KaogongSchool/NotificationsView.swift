import SwiftUI

/// 通知中心：督导老师到点提醒今天的学习任务。
struct NotificationsView: View {
    @State private var items: [NotificationItem] = []
    @State private var unread = 0
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        List {
            if let error {
                Section {
                    Text(error).font(.caption).foregroundStyle(.red)
                }
            }
            if loading {
                ProgressView("加载中…")
            } else if items.isEmpty {
                ContentUnavailableView(
                    "暂无通知",
                    systemImage: "bell.slash",
                    description: Text("到点后督导老师会提醒今天的学习任务。")
                )
            } else {
                ForEach(items) { item in
                    Button {
                        Task { await markRead(item) }
                    } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            HStack(spacing: 6) {
                                if !item.read {
                                    Circle()
                                        .fill(Theme.accent)
                                        .frame(width: 6, height: 6)
                                }
                                Text(item.title)
                                    .font(.subheadline.weight(item.read ? .regular : .semibold))
                                    .foregroundStyle(Theme.ink)
                                Spacer()
                            }
                            Text(item.body)
                                .font(.caption)
                                .foregroundStyle(Theme.muted)
                            Text(item.created_at.prefix(16).replacingOccurrences(of: "T", with: " "))
                                .font(.caption2)
                                .foregroundStyle(Theme.muted)
                        }
                        .padding(.vertical, 2)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .navigationTitle("通知")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if unread > 0 {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("全部已读") { Task { await markAll() } }
                }
            }
        }
        .task { await load() }
        .refreshable { await load() }
    }

    private func load() async {
        do {
            let data = try await APIClient.shared.notifications()
            items = data.items
            unread = data.unread
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func markRead(_ item: NotificationItem) async {
        guard !item.read else { return }
        do {
            try await APIClient.shared.markNotificationRead(id: item.id)
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func markAll() async {
        do {
            try await APIClient.shared.markAllNotificationsRead()
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
