import SwiftUI

enum Theme {
    static let background = Color(red: 0.972, green: 0.957, blue: 0.933)
    static let paper = Color(red: 0.996, green: 0.988, blue: 0.972)
    static let ink = Color(red: 0.11, green: 0.13, blue: 0.15)
    static let muted = Color(red: 0.45, green: 0.43, blue: 0.38)
    static let line = Color(red: 0.88, green: 0.85, blue: 0.79)
    static let accent = Color(red: 0.36, green: 0.44, blue: 0.36)
    static let accentSoft = Color(red: 0.91, green: 0.94, blue: 0.91)
    static let warm = Color(red: 0.88, green: 0.80, blue: 0.62)
}

struct RootView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        TabView {
            ChatView()
                .tabItem { Label("对话", systemImage: "message") }
            DashboardView()
                .tabItem { Label("学情", systemImage: "chart.bar") }
            ExamsView()
                .tabItem { Label("考试", systemImage: "doc.text") }
            LibraryView()
                .tabItem { Label("资料", systemImage: "books.vertical") }
            SettingsView()
                .tabItem { Label("设置", systemImage: "gearshape") }
        }
        .tint(Theme.accent)
        .background(Theme.background)
    }
}

#Preview {
    RootView().environmentObject(AppStore())
}
