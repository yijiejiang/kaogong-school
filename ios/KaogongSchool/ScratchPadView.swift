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
        guard let data = try? Data(contentsOf: fileURL(examId: examId)) else {
            return
        }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        guard let rows = try? decoder.decode([ScratchDraft].self, from: data) else {
            return
        }
        for row in rows {
            drafts[row.questionId] = row
        }
    }

    func hasContent(questionId: String) -> Bool {
        !(drafts[questionId]?.drawing.isEmpty ?? true)
    }

    func drawing(examId: String, questionId: String) -> PKDrawing {
        guard let row = drafts[questionId] else { return PKDrawing() }
        return (try? PKDrawing(data: row.drawing)) ?? PKDrawing()
    }

    func update(
        examId: String,
        questionId: String,
        index: Int,
        drawing: PKDrawing
    ) {
        var draft = drafts[questionId] ?? ScratchDraft(
            id: questionId,
            examId: examId,
            questionId: questionId,
            questionIndex: index,
            drawing: Data(),
            updatedAt: Date()
        )
        draft.drawing = drawing.dataRepresentation()
        draft.updatedAt = Date()
        drafts[questionId] = draft
        save(examId: examId)
    }

    func clear(examId: String, questionId: String, index: Int) {
        update(
            examId: examId,
            questionId: questionId,
            index: index,
            drawing: PKDrawing()
        )
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
///
/// 只在题目切换或显式清空时重设画布；绘制过程中不因父视图重排而重置，
/// 避免拖动分屏时画面闪烁。
struct ScratchCanvas: UIViewRepresentable {
    let questionId: String
    let revision: Int
    let initialDrawing: PKDrawing
    var tool: PKTool
    var onChanged: (String, PKDrawing) -> Void

    func makeUIView(context: Context) -> PKCanvasView {
        let view = PKCanvasView()
        view.drawingPolicy = .anyInput
        view.backgroundColor = .clear
        view.isOpaque = false
        view.alwaysBounceVertical = true
        view.alwaysBounceHorizontal = true
        view.contentSize = CGSize(width: 4000, height: 4000)
        view.tool = tool
        view.delegate = context.coordinator

        context.coordinator.questionId = questionId
        context.coordinator.revision = revision
        context.coordinator.suppress = true
        view.drawing = initialDrawing
        context.coordinator.suppress = false
        return view
    }

    func updateUIView(_ view: PKCanvasView, context: Context) {
        view.tool = tool

        let coordinator = context.coordinator
        guard coordinator.questionId != questionId
            || coordinator.revision != revision
        else { return }

        coordinator.questionId = questionId
        coordinator.revision = revision
        coordinator.suppress = true
        view.drawing = initialDrawing
        coordinator.suppress = false
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(onChanged: onChanged)
    }

    final class Coordinator: NSObject, PKCanvasViewDelegate {
        var questionId = ""
        var revision = 0
        var suppress = false
        private let onChanged: (String, PKDrawing) -> Void

        init(onChanged: @escaping (String, PKDrawing) -> Void) {
            self.onChanged = onChanged
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            guard !suppress else { return }
            // 用画布自己记录的题号，避免切换瞬间把上一题的内容写进新题
            onChanged(questionId, canvasView.drawing)
        }
    }
}

/// 共享的笔色/粗细面板。
struct ScratchToolbar: View {
    @Binding var color: UIColor
    @Binding var width: Double
    @Binding var eraser: Bool
    var onToolChange: () -> Void
    var onClear: () -> Void
    var canClear: Bool

    var body: some View {
        HStack(spacing: 12) {
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
                    onToolChange()
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

            Divider().frame(height: 20)

            Button {
                eraser = true
                onToolChange()
            } label: {
                Image(systemName: "eraser")
                    .foregroundStyle(eraser ? Theme.accent : Theme.ink)
            }
            .accessibilityLabel("橡皮")

            Slider(value: $width, in: 1...10, step: 0.5) { _ in
                eraser = false
                onToolChange()
            }
            .frame(maxWidth: 120)

            Spacer(minLength: 0)

            Button {
                onClear()
            } label: {
                Image(systemName: "trash")
                    .foregroundStyle(canClear ? Theme.ink : Theme.muted)
            }
            .disabled(!canClear)
            .accessibilityLabel("清空草稿")
        }
    }
}

/// 草稿分屏的排布方向。
enum ScratchAxis {
    case vertical    // 竖屏：上下分，拖动上边缘调高度
    case horizontal  // 横屏：左右分，拖动左边缘调宽度
}

/// 做题页里的草稿分屏。
struct ScratchSplitPanel: View {
    let examId: String
    let questions: [(id: String, index: Int)]
    @Binding var currentIndex: Int
    @Binding var height: CGFloat
    @Binding var panelWidth: CGFloat
    var axis: ScratchAxis
    var onClose: () -> Void

    @StateObject private var store = ScratchStore.shared
    @State private var drawing = PKDrawing()
    @State private var revision = 0
    @State private var displayedQuestionId = ""
    @State private var tool: PKTool = PKInkingTool(.pen, color: .label, width: 2.5)
    @State private var color: UIColor = .label
    @State private var width: Double = 2.5
    @State private var eraser = false
    @State private var saveTask: Task<Void, Never>?
    @State private var dragStartSize: CGFloat = 0

    private var current: (id: String, index: Int)? {
        guard questions.indices.contains(currentIndex) else { return nil }
        return questions[currentIndex]
    }

    private var indexForDisplayed: Int {
        questions.first(where: { $0.id == displayedQuestionId })?.index
            ?? current?.index
            ?? 0
    }

    var body: some View {
        Group {
            switch axis {
            case .vertical:
                VStack(spacing: 0) {
                    horizontalGrabber
                    header
                    content
                }
                .frame(height: height)
                .overlay(alignment: .top) {
                    Rectangle().fill(Theme.line).frame(height: 1)
                }
            case .horizontal:
                HStack(spacing: 0) {
                    verticalGrabber
                    VStack(spacing: 0) {
                        header
                        content
                    }
                }
                .frame(width: panelWidth)
                .overlay(alignment: .leading) {
                    Rectangle().fill(Theme.line).frame(width: 1)
                }
            }
        }
        .background(Theme.background)
        .onAppear { loadCurrent() }
        .onChange(of: currentIndex) { loadCurrent() }
        .onDisappear { flush() }
    }

    private var content: some View {
        VStack(spacing: 0) {
            picker
            Divider()
            ZStack {
                Color(uiColor: .secondarySystemBackground)
                ScratchCanvas(
                    questionId: displayedQuestionId,
                    revision: revision,
                    initialDrawing: drawing,
                    tool: tool,
                    onChanged: handleDrawing
                )
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .padding(6)
            }
            Divider()
            ScratchToolbar(
                color: $color,
                width: $width,
                eraser: $eraser,
                onToolChange: applyTool,
                onClear: clear,
                canClear: !drawing.strokes.isEmpty
            )
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Theme.paper)
        }
    }

    private var header: some View {
        HStack(spacing: 6) {
            Text("草稿")
                .font(.caption.bold())
                .foregroundStyle(Theme.ink)
            Text("第 \(indexForDisplayed) 题")
                .font(.caption2)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Theme.accentSoft)
                .foregroundStyle(Theme.accent)
                .clipShape(Capsule())
            if !drawing.strokes.isEmpty {
                Image(systemName: "pencil.tip")
                    .font(.system(size: 9))
                    .foregroundStyle(Theme.accent)
            }
            Spacer()
            Button(action: onClose) {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(Theme.muted)
            }
            .accessibilityLabel("收起草稿")
        }
        .padding(.horizontal, 14)
        .padding(.top, 2)
        .padding(.bottom, 2)
    }

    /// 竖屏时在顶部的横向拖动手柄。
    private var horizontalGrabber: some View {
        VStack(spacing: 0) {
            Capsule()
                .fill(Theme.line)
                .frame(width: 40, height: 5)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 6)
        .padding(.bottom, 4)
        .contentShape(Rectangle())
        .gesture(
            DragGesture(minimumDistance: 1)
                .onChanged { value in
                    if dragStartSize == 0 { dragStartSize = height }
                    let next = dragStartSize - value.translation.height
                    height = min(max(next, 200), 760)
                }
                .onEnded { _ in dragStartSize = 0 }
        )
        .accessibilityLabel("拖动调整草稿高度")
    }

    /// 横屏时在左侧的纵向拖动手柄。
    private var verticalGrabber: some View {
        VStack(spacing: 0) {
            Capsule()
                .fill(Theme.line)
                .frame(width: 5, height: 44)
                .padding(.top, 14)
            Spacer(minLength: 0)
        }
        .frame(width: 24)
        .frame(maxHeight: .infinity)
        .background(Theme.paper)
        .contentShape(Rectangle())
        .gesture(
            DragGesture(minimumDistance: 1)
                .onChanged { value in
                    if dragStartSize == 0 { dragStartSize = panelWidth }
                    let next = dragStartSize - value.translation.width
                    panelWidth = min(max(next, 260), 760)
                }
                .onEnded { _ in dragStartSize = 0 }
        )
        .accessibilityLabel("拖动调整草稿宽度")
    }

    private var picker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(Array(questions.enumerated()), id: \.element.id) { position, item in
                    let filled = store.hasContent(questionId: item.id)
                    Button {
                        currentIndex = position
                    } label: {
                        Text("\(item.index)")
                            .font(.caption2.bold())
                            .frame(width: 28, height: 28)
                            .background(
                                position == currentIndex ? Theme.accent : Theme.paper
                            )
                            .foregroundStyle(
                                position == currentIndex ? Theme.onAccent : Theme.muted
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
            .padding(.horizontal, 14)
            .padding(.bottom, 6)
        }
    }

    private func handleDrawing(questionId: String, value: PKDrawing) {
        // 画布回调带的题号必须和当前显示一致才接受
        guard questionId == displayedQuestionId else { return }
        drawing = value
        let index = questions.first(where: { $0.id == questionId })?.index ?? 0
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            store.update(
                examId: examId,
                questionId: questionId,
                index: index,
                drawing: value
            )
        }
    }

    private func flush() {
        saveTask?.cancel()
        let questionId = displayedQuestionId
        guard !questionId.isEmpty,
              let index = questions.first(where: { $0.id == questionId })?.index
        else { return }
        store.update(
            examId: examId,
            questionId: questionId,
            index: index,
            drawing: drawing
        )
    }

    private func loadCurrent() {
        guard let item = current else { return }
        if !displayedQuestionId.isEmpty, displayedQuestionId != item.id {
            flush()
        }
        displayedQuestionId = item.id
        drawing = store.drawing(examId: examId, questionId: item.id)
        revision += 1
    }

    private func applyTool() {
        tool = eraser
            ? PKEraserTool(.vector)
            : PKInkingTool(.pen, color: color, width: CGFloat(width))
    }

    private func clear() {
        drawing = PKDrawing()
        revision += 1
        guard let item = current else { return }
        store.clear(examId: examId, questionId: item.id, index: item.index)
    }
}

