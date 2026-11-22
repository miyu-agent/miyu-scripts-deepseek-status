<p align="center">
  <a href="README.md">English</a> | 简体中文
</p>

# DeepSeek 服务状态

> <sub>本文档由 Anthropic 的 Claude Fable 5.2 生成。</sub>

这是 Miyu 的一个脚本软件包，提供一件工具 `deepseek_status`。它读取 DeepSeek 官方状态页 <https://status.deepseek.com/>，返回每项服务（各个 API 模型、对话、搜索、上传文件……）现在的状态和近 30 天的可用率、正在处理的故障（影响哪些服务、最新进展），以及最近几起故障。

| 参数 | 说明 |
|---|---|
| `incidents` | 列出最近几起故障，0–20，默认 3；0 表示不列出 |
| `format` | `md`（默认）给人和 AI 阅读；`json` 给代码使用，例如用 `miyu call` 接上 `jq` 或者 Python。出错时同样返回 JSON：`{"ok": false, "error": …}` |

服务列表按状态页现有的内容列出，没有写死在脚本里。时间是北京时间。工具只使用标准库。状态页是 Next.js 页面，数据从页面里的 `self.__next_f.push` 片段里读取；如果页面改版以后读不出数据，工具会明确说明，并让用户自己打开状态页查看。
