# 考公私塾（Kaogong School）

个人考公多智能体辅导系统。目标：**单一对话框 + 辅导员主入口 + 专业老师协同 + 资料/知识/出卷/改卷/学情闭环**。

架构图与分层说明见 [docs/architecture.md](docs/architecture.md)。

## 当前阶段

- **P0 已跑通**：辅导员主入口、学习督导/出卷老师转接、SSE 流式、会话持久化、LLM 按角色配置。
- **P1 已接入**：资料库（PDF/DOCX/TXT/Markdown/网页）、自动分块与知识点打标、混合检索、资料搜集/资料整理/知识点整理三个 Agent、知识树与知识卡片、聊天内文件上传。
- **P2 已接入**：题库与组卷、考试中心、限时答题、自动保存、客观题+主观题评分、举一反三、错题本、掌握度 v1、改卷老师对话解释。
- **P3 已接入**：学情看板（雷达/趋势/热力图/薄弱点/覆盖度）、掌握度 v2、周计划与每日任务、周报、督导老师真实学情与计划生成。
- **P4 已接入**：图片 OCR、视频字幕/语音转写、每日提醒/周报通知、PWA；图片/音频/视频入库。
- **P4.5 已接入**：五模块题库与申论主观题、AI 原创题、按角色 token/成本看板、模型自动发现与按角色独立配置、资料多标签打标与 chunk 类型、评测集、本地多用户、launchd 常驻、Cloud Run 部署文件、SwiftUI iOS 客户端。
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

iPad / iPhone 连接后端最简单的方式是扫码：

1. Mac 与 iPad 连接同一个 Wi-Fi。
2. 后端用 `make backend-lan` 启动（监听 `0.0.0.0`）。
3. 打开网页端「设置 → 用 iPad / iPhone 扫码连接」，用 iPad 系统相机扫码，
   或在 App 内「设置 → 扫码连接后端」扫码。
4. 扫码会自动写入 `http://<Mac 局域网 IP>:8000`，不需要手输 IP。

模拟器也可以直接使用 `http://127.0.0.1:8000`。真机连不上时，检查 macOS
防火墙是否允许 Python/uvicorn 接受传入连接。

外网访问（不在同一 Wi-Fi）推荐 Tailscale：Mac 和 iPad 登录同一个 tailnet，
用 `tailscale serve` 暴露私有 HTTPS 地址，再设置 `PUBLIC_BASE_URL` 即可让二维码
编码这个地址。完整步骤见 [deploy/tailscale.md](deploy/tailscale.md)。

TestFlight 打包与上传步骤见 [deploy/testflight.md](deploy/testflight.md)。

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
- **Swift iOS**：`ios/` 是原生 SwiftUI 客户端，支持对话流式、Markdown 渲染、学情、考试、资料上传与设置；设置页显示连接状态与连接历史，支持扫码连接后端。模型配置由服务端统一管理，iOS 默认不要求重复配置。
- **远程访问**：`PUBLIC_BASE_URL` 可指向 Tailscale Serve 的私有 HTTPS 地址，二维码会优先使用它；局域网未配置时仍自动检测 Mac IP。

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

## 资料库智能打标

- **多标签**：每个分块保留 Top-3 候选知识点、分数和置信度，不再只取一个最佳标签。
- **混合召回**：关键词命中 + 分块向量与知识点画像的相似度共同打分；知识点画像包含名称、描述、知识卡的 summary/methods/traps。
- **chunk 类型**：method / formula / definition / trap / example / question / summary，按标题和正文线索分类。
- **标题路径**：保留 `资料 > 章节 > 小节` 路径，例如「资料分析速算技巧 > 二、截位直除」。
- **评测集**：`backend/evals/library_cases.json` 覆盖打标、类型和检索用例；运行 `cd backend && uv run python scripts/evaluate_library.py` 查看 Top-1、Top-3 召回、类型准确率和 Recall@5。
- 旧资料需要点一次「重新索引」才会生成多标签、类型和标题路径；新资料入库时自动完成。

## 视频幻灯片理解（MVP）

视频链接入库时，除了字幕/语音稿，还会抽取画面并整理成逐页笔记：

- **抽帧**：`ffmpeg` 按 2–8 秒采样（视频越长间隔越大，最多约 300 帧），避免逐帧处理。
- **幻灯片识别**：macOS Vision OCR 每帧文字，用 dHash + 文本相似度合并连续相似画面，选出每页最完整的代表帧。
- **时间对齐**：优先使用带时间戳的字幕；没有字幕时使用带时间戳的本地语音转写，再退化为按时间均分讲解稿。
- **本地转写**：没有字幕的视频需要 `uv add faster-whisper`；默认使用 `small` 模型，可用 `ASR_LOCAL_MODEL=medium` 提升准确率，或在 `.env` 配置独立 ASR API。
- **逐页总结**：知识角色模型为每页生成标题、摘要和要点；模型不可用时使用 OCR 首行和原文摘要兜底。
- **入库与展示**：每个分块带 `time_start / time_end / frame_path`，资料库分块预览显示时间范围和关键帧缩略图；关键帧通过 `/api/materials/{id}/frames/{filename}` 提供。
- **回退**：抽帧或幻灯片识别失败时，自动回退到原来的字幕/语音稿索引，不影响资料可用性。

