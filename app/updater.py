# -*- coding: utf-8 -*-
"""PartBridge 软件更新 —— 复用 LabConsole 的检查/升级机制。

LabConsole 联网踩坑的对策（全部继承）：
1. GitHub 匿名 API 每 IP 每小时 60 次极易 403 → 带 If-None-Match 条件请求，
   304 不计配额；ETag 与结果落盘缓存，重启不丢
2. 403/429 时降级 releases.atom 订阅源（不计配额，但无附件清单 → 引导发布页）
3. 304 命中的缓存可能是旧版本时代算的 → available 必须按当前版本重算
4. DNS/代理故障 → 复用 lcsc.urlopen_smart（公共 DNS 兜底 + IP 直连）

本项目的差异点（按用户要求）：
- 升级包下载到**软件安装目录**（不放 TEMP），安装器覆盖安装后由
  [InstallDelete] 与下次启动时的 clean_stale 自动清除残留
- 设置缓存 update_cache.json 与 settings.json 同目录（exe 旁，不放 Roaming）
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import lcsc

GITHUB_REPO = "li-wanxin/ComponentLib_PartBridge"
_LOCK = threading.Lock()
_CACHE_FNAME = "update_cache.json"
_INFO: dict = {"available": False}
_ETAG = ""


def _base_dir() -> Path:
    """缓存与升级包目录：冻结模式 = exe 所在目录（安装目录），开发 = app 目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _cache_path() -> Path:
    return _base_dir() / _CACHE_FNAME


def _load_cache(app_version: str) -> None:
    global _INFO, _ETAG
    try:
        data = json.loads(_cache_path().read_text("utf-8"))
        _INFO = dict(data.get("info") or {"available": False})
        _ETAG = str(data.get("etag") or "")
        _recompute_available(_INFO, app_version)
    except (OSError, ValueError):
        pass


def _save_cache() -> None:
    try:
        _cache_path().write_text(
            json.dumps({"etag": _ETAG, "info": _INFO}, ensure_ascii=False), "utf-8")
    except OSError:
        pass


def _version_tuple(tag: str):
    try:
        return tuple(int(x) for x in tag.split("."))
    except ValueError:
        return None


def _recompute_available(info: dict, app_version: str) -> None:
    """按当前版本重算 available（缓存可能是旧版本时代算出的）。"""
    tag = str(info.get("latest") or "")
    if not tag:
        return
    vt, vc = _version_tuple(tag), _version_tuple(app_version)
    info["available"] = (vt > vc) if (vt and vc) else (tag != app_version)


def _check_via_atom(app_version: str) -> dict | None:
    """降级通道：releases.atom 不走 API 配额；只含 tag 名，无附件清单。"""
    try:
        url = f"https://github.com/{GITHUB_REPO}/releases.atom"
        req = urllib.request.Request(url, headers={"User-Agent": f"PartBridge/{app_version}"})
        with lcsc.urlopen_smart(req, timeout=8) as resp:
            text = resp.read(1 << 20).decode("utf-8", "replace")
        m = re.search(r'href="[^"]*/releases/tag/([^"]+)"', text)
        if not m:
            return None
        tag = m.group(1).split("/")[-1].lstrip("vV")
        vt, vc = _version_tuple(tag), _version_tuple(app_version)
        newer = (vt > vc) if (vt and vc) else (tag != app_version)
        return {"latest": tag, "available": newer, "assets": [],
                "html_url": f"https://github.com/{GITHUB_REPO}/releases/latest",
                "checked_at": time.time(),
                "note": "经由订阅源检查（API 限流降级），安装包请到发布页下载"}
    except Exception:
        return None


def check_once(app_version: str, log=None) -> dict:
    """查询 GitHub 最新 Release；网络失败静默（保留上次缓存结果）。"""
    global _INFO, _ETAG
    with _LOCK:
        prev = dict(_INFO or {})
        etag = _ETAG
    info: dict = {"available": False, "checked_at": time.time()}
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        headers = {"User-Agent": f"PartBridge/{app_version}",
                   "Accept": "application/vnd.github+json"}
        if etag:
            headers["If-None-Match"] = etag
        req = urllib.request.Request(url, headers=headers)
        try:
            with lcsc.urlopen_smart(req, timeout=8) as resp:
                data = json.load(resp)
            new_etag = resp.headers.get("ETag", "")
        except urllib.error.HTTPError as he:
            if he.code == 304 and prev.get("latest"):
                prev["checked_at"] = time.time()
                prev.pop("error", None)
                _recompute_available(prev, app_version)
                with _LOCK:
                    _INFO = prev
                _save_cache()
                return dict(_INFO)
            if he.code in (403, 429):
                alt = _check_via_atom(app_version)
                if alt:
                    alt["error"] = "GitHub API 限流，已自动改用订阅源检查（安装包请到发布页下载）"
                    if log:
                        log("warn", "GitHub API 限流 (403)，已降级经 releases.atom 检查")
                    with _LOCK:
                        _INFO = alt
                    _save_cache()
                    return dict(_INFO)
                info = dict(prev) if prev.get("latest") else info
                _recompute_available(info, app_version)
                info["checked_at"] = time.time()
                info["error"] = ("GitHub API 限流（匿名接口每 IP 每小时 60 次），请几分钟后再试；"
                                 "也可直接到发布页下载：https://github.com/" + GITHUB_REPO + "/releases/latest")
                with _LOCK:
                    _INFO = info
                return dict(_INFO)
            raise
        tag = str(data.get("tag_name", "")).lstrip("vV")
        vt, vc = _version_tuple(tag), _version_tuple(app_version)
        newer = (vt > vc) if (vt and vc) else (tag != app_version)
        assets = [{"name": a["name"], "url": a["browser_download_url"], "size": a.get("size", 0)}
                  for a in data.get("assets", []) if str(a.get("name", "")).lower().endswith(".exe")]
        info.update({"latest": tag, "available": newer,
                     "html_url": data.get("html_url", ""), "assets": assets})
        if newer and log:
            log("info", f"发现新版本 v{tag}（当前 v{app_version}），可在设置页更新")
        with _LOCK:
            _INFO = info
            _ETAG = new_etag or etag
        _save_cache()
    except Exception as exc:  # noqa: BLE001  无网络/DNS 故障：静默，保留旧缓存
        info["error"] = str(exc)[:200]
        with _LOCK:
            _INFO = info
    with _LOCK:
        return dict(_INFO)


