import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @State private var materials: [MaterialItem] = []
    @State private var tree: [KnowledgeNode] = []
    @State private var loading = true
    @State private var error: String?
    @State private var showImporter = false
    @State private var showURLAlert = false
    @State private var urlText = ""
    @State private var busy = false
    @State private var query = ""
    @State private var searching = false
    @State private var searchResult: SearchResponse?

    var body: some View {
        List {
            Section("在资料库中搜索") {
                HStack(spacing: 8) {
                    TextField("搜索知识点、原文或题型", text: $query)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .onSubmit { Task { await search() } }
                    Button {
                        Task { await search() }
                    } label: {
                        if searching {
                            ProgressView()
                        } else {
                            Image(systemName: "magnifyingglass")
                        }
                    }
                    .disabled(searching || query.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                if let searchResult {
                    searchResults(searchResult)
                }
            }
    
            Section("知识树") {
                NavigationLink {
                    KnowledgeTreeView()
                } label: {
                    HStack {
                        Label("浏览知识树", systemImage: "tree")
                        Spacer()
                        Text("\(tree.count) 个节点")
                            .font(.caption2)
                            .foregroundStyle(Theme.muted)
                    }
                }
            }
    
            Section("资料列表") {
                if loading {
                    ProgressView("正在加载资料…")
                } else if materials.isEmpty {
                    Text("资料库还是空的。点右上角上传文件、导入网页或添加示例资料。")
                        .font(.caption)
                        .foregroundStyle(Theme.muted)
                } else {
                    ForEach(materials) { material in
                        NavigationLink {
                            MaterialDetailView(materialId: material.id)
                        } label: {
                            materialRow(material)
                        }
                    }
                }
            }
    
            if let error {
                Section {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }
        }
        .listStyle(.insetGrouped)
        .background(Theme.background.ignoresSafeArea())
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button {
                        showImporter = true
                    } label: {
                        Label("上传文件", systemImage: "square.and.arrow.up")
                    }
                    Button {
                        urlText = ""
                        showURLAlert = true
                    } label: {
                        Label("导入网页", systemImage: "link")
                    }
                    Button {
                        Task { await importSample() }
                    } label: {
                        Label("添加示例资料", systemImage: "sparkles")
                    }
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .overlay {
            if busy {
                ProgressView("正在处理…")
                    .padding()
                    .background(.regularMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
        .fileImporter(
            isPresented: $showImporter,
            allowedContentTypes: [.pdf, .plainText, .image, .audio, .movie, .data],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first { Task { await upload(url) } }
            case .failure(let failure):
                error = failure.localizedDescription
            }
        }
        .alert("导入网页", isPresented: $showURLAlert) {
            TextField("https://…", text: $urlText)
            Button("取消", role: .cancel) {}
            Button("导入") {
                Task { await importURL() }
            }
        } message: {
            Text("只支持公网 http/https 地址。")
        }
        .task { await load() }
        .refreshable { await load() }
    }

    private func load() async {
        do {
            async let materialTask = APIClient.shared.materials()
            async let treeTask = APIClient.shared.knowledgeTree()
            materials = try await materialTask
            tree = try await treeTask
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func search() async {
        let target = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !target.isEmpty else { return }
        searching = true
        defer { searching = false }
        do {
            searchResult = try await APIClient.shared.searchMaterials(
                query: target,
                topK: 6
            )
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func upload(_ url: URL) async {
        busy = true
        defer { busy = false }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        do {
            let data = try Data(contentsOf: url)
            let filename = url.lastPathComponent
            let mime = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType
                ?? "application/octet-stream"
            let material = try await APIClient.shared.uploadMaterial(
                data: data,
                filename: filename,
                mimeType: mime
            )
            materials.insert(material, at: 0)
            await waitForReady(material.id)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func importURL() async {
        busy = true
        defer { busy = false }
        do {
            let material = try await APIClient.shared.importURL(urlText)
            materials.insert(material, at: 0)
            await waitForReady(material.id)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func importSample() async {
        busy = true
        defer { busy = false }
        do {
            let material = try await APIClient.shared.seedSample()
            materials.insert(material, at: 0)
            await waitForReady(material.id)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func waitForReady(_ id: String) async {
        for _ in 0..<30 {
            try? await Task.sleep(for: .seconds(2))
            await load()
            if let item = materials.first(where: { $0.id == id }),
               item.status == "ready" || item.status == "failed" {
                return
            }
        }
    }

    private func materialRow(_ material: MaterialItem) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(material.title)
                    .font(.subheadline.bold())
                    .lineLimit(1)
                Spacer()
                statusBadge(material.status)
            }
            HStack(spacing: 6) {
                Text(kindLabel(material.kind))
                Text("·")
                Text("\(material.chunkCount) 个分块")
                if !material.subject.isEmpty || !material.module.isEmpty {
                    Text("·")
                    Text([material.subject, material.module]
                        .filter { !$0.isEmpty }
                        .joined(separator: " / "))
                }
            }
            .font(.caption2)
            .foregroundStyle(Theme.muted)
            if !material.error.isEmpty {
                Text(material.error)
                    .font(.caption2)
                    .foregroundStyle(.red)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 2)
    }

    @ViewBuilder
    private func searchResults(_ result: SearchResponse) -> some View {
        if !result.cards.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                Text("知识卡片")
                    .font(.caption.bold())
                    .foregroundStyle(Theme.muted)
                ForEach(result.cards) { card in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(card.title)
                            .font(.subheadline.bold())
                        if !card.summary.isEmpty {
                            Text(card.summary)
                                .font(.caption)
                                .foregroundStyle(Theme.muted)
                                .lineLimit(3)
                        }
                    }
                    .padding(9)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.accentSoft)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
        }
        ForEach(result.results) { hit in
            NavigationLink {
                MaterialDetailView(materialId: hit.materialId)
            } label: {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(hit.materialTitle)
                            .font(.caption.bold())
                        if let page = hit.page {
                            Text("第 \(page) 页")
                                .font(.caption2)
                                .foregroundStyle(Theme.muted)
                        }
                        if let start = hit.timeStart {
                            Text(chunkTimeLabel(start, hit.timeEnd))
                                .font(.caption2)
                                .foregroundStyle(Theme.accent)
                        }
                        Spacer()
                        Text(String(format: "%.2f", hit.score))
                            .font(.caption2)
                            .foregroundStyle(Theme.muted)
                    }
                    Text(hit.content)
                        .font(.caption)
                        .lineLimit(4)
                    if !hit.knowledgePointName.isEmpty {
                        Text(hit.knowledgePointName)
                            .font(.caption2)
                            .foregroundStyle(Theme.accent)
                    }
                }
                .padding(.vertical, 2)
            }
        }
        if result.cards.isEmpty && result.results.isEmpty {
            Text("没有找到相关内容。")
                .font(.caption)
                .foregroundStyle(Theme.muted)
        }
    }

    private func statusBadge(_ status: String) -> some View {
        let label: String
        let color: Color
        switch status {
        case "ready":
            label = "已就绪"
            color = Theme.accent
        case "failed":
            label = "失败"
            color = .red
        default:
            label = "入库中"
            color = .orange
        }
        return Text(label)
            .font(.caption2.bold())
            .padding(.horizontal, 7)
            .padding(.vertical, 2)
            .background(color.opacity(0.12))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }

    private func kindLabel(_ kind: String) -> String {
        switch kind {
        case "url": return "网页"
        case "image": return "图片"
        case "video": return "视频"
        case "audio": return "音频"
        case "sample": return "示例"
        default: return "文件"
        }
    }
}

private struct MaterialDetailView: View {
    let materialId: String

    @Environment(\.dismiss) private var dismiss
    @State private var detail: MaterialDetail?
    @State private var loading = true
    @State private var error: String?
    @State private var busy = false
    @State private var showDelete = false
    @State private var selectedChunk: MaterialChunk?

    var body: some View {
        Group {
            if loading {
                ProgressView("正在读取资料…")
            } else if let detail {
                List {
                    Section("资料信息") {
                        LabeledContent("标题", value: detail.material.title)
                        LabeledContent("类型", value: kindLabel(detail.material.kind))
                        LabeledContent("状态", value: statusLabel(detail.material.status))
                        if !detail.material.subject.isEmpty {
                            LabeledContent("科目", value: detail.material.subject)
                        }
                        if !detail.material.module.isEmpty {
                            LabeledContent("模块", value: detail.material.module)
                        }
                        LabeledContent("分块", value: "\(detail.material.chunkCount)")
                        if let model = detail.material.embeddingModel, !model.isEmpty {
                            LabeledContent("向量模型", value: model)
                        }
                        if let size = detail.material.sizeBytes, size > 0 {
                            LabeledContent("大小", value: formatSize(size))
                        }
                        if !detail.material.error.isEmpty {
                            Text(detail.material.error)
                                .font(.caption)
                                .foregroundStyle(.red)
                        }
                    }

                    Section("操作") {
                        Button {
                            Task { await reindex() }
                        } label: {
                            Label("重新索引", systemImage: "arrow.clockwise")
                        }
                        .disabled(busy)
                        Button(role: .destructive) {
                            showDelete = true
                        } label: {
                            Label("删除资料", systemImage: "trash")
                        }
                        .disabled(busy)
                    }

                    Section("分块内容") {
                        if detail.chunks.isEmpty {
                            Text("还没有分块。")
                                .font(.caption)
                                .foregroundStyle(Theme.muted)
                        } else {
                            ForEach(detail.chunks) { chunk in
                                Button {
                                    selectedChunk = chunk
                                } label: {
                                    MaterialChunkCard(chunk: chunk)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
            } else {
                ContentUnavailableView(
                    "资料不可用",
                    systemImage: "doc.questionmark",
                    description: Text(error ?? "没有找到这份资料。")
                )
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle(detail?.material.title ?? "资料详情")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
        .confirmationDialog(
            "删除这份资料？",
            isPresented: $showDelete,
            titleVisibility: .visible
        ) {
            Button("删除", role: .destructive) {
                Task { await delete() }
            }
            Button("取消", role: .cancel) {}
        } message: {
            Text("会同时删除分块与索引，无法恢复。")
        }
        .sheet(item: $selectedChunk) { chunk in
            ChunkDetailSheet(
                chunk: chunk,
                material: detail?.material
            )
        }
    }

    private func load() async {
        do {
            detail = try await APIClient.shared.materialDetail(id: materialId)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func reindex() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await APIClient.shared.reindexMaterial(id: materialId)
            for _ in 0..<20 {
                try? await Task.sleep(for: .seconds(2))
                await load()
                if let status = detail?.material.status,
                   status == "ready" || status == "failed" {
                    return
                }
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func delete() async {
        busy = true
        defer { busy = false }
        do {
            try await APIClient.shared.deleteMaterial(id: materialId)
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "ready": return "已就绪"
        case "failed": return "失败"
        case "processing": return "入库中"
        default: return "等待中"
        }
    }

    private func kindLabel(_ kind: String) -> String {
        switch kind {
        case "url": return "网页"
        case "image": return "图片"
        case "video": return "视频"
        case "audio": return "音频"
        case "sample": return "示例"
        default: return "文件"
        }
    }

    private func formatSize(_ bytes: Int) -> String {
        if bytes >= 1_048_576 {
            return String(format: "%.1f MB", Double(bytes) / 1_048_576)
        }
        if bytes >= 1024 {
            return String(format: "%.1f KB", Double(bytes) / 1024)
        }
        return "\(bytes) B"
    }
}

private struct MaterialChunkCard: View {
    let chunk: MaterialChunk

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text("#\(chunk.chunkIndex + 1)")
                    .font(.caption2.bold())
                    .foregroundStyle(Theme.muted)
                if let page = chunk.page {
                    Text(chunk.timeStart == nil ? "第 \(page) 页" : "幻灯片 \(page)")
                        .font(.caption2)
                        .foregroundStyle(Theme.muted)
                }
                if let start = chunk.timeStart {
                    Text(chunkTimeLabel(start, chunk.timeEnd))
                        .font(.caption2)
                        .foregroundStyle(Theme.accent)
                }
                if !chunk.heading.isEmpty {
                    Text(chunk.heading)
                        .font(.caption2)
                        .foregroundStyle(Theme.muted)
                        .lineLimit(1)
                }
                Text(chunkTypeLabel(chunk.chunkType))
                    .font(.caption2)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(Theme.line.opacity(0.4))
                    .clipShape(Capsule())
                Spacer()
                if !chunk.knowledgePointName.isEmpty {
                    Text(chunk.knowledgePointName)
                        .font(.caption2)
                        .foregroundStyle(Theme.accent)
                }
            }
            if !chunk.headingPath.isEmpty {
                Text(chunk.headingPath)
                    .font(.caption2)
                    .foregroundStyle(Theme.muted)
                    .lineLimit(1)
            }
            HStack(alignment: .top, spacing: 8) {
                if let url = APIClient.shared.frameURL(chunk.frameURL) {
                    AsyncImage(url: url) { image in
                        image
                            .resizable()
                            .scaledToFill()
                    } placeholder: {
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Theme.line.opacity(0.35))
                    }
                    .frame(width: 104, height: 62)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                MarkdownText(content: chunk.content)
                    .font(.caption)
            }
            if chunk.labels.count > 1 {
                Text(
                    "候选：" + chunk.labels.prefix(3).map {
                        "\($0.knowledgePointName) \(Int($0.confidence * 100))%"
                    }.joined(separator: " · ")
                )
                .font(.caption2)
                .foregroundStyle(Theme.muted)
                .lineLimit(2)
            }
            if !chunk.tags.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 5) {
                        ForEach(chunk.tags, id: \.self) { tag in
                            Text(tag)
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Theme.line.opacity(0.35))
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        }
        .padding(.vertical, 5)
    }

    private func chunkTypeLabel(_ type: String) -> String {
        switch type {
        case "method": return "方法"
        case "formula": return "公式"
        case "definition": return "定义"
        case "trap": return "易错"
        case "example": return "例题"
        case "question": return "题目"
        default: return "概述"
        }
    }
}

private struct KnowledgeTreeView: View {
    @State private var tree: [KnowledgeNode] = []
    @State private var loading = true
    @State private var error: String?

    private var subjects: [String] {
        Array(Set(tree.map(\.subject))).sorted()
    }

    var body: some View {
        Group {
            if loading {
                ProgressView("正在加载知识树…")
            } else if tree.isEmpty {
                ContentUnavailableView(
                    "知识树为空",
                    systemImage: "tree",
                    description: Text(error ?? "后端还没有初始化知识树。")
                )
            } else {
                List {
                    ForEach(subjects, id: \.self) { subject in
                        Section(subject) {
                            ForEach(
                                tree.filter { $0.subject == subject }
                                    .sorted {
                                        if $0.level == $1.level {
                                            return $0.name < $1.name
                                        }
                                        return $0.level < $1.level
                                    }
                            ) { node in
                                NavigationLink {
                                    KnowledgeCardView(kpId: node.id)
                                } label: {
                                    HStack(spacing: 6) {
                                        Text(node.name)
                                            .font(node.level <= 2 ? .subheadline.bold() : .subheadline)
                                            .padding(.leading, CGFloat(max(0, node.level - 1)) * 12)
                                        Spacer()
                                        if node.chunkCount > 0 {
                                            Text("\(node.chunkCount) 块")
                                                .font(.caption2)
                                                .foregroundStyle(Theme.muted)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("知识树")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        do {
            tree = try await APIClient.shared.knowledgeTree()
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }
}

private struct KnowledgeCardView: View {
    let kpId: String
    @State private var card: KnowledgeCardDetail?
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        Group {
            if loading {
                ProgressView("正在读取知识卡片…")
            } else if let card {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        Text(card.title)
                            .font(.title3.bold())
                        if !card.summary.isEmpty {
                            MarkdownText(content: card.summary)
                        }
                        if !card.methods.isEmpty {
                            cardSection("方法", card.methods)
                        }
                        if !card.traps.isEmpty {
                            cardSection("易错点", card.traps)
                        }
                        if !card.sourceChunks.isEmpty {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("资料来源")
                                    .font(.headline)
                                ForEach(card.sourceChunks) { hit in
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text("《\(hit.materialTitle)》"
                                            + (hit.page.map { "第 \($0) 页" } ?? ""))
                                            .font(.caption.bold())
                                        Text(hit.content)
                                            .font(.caption)
                                            .lineLimit(4)
                                    }
                                    .padding(9)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .background(Theme.paper)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 9)
                                            .stroke(Theme.line)
                                    )
                                    .clipShape(RoundedRectangle(cornerRadius: 9))
                                }
                            }
                        }
                    }
                    .padding()
                }
            } else {
                ContentUnavailableView(
                    "知识点不可用",
                    systemImage: "book.closed",
                    description: Text(error ?? "没有找到这个知识点。")
                )
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("知识卡片")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        do {
            card = try await APIClient.shared.knowledgeCard(kpId: kpId)
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func cardSection(_ title: String, _ content: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.headline)
            MarkdownText(content: content)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.paper)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

private func chunkTimeLabel(_ start: Double, _ end: Double?) -> String {
    func format(_ value: Double) -> String {
        let total = max(0, Int(value))
        return String(format: "%02d:%02d", total / 60, total % 60)
    }
    if let end {
        return "\(format(start))–\(format(end))"
    }
    return format(start)
}

private struct ChunkDetailSheet: View {
    let chunk: MaterialChunk
    let material: MaterialItem?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 8) {
                        Text("#\(chunk.chunkIndex + 1)")
                            .font(.caption.bold())
                            .foregroundStyle(Theme.muted)
                        if let page = chunk.page {
                            Text(material?.kind == "video" ? "幻灯片 \(page)" : "第 \(page) 页")
                                .font(.caption)
                                .foregroundStyle(Theme.muted)
                        }
                        if let start = chunk.timeStart {
                            Text(chunkTimeLabel(start, chunk.timeEnd))
                                .font(.caption)
                                .padding(.horizontal, 7)
                                .padding(.vertical, 2)
                                .background(Theme.accentSoft)
                                .foregroundStyle(Theme.accent)
                                .clipShape(Capsule())
                        }
                        Spacer()
                    }
                    Text(chunk.heading.isEmpty ? (material?.title ?? "分块详情") : chunk.heading)
                        .font(.title3.bold())
                    if !chunk.headingPath.isEmpty {
                        Text(chunk.headingPath)
                            .font(.caption2)
                            .foregroundStyle(Theme.muted)
                    }
                    if let url = APIClient.shared.frameURL(chunk.frameURL) {
                        AsyncImage(url: url) { image in
                            image.resizable().scaledToFit()
                        } placeholder: {
                            RoundedRectangle(cornerRadius: 10)
                                .fill(Theme.line.opacity(0.3))
                                .frame(height: 160)
                        }
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                    MarkdownText(content: chunk.content)
                        .font(.subheadline)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Theme.paper)
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    if !chunk.labels.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("候选知识点").font(.caption.bold())
                            ForEach(chunk.labels) { label in
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack {
                                        Text(label.knowledgePointName)
                                            .font(.caption.weight(.medium))
                                        Spacer()
                                        Text("\(Int(label.confidence * 100))%")
                                            .font(.caption2)
                                            .foregroundStyle(Theme.muted)
                                    }
                                    Text("\(label.subject)\(label.module.isEmpty ? "" : " · \(label.module)")")
                                        .font(.caption2)
                                        .foregroundStyle(Theme.muted)
                                    if !label.tags.isEmpty {
                                        Text(label.tags.joined(separator: " · "))
                                            .font(.caption2)
                                            .foregroundStyle(Theme.accent)
                                    }
                                }
                                .padding(9)
                                .background(Theme.paper)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                        }
                    }
                    VStack(alignment: .leading, spacing: 3) {
                        LabeledContent("资料", value: material?.title ?? "—")
                        LabeledContent("知识点", value: chunk.knowledgePointName.isEmpty ? "未归类" : chunk.knowledgePointName)
                        if !chunk.tags.isEmpty {
                            LabeledContent("标签", value: chunk.tags.joined(separator: "、"))
                        }
                    }
                    .font(.caption)
                }
                .padding()
            }
            .navigationTitle("分块详情")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("关闭") { dismiss() }
                }
            }
        }
    }
}
