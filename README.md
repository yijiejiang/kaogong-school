# 考公私塾（Kaogong School）

个人考公多智能体辅导系统。目标：**单一对话框 + 辅导员主入口 + 专业老师协同 + 资料/知识/出卷/改卷/学情闭环**。

架构图与分层说明见 [docs/architecture.md](docs/architecture.md)。

## 当前阶段

- **P0 已跑通**：辅导员主入口、学习督导/出卷老师转接、SSE 流式、会话持久化、LLM 按角色配置。
- **P1 已接入**：资料库（PDF/DOCX/TXT/Markdown/网页）、自动分块与知识点打标、混合检索、资料搜集/资料整理/知识点整理三个 Agent、知识树与知识卡片、聊天内文件上传。
- **P2 已接入**：题库与组卷、考试中心、限时答题、自动保存、客观题+主观题评分、举一反三、错题本、掌握度 v1、改卷老师对话解释。
- **P3 已接入**：学情看板（雷达/趋势/热力图/薄弱点/覆盖度）、掌握度 v2、周计划与每日任务、周报、督导老师真实学情与计划生成。
- **P4 已接入**：图片 OCR、视频字幕/语音转写、每日提醒/周报通知、PWA；图片/音频/视频入库。
- **P4.5 已接入**：五模块题库与申论主观题、AI 原创题、按角色 token/成本看板、模型自动发现与按角色独立配置、本地多用户、launchd 常驻、Cloud Run 部署文件、SwiftUI iOS 客户端。
- **后续**：真实 LLM 全链路验收、对象存储、登录鉴权、多设备同步、语音对话与更完整的移动端。

## 技术栈

- 后端：Python 3.12、FastAPI、Google ADK、LiteLLM、SQLAlchemy、SQLite/PostgreSQL
- 前端：Next.js App Router、TypeScript、Tailwind CSS
- 检索：本地哈希向量或 OpenAI 兼容 Embedding API + 关键词混合检索
- 部署：Mac 本地优先；Docker Compose 提供 PostgreSQL / Redis

## 目录

```
backend/    FastAPI + ADK 智能体 + 资料入库 + 检索 + 考试
frontend/   Next.js 聊天 / 资料库 / 考试 / 学情看板 / 设置
ios/        SwiftUI iOS 客户端（Xcode 工程）
deploy/     launchd 常驻脚本与 Cloud Run 部署说明
docker-compose.yml
Makefile
```

## 快速开始

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 APP_SECRET_KEY
make install
make infra        # 可选：启动 PostgreSQL / Redis；默认使用 SQLite
make backend      # http://localhost:8000
make frontend     # http://localhost:3000
```

移动端：

```bash
open ios/KaogongSchool.xcodeproj
```

在 iOS「设置」里把后端地址改成 `http://127.0.0.1:8000`（模拟器）或
`http://<Mac 局域网 IP>:8000`（真机，后端用 `make backend-lan` 启动）。

常驻运行（开机自启）：

```bash
make install-service    # 生成 launchd plist 并启动后端
make service-logs       # 查看后端日志
make uninstall-service  # 停止并移除
```

首次打开网页后，进入“设置”填写 LLM 的 Base URL、API Key 与模型名，保存并测试连接。

### 先不配 Key，体验完整链路

如果没有可用的 LLM Key，可以先用本地演示模式：

```bash
make backend-demo   # MOCK_LLM=1 uvicorn ... --reload
make frontend
```

演示模式会返回固定的学情报告、出卷卡片和知识库回答。资料入库默认使用本地哈希向量，
所以**不需要 Embedding Key 也能上传、分块、检索、带引用回答**。

配置真实模型后，在 `backend/.env` 里设置 `MOCK_LLM=0` 并重启后端即可切换。

> 如果设置页填了真实 API 仍显示「本地演示模式」，说明后端是以 `MOCK_LLM=1` 启动的。
> 请用 `make backend` 启动，而不是 `make backend-demo`；设置页的模型配置不会覆盖这个启动参数。

