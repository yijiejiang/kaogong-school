# 考公私塾 iOS 客户端

原生 SwiftUI 客户端，复用后端的 REST + SSE 接口。最低 iOS 17。

## 打开与运行

```bash
open ios/KaogongSchool.xcodeproj
```

在 Xcode 里选择 `KaogongSchool` scheme 和任意 iPhone 模拟器，运行即可。
首次启动后进入「设置」：

1. **推荐扫码**：Mac 网页端「设置 → 用 iPad / iPhone 扫码连接」会显示二维码；
   在 App 内点「扫码连接后端」扫描，或直接用系统相机扫码。
2. 也可以手动填写后端地址：
   - 模拟器：`http://127.0.0.1:8000`
   - 真机：`http://<Mac 的局域网 IP>:8000`（后端需用 `make backend-lan` 监听 `0.0.0.0`）
3. 填写学习者 ID（默认 `local-user`）。
4. 模型配置与网页端共用，已配置过就不必重复填写。iOS 设置页默认只显示「已由服务端配置」；
   需要临时修改时再展开「高级：修改服务端模型配置」。

## 已实现

- 对话：SSE 流式输出、Markdown 渲染（标题/列表/表格/代码块/引用）、辅导员转接提示、历史会话切换、回答朗读（系统 TTS）、对话框内上传资料；支持系统深色模式。
- 学情：练习次数 / 正确率 / 时长 / 覆盖度、薄弱点、本周计划勾选、模型用量。
- 考试：试卷列表、历史作答与成绩、继续作答、生成试卷（含 AI 原创题）、倒计时、答题卡、自动保存、自动交卷、完整批改报告（逐题解析、评分细则、举一反三、对应技能、知识点/技能掌握度变化）。
- 知识：一个 Tab 内切换「资料 / 挖掘 / 技能地图」。
  - 资料：上传文件 / 网页 / 示例资料、资料详情与分块标签、视频关键帧与时间范围、重新索引、删除、资料库检索、知识树与知识卡片。
  - 挖掘：知识单元与技能审核、按状态/新知识点筛选、查看步骤/考法/变式/易错点、编辑标题和摘要、创建新知识点、重新抽取。
  - 技能地图：按科目/模块查看技能掌握状态（熟练/会用/了解/不清楚/待复习）、技能详情、来源资料和知识点估算标注。
- 设置：后端连接状态（延迟/失败原因）、连接历史（点一下切换并重连）、扫码连接、学习者、学习档案、默认模型与端点、每个角色的独立模型/端点/Key/采样参数、Embedding、语音转写、DeepSeek 官方能力配置；填写 Base URL + Key 后可「获取模型」并从列表选择。

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
