import SwiftUI

struct KnowledgeHubView: View {
    private enum Section: String, CaseIterable {
        case library = "资料"
        case mining = "挖掘"
        case skills = "技能地图"
    }

    @State private var section: Section = .library

    var body: some View {
        VStack(spacing: 0) {
            Picker("知识", selection: $section) {
                ForEach(Section.allCases, id: \.self) { item in
                    Text(item.rawValue).tag(item)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(Theme.background)

            switch section {
            case .library:
                LibraryView()
            case .mining:
                KnowledgeMiningView()
            case .skills:
                SkillMapView()
            }
        }
        .background(Theme.background)
    }
}