## P1 能力

- 资料上传：PDF、DOCX、TXT、Markdown；单文件上限 50 MB。
- 网页导入：公网 http/https，带 SSRF 防护。
- 入库流水线：解析 → 清洗 → 按结构分块 → 知识点打标 → 向量化 → 写入索引。
- 知识树：行测 / 申论两棵树，覆盖言语、数量、判断、资料、常识、申论五大题型。
- 知识卡片：每个知识点有 summary / methods / traps，资料分块会挂到对应知识点。
- 混合检索：向量相似度 + 中文关键词；结果带《资料名》和页码引用。
- 资料库页面：上传、网页导入、状态轮询、分块预览、重新索引、删除、检索测试。
- 聊天上传：对话框左侧回形针上传后，资料卡片会出现在对话中，可跳到资料库查看进度。
- 三个新 Agent：
  - 资料搜集：处理上传/链接/网页搜索，报告资料状态；
  - 资料整理：查看入库质量、失败原因，重新索引；
  - 知识点整理：基于资料库回答，必须带来源，资料不足时明确说明。

P1 还未接入：AI 原创题/多模块题库、视频转写与 OCR。

## P2 能力

- **题库**：内置资料分析 38 题、言语理解、数量关系、判断推理、常识判断与申论主观题，
  共 80+ 道合成题，保证没有 LLM Key 也能完整演示。
- **组卷**：按科目、模块、题量、限时、难度从题库组卷；30 题默认 28 单选 + 2 简答，总分 100。
- **AI 原创题**：配置真实 LLM 后，可按题量生成原创单选；生成失败或演示模式自动回退题库并提示。
- **考试中心**：生成试卷、最近试卷、最近作答。
- **答题页**：倒计时、题目导航、答题卡、自动保存、时间到自动交卷。
- **判分**：客观题自动判分；主观题按评分细则踩点给分（真实 LLM 可用时调用 grader 模型，失败回退关键词）。
- **报告**：总分/得分率、逐题解析、评分细则命中、错题本、举一反三 3 条、知识点掌握度变化。
- **改卷老师**：在对话里读取最近一次报告，解释错题和变式。

P2 已完成 AI 原创题、多模块题库与图片/音频/视频入库；真实 LLM 下的 AI 命题仍需用有效 Key 验收。

## P3 能力

- **学情看板**：行测五模块雷达图、最近 14 天正确率趋势、知识点热力图、薄弱点、覆盖度。
- **掌握度 v2**：按题目难度加权、计算置信度、按时间衰减、生成复习到期日（1/3/7/14 天间隔）。
- **周计划**：按薄弱点、到期复习和未覆盖知识点自动生成 7 天任务；支持生成本周计划、每日任务勾选和完成率。
- **周报**：本周练习次数、题量、正确率、错题、学习时长、计划完成度，全部来自真实作答记录。
- **督导老师**：在对话里读取真实学情快照，能直接生成本周计划。
- **主动提醒**：看板顶部显示考试倒计时、到期复习、未练习知识点；后台定时调度见 P4。

## P4 能力

- **图片 OCR**：上传 PNG/JPG/WebP，使用 macOS Vision 中文 OCR；tesseract 作为英文兜底；OCR 文本进入分块、知识点打标和 RAG。
- **视频导入**：支持 Bilibili/YouTube 等视频 URL；优先抓字幕，字幕缺失或限流时索引视频简介并给出提示。
- **语音转写**：音频文件与视频音轨可走 OpenAI 兼容 `/audio/transcriptions`；也可安装
  `faster-whisper` 做本地转写。未配置时明确提示，不会编造内容。
