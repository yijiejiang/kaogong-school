@preconcurrency import AVFoundation
import SwiftUI
import UIKit

private final class SessionBox: @unchecked Sendable {
    let session: AVCaptureSession

    init(_ session: AVCaptureSession) {
        self.session = session
    }
}

enum ConnectLink {
    static func base(from url: URL) -> String? {
        if url.scheme?.lowercased() == "kaogong" {
            let components = URLComponents(
                url: url,
                resolvingAgainstBaseURL: false
            )
            if let value = components?.queryItems?
                .first(where: { $0.name == "base" })?.value,
               value.hasPrefix("http://") || value.hasPrefix("https://") {
                return value.hasSuffix("/") ? String(value.dropLast()) : value
            }
        }
        if let scheme = url.scheme?.lowercased(),
           scheme == "http" || scheme == "https",
           url.host != nil {
            return url.absoluteString
        }
        return nil
    }
}

@MainActor
final class QRScannerController: NSObject, ObservableObject,
    AVCaptureMetadataOutputObjectsDelegate {
    let session = AVCaptureSession()
    @Published var error: String?
    var onCode: ((String) -> Void)?

    private var configured = false

    func start() async {
        let authorized = await requestAccess()
        guard authorized else {
            error = "没有相机权限。请到系统设置里允许考公私塾使用相机。"
            return
        }
        guard AVCaptureDevice.default(
            .builtInWideAngleCamera,
            for: .video,
            position: .back
        ) != nil else {
            error = "当前设备没有可用摄像头。模拟器请用手动填写，真机请扫码。"
            return
        }
        if configured {
            let box = SessionBox(session)
            DispatchQueue.global(qos: .userInitiated).async {
                box.session.startRunning()
            }
            return
        }

        guard let device = AVCaptureDevice.default(
            .builtInWideAngleCamera,
            for: .video,
            position: .back
        ),
            let input = try? AVCaptureDeviceInput(device: device),
            session.canAddInput(input)
        else {
            error = "无法打开摄像头。"
            return
        }

        session.beginConfiguration()
        session.addInput(input)
        let output = AVCaptureMetadataOutput()
        if session.canAddOutput(output) {
            session.addOutput(output)
            output.setMetadataObjectsDelegate(self, queue: .main)
            output.metadataObjectTypes = [.qr]
        }
        session.commitConfiguration()
        configured = true

        let box = SessionBox(session)
        DispatchQueue.global(qos: .userInitiated).async {
            box.session.startRunning()
        }
    }

    func stop() {
        let box = SessionBox(session)
        DispatchQueue.global(qos: .userInitiated).async {
            box.session.stopRunning()
        }
    }

    private func requestAccess() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            return true
        case .notDetermined:
            return await AVCaptureDevice.requestAccess(for: .video)
        default:
            return false
        }
    }

    nonisolated func metadataOutput(
        _ output: AVCaptureMetadataOutput,
        didOutput metadataObjects: [AVMetadataObject],
        from connection: AVCaptureConnection
    ) {
        guard let object = metadataObjects.first
            as? AVMetadataMachineReadableCodeObject,
            let value = object.stringValue
        else {
            return
        }
        Task { @MainActor in
            onCode?(value)
            stop()
        }
    }
}

struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {
        uiView.previewLayer.session = session
    }

    final class PreviewView: UIView {
        override class var layerClass: AnyClass {
            AVCaptureVideoPreviewLayer.self
        }

        var previewLayer: AVCaptureVideoPreviewLayer {
            layer as! AVCaptureVideoPreviewLayer
        }
    }
}

struct QRConnectView: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var scanner = QRScannerController()
    @State private var message: String?
    let onConnected: (String) -> Void

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()
                CameraPreview(session: scanner.session)
                    .ignoresSafeArea()

                VStack {
                    Spacer()
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(Color.white.opacity(0.9), lineWidth: 3)
                        .frame(width: 240, height: 240)
                    Text("把电脑上的二维码放进框内")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                        .padding(.top, 18)
                    if let text = message ?? scanner.error {
                        Text(text)
                            .font(.caption)
                            .multilineTextAlignment(.center)
                            .foregroundStyle(.white.opacity(0.9))
                            .padding(.horizontal, 30)
                            .padding(.top, 10)
                    }
                    Spacer()
                }
            }
            .navigationTitle("扫码连接")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
            }
            .task {
                scanner.onCode = { code in
                    guard let url = URL(string: code),
                          let base = ConnectLink.base(from: url)
                    else {
                        message = "二维码内容不正确，请扫描电脑设置页上的连接码。"
                        return
                    }
                    onConnected(base)
                    dismiss()
                }
                await scanner.start()
            }
            .onDisappear { scanner.stop() }
        }
    }
}