/// 全屏草稿，交卷后查看用。
struct ScratchPadView: View {
    let examId: String
    let questions: [(id: String, index: Int, title: String)]
    @Binding var currentIndex: Int

    @Environment(\.dismiss) private var dismiss
    @StateObject private var store = ScratchStore.shared
    @State private var drawing = PKDrawing()
    @State private var revision = 0
    @State private var displayedQuestionId = ""
    @State private var tool: PKTool = PKInkingTool(.pen, color: .label, width: 2.5)
    @State private var color: UIColor = .label
    @State private var width: Double = 2.5
    @State private var eraser = false
    @State private var saveTask: Task<Void, Never>?

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
                    Color(uiColor: .secondarySystemBackground)
                    ScratchCanvas(
                        questionId: displayedQuestionId,
                        revision: revision,
                        initialDrawing: drawing,
                        tool: tool,
                        onChanged: handleDrawing
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(10)
                }
                Divider()
                ScratchToolbar(
                    color: $color,
                    width: $width,
                    eraser: $eraser,
                    onToolChange: applyTool,
                    onClear: clear,
                    canClear: !drawing.strokes.isEmpty
                )
                .padding(.horizontal)
                .padding(.vertical, 10)
                .background(Theme.paper)
            }
            .navigationTitle("草稿纸")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") {
                        flush()
                        dismiss()
                    }
                }
            }
            .onAppear { loadCurrent() }
            .onChange(of: currentIndex) { loadCurrent() }
            .onDisappear { flush() }
        }
    }

    private var picker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(Array(questions.enumerated()), id: \.element.id) { position, item in
                    let filled = store.hasContent(questionId: item.id)
                    Button {
                        currentIndex = position
                    } label: {
                        Text("\(item.index)")
                            .font(.caption2.bold())
                            .frame(width: 30, height: 30)
                            .background(position == currentIndex ? Theme.accent : Theme.paper)
                            .foregroundStyle(
                                position == currentIndex ? Theme.onAccent : Theme.muted
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

    private func handleDrawing(questionId: String, value: PKDrawing) {
        guard questionId == displayedQuestionId else { return }
        drawing = value
        let index = questions.first(where: { $0.id == questionId })?.index ?? 0
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            store.update(
                examId: examId,
                questionId: questionId,
                index: index,
                drawing: value
            )
        }
    }

    private func flush() {
        saveTask?.cancel()
        let questionId = displayedQuestionId
        guard !questionId.isEmpty,
              let index = questions.first(where: { $0.id == questionId })?.index
        else { return }
        store.update(
            examId: examId,
            questionId: questionId,
            index: index,
            drawing: drawing
        )
    }

    private func loadCurrent() {
        guard let item = current else { return }
        if !displayedQuestionId.isEmpty, displayedQuestionId != item.id {
            flush()
        }
        displayedQuestionId = item.id
        drawing = store.drawing(examId: examId, questionId: item.id)
        revision += 1
    }

    private func applyTool() {
        tool = eraser
            ? PKEraserTool(.vector)
            : PKInkingTool(.pen, color: color, width: CGFloat(width))
    }

    private func clear() {
        drawing = PKDrawing()
        revision += 1
        guard let item = current else { return }
        store.clear(examId: examId, questionId: item.id, index: item.index)
    }
}