- **常驻督导**：后端启动后每 30 分钟检查一次，生成每日学习提醒；周一生成本周周报通知。通知铃铛显示未读数，支持单条/全部已读。
- **PWA**：manifest、192/512 图标、Apple touch icon；iOS Safari 可“添加到主屏幕”，暂不包含离线缓存。
- **本地优先**：OCR、通知、计划和周报都在本地完成，不上传资料内容。

## P4.5 能力

- **五模块题库**：资料分析、言语理解与表达、数量关系、判断推理、常识判断，外加申论归纳概括/综合分析/提出对策/文章写作主观题。
- **AI 原创题**：组卷时可指定 0–10 道 AI 命题；演示模式、未配置模型或调用失败会自动回退题库，并在试卷 `warning` 中说明。
- **用量与成本**：每次对话按角色记录 prompt/completion token；设置页可填输入/输出单价，学情看板显示 14 天用量、成本与角色分布。
- **本地多用户**：设置页可切换学习者 ID；资料库共享，做题记录、掌握度、计划与通知按学习者隔离。
- **常驻运行**：`make install-service` 用 launchd 开机自启后端，日志写到 `backend/data/logs/`。
- **Cloud Run**：`backend/Dockerfile` + `deploy/cloudrun.md`，建议配 Cloud SQL PostgreSQL；本地上传目录仍需接对象存储。
- **Swift iOS**：`ios/` 是原生 SwiftUI 客户端，支持对话流式、学情、考试、资料上传与设置。

### 通知与常驻督导说明

- 调度器是后端进程内的轻量循环，后端运行时才生效；`make install-service` 可让后端开机自启。
- 通知通过 `dedupe_key` 去重：同一天同一用户只生成一条每日提醒、一条周报。
- 视频字幕/音频下载可能受平台限流或需要登录 Cookie；失败时会回退到视频简介，不会编造字幕内容。

## 模型配置

- **主流平台预设**：OpenDesign / AMR、OpenAI、DeepSeek、硅基流动、Moonshot、智谱 GLM、
  通义千问 DashScope、OpenRouter、Ollama、LM Studio；选中后自动填入 Base URL。
- **模型自动发现**：填好 Base URL / API Key 后点「获取」，调用 OpenAI 兼容的 `/models`
  拉取模型列表，可在默认模型、角色模型、Embedding、语音转写输入框下拉选择。
- **全局默认**：Base URL、API Key、默认模型；未单独配置的角色和服务都会使用它。
- **按角色独立配置**：每个角色可设置自己的模型、Base URL、API Key、temperature、max_tokens、top_p；
  留空即沿用全局。适合辅导员用便宜模型、出卷/改卷用强推理模型，或不同角色接不同供应商。
- **Embedding / 语音转写**：各自支持独立的模型、Base URL 与 API Key，留空沿用全局。
- **安全**：全局与角色的 API Key 都加密存储，接口只返回脱敏值；角色 Key 可一键清除。
- **连通性测试**：全局和每个角色都有独立「测试」按钮，按该角色自己的端点和参数发起请求。

## Embedding 与检索

- **不填 Embedding 模型**：使用 `hash-384` 本地哈希向量，不需要 Key，适合演示和中小资料库。
- **填写 Embedding 模型**：例如 `text-embedding-3-small`、`bge-m3`；会复用 LLM 的 Base URL / API Key
  调用 OpenAI 兼容的 Embedding API。更换模型后请到资料库点“重新索引”。
- 检索分数 = 向量相似度 + 关键词命中；回答会引用《资料名》与页码（如 PDF 有页码）。

## 网页搜索

资料搜集 Agent 的 `web_search` 需要 Tavily：

```bash
# backend/.env
TAVILY_API_KEY=你的_key
```

未配置时会明确返回“暂时不能进行网页搜索”，不会编造结果。

## 主要 API

