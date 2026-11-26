# 参与贡献

感谢你愿意改进考公私塾。这个项目最初是为一个人的备考做的，所以最看重的是「真实能用、边界清楚、不编造」。

## 开始之前

- 先搜一下现有 Issue 和 PR，避免重复。
- 较大的功能（新 Agent、新数据源、架构调整）建议先开 Issue 说明动机和方案，再动手。
- 小修复（错字、样式、明确 bug）可以直接提 PR。

## 环境准备

```bash
git clone https://github.com/yijiejiang/kaogong-school.git
cd kaogong-school
cp backend/.env.example backend/.env
make install
```

至少需要：

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js 20+ 与 pnpm
- macOS（图片 OCR 与 iOS 需要）
- `ffmpeg`（视频抽帧与音频处理）

## 开发

```bash
make backend        # http://localhost:8000
make frontend       # http://localhost:3000
make backend-demo   # 无 Key 的本地演示模式
```

不需要 LLM Key 也能跑通资料入库、检索、出卷、判分和学情：

- 资料入库默认使用本地 `hash-384` 向量；
- 没有真实模型时，对话和 AI 原创题会使用内置演示逻辑。

## 提交前自检

```bash
cd backend && uv run ruff check app tests scripts && uv run pytest -q
cd frontend && pnpm build
```

如果改了资料解析、打标或检索，请额外跑评测：

```bash
cd backend && uv run python scripts/evaluate_library.py
```

如果改了 iOS：

```bash
make ios-build
```

请在 PR 描述里贴出实际运行的命令和结果，而不是「应该能通过」。

## 代码约定

### 后端（Python）

- 使用 `uv` 管理依赖，不要直接改 `requirements.txt`。
- 遵循 `ruff` 规则（`uv run ruff check app tests scripts`，与 CI 一致）。
- 异步优先：数据库、HTTP、文件 IO 用 `async`；阻塞操作放 `asyncio.to_thread`。
- 新增 API 时同步补测试（`backend/tests/test_api.py`）。
- 新增配置项时同步更新 `backend/.env.example` 和 README 的配置表。
- 不要提交 `backend/.env`、API Key、`backend/data/` 下的资料或数据库。

### 前端（TypeScript / React）

- 使用 TypeScript，优先 `const`、可选链和空值合并。
- 组件保持小而专注，样式使用 Tailwind。
- API 类型定义放在 `frontend/lib/types.ts`，请求封装放在 `frontend/lib/api.ts`。
- 页面配色沿用现有的暖色纸张风格与 `Theme` 变量，不要引入新的主色。

### iOS（SwiftUI）

- 最低 iOS 17，使用 Xcode 的 file-system synchronized group，新文件会自动加入 target。
- 颜色统一走 `Theme`，不要硬编码明暗模式颜色。
- 新增接口时同步更新 `Models.swift` 与 `APIClient.swift`。

### 资料与知识逻辑

这部分最容易「看起来对但实际错」，请特别注意：

- 不要编造资料内容、页码、时间戳或分数。
- 资料不足时，工具应返回明确的不可用信息，而不是猜测。
- 检索与打标改动需要能被 `backend/evals/library_cases.json` 验证。
- 涉及 LLM 输出的地方要有失败回退，不能让一次模型错误导致整个任务失败。

## 提交信息

用中文或英文都可以，保持一行摘要 + 可选的要点正文，例如：

```
修复视频字幕缺少时间戳时的对齐问题

- 无字幕时不再用简介代替时间轴
- 补充对应的单元测试
```

## Pull Request

- 一个 PR 只做一件事；把无关的格式化改动拆出去。
- 描述里说明：改了什么、为什么改、怎么验证的、有什么已知边界。
- 涉及界面改动时附上截图或录屏。
- 涉及数据库结构改动时说明迁移方式（当前用 `create_all` + `_ensure_columns` 兼容旧库）。
- 如果引入新的外部依赖（模型、API、二进制工具），说明它是否必需、如何降级。

## 安全与隐私

- 不要把 API Key、Cookie、个人资料或真实试卷上传到仓库或 Issue。
- 报告安全问题时请不要公开利用细节，先通过 Issue 说明大致范围，由维护者联系你。
- 本项目是个人本地优先工具，默认没有登录鉴权；涉及公网部署的改动请明确说明风险。

## 行为准则

- 讨论聚焦技术本身，尊重不同水平和背景的贡献者。
- 不接受针对个人的攻击、歧视性言论或骚扰。
- 维护者可以关闭不符合上述原则的 Issue 或 PR。

## License

提交代码即表示你同意以 [MIT](LICENSE) 许可证发布你的贡献。
