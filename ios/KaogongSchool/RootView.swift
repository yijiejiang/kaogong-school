import Foundation
import SwiftUI
import UIKit

enum Theme {
    private static func adaptive(light: UIColor, dark: UIColor) -> Color {
        Color(
            uiColor: UIColor { traits in
                traits.userInterfaceStyle == .dark ? dark : light
            }
        )
    }

    static let background = adaptive(
        light: UIColor(red: 0.972, green: 0.957, blue: 0.933, alpha: 1),
        dark: UIColor(red: 0.055, green: 0.052, blue: 0.048, alpha: 1)
    )
    static let paper = adaptive(
        light: UIColor(red: 0.996, green: 0.988, blue: 0.972, alpha: 1),
        dark: UIColor(red: 0.105, green: 0.10, blue: 0.092, alpha: 1)
    )
    static let ink = adaptive(
        light: UIColor(red: 0.11, green: 0.13, blue: 0.15, alpha: 1),
        dark: UIColor(red: 0.93, green: 0.91, blue: 0.87, alpha: 1)
    )
    static let muted = adaptive(
        light: UIColor(red: 0.45, green: 0.43, blue: 0.38, alpha: 1),
        dark: UIColor(red: 0.64, green: 0.62, blue: 0.57, alpha: 1)
    )
    static let line = adaptive(
        light: UIColor(red: 0.88, green: 0.85, blue: 0.79, alpha: 1),
        dark: UIColor(red: 0.23, green: 0.22, blue: 0.20, alpha: 1)
    )
    static let accent = adaptive(
        light: UIColor(red: 0.36, green: 0.44, blue: 0.36, alpha: 1),
        dark: UIColor(red: 0.55, green: 0.73, blue: 0.59, alpha: 1)
    )
    static let accentSoft = adaptive(
        light: UIColor(red: 0.91, green: 0.94, blue: 0.91, alpha: 1),
        dark: UIColor(red: 0.16, green: 0.22, blue: 0.18, alpha: 1)
    )
    static let solid = adaptive(
        light: UIColor(red: 0.11, green: 0.13, blue: 0.15, alpha: 1),
        dark: UIColor(red: 0.92, green: 0.90, blue: 0.86, alpha: 1)
    )
    static let onSolid = adaptive(
        light: .white,
        dark: UIColor(red: 0.09, green: 0.10, blue: 0.09, alpha: 1)
    )
    static let onAccent = adaptive(
        light: .white,
        dark: UIColor(red: 0.06, green: 0.10, blue: 0.07, alpha: 1)
    )
    static let codeBackground = adaptive(
        light: UIColor(red: 0.95, green: 0.94, blue: 0.91, alpha: 1),
        dark: UIColor(red: 0.07, green: 0.07, blue: 0.065, alpha: 1)
    )
    static let warm = adaptive(
        light: UIColor(red: 0.88, green: 0.80, blue: 0.62, alpha: 1),
        dark: UIColor(red: 0.42, green: 0.35, blue: 0.24, alpha: 1)
    )
}

struct RootView: View {
    @EnvironmentObject private var store: AppStore
    @State private var connectMessage: String?

    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ChatView()
                .tabItem { Label("对话", systemImage: "message") }
                .tag(0)
            DashboardView()
                .tabItem { Label("学情", systemImage: "chart.bar") }
                .tag(1)
            ExamsView()
                .tabItem { Label("考试", systemImage: "doc.text") }
                .tag(2)
            KnowledgeHubView()
                .tabItem { Label("知识", systemImage: "books.vertical") }
                .tag(3)
            SettingsView()
                .tabItem { Label("设置", systemImage: "gearshape") }
                .tag(4)
        }
        .onChange(of: store.requestedTab) { _, newValue in
            selectedTab = newValue
        }
        .tint(Theme.accent)
        .background(Theme.background)
        .onOpenURL { url in
            guard let base = ConnectLink.base(from: url) else { return }
            UserDefaults.standard.set(base, forKey: "apiBaseURL")
            connectMessage = "已连接到 \(base)"
            Task { await store.bootstrap() }
        }
        .alert(
            "连接成功",
            isPresented: Binding(
                get: { connectMessage != nil },
                set: { if !$0 { connectMessage = nil } }
            )
        ) {
            Button("好", role: .cancel) {}
        } message: {
            Text(connectMessage ?? "")
        }
    }
}

#Preview {
    RootView().environmentObject(AppStore())
}
