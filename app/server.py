# -*- coding: utf-8 -*-
"""ComponentLib 物料入库台 —— 本地 HTTP 服务（JSON API）。

复用既有后端模块：db.py / lcsc.py / conventions.py（与 Qt 版完全一致）。
所有状态访问走全局锁；前端通过 fetch 调用 /api/* 端点。
"""
import json
import os
import shutil
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from db import MdbDatabase, MdbError
import conventions as conv
import lcsc

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
WEB_DIR = os.path.join(APP_DIR, "web")

REQUIRED = conv.REQUIRED_KEYS


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            return json.load(open(SETTINGS_PATH, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_settings(s):
    try:
        json.dump(s, open(SETTINGS_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass


class AppState:
    def __init__(self):
        self.lock = threading.RLock()
        self.db = None
        self.lib_root = ""
        self.settings = load_settings()
        self.logs = []

    def log(self, kind, msg):
        self.logs.append({"t": datetime_now(), "kind": kind, "msg": msg})
        self.logs = self.logs[-200:]

    def connect(self, path):
        with self.lock:
            if self.db:
                try:
                    self.db.close()
                except Exception:
                    pass
            self.db = MdbDatabase(path)
            self.lib_root = os.path.dirname(path)
            self.settings["db_path"] = path
            save_settings(self.settings)
            self.log("ok", f"数据库已载入: {path}")

    def ensure_db(self):
        with self.lock:
            if self.db:
                return True
            candidates = [
                self.settings.get("db_path"),
                r"X:\ComponentLib\DataBase\ComponentLib.mdb",
                os.path.normpath(os.path.join(APP_DIR, "..", "test-lib", "ComponentLib.mdb")),
            ]
            for c in candidates:
                if c and os.path.exists(c):
                    self.connect(os.path.normpath(os.path.abspath(c)))
                    return True
            return False


def datetime_now():
    import datetime
    return datetime.datetime.now().strftime("%H:%M:%S")


STATE = AppState()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 静默默认访问日志
        pass

    # ---------- 基础 ----------
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _ok(self, **kw):
        self._json({"ok": True, **kw})

    def _err(self, msg, code=400, **kw):
        self._json({"ok": False, "error": str(msg), **kw}, code)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    # ---------- 静态文件 ----------
    def _serve_static(self, path):
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not full.startswith(WEB_DIR) or not os.path.exists(full):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        ctype = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
                 ".png": "image/png", ".ico": "image/x-icon"}.get(
            os.path.splitext(full)[1], "application/octet-stream")
        data = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # 静态资源禁缓存：开发迭代期防止 WebView2 用旧 JS/CSS
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path
        if not p.startswith("/api/"):
            return self._serve_static(p)
        try:
            return self._api_get(p, q)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._err(f"{type(e).__name__}: {e}", 500)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = self._body()
        except Exception as e:
            return self._err(f"请求体解析失败: {e}")
        try:
            return self._api_post(u.path, body)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._err(f"{type(e).__name__}: {e}", 500)

    # ---------- GET API ----------
    def _api_get(self, p, q):
        st = STATE
        if p == "/api/bootstrap":
            loaded = st.ensure_db()
            with st.lock:
                tables, total = [], 0
                if loaded:
                    for t in st.db.get_tables():
                        try:
                            n = st.db.count(t)
                        except Exception:
                            n = -1
                        tables.append({"name": t, "count": n})
                        if n > 0:
                            total += n
            return self._ok(loaded=loaded, tables=tables, total=total,
                            db_path=st.db.path if st.db else "",
                            lib_root=st.lib_root,
                            settings=st.settings)
        if p == "/api/table":
            if not st.ensure_db():
                return self._err("未连接数据库")
            name = q.get("name", "")
            with st.lock:
                cols, rows = st.db.read_table(name, q.get("q") or "")
            return self._ok(columns=cols, rows=rows)
        if p == "/api/columns":
            if not st.ensure_db():
                return self._err("未连接数据库")
            with st.lock:
                cols = st.db.get_columns(q.get("table", ""))
            return self._ok(columns=cols)
        if p == "/api/distinct":
            if not st.ensure_db():
                return self._err("未连接数据库")
            with st.lock:
                vals = st.db.distinct_values(q.get("table", ""), q.get("column", "Type"))
            return self._ok(values=vals)
        if p == "/api/logs":
            return self._ok(logs=st.logs[-100:])
        if p == "/api/model3d_exists":
            if not st.ensure_db():
                return self._err("未连接数据库")
            with st.lock:
                data = {"PCB3D Path": q.get("path", ""), "PCB3D Ref": q.get("ref", "")}
                dest = self._model3d_target(data, st)
            return self._ok(exists=bool(dest) and os.path.exists(dest))
        return self._err("未知端点 " + p, 404)

    # ---------- 规格书落盘 ----------
    def _handle_datasheet(self, data, local_file, ds_url, st):
        """按 ComponentLink2URL 落盘规格书。
        已存在→保留原文件；本地选定文件→复制改名；立创有直链→下载。
        任何失败只返回说明文字，不影响入库结果。"""
        target = (data.get("ComponentLink2URL") or "").strip()
        if not target or "无可下载规格书" in target or not target.lower().endswith(".pdf"):
            if local_file:
                return "已选择本地文件，但 C2URL 不是有效目标路径（需以 .pdf 结尾）"
            return ""
        dest = target.replace("/", os.sep)
        if not os.path.isabs(dest):
            dest = os.path.join(st.lib_root or os.getcwd(), dest)
        dest_n = os.path.normpath(dest)
        root_n = os.path.normpath(st.lib_root) if st.lib_root else ""
        inside = bool(root_n) and dest_n.lower().startswith(root_n.lower() + os.sep)
        try:
            if not os.path.isdir(os.path.dirname(dest_n)):
                if not inside:
                    return f"目标路径不在库目录下且父目录不存在，未处理：{target}"
                os.makedirs(os.path.dirname(dest_n), exist_ok=True)
            if os.path.exists(dest_n):
                return "规格书已存在，保留原文件"
            if local_file and os.path.exists(local_file):
                shutil.copy2(local_file, dest_n)
                return "已从选定文件复制规格书"
            if ds_url:
                req = urllib.request.Request(ds_url, headers={"User-Agent": lcsc.UA})
                tmp = dest_n + ".part"
                got = 0
                with urllib.request.urlopen(req, timeout=60, context=lcsc.CTX) as r, \
                        open(tmp, "wb") as f:
                    while True:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        got += len(chunk)
                        if got > 200 * 1024 * 1024:
                            raise RuntimeError("文件超过 200MB，已中止下载")
                        f.write(chunk)
                os.replace(tmp, dest_n)
                return f"规格书已下载（{got // 1024} KB）"
            return "无可下载规格书"
        except Exception as e:
            if os.path.exists(dest_n + ".part"):
                try:
                    os.remove(dest_n + ".part")
                except Exception:
                    pass
            return f"规格书处理失败: {e}"

    # ---------- 3D 模型落盘 ----------
    def _model3d_target(self, data, st):
        """由 PCB3D Path（缺省时按 PCB3D Ref 生成 StepModel/<封装>.STEP，仓库约定）
        计算模型目标绝对路径；路径无效返回空串。"""
        path = (data.get("PCB3D Path") or "").strip()
        if not path:
            pkg = (data.get("PCB3D Ref") or "").strip()
            for ch in '\\/:*?"<>|':
                pkg = pkg.replace(ch, "")
            if not pkg:
                return ""
            path = f"StepModel/{pkg}.STEP"
        if not path.lower().endswith(".step"):
            return ""
        dest = path.replace("/", os.sep)
        if not os.path.isabs(dest):
            dest = os.path.join(st.lib_root or os.getcwd(), dest)
        return os.path.normpath(dest)

    def _download_step(self, uuid):
        """从 modules 直链下载 STEP 文件（国内镜像优先），返回 bytes。
        校验响应含 ISO-10303-21 文件头（LCSC3D 同款校验），失败抛异常。"""
        last = None
        for tpl in lcsc.MODEL_STEP_TPLS:
            try:
                req = urllib.request.Request(tpl.format(uuid=uuid),
                                             headers={"User-Agent": lcsc.UA})
                with urllib.request.urlopen(req, timeout=90, context=lcsc.CTX) as r:
                    raw = r.read(200 * 1024 * 1024 + 1)
                if len(raw) > 200 * 1024 * 1024:
                    raise RuntimeError("文件超过 200MB，已中止下载")
                if b"ISO-10303-21" not in raw[:2048]:
                    raise RuntimeError("接口未返回有效的 STEP 文件")
                return raw
            except Exception as e:
                last = e
                continue
        raise last if last else RuntimeError("无可用下载通道")

    def _handle_model3d(self, data, model3d, st):
        """按 PCB3D Path（或 PCB3D Ref 生成）落盘 3D 模型。
        已存在→保留原文件不下载；uuid 失效→走官方 3D 库备用链解析。
        任何失败只返回说明文字，不影响入库结果。"""
        dest_n = self._model3d_target(data, st)
        if not dest_n:
            return ""
        target = (data.get("PCB3D Path") or f"StepModel/{data.get('PCB3D Ref')}.STEP").strip()
        root_n = os.path.normpath(st.lib_root) if st.lib_root else ""
        inside = bool(root_n) and dest_n.lower().startswith(root_n.lower() + os.sep)
        try:
            if not os.path.isdir(os.path.dirname(dest_n)):
                if not inside:
                    return f"3D 模型目标路径不在库目录下且父目录不存在，未处理：{target}"
                os.makedirs(os.path.dirname(dest_n), exist_ok=True)
            if os.path.exists(dest_n):
                return "3D 模型已存在，保留原文件"
            m = model3d or {}
            uuid = str(m.get("uuid") or "").strip()
            if not uuid and m.get("uuid_3d"):
                uuid = lcsc.resolve_library_model_uuid(m["uuid_3d"])
            if not uuid:
                return "官方库未关联 3D 模型文件编号"
            raw = self._download_step(uuid)
            tmp = dest_n + ".part"
            with open(tmp, "wb") as f:
                f.write(raw)
            os.replace(tmp, dest_n)
            return f"3D 模型已下载（{len(raw) // 1024} KB）"
        except Exception as e:
            if os.path.exists(dest_n + ".part"):
                try:
                    os.remove(dest_n + ".part")
                except Exception:
                    pass
            return f"3D 模型处理失败: {e}"

    # ---------- POST API ----------
    def _api_post(self, p, body):
        st = STATE
        if p == "/api/sn":
            sn = (body.get("sn") or "").strip().upper()
            res = lcsc.fetch(sn)
            ds_url = ""
            if res.ok:
                try:
                    ds_url = lcsc.fetch_datasheet_url(sn)
                except Exception:
                    ds_url = ""
            with st.lock:
                sug_table = res.suggest_table
                sug_fields = {}
                sug_pn = ""
                if res.ok and st.db:
                    table = sug_table or ""
                    sug = conv.suggest_library_fields(table, res.pkg_family, st.lib_root)
                    sug_fields = sug
                    sug_pn = conv.suggest_part_number(table,
                                                      res.data.get("Component Type", ""),
                                                      res.pkg_family)
            return self._ok(fetched=res.ok, data=res.data, package=res.package,
                            pkg_family=res.pkg_family, suggest_table=sug_table,
                            suggest_fields=sug_fields, suggest_part_number=sug_pn,
                            datasheet_url=ds_url, model3d=res.model3d,
                            source=res.source, logs=res.logs)
        if p == "/api/dup":
            if not st.ensure_db():
                return self._err("未连接数据库")
            with st.lock:
                dup = st.db.check_duplicate(body.get("table", ""), body.get("data", {}))
            return self._ok(dup=dup)
        if p == "/api/insert":
            if not st.ensure_db():
                return self._err("未连接数据库")
            table = body.get("table", "")
            data = body.get("data", {})
            local_file = (body.get("local_file") or "").strip()
            ds_url = (body.get("datasheet_url") or "").strip()
            model3d = body.get("model3d") or None
            with st.lock:
                if st.settings.get("backup_write", True):
                    try:
                        st.db.backup_daily()
                    except Exception as e:
                        st.log("warn", f"自动备份失败: {e}")
                try:
                    st.db.insert(table, data)
                except MdbError as e:
                    return self._err(str(e))
                st.log("ok", f"写入 [{table}] {data.get('Component Type', '')}")
            # 规格书落盘（写入成功后才处理；失败不影响入库结果）
            warn = self._handle_datasheet(data, local_file, ds_url, st)
            if warn:
                st.log("warn", f"[{table}] 规格书: {warn}")
            # 3D 模型落盘（已存在则保留，不存在时按 Path/名称下载；失败不影响入库结果）
            warn3d = self._handle_model3d(data, model3d, st)
            if warn3d:
                st.log("warn", f"[{table}] 3D 模型: {warn3d}")
            warn = " ｜ ".join(w for w in (warn, warn3d) if w)
            return self._ok(warn=warn)
        if p == "/api/update":
            if not st.ensure_db():
                return self._err("未连接数据库")
            table = body.get("table", "")
            old = body.get("old", {})
            data = body.get("data", {})
            if not old or not data:
                return self._err("缺少定位行（old）或新值（data）")
            with st.lock:
                if st.settings.get("backup_write", True):
                    try:
                        st.db.backup_daily()
                    except Exception as e:
                        st.log("warn", f"自动备份失败: {e}")
                try:
                    st.db.update(table, old, data)
                except MdbError as e:
                    return self._err(str(e))
                st.log("ok", f"更新 [{table}] {data.get('Component Type', '')}")
            return self._ok()
        if p == "/api/create_table":
            if not st.ensure_db():
                return self._err("未连接数据库")
            name = (body.get("name") or "").strip()
            if not name:
                return self._err("分类名不能为空")
            if len(name) > 64 or any(ch in name for ch in "[]`\"'"):
                return self._err("分类名不合法（≤64字符，且不能含 [] 引号等）")
            STD_COLS = ["Part Number", "Component Type", "Vendor", "Value", "Tolerance",
                        "Type", "Description", "Suppiler", "Suppiler Number",
                        "Library Ref", "Library Path", "Footprint Ref", "Footprint Path",
                        "PCB3D Ref", "PCB3D Path", "ComponentLink2Description",
                        "ComponentLink2URL", "LatestRevisionDate"]
            with st.lock:
                if name in st.db.get_tables():
                    return self._err(f"分类表 [{name}] 已存在")
                sql = (f"CREATE TABLE [{name}] ("
                       + ", ".join(f"[{c}] TEXT(255)" for c in STD_COLS) + ")")
                cur = st.db.conn.cursor()
                try:
                    cur.execute(sql)
                finally:
                    cur.close()
            st.log("ok", f"新建分类表 [{name}]（18 个标准字段）")
            return self._ok(name=name)
        if p == "/api/model3d":
            if not st.ensure_db():
                return self._err("未连接数据库")
            data = {"PCB3D Path": body.get("path") or "", "PCB3D Ref": body.get("package") or ""}
            warn = self._handle_model3d(data, body.get("model3d") or body, st)
            return self._ok(warn=warn)
        if p == "/api/settings":
            s = st.settings
            if "dark" in body:
                s["dark"] = bool(body["dark"])
            if "auto_load" in body:
                s["auto_load"] = bool(body["auto_load"])
            if "backup_write" in body:
                s["backup_write"] = bool(body["backup_write"])
            save_settings(s)
            if body.get("db_path"):
                try:
                    st.connect(body["db_path"])
                except Exception as e:
                    return self._err(f"数据库连接失败: {e}")
            return self._ok(settings=s)
        return self._err("未知端点 " + p, 404)


def build_server(host="127.0.0.1", port=0):
    srv = ThreadingHTTPServer((host, port), Handler)
    return srv