```
POST /api/chat/stream             SSE 对话
GET  /api/chat/sessions           会话列表
GET  /api/chat/sessions/{id}/messages

POST /api/materials/upload        上传资料
POST /api/materials/import-url    导入网页
POST /api/materials/seed-sample   导入内置示例资料
GET  /api/materials               资料列表
GET  /api/materials/{id}          资料详情 + 分块
POST /api/materials/{id}/reindex  重新索引
DELETE /api/materials/{id}        删除资料
POST /api/search                  资料库检索
GET  /api/knowledge/tree          知识树
GET  /api/knowledge/cards/{kp_id} 知识卡片

POST /api/exams/generate          按条件生成试卷
GET  /api/exams                   试卷列表
GET  /api/exams/{id}              试卷详情（不含答案）
POST /api/exams/{id}/start        开始/继续作答
POST /api/attempts/{id}/answers   自动保存答案
POST /api/attempts/{id}/submit    交卷并判分
GET  /api/attempts/{id}/report    批改报告
GET  /api/attempts                作答历史

GET  /api/analytics/overview      学情总览（统计/雷达/热力图/趋势/薄弱点）
GET  /api/analytics/weekly-report 本周周报
GET  /api/analytics/usage         按角色 token / 成本统计
GET  /api/plan/week               本周计划
POST /api/plan/generate           按薄弱点生成/重排本周计划
PATCH /api/plan/tasks/{id}        勾选任务完成

GET  /api/notifications           通知列表 + 未读数
PATCH /api/notifications/{id}/read 单条已读
POST /api/notifications/read-all  全部已读
POST /api/notifications/run       手动触发生成（调试/测试）

GET  /api/asr/status              语音转写是否可用
POST /api/asr/transcribe          音频转文字

GET  /api/users                   本地学习者列表
GET/PUT /api/settings             LLM / Embedding / ASR / 单价 / 学习档案
POST /api/settings/models         用 Base URL + Key 获取模型列表
POST /api/settings/test           LLM 连通性测试
```

所有按学习者隔离的接口都接受 `user_id` 查询参数；网页与 iOS 客户端会把当前学习者 ID
自动带上。

## 说明

- 默认数据库为 SQLite，开箱即用；切换 PostgreSQL 时把 `DATABASE_URL` 改为
  `postgresql+asyncpg://kaogong:kaogong@localhost:5433/kaogong`，并执行 `make infra`。
- 上传文件、索引数据都在 `backend/data/`，备份该目录即可。
- API Key 在数据库中加密存储，接口返回时脱敏；`APP_SECRET_KEY` 变更后需要重新填写 Key。
- 扫描版 PDF 暂未接入 OCR；图片 OCR 与音频/视频转写已接入。
- 题库是内置合成题，保证没有 LLM Key 也能完整演示；AI 原创题需要有可用的 LLM。
- 主观题评分在本地演示模式使用评分细则关键词；配置真实 LLM 后会调用 grader 模型，失败时回退关键词。
- 学情看板、周计划和周报使用确定性规则计算，不依赖 LLM；督导老师只负责解释这些真实数据。
- 图片 OCR 使用 macOS Vision；没有中文视觉能力时会回退到 tesseract 英文识别，复杂手写体的准确率会下降。
- 视频字幕受平台限流/Cookie 影响；没有字幕时先尝试语音转写，再回退视频简介。
- 语音转写复用 LLM 的 Base URL / API Key 调用 `/audio/transcriptions`；也可安装
  `faster-whisper` 做本地转写（`uv pip install faster-whisper`）。
- 成本看板按设置页填写的单价估算；单价为 0 时只统计 token，不计算金额。
- 本地多用户没有登录鉴权，仅适合个人电脑使用；公网部署前必须加认证。
- PWA 目前是安装壳，没有离线缓存；Swift iOS 客户端已复用同一套 REST + SSE API。
- 常驻运行用 `make install-service`；日志在 `backend/data/logs/`。Cloud Run 部署见 `deploy/cloudrun.md`。
- 真实 LLM 全链路（对话、AI 命题、主观题 LLM 评分、语音转写）仍需用有效 Key 做最终验收。
