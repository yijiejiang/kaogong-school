import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @State private var materials: [MaterialItem] = []
    @State private var loading = true
    @State private var error: String?
    @State private var showImporter = false
    @State private var showURLAlert = false
    @State private var urlText = ""
    @State private var busy = false

    var body: some View {
        NavigationStack {
            Group {
                if loading {
                    ProgressView("正在加载资料…")
                } else if materials.isEmpty {
                    ContentUnavailableView(
                        "资料库还是空的",
                        systemImage: "books.vertical",
                        description: Text("上传 PDF / Word / 图片 / 音频，或导入一个网页。")
                    )
                } else {
                    List(materials) { material in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(material.title)
                                    .font(.subheadline.bold())
                                Spacer()
                                statusBadge(material.status)
                            }
                            HStack(spacing: 6) {
                                Text(kindLabel(material.kind))
                                Text("·")
                                Text("\(material.chunkCount) 个分块")
                                if !material.subject.isEmpty || !material.module.isEmpty {
                                    Text("·")
                                    Text("\(material.subject) / \(material.module)")
                                }
                            }
                            .font(.caption2)
                            .foregroundStyle(Theme.muted)
                            if !material.error.isEmpty {
                                Text(material.error)
                                    .font(.caption2)
                                    .foregroundStyle(.red)
                            }
                        }
                        .padding(.vertical, 2)
                    }
                    .listStyle(.plain)
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("资料库")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        showImporter = true
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                    }
                    Button {
                        urlText = ""
                        showURLAlert = true
                    } label: {
                        Image(systemName: "link")
                    }
                }
            }
            .overlay {
                if busy {
                    ProgressView("正在上传…")
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
    }

    private func load() async {
        do {
            materials = try await APIClient.shared.materials()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
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
            color = Color.orange
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
