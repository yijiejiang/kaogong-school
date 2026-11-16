# 考公私塾 iOS 客户端

原生 SwiftUI 客户端，复用后端的 REST + SSE 接口。最低 iOS 17。

## 打开与运行

```bash
open ios/KaogongSchool.xcodeproj
```

在 Xcode 里选择 `KaogongSchool` scheme 和任意 iPhone 模拟器，运行即可。
首次启动后进入「设置」：

1. 把 **后端 Base URL** 改成后端地址：
   - 模拟器：`http://127.0.0.1:8000`
   - 真机：`http://<Mac 的局域网 IP>:8000`（后端需监听 `0.0.0.0`）
2. 填写学习者 ID（默认 `local-user`）。
3. 模型配置与网页端共用，已配置过就不必重复填写。

## 已实现

- 对话：SSE 流式输出、辅导员转接提示、历史会话切换、回答朗读（系统 TTS）。
- 学情：练习次数 / 正确率 / 时长 / 覆盖度、薄弱点、本周计划勾选、模型用量。
- 考试：试卷列表、按科目/模块/题量/难度/AI 原创题数量组卷、限时作答、交卷判分。
- 资料：资料列表、文件上传（PDF/Word/图片/音频/视频）、网页导入、入库状态轮询。
- 设置：后端地址、学习者、学习档案、默认模型、API Key、Embedding、语音转写与单价。

## 说明

- 工程使用 Xcode 的 file-system synchronized group，新增 Swift 文件会自动加入 target。
- `KaogongSchool-Info.plist` 为本地开发放开了 HTTP（`NSAllowsArbitraryLoads`）；
  正式发布前应改为 HTTPS 并移除该例外。
- 真机访问 Mac 后端时，后端启动加 `--host 0.0.0.0`，并在 macOS 防火墙放行。
- 本地多用户没有登录鉴权，仅适合个人使用；公网部署前需要加认证。
- 命令行编译验证：

```bash
xcodebuild -project ios/KaogongSchool.xcodeproj \
  -target KaogongSchool -configuration Debug \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```
