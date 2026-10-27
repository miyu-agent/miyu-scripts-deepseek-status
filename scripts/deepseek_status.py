#!/usr/bin/env python3
# Display name: DeepSeek status
# 显示名称：DeepSeek 服务状态
# Description: Check DeepSeek's official status page: each service (API models, chat, search, file upload) with its state and 30-day uptime, plus ongoing and recent incidents.
# 描述：查 DeepSeek 官方状态页：各项服务（各个 API 模型、对话、搜索、上传文件）现在好不好、近 30 天可用率，正在发生的和最近的故障。
# Timeout: 30
# Clicall: yes
# Parameters:
# {"type": "object", "properties": {
#   "incidents": {"type": "integer", "minimum": 0, "maximum": 20, "description": "How many recent incidents to list, newest first; default 3, 0 for none."},
#   "format": {"type": "string", "enum": ["md", "json"], "description": "md (default) for reading; json for code, e.g. piping miyu call into jq or python."}
# }}
"""Reads https://status.deepseek.com/, a Next.js page: the data rides in
`self.__next_f.push([1,"…"])` chunks. Pulls initialPageConfig (components),
component_uptimes, active_changes (ongoing) and initialCalendarData (history).
"""

import datetime as dt
import json
import sys
import urllib.error
import urllib.request

URL = "https://status.deepseek.com/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MARKER = 'self.__next_f.push([1,"'
KEYS = ("initialPageConfig", "active_changes", "initialCalendarData", "component_uptimes")
CN = dt.timezone(dt.timedelta(hours=8))
SEVERITY = {"full_outage": 4, "major_outage": 4, "partial_outage": 3, "degraded": 2,
            "degraded_performance": 2, "maintenance": 1}
STATE_ZH = {"operational": "正常", "full_outage": "完全中断", "major_outage": "完全中断",
            "partial_outage": "部分中断", "degraded": "性能下降", "degraded_performance": "性能下降",
            "maintenance": "维护中", "investigating": "排查中", "identified": "已定位",
            "monitoring": "观察中", "resolved": "已解决"}


AS_JSON = [False]   # 读参数时一认出 json 就改，出错也照它交


def fail(message):
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False) if AS_JSON[0] else f"错误：{message}")
    sys.exit(1)


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        fail(f"状态页回 HTTP {exc.code}。可以让用户自己打开 {URL} 看")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"连不上 {URL}：{getattr(exc, 'reason', exc)}")


def chunks(html):
    """Each push payload is a JS string literal; JSON can decode it."""
    pos = 0
    while (start := html.find(MARKER, pos)) != -1:
        start += len(MARKER)
        end = start
        while end < len(html):
            if html[end] == "\\":
                end += 2
                continue
            if html[end] == '"' and html.startswith("])", end + 1):
                break
            end += 1
        pos = end
        try:
            text = json.loads(f'"{html[start:end]}"')
        except json.JSONDecodeError:
            continue
        # "<id>:<json>" lines; a chunk may hold several
        for line in text.split("\n"):
            _, sep, body = line.partition(":")
            if sep:
                try:
                    yield json.loads(body)
                except json.JSONDecodeError:
                    pass


def collect(value, found):
    if isinstance(value, dict):
        for key in KEYS:
            if key not in found and key in value:
                found[key] = value[key]
        for child in value.values():
            collect(child, found)
    elif isinstance(value, list):
        for item in value:
            collect(item, found)


def when(seconds):
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        return None
    return dt.datetime.fromtimestamp(seconds, CN)


def span(seconds):
    seconds = int(seconds)
    if seconds < 3600:
        return f"{max(1, round(seconds / 60))} 分钟"
    hours, rest = divmod(seconds, 3600)
    return f"{hours} 小时 {round(rest / 60)} 分钟" if rest >= 60 else f"{hours} 小时"


def zh(state):
    return STATE_ZH.get(state, state or "未知")


def names(change):
    return [c.get("name") or c.get("component_name") or "?" for c in change.get("affected_components") or []
            if isinstance(c, dict)]


def last_update(change):
    updates = [u for u in change.get("updates") or [] if isinstance(u, dict)]
    if not updates:
        return ""
    latest = max(updates, key=lambda u: u.get("at_seconds") or 0)
    text = (latest.get("description") or "").strip()
    return text.split("\n\n")[0].strip()  # 中文在前，英文在后


