# DeepSeek AutoQA

基于 Python + Playwright 的大模型自动问答采集原型工具：读取 Excel 问题集，自动向 DeepSeek 网页版逐条提问，完整留存回答截图与引用信息。

## 功能

- 读取 Excel 问题集，逐条向 chat.deepseek.com 提问
- 自动截图保存完整回答内容（不截断、不遗漏）
- 引用来源提取（含折叠面板展开处理）
- 会话管理：每题独立会话，避免上下文污染
- 失败重试与限速控制，降低平台风控触发

## 环境要求

- Python >= 3.8
- Playwright + Chromium
- openpyxl（读取问题集）

## 使用

```bash
pip install playwright openpyxl
playwright install chromium
python autoqa.py --excel questions.xlsx --out ./output
```

## 说明

本仓库为个人学习原型，核心架构（provider 工厂、限流器、会话管理、截图留存）后续迭代进了生产级多平台采集引擎，覆盖 DeepSeek / 豆包 / 元宝 / Kimi / 通义千问 / 智谱六平台。
