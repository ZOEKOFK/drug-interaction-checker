#!/usr/bin/env python
"""
离线演示截图兜底（断网/环境故障时用）。

通过 Edge / Chrome 的 DevTools Protocol 驱动真实页面，把六个页面 + API 文档
截图到 deploy/screenshots/。仅依赖标准库 + websocket-client，无需 Playwright。

用法（先启动服务 python -m uvicorn app.main:app --port 8000）：
    python deploy/capture_screenshots.py [--base http://127.0.0.1:8000]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket  # websocket-client

OUT_DIR = Path(__file__).resolve().parent / "screenshots"
PORT = 9333
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser() -> str:
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 Edge/Chrome，可手动截图后放入 deploy/screenshots/")


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.seq = 0

    def call(self, method: str, **params):
        self.seq += 1
        self.ws.send(json.dumps({"id": self.seq, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.seq:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expression: str):
        r = self.call(
            "Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True
        )
        return r.get("result", {}).get("value")

    def wait_js(self, expression: str, timeout: float = 12.0, label: str = ""):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self.js(expression):
                    return True
            except Exception:  # noqa: BLE001 - 页面切换期间上下文可能短暂失效
                pass
            time.sleep(0.25)
        print(f"  [warn] 等待超时: {label or expression[:60]}")
        return False

    def click_text(self, text: str) -> bool:
        ok = self.js(
            "(() => { const b=[...document.querySelectorAll('button,a')]"
            f".find(x=>(x.textContent||'').includes({json.dumps(text, ensure_ascii=False)}));"
            "if(!b) return false; b.click(); return true })()"
        )
        return bool(ok)

    def goto(self, url: str):
        self.call("Page.navigate", url=url)
        self.wait_js("document.readyState === 'complete'", 20, f"load {url}")

    def shot(self, name: str, max_height: int = 3200):
        """按内容高度截取整页（宽度固定 1440）。"""
        h = self.js("Math.min(Math.ceil(document.documentElement.scrollHeight), %d)" % max_height) or 1000
        h = max(int(h), 900)
        self.call(
            "Emulation.setDeviceMetricsOverride",
            width=1440, height=h, deviceScaleFactor=2, mobile=False,
        )
        time.sleep(0.45)
        data = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
        path = OUT_DIR / name
        path.write_bytes(base64.b64decode(data["data"]))
        print(f"  ✓ {name}  (1440×{h})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="saferx-shot-")
    proc = subprocess.Popen(
        [
            find_browser(),
            "--headless=new",
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={profile}",
            "--hide-scrollbars",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # 等待调试端口就绪
        targets = None
        for _ in range(40):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2))
                if any(t.get("type") == "page" for t in targets):
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.3)
        if not targets:
            raise SystemExit("浏览器调试端口未就绪")

        page = next(t for t in targets if t["type"] == "page")
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", width=1440, height=1000, deviceScaleFactor=2, mobile=False)

        # 1) 首页
        cdp.goto(base + "/")
        cdp.wait_js("document.body.innerText.includes('看清所有')", 15, "首页渲染")
        time.sleep(2.2)  # 等数字滚动动画结束
        cdp.shot("01-home.png")

        # 2) 药单页（载入主演示模板）
        if cdp.click_text("载入药单并预检"):
            cdp.wait_js("location.pathname === '/medications'", 10, "跳转药单页")
            cdp.wait_js("document.body.innerText.includes('我的药单')", 10, "药单渲染")
            time.sleep(1.5)
            cdp.shot("02-medications.png")

        # 3) 检查结果页
        if cdp.click_text("开始完整检查"):
            cdp.wait_js("location.pathname === '/results'", 12, "跳转结果页")
            time.sleep(1.6)
            cdp.shot("03-results.png")

        # 4) 图谱页（保持同一 SPA 会话，药单状态不丢）
        if cdp.click_text("交互图谱") or cdp.js("(()=>{const a=document.querySelector('a[href=\"/graph\"]');if(a){a.click();return true}return false})()"):
            cdp.wait_js("location.pathname === '/graph'", 12, "跳转图谱页")
            time.sleep(2.0)  # 力导向图布局稳定
            cdp.shot("04-graph.png")

        # 5) AI 实验室（跑一次抽取）
        cdp.js("(()=>{const a=document.querySelector('a[href=\"/lab\"]');if(a){a.click();return true}return false})()")
        cdp.wait_js("location.pathname === '/lab'", 12, "跳转实验室")
        time.sleep(0.8)
        cdp.click_text("开始抽取")
        cdp.wait_js("document.body.innerText.includes('实体识别结果')", 15, "抽取完成")
        time.sleep(0.8)
        cdp.shot("05-lab.png")

        # 6) 关于页
        cdp.js("(()=>{const a=document.querySelector('a[href=\"/about\"]');if(a){a.click();return true}return false})()")
        cdp.wait_js("location.pathname === '/about'", 12, "跳转关于页")
        cdp.wait_js("document.body.innerText.includes('数据覆盖与已知局限')", 12, "覆盖度区块渲染")
        time.sleep(0.8)
        cdp.shot("06-about.png")

        # 7) API 自动文档
        cdp.goto(base + "/docs")
        cdp.wait_js("document.body.innerText.includes('SafeRx')", 15, "API 文档渲染")
        time.sleep(0.8)
        cdp.shot("07-api-docs.png", max_height=1600)

        print(f"\n截图输出: {OUT_DIR}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
