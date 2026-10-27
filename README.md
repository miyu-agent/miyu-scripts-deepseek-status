# DeepSeek 服务状态

Miyu 脚本包，带一件工具 `deepseek_status`：读 DeepSeek 官方状态页 <https://status.deepseek.com/>，交回每项服务（各个 API 模型、对话、搜索、上传文件……）现在的状态和近 30 天可用率，正在处理的故障（影响哪些服务、最新进展），和最近几起故障。

| 参数 | 说明 |
|---|---|
| `incidents` | 列最近几起故障，0–20，默认 3；0 不列 |
| `format` | `md`（默认）给人和 AI 读；`json` 给代码用，比如 `miyu call` 接 `jq`、Python。出错也是 JSON：`{"ok": false, "error": …}` |

服务列表照状态页现有的列，不写死。时间是北京时间。只用标准库。状态页是 Next.js 页面，数据从页面里的 `self.__next_f.push` 片段里读；页面改版读不出时会说清楚，让用户自己打开状态页看。
