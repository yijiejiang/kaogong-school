# 资料库评测

`library_cases.json` 是资料库的黄金集：

- `tagging`：片段 → 期望主知识点、期望 chunk 类型
- `retrieval`：查询 → 期望命中的知识点

运行：

```bash
cd backend
uv run python scripts/evaluate_library.py
```

脚本会输出：

- 主知识点 Top-1 准确率
- Top-3 多标签召回率
- chunk 类型准确率
- 检索 Recall@5

阈值低于 0.70 时脚本以非 0 退出。首次运行如果资料库没有可用分块，会自动导入内置示例资料。

修改打标规则、分块策略或 Embedding 模型后，先跑这个脚本，再决定是否合并。
