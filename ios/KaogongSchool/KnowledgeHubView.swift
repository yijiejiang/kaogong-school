import SwiftUI

struct KnowledgeHubView: View {
    private enum Section: String, CaseIterable {
        case library = "资料"
        case mining = "挖掘"
        case skills = "技能地图"

        var title: String {
            switch self {
            case .library: return "资料库"
            case .mining: return "知识挖掘"
            case .skills: return "技能地图"
            }
        }
    }

    @State private var section: Section = .library

    var body: some View {
        NavigationStack {
            Group {
                switch section {
                case .library:
                    LibraryView()
                case .mining:
                    KnowledgeMiningView()
                case .skills:
                    SkillMapView()
                }
            }
            .safeAreaInset(edge: .top, spacing: 0) {
                VStack(spacing: 0) {
                    Picker("知识", selection: $section) {
                        ForEach(Section.allCases, id: \.self) { item in
                            Text(item.rawValue).tag(item)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                    .background(.bar)
                }
            }
            .navigationTitle(section.title)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
