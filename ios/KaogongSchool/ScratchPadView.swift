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

    func drawing(examId: String, questionId: String, index: Int) -> PKDrawing {
        let draft = draft(examId: examId, questionId: questionId, index: index)
        return (try? PKDrawing(data: draft.drawing)) ?? PKDrawing()
    }

    func hasContent(questionId: String) -> Bool {
        !(drafts[questionId]?.drawing.isEmpty ?? true)
    }

    func update(examId: String, questionId: String, index: Int, drawing: PKDrawing) {
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
        view.contentSize = CGSize(width: 4000, height: 4000)
        view.drawing = drawing
        view.tool = tool
        view.delegate = context.coordinator
        return view
    }

    func updateUIView(_ view: PKCanvasView, context: Context) {
        // 只在外部主动切换内容时重设画布，避免打断正在写的笔画
        context.coordinator.tool = tool
        view.tool = tool
        if context.coordinator.isProgrammaticUpdate { return }
        let current = view.drawing.dataRepresentation()
        let target = drawing.dataRepresentation()
        if current != target {
            context.coordinator.isProgrammaticUpdate = true
            view.drawing = drawing
            context.coordinator.isProgrammaticUpdate = false
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(onChanged: onChanged, tool: tool)
    }

    final class Coordinator: NSObject, PKCanvasViewDelegate {
        var onChanged: (PKDrawing) -> Void
        var tool: PKTool
        var isProgrammaticUpdate = false

        init(onChanged: @escaping (PKDrawing) -> Void, tool: PKTool) {
            self.onChanged = onChanged
            self.tool = tool
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            guard !isProgrammaticUpdate else { return }
            onChanged(canvasView.drawing)
        }
    }
}

/// 共享的笔色/粗细面板，分屏和全屏都用它。
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

/// 做题页底部的草稿分屏，可拖动调整高度。
struct ScratchSplitPanel: View {
    let examId: String
    let questions: [(id: String, index: Int)]
    @Binding var currentIndex: Int
    @Binding var height: CGFloat
    var onClose: () -> Void

    @StateObject private var store = ScratchStore.shared
    @State private var drawing = PKDrawing()
    @State private var tool: PKTool = PKInkingTool(.pen, color: .label, width: 2.5)
    @State private var color: UIColor = .label
    @State private var width: Double = 2.5
    @State private var eraser = false
    @State private var saveTask: Task<Void, Never>?
    @State private var isDragging = false
    @State private var dragStartHeight: CGFloat = 0

    private var current: (id: String, index: Int)? {
        guard questions.indices.contains(currentIndex) else { return nil }
        return questions[currentIndex]
    }

    var body: some View {
        VStack(spacing: 0) {
            handle
            picker
            Divider()
            ZStack {
                Color(uiColor: .secondarySystemBackground)
                ScratchCanvas(drawing: $drawing, tool: tool, onChanged: handleDrawing)
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
        .frame(height: height)
        .background(Theme.background)
        .overlay(alignment: .top) {
            Rectangle().fill(Theme.line).frame(height: 1)
        }
        .onAppear { loadCurrent() }
        .onChange(of: currentIndex) {
            flush()
            loadCurrent()
        }
        .onDisappear { flush() }
    }

    private var handle: some View {
        VStack(spacing: 4) {
            Capsule()
                .fill(Theme.line)
                .frame(width: 40, height: 5)
            HStack {
                Text(current.map { "第 \($0.index) 题草稿" } ?? "草稿")
                    .font(.caption.bold())
                    .foregroundStyle(Theme.ink)
                Spacer()
                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Theme.muted)
                }
                .accessibilityLabel("收起草稿")
            }
            .padding(.horizontal, 14)
        }
        .padding(.top, 6)
        .padding(.bottom, 4)
        .frame(maxWidth: .infinity)
        .contentShape(Rectangle())
        .gesture(
            DragGesture(minimumDistance: 1)
                .onChanged { value in
                    if !isDragging {
                        isDragging = true
                        dragStartHeight = height
                    }
                    let next = dragStartHeight - value.translation.height
                    height = min(max(next, 220), 720)
                }
                .onEnded { _ in
                    isDragging = false
                }
        )
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

    private func handleDrawing(_ value: PKDrawing) {
        // 状态立即更新，保证切换题目或关闭时拿到的是最新笔迹
        drawing = value
        guard let item = current else { return }
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(for: .milliseconds(350))
            guard !Task.isCancelled else { return }
            store.update(
                examId: examId,
                questionId: item.id,
                index: item.index,
                drawing: value
            )
        }
    }

    private func flush() {
        saveTask?.cancel()
        guard let item = current else { return }
        store.update(
            examId: examId,
            questionId: item.id,
            index: item.index,
            drawing: drawing
        )
    }

    private func loadCurrent() {
        guard let item = current else { return }
        drawing = store.drawing(
            examId: examId,
            questionId: item.id,
            index: item.index
        )
    }

    private func applyTool() {
        tool = eraser
            ? PKEraserTool(.vector)
            : PKInkingTool(.pen, color: color, width: CGFloat(width))
    }

    private func clear() {
        drawing = PKDrawing()
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
                    Theme.background
                    ScratchCanvas(drawing: $drawing, tool: tool, onChanged: handleDrawing)
                        .padding(10)
                        .background(Color(uiColor: .secondarySystemBackground))
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
            .onChange(of: currentIndex) {
                flush()
                loadCurrent()
            }
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

    private func handleDrawing(_ value: PKDrawing) {
        drawing = value
        guard let item = current else { return }
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(for: .milliseconds(350))
            guard !Task.isCancelled else { return }
            store.update(
                examId: examId,
                questionId: item.id,
                index: item.index,
                drawing: value
            )
        }
    }

    private func flush() {
        saveTask?.cancel()
        guard let item = current else { return }
        store.update(
            examId: examId,
            questionId: item.id,
            index: item.index,
            drawing: drawing
        )
    }

    private func loadCurrent() {
        guard let item = current else { return }
        drawing = store.drawing(
            examId: examId,
            questionId: item.id,
            index: item.index
        )
    }

    private func applyTool() {
        tool = eraser
            ? PKEraserTool(.vector)
            : PKInkingTool(.pen, color: color, width: CGFloat(width))
    }

    private func clear() {
        drawing = PKDrawing()
        guard let item = current else { return }
        store.clear(examId: examId, questionId: item.id, index: item.index)
    }
}