def known_params():
    """开头 Parameters 里写的参数名：不认识的参数直接报错，免得写错的名字被悄悄当成没给。"""
    lines, inside = [], False
    with open(__file__, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                break
            if line.startswith("# Parameters:"):
                inside = True
            elif inside:
                lines.append(line[1:])
    return set(json.loads("".join(lines)).get("properties", {}))


def reject_unknown(args):
    unknown = sorted(set(args) - known_params())
    if unknown:
        fail(f"不认识的参数：{'、'.join(unknown)}。能用的：{'、'.join(sorted(known_params()))}")


def main():
    try:
        args = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        fail(f"参数不是 JSON：{exc}")
    if not isinstance(args, dict):
        fail("参数要是一个 JSON 对象")
    AS_JSON[0] = args.get("format") == "json"
    reject_unknown(args)
    if args.get("format") not in (None, "md", "json"):
        fail(f"format 只认 md、json，不认 {args['format']}")
    count = args.get("incidents", 3)
    if isinstance(count, bool) or not isinstance(count, int):
        fail("incidents 要是 0 到 20 的整数")
    count = max(0, min(count, 20))

    found = {}
    for data in chunks(fetch()):
        collect(data, found)
    page = found.get("initialPageConfig") or {}
    components = [c for c in page.get("components") or [] if isinstance(c, dict)]
    if not components:
        fail(f"状态页的结构变了，读不出服务列表。可以让用户自己打开 {URL} 看")

    uptime = {u.get("component_id"): u.get("uptime") for u in found.get("component_uptimes") or []
              if isinstance(u, dict)}
    active = [c for c in found.get("active_changes") or [] if isinstance(c, dict)]
    state = {}
    for change in active:
        for item in change.get("affected_components") or []:
            if not isinstance(item, dict):
                continue
            cid, st = item.get("component_id"), change.get("status") or "unknown"
            if SEVERITY.get(st, 0) >= SEVERITY.get(state.get(cid), 0):
                state[cid] = st

    now = dt.datetime.now(CN)
    out = [f"DeepSeek 服务状态（{now:%Y-%m-%d %H:%M} 北京时间，来源 {URL}）"]
    out.append("全部正常" if not active else f"有 {len(active)} 起故障正在处理")
    out.append("")
    for comp in components:
        cid = comp.get("component_id")
        rate = uptime.get(cid)
        rate = f"，30 天可用率 {rate}%" if isinstance(rate, (int, float)) else ""
        out.append(f"- {comp.get('name', '?')}：{zh(state.get(cid, 'operational'))}{rate}")

    if active:
        out += ["", "正在处理："]
        for change in active:
            start = when(change.get("start_at_seconds"))
            began = f"{start:%m-%d %H:%M} 起，" if start else ""
            out.append(f"- {change.get('title', '?')}（{began}{zh(change.get('status'))}）")
            if names(change):
                out.append(f"  影响：{'、'.join(names(change))}")
            if last_update(change):
                out.append(f"  最新：{last_update(change)}")

    history = (found.get("initialCalendarData") or {}).get("changes") or []
    history = [c for c in history if isinstance(c, dict)]
    history.sort(key=lambda c: c.get("start_at_seconds") or 0, reverse=True)
    if count and history:
        out += ["", f"最近 {min(count, len(history))} 起故障："]
        for change in history[:count]:
            start, end = when(change.get("start_at_seconds")), when(change.get("close_at_seconds"))
            if start and end:
                period = f"{start:%m-%d %H:%M}，持续 {span((end - start).total_seconds())}"
            elif start:
                period = f"{start:%m-%d %H:%M} 起，还没结束"
            else:
                period = "时间不明"
            kind = "维护" if change.get("type") == "maintenance" else zh(change.get("status"))
            out.append(f"- {change.get('title', '?')}（{period}，{kind}）")
            if names(change):
                out.append(f"  影响：{'、'.join(names(change))}")
    if AS_JSON[0]:
        print(json.dumps(to_json(now, components, uptime, state, active, history[:count]), ensure_ascii=False))
    else:
        print("\n".join(out))


def stamp(seconds):
    moment = when(seconds)
    return moment.isoformat(timespec="minutes") if moment else None


def to_json(now, components, uptime, state, active, recent):
    def change_json(change, ongoing):
        out = {"title": change.get("title"), "type": change.get("type"), "status": change.get("status"),
               "started": stamp(change.get("start_at_seconds")), "affected": names(change)}
        if ongoing:
            out["latest_update"] = last_update(change) or None
        else:
            out["ended"] = stamp(change.get("close_at_seconds"))
        return out
    return {"ok": True, "checked": now.isoformat(timespec="minutes"), "source": URL, "all_operational": not active,
            "components": [{"name": c.get("name"), "status": state.get(c.get("component_id"), "operational"),
                            "uptime_30d": uptime.get(c.get("component_id"))
                            if isinstance(uptime.get(c.get("component_id")), (int, float)) else None}
                           for c in components],
            "ongoing": [change_json(c, True) for c in active],
            "recent": [change_json(c, False) for c in recent]}


if __name__ == "__main__":
    main()
