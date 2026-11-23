import PencilKit
import SwiftUI

/// 一张草稿：题目 id + 画布。
struct ScratchDraft: Codable, Identifiable, Equatable {
    var id: String
    var examId: String
    var questionId: String
    var questionIndex: Int
    var drawing: Data
    var updatedAt: Date

    var isEmpty: Bool { drawing.isEmpty }
}

/// 草稿按题目存在本地，交卷后仍可查看。
@MainActor
final class ScratchStore: ObservableObject {
    static let shared = ScratchStore()

    @Published private(set) var drafts: [String: ScratchDraft] = [:]
    private var loadedExamIds: Set<String> = []

    private init() {}

    private func fileURL(examId: String) -> URL {
        let base = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        )[0]
        let folder = base.appendingPathComponent("Scratch", isDirectory: true)
        try? FileManager.default.createDirectory(
            at: folder,
            withIntermediateDirectories: true
        )
        return folder.appendingPathComponent("\(examId).json")
    }

    func load(examId: String) {
        guard !loadedExamIds.contains(examId) else { return }
        loadedExamIds.insert(examId)
        let url = fileURL(examId: examId)
        guard let data = try? Data(contentsOf: url) else { return }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        guard let rows = try? decoder.decode([ScratchDraft].self, from: data) else {
            return
        }
        for row in rows {
            drafts[row.questionId] = row
        }
    }

    func draft(examId: String, questionId: String, index: Int) -> ScratchDraft {
        load(examId: examId)
        if let existing = drafts[questionId] {
            return existing
        }
        let empty = ScratchDraft(
            id: questionId,
            examId: examId,
            questionId: questionId,
            questionIndex: index,
            drawing: Data(),
            updatedAt: Date()
        )
        drafts[questionId] = empty
        return empty
    }

    func update(examId: String, questionId: String, index: Int, drawing: PKDrawing) {
        let data = drawing.dataRepresentation()
        var draft = drafts[questionId] ?? ScratchDraft(
            id: questionId,
            examId: examId,
            questionId: questionId,
            questionIndex: index,
            drawing: Data(),
            updatedAt: Date()
        )
        draft.drawing = data
        draft.updatedAt = Date()
        drafts[questionId] = draft
        save(examId: examId)
    }

    func clear(examId: String, questionId: String, index: Int) {
        var draft = drafts[questionId] ?? ScratchDraft(
            id: questionId,
            examId: examId,
            questionId: questionId,
            questionIndex: index,
            drawing: Data(),
            updatedAt: Date()
        )
        draft.drawing = Data()
        draft.updatedAt = Date()
        drafts[questionId] = draft
        save(examId: examId)
    }

    func drawings(examId: String) -> [(index: Int, questionId: String, drawing: PKDrawing)] {
        load(examId: examId)
        return drafts.values
            .filter { $0.examId == examId && !$0.drawing.isEmpty }
            .compactMap { draft in
                guard let drawing = try? PKDrawing(data: draft.drawing) else {
                    return nil
                }
                return (draft.questionIndex, draft.questionId, drawing)
            }
            .sorted { $0.0 < $1.0 }
    }

    private func save(examId: String) {
        let rows = drafts.values
            .filter { $0.examId == examId }
            .sorted { $0.questionIndex < $1.questionIndex }
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        guard let data = try? encoder.encode(rows) else { return }
        try? data.write(to: fileURL(examId: examId), options: .atomic)
    }
}

/// 备忘录风格的手写画布。
struct ScratchCanvas: UIViewRepresentable {
    @Binding var drawing: PKDrawing
    var tool: PKTool
    var onChanged: (PKDrawing) -> Void

    func makeUIView(context: Context) -> PKCanvasView {
        let view = PKCanvasView()
        view.drawingPolicy = .anyInput
        view.backgroundColor = .clear
        view.isOpaque = false
        view.alwaysBounceVertical = true
        view.alwaysBounceHorizontal = true
        view.contentSize = CGSize(width: 2000, height: 2000)
        view.drawing = drawing
        view.tool = tool
        view.delegate = context.coordinator
        return view
    }