MVP 目前使用固定采样，不含镜头检测、动画合并和视觉模型图表理解；字幕缺失时讲解与画面的对齐是近似值。

## 知识挖掘与审核

- **入库自动抽取**：资料索引完成后，从方法 / 公式 / 定义 / 陷阱 / 例题分块中抽取知识单元（标题、定义、适用条件、步骤、易错点、例子、原文依据）。
- **深度洞察**：每个知识单元/技能还会整理「怎么考、题目识别信号、常见变式、出题人怎么设干扰、关联知识点」。
- **LLM + 规则双通道**：知识角色配置了模型时按每批 4 个分块调用 LLM；输出被截断时自动二分重试，未覆盖的片段用规则抽取补齐；`ENABLE_KNOWLEDGE_EXTRACTION=0` 可关闭。
- **技能聚类**：同一知识点下的知识单元按技能名归一化合并为技能，聚合步骤、易错点、考法、变式和来源单元。
- **新知识点候选**：抽取时如果发现现有知识树没覆盖的新考点，会写入「新知识点候选」；在「知识挖掘 → 新知识点」里一键挂到父级知识点下。
- **技能地图**：侧边栏「技能地图」按科目/模块展示每项技能的掌握状态（熟练/会用/了解/不清楚/待复习），点开可看考法、识别信号、步骤、易错点、变式和来源资料。
- **技能级掌握度**：出卷时为题目匹配 `skill_id`，交卷后按题目更新 `skill_mastery`；技能地图优先显示真实技能练习数据，没有技能数据时回退到知识点掌握度并标注「知识点估算」。
- **试卷报告**：逐题报告显示对应技能和技能掌握变化，改卷老师也可以按技能解释错题。
- **知识老师**：回答时按「是什么 → 怎么识别 → 标准步骤 → 易错点 → 怎么考 → 变式/关联」组织，并可通过 `find_skills` / `get_skill_detail` / `get_skill_overview` 查技能地图。
- **审核流**：知识单元和技能都有 `draft / approved / rejected` 状态，可在「知识挖掘」页编辑、通过、驳回、退回。
- **重新抽取**：资料重新索引会清空该资料的旧单元；审核页可对单份资料手动重新抽取。
- **入口**：侧边栏「知识挖掘」或资料库右上角；预览默认只看待审核内容。
- PDF 解析会去除重复页眉页脚、水印、页码和目录点线，并识别「一、」「6.3」等中文标题层级；旧资料需重新索引后生效。

## Embedding 与检索

- **不填 Embedding 模型**：使用 `hash-384` 本地哈希向量，不需要 Key，适合演示和中小资料库。
- **填写 Embedding 模型**：例如 `text-embedding-3-small`、`bge-m3`；会复用 LLM 的 Base URL / API Key
  调用 OpenAI 兼容的 Embedding API。更换模型后请到资料库点“重新索引”。
- 检索分数 = 向量相似度 + 关键词命中；回答会引用《资料名》与页码（如 PDF 有页码）。

## 联网搜索与 DeepSeek 官方能力

资料搜集 Agent 的 `web_search` / `read_web_page` 优先使用 DeepSeek 官方 Search / Fetch 接口；没有配置时回退 Tavily：

- **DeepSeek 官方能力**：设置页「DeepSeek 官方能力（可选）」填官方 Base URL 和 Key（默认 `https://api.deepseek.com`），或写 `backend/.env` 的 `DEEPSEEK_API_KEY`。
- **Tavily 兜底**：`backend/.env` 中配 `TAVILY_API_KEY=你的_key`。
- 两者都没有时，工具会明确返回“暂时不能进行网页搜索”，不会编造结果。

DeepSeek 官方 Key 还用于：

- **扫描版 PDF OCR**：PyMuPDF 提取不到文字的 PDF 会调用 `/v1/tools/ocr` 逐页识别；图片仍优先用 macOS Vision，识别为空时再调官方 OCR。
- **短音频转写**：≤ 8 MB 的音频优先走 `/v1/tools/asr`，失败或超限时回退到已配置的 ASR 端点或本地 faster-whisper。
- **日期元信息**：每个 Agent 的指令会带上当前日期与星期，计划和倒计时不再依赖模型猜测。

这些接口与聊天模型相互独立，不会改变当前聊天/出卷/改卷使用的代理模型。

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
GET  /api/materials/{id}/frames/{filename} 视频关键帧图片
POST /api/materials/{id}/reindex  重新索引
DELETE /api/materials/{id}        删除资料
POST /api/search                  资料库检索
GET  /api/knowledge/tree          知识树
GET  /api/knowledge/cards/{kp_id} 知识卡片
GET  /api/knowledge/units         知识单元（可按 status/material_id/knowledge_point_id 过滤）
PATCH /api/knowledge/units/{id}   编辑或审核知识单元
GET  /api/knowledge/skills        技能列表
GET  /api/knowledge/skills/{id}   技能详情 + 来源单元
PATCH /api/knowledge/skills/{id}  编辑或审核技能
GET  /api/knowledge/skill-map     个人技能地图（按科目/模块聚合掌握度）
POST /api/knowledge/units/{id}/create-point 把新知识点候选落到知识树
POST /api/knowledge/extract/{material_id} 重新抽取资料的知识单元

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
GET  /api/connect/info            局域网地址与扫码 payload
GET  /api/connect/qr.png          连接二维码
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
