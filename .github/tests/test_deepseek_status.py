# deepseek_status.py 的测试（审计 2026-11-18）。
#
# 跑法（在仓库根）：
#   python3 -I -B -m unittest discover -s .github/tests
# （不加 -t .：.github 不是合法的包名，加了 unittest 会报 Start directory is not importable。）
#
# 只用标准库；不联网：urllib.request.urlopen 换成交回构造页面的桩。HOME、XDG_*、MIYU_* 都指到临时目录。
# 放在 .github/tests/ 而不是 tests/：打包会跳过 .github，测试不会进包。

import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "deepseek_status.py"


def load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("deepseek_status_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def page(data):
    """照状态页的样子：数据装在 self.__next_f.push([1,"<id>:<json>"]) 里。"""
    return 'self.__next_f.push([1,"' + json.dumps("0:" + json.dumps(data))[1:-1] + '"])'


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Sandbox(unittest.TestCase):
    """每条测试一个临时目录，环境里去掉所有 MIYU_*、XDG_*。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("MIYU_", "XDG_"))}
        env.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "cfg"),
                   XDG_CACHE_HOME=str(root / "xdg-cache"), XDG_STATE_HOME=str(root / "xdg-state"),
                   XDG_DATA_HOME=str(root / "xdg-data"))
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = root
        self.mod = load()

    def call(self, args, data):
        """照 main() 跑一次：stdin 喂 JSON，状态页换成 data 拼的页面，返回 (退出码, 输出)。"""
        out = io.StringIO()
        code = 0
        html = page(data).encode("utf-8")
        with mock.patch("urllib.request.urlopen", lambda *a, **k: FakeResponse(html)), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(args))), redirect_stdout(out):
            try:
                self.mod.main()
            except SystemExit as exc:
                code = exc.code or 0
        return code, out.getvalue()


class UptimeType(Sandbox):
    # 审计 #178：可用率只认 isinstance(rate, (int, float))，bool 是 int 的子类，
    # 页面里 uptime 写成 true 时 md 印「30 天可用率 True%」，json 交 "uptime_30d": true。
    DATA = {"initialPageConfig": {"components": [{"component_id": "a", "name": "API"},
                                                 {"component_id": "b", "name": "Chat"}]},
            "component_uptimes": [{"component_id": "a", "uptime": True},
                                  {"component_id": "b", "uptime": 99.5}]}

    def test_md_skips_bool_uptime(self):
        code, out = self.call({}, self.DATA)
        self.assertEqual(code, 0, out)
        self.assertNotIn("True%", out)
        self.assertIn("- API：正常\n", out)
        self.assertIn("- Chat：正常，30 天可用率 99.5%", out)

    def test_json_bool_uptime_is_null(self):
        code, out = self.call({"format": "json"}, self.DATA)
        self.assertEqual(code, 0, out)
        comps = {c["name"]: c["uptime_30d"] for c in json.loads(out)["components"]}
        self.assertEqual(comps, {"API": None, "Chat": 99.5})


if __name__ == "__main__":
    unittest.main()
