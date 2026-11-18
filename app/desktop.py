#!/usr/bin/env python3
"""ComponentLib 物料入库台 —— 桌面版入口。

架构与 lab-console 一致：pywebview（Windows WebView2）原生窗口承载网页界面，
界面与后端在本机回环地址（127.0.0.1，端口随机）通信，外部无法访问。
pywebview 不可用时自动回退浏览器打开。
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server as backend

APP_TITLE = "ComponentLib 维护平台"


def _window_size() -> tuple[int, int]:
    """按屏幕分辨率给一个合适的初始窗口尺寸（lab-console 同款启发式）。"""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        sw, sh = 1920, 1080
    w = max(1120, min(1580, int(sw * 0.86)))
    h = max(700, min(1000, int(sh * 0.88)))
    return w, h


def _start_server() -> tuple[threading.Thread, str]:
    srv = backend.build_server("127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True, name="http")
    t.start()
    import time
    # 启动 URL 加时间戳：强制 WebView2 拉取最新 index.html（其内再注入 css/js mtime 版本）
    return t, f"http://127.0.0.1:{port}/?t={int(time.time())}"


class Api:
    """暴露给前端的原生能力（文件选择对话框等）。"""

    def __init__(self):
        self._window = None
        self.wv = None
        self.last_dir = os.path.dirname(backend.SETTINGS_PATH)

    def pick_db_file(self) -> dict:
        try:
            if self._window is None or self.wv is None:
                return {"ok": False, "error": "当前环境不支持文件对话框"}
            target = self._window.create_file_dialog(
                self.wv.OPEN_DIALOG,
                directory=self.last_dir,
                file_types=("Access 数据库 (*.mdb;*.accdb)",),
            )
            if not target:
                return {"cancelled": True}
            path = target if isinstance(target, str) else target[0]
            self.last_dir = os.path.dirname(path)
            return {"ok": True, "path": path}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def pick_datasheet_file(self) -> dict:
        """选择本地规格书文件（任意 PDF），供确认写入后复制更名。"""
        try:
            if self._window is None or self.wv is None:
                return {"ok": False, "error": "当前环境不支持文件对话框"}
            target = self._window.create_file_dialog(
                self.wv.OPEN_DIALOG,
                directory=self.last_dir,
                file_types=("PDF 文件 (*.pdf)", "所有文件 (*.*)",),
            )
            if not target:
                return {"cancelled": True}
            path = target if isinstance(target, str) else target[0]
            return {"ok": True, "path": path}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_url(self, url: str) -> dict:
        """用系统默认浏览器打开外部链接（规格书网页/PDF 等）。"""
        try:
            url = str(url or "").strip()
            if not url.startswith(("http://", "https://")):
                return {"ok": False, "error": "仅支持 http/https 链接"}
            webbrowser.open(url)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def reveal(self, path: str) -> dict:
        try:
            import subprocess
            subprocess.Popen(["explorer", "/select,", path])
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    _thread, url = _start_server()
    api = Api()

    try:
        import webview
    except ImportError:
        print("未安装 pywebview，改用浏览器模式…")
        webbrowser.open(url)
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            return

    api.wv = webview
    win_w, win_h = _window_size()
    window = webview.create_window(
        APP_TITLE,
        url,
        js_api=api,
        width=win_w,
        height=win_h,
        min_size=(1120, 700),
        background_color="#edf1f6",
    )
    api._window = window
    print(f"桌面窗口已启动: {url}")
    # WebView2 用户数据（缓存/Local Storage 等）统一放软件目录下，
    # 不散落在用户 AppData（安装版=安装目录，绿色版=exe 所在目录）
    if getattr(sys, "frozen", False):
        _data_dir = os.path.join(os.path.dirname(sys.executable), "UserData")
    else:
        _data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "UserData")
    try:
        os.makedirs(_data_dir, exist_ok=True)
        webview.start(debug=False, private_mode=False, storage_path=_data_dir)
    except TypeError:
        # 旧版 pywebview 不支持 storage_path
        webview.start(debug=False, private_mode=False)
    except Exception as exc:
        # WebView2 运行时缺失等情况下退回浏览器，保证软件仍可用
        print(f"桌面窗口启动失败({exc})，改用浏览器打开…")
        webbrowser.open(url)
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    print("已退出")


if __name__ == "__main__":
    main()
