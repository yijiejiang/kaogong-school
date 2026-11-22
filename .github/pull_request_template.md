---
name: Pull Request
about: 提交一个改动
title: ""
labels: ""
assignees: ""
---

## 改了什么

<!-- 一两句话说明这个 PR 做了什么 -->

## 为什么

<!-- 关联 Issue，说明动机或要解决的问题。没有 Issue 就说明背景 -->

Closes #

## 怎么验证的

<!-- 贴出实际运行的命令和结果 -->

- [ ] `cd backend && uv run ruff check .`
- [ ] `cd backend && uv run pytest -q`
- [ ] `cd frontend && pnpm build`（改了前端时）
- [ ] `make ios-build`（改了 iOS 时）
- [ ] `cd backend && uv run python scripts/evaluate_library.py`（改了资料解析 / 打标 / 检索时）

## 截图

<!-- 界面改动请附截图或录屏；没有则删除本节 -->

## 已知边界

<!-- 这个改动还没覆盖什么？有哪些限制？ -->

## 检查清单

- [ ] 一个 PR 只做一件事，没有混入无关的格式化改动
- [ ] 新增或修改了配置项，已同步 `.env.example` 与 README
- [ ] 新增或修改了 API，已同步前端类型 / iOS 模型
- [ ] 涉及 LLM 输出的路径有失败回退
- [ ] 没有提交 `backend/.env`、API Key、`backend/data/` 下的资料或数据库
- [ ] 同意以 [MIT](../LICENSE) 许可证发布本次贡献