def snapshot() -> dict:
    with _LOCK:
        return dict(_INFO)


def _delayed_check(app_version: str, log=None) -> None:
    time.sleep(3.0)
    check_once(app_version, log)


def clean_stale() -> list:
    """启动时清理安装目录下的升级包残留（PartBridge-Setup-*.exe）。
    本体 PartBridge.exe 不匹配，不会误删正在运行的程序。"""
    removed = []
    try:
        for p in _base_dir().glob("PartBridge-Setup-*.exe"):
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    except OSError:
        pass
    return removed


def download_update(app_version: str, log=None) -> dict:
    """下载最新版升级包到**安装目录**并按运行形态处理：
    安装版 → 启动覆盖安装向导后自动退出；便携版 → 同目录改名就位替换。"""
    with _LOCK:
        info = dict(_INFO or {})
    if not info.get("available"):
        raise RuntimeError("当前已是最新版本，无需更新")
    assets = info.get("assets") or []
    base = _base_dir()
    frozen = getattr(sys, "frozen", False)
    exe = Path(sys.executable) if frozen else None
    if exe is None:
        import webbrowser
        url = info.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
        webbrowser.open(url)
        return {"mode": "dev", "url": url,
                "message": "开发模式无法自动替换，已打开发布页，请手动下载"}

    # 运行形态判定（LabConsole 同款）：{app} 下必有 unins000.* 或 exe 固定名 PartBridge.exe
    try:
        has_unins = any(exe.parent.glob("unins*"))
    except OSError:
        has_unins = False
    is_setup = has_unins or exe.name.lower() == "partbridge.exe"
    want = "PartBridge-Setup" if is_setup else "PartBridge-Portable"
    asset = next((a for a in assets if a["name"].startswith(want)), None)
    if asset is None:
        import webbrowser
        url = info.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
        webbrowser.open(url)
        return {"mode": "manual", "url": url,
                "message": f"新版本 v{info.get('latest')} 的安装包请在新打开的发布页下载（{want}）"}

    # 升级包放安装目录（用户要求；目录已授 Users 写权限）
    dest = base / asset["name"]
    if log:
        log("info", f"开始下载更新到安装目录: {asset['name']} ({max(asset['size'] // 1024 // 1024, 1)} MB)")
    try:
        req = urllib.request.Request(asset["url"], headers={"User-Agent": f"PartBridge/{app_version}"})
        with lcsc.urlopen_smart(req, timeout=180) as resp, open(dest, "wb") as f:
            got = 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                got += len(chunk)
                f.write(chunk)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"下载失败: {exc}") from exc
    if log:
        log("ok", f"升级包已下载 → {dest}")

    if is_setup:
        os.startfile(str(dest))            # 安装向导接管，覆盖安装
        if log:
            log("ok", "更新安装向导已启动")
        # 安装器要覆盖本程序文件：尽快退出释放 PartBridge.exe（竞态对策，LabConsole 同款）
        threading.Timer(0.8, os._exit, args=(0,)).start()
        return {"mode": "setup", "path": str(dest),
                "message": "安装向导已启动（升级包在安装目录内，安装完成后会自动清除），"
                           "本程序即将自动关闭，按提示完成覆盖安装后重新打开即可"}

    # 便携版：运行中的 exe 允许改名不允许覆盖 → 三步就位替换（LabConsole 同款）
    new = exe.with_name(exe.stem + "_更新下载.exe")
    old = exe.with_name(exe.stem + "_旧版本.exe")
    try:
        dest.replace(new)
        try:
            old.unlink()
        except OSError:
            pass
        exe.rename(old)
        new.rename(exe)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"自动替换失败（{exc}）。新版本已下载到 {new}，"
                           f"请关闭本程序后手动将其重命名为「{exe.name}」")
    if log:
        log("ok", "便携版更新已就位，重新打开即为新版本")
    return {"mode": "portable", "path": str(exe),
            "message": "更新已就位！请完全关闭本程序，然后重新打开即为新版本"}