    func updateUIView(_ view: PKCanvasView, context: Context) {
        view.tool = tool
        if view.drawing.dataRepresentation() != drawing.dataRepresentation() {
            view.drawing = drawing
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(onChanged: onChanged)
    }

    final class Coordinator: NSObject, PKCanvasViewDelegate {
        private let onChanged: (PKDrawing) -> Void
        private var lastSave = Date.distantPast

        init(onChanged: @escaping (PKDrawing) -> Void) {
            self.onChanged = onChanged
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            let now = Date()
            // 落笔过程中降低写盘频率，停笔后立即保存
            guard now.timeIntervalSince(lastSave) > 0.6 else { return }
            lastSave = now
            onChanged(canvasView.drawing)
        }
    }
}

/// 草稿纸：一页一笔，按题目切换。
struct ScratchPadView: View {
    let examId: String
    let questions: [(id: String, index: Int, title: String)]
    @Binding var currentIndex: Int

    @Environment(\.dismiss) private var dismiss
    @StateObject private var store = ScratchStore.shared
    @State private var drawing = PKDrawing()
    @State private var tool: PKTool = PKInkingTool(.pen, color: .label, width: 2.5)
    @State private var eraser = false
    @State private var color: UIColor = .label
    @State private var width: Double = 2.5
    @State private var didLoad = false

    private var current: (id: String, index: Int, title: String)? {
        guard questions.indices.contains(currentIndex) else { return nil }
        return questions[currentIndex]
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                picker
                Divider()
                ZStack {
                    Theme.background
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(uiColor: .secondarySystemBackground))
                        .padding(10)
                    ScratchCanvas(
                        drawing: $drawing,
                        tool: tool,
                        onChanged: persist
                    )
                    .padding(10)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                Divider()
                toolbar
            }
            .navigationTitle("草稿纸")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") {
                        persist(drawing)
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("清空") { clear() }
                        .disabled(drawing.strokes.isEmpty)
                }
            }
            .onAppear { loadCurrent() }
            .onChange(of: currentIndex) {
                persist(drawing)
                loadCurrent()
            }
        }
    }

    private var picker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(Array(questions.enumerated()), id: \.element.id) { position, item in
                    let filled = !(store.drafts[item.id]?.drawing.isEmpty ?? true)
                    Button {
                        currentIndex = position
                    } label: {
                        Text("\(item.index)")
                            .font(.caption2.bold())
                            .frame(width: 30, height: 30)
                            .background(
                                position == currentIndex
                                    ? Theme.accent
                                    : Theme.paper
                            )
                            .foregroundStyle(
                                position == currentIndex
                                    ? Theme.onAccent
                                    : Theme.muted
                            )
                            .overlay(
                                Circle().stroke(
                                    filled && position != currentIndex
                                        ? Theme.accent.opacity(0.6)
                                        : Theme.line
                                )
                            )
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(Theme.background)
    }

    private var toolbar: some View {
        HStack(spacing: 14) {
            ForEach(
                [
                    (UIColor.label, "黑"),
                    (UIColor.systemRed, "红"),
                    (UIColor.systemBlue, "蓝"),
                    (UIColor.systemGreen, "绿"),
                ],
                id: \.1
            ) { value, label in
                Button {
                    color = value
                    eraser = false
                    applyTool()
                } label: {
                    Circle()
                        .fill(Color(uiColor: value))
                        .frame(width: 22, height: 22)
                        .overlay(
                            Circle().stroke(
                                color == value && !eraser
                                    ? Theme.accent
                                    : Color.clear,
                                lineWidth: 2
                            )
                        )
                        .accessibilityLabel(label)
                }
                .buttonStyle(.plain)
            }

            Divider().frame(height: 22)

            Button {
                eraser = true
                tool = PKEraserTool(.vector)
            } label: {
                Image(systemName: "eraser")
                    .foregroundStyle(eraser ? Theme.accent : Theme.ink)
            }
            .accessibilityLabel("橡皮")

            Divider().frame(height: 22)

            Slider(value: $width, in: 1...10, step: 0.5) { _ in
                applyTool()
            }
            .frame(width: 110)

            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(Theme.paper)
    }

    private func applyTool() {
        tool = PKInkingTool(.pen, color: color, width: CGFloat(width))
    }

    private func loadCurrent() {
        guard let item = current else { return }
        let draft = store.draft(
            examId: examId,
            questionId: item.id,
            index: item.index
        )
        drawing = (try? PKDrawing(data: draft.drawing)) ?? PKDrawing()
        didLoad = true
    }

    private func persist(_ value: PKDrawing) {
        guard didLoad, let item = current else { return }
        store.update(
            examId: examId,
            questionId: item.id,
            index: item.index,
            drawing: value
        )
    }

    private func clear() {
        guard let item = current else { return }
        drawing = PKDrawing()
        store.clear(examId: examId, questionId: item.id, index: item.index)
    }
}
