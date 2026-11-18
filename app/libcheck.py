# -*- coding: utf-8 -*-
"""库文件核对：检查记录中的封装引用是否真实存在于库文件中。

覆盖 4 类：
  1. Altium 原理图：Library Ref 是否存在于 Library Path 的 .SchLib（顶层 storage）
  2. Altium PCB：Footprint Ref 是否存在于 Footprint Path 的 .PcbLib（顶层 storage）
  3. Cadence 原理图：Library Ref 是否存在于 CadenceSchLib/*.OLB 的 Packages/<名> 流
     （扫描目录下全部 OLB，命中即报出所在文件；DB 中的 OLB 常为表名或表名前段）
  4. Cadence PCB：CadencePcbLib/<Footprint Ref>.dra 与 .psm 是否存在

SchLib/PcbLib/OLB 均为 OLE 复合文档，用 olefile 列目录即可，无需外部工具。
结果按文件 (path, mtime, size) 缓存，同一文件重复核对零开销。
"""
import os
import re

try:
    import olefile
except ImportError:
    olefile = None

# 结果状态：ok 存在 / missing 引用不存在 / nofile 库文件缺失 / nodata 字段未填
_CACHE = {}   # path -> (mtime, size, names set 或 packages set)


def _norm_relpath(p):
    """规范化 DB 中的相对路径：去前导 /\\、统一分隔符。"""
    p = (p or "").strip().replace("\\", "/").lstrip("/")
    return p


def _cached_names(path, packages_only=False):
    """OLE 文件的顶层 storage 名集合（Altium）或 Packages/ 流名集合（OLB）。
    带文件指纹缓存；文件打不开返回 None。"""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = path
    hit = _CACHE.get(key)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    if olefile is None:
        return None
    try:
        ole = olefile.OleFileIO(path)
    except Exception:
        return None
    try:
        if packages_only:
            names = {"/".join(e[1:]) for e in ole.listdir(["Packages"])
                     if ole.get_type("/".join(e)) == 2}   # 流（排除 xxx Directory）
        else:
            # listdir 返回每个流的完整路径，其首段即顶层 storage 名（Altium 元件）
            names = {e[0] for e in ole.listdir() if len(e) >= 2}
            names.discard("Storage")         # Altium 内部条目
    finally:
        ole.close()
    _CACHE[key] = (st.st_mtime, st.st_size, names)
    return names


_SCH_PART_SUFFIX = re.compile(r"-R_\d+$")    # SchLib 多分部元件后缀，如 RES-R_2


def check_altium(lib_root, path_field, ref):
    """Altium .SchLib/.PcbLib 核对。返回 dict(status, detail)。"""
    rel = _norm_relpath(path_field)
    ref = (ref or "").strip()
    if not rel or not ref:
        return {"status": "nodata"}
    full = os.path.join(lib_root, rel.replace("/", os.sep))
    names = _cached_names(full)
    if names is None:
        return {"status": "nofile", "detail": rel}
    hit = ref.lower() in {n.lower() for n in names} or \
        _SCH_PART_SUFFIX.sub("", ref).lower() in {_SCH_PART_SUFFIX.sub("", n).lower() for n in names}
    return {"status": "ok" if hit else "missing", "detail": rel}


def check_cadence_schlib(lib_root, ref):
    """Cadence OLB 核对：扫描 CadenceSchLib/*.olb（含一层子目录）的 Packages/<ref>。"""
    ref = (ref or "").strip()
    if not ref:
        return {"status": "nodata"}
    d = os.path.join(lib_root, "CadenceSchLib")
    if not os.path.isdir(d):
        return {"status": "nofile", "detail": "CadenceSchLib/"}
    rl = ref.lower()
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            if not f.lower().endswith(".olb"):
                continue
            full = os.path.join(root, f)
            pkgs = _cached_names(full, packages_only=True)
            if pkgs and rl in {p.lower() for p in pkgs}:
                rel = os.path.relpath(full, lib_root).replace(os.sep, "/")
                return {"status": "ok", "detail": rel}
    return {"status": "missing"}


def check_cadence_pcblib(lib_root, ref):
    """Cadence PCB 核对：CadencePcbLib/<ref>.dra 与 .psm 是否存在。"""
    ref = (ref or "").strip()
    if not ref:
        return {"status": "nodata"}
    d = os.path.join(lib_root, "CadencePcbLib")
    if not os.path.isdir(d):
        return {"status": "nofile", "detail": "CadencePcbLib/"}
    safe = re.sub(r'[\\/:*?"<>|]', "", ref)
    have, miss = [], []
    for ext in (".dra", ".psm"):
        p = os.path.join(d, safe + ext)
        (have if os.path.exists(p) else miss).append(ext)
    if not miss:
        return {"status": "ok"}
    if have:
        return {"status": "missing", "detail": "缺 " + " ".join(miss)}
    return {"status": "missing"}


def check_fields(lib_root, d):
    """添加物料页用：按四个字段一次性核对，返回简版 dict（供 Path 行标注）。
    键名兼容两种风格：DB 字段名（Library Ref）与前端小写（library_ref）。"""
    def g(a, b):
        v = d.get(a)
        if v is None:
            v = d.get(b)
        return v or ""

    return {
        "altium_sch": check_altium(lib_root, g("Library Path", "library_path"),
                                   g("Library Ref", "library_ref")),
        "cadence_sch": check_cadence_schlib(lib_root, g("Library Ref", "library_ref")),
        "altium_pcb": check_altium(lib_root, g("Footprint Path", "footprint_path"),
                                   g("Footprint Ref", "footprint_ref")),
        "cadence_pcb": check_cadence_pcblib(lib_root, g("Footprint Ref", "footprint_ref")),
    }


def check_record(lib_root, table, data):
    """按记录字段核对 4 类封装存在性，返回统一 items 列表（供前端渲染）。"""
    items = []

    def add(kind, label, r):
        items.append({"kind": kind, "label": label, **r})

    # 1. Altium 原理图
    r = check_altium(lib_root, data.get("Library Path"), data.get("Library Ref"))
    if r["status"] != "nodata":
        add("altium_sch", "Altium 原理图符号", r)
    # 2. Altium PCB
    r = check_altium(lib_root, data.get("Footprint Path"), data.get("Footprint Ref"))
    if r["status"] != "nodata":
        add("altium_pcb", "Altium PCB 封装", r)
    # 3. Cadence 原理图
    if data.get("Library Ref"):
        r = check_cadence_schlib(lib_root, data.get("Library Ref"))
        add("cadence_sch", "Cadence 原理图符号", r)
    # 4. Cadence PCB
    if data.get("Footprint Ref"):
        r = check_cadence_pcblib(lib_root, data.get("Footprint Ref"))
        add("cadence_pcb", "Cadence PCB 封装", r)
    return items
