# -*- coding: utf-8 -*-
"""符号/封装库生成器：摘取 LCSC3D (AGPL-3.0, github.com/Travelerrrrrr/LCSC3D)
的 EasyEDA→Altium 生成器（lcsc3d/ 为 vendored 副本）。

链路：立创官方库组件 JSON（与 SN 查询同源接口）
  → export_schlib/export_pcblib 生成原生 .SchLib/.PcbLib 字节
  → append_library 追加进现有库文件（不改动已有元件；库文件不存在则新建）。
"""
import json
import os
import re

import lcsc
from lcsc3d.eda.altium import export_schlib, export_pcblib
from lcsc3d.eda.library_merge import append_library


def fetch_cad_data(sn):
    """拉取官方库组件数据，并按 LCSC3D 约定把 dataStr/packageDetail 转成 dict。"""
    sn = (sn or "").strip().upper()
    if not re.fullmatch(r"C\d{3,10}", sn):
        raise ValueError("SN 格式不符（应为 C+数字）")
    last = None
    for dom in lcsc.DOMAINS:
        try:
            obj = lcsc._http_json(f"{dom}/api/products/{sn}/components")
        except Exception as e:
            last = e
            continue
        if not obj.get("success") or not obj.get("result"):
            last = RuntimeError("官方器件库中无此编号")
            continue
        r = obj["result"]
        for key in ("dataStr", "packageDetail"):
            if isinstance(r.get(key), str):
                try:
                    r[key] = json.loads(r[key])
                except ValueError:
                    r[key] = {}
        pkg = r.get("packageDetail")
        if isinstance(pkg, dict) and isinstance(pkg.get("dataStr"), str):
            try:
                pkg["dataStr"] = json.loads(pkg["dataStr"])
            except ValueError:
                pass
        return r
    raise last or RuntimeError("官方库请求失败")


def availability(data):
    """官方库是否带符号/封装可导出数据（供胶囊点击查询）。"""
    pkg = data.get("packageDetail") or {}
    return {"symbol": bool(data.get("dataStr")), "footprint": bool(pkg.get("dataStr"))}


def download_and_append(kind, sn, lib_root, rel_path):
    """生成符号/封装并追加进库文件。
    kind: 'sch'（Altium SCH 符号 → .SchLib）| 'pcb'（Altium PCB 封装 → .PcbLib）
    rel_path: 库相对路径（如 AltiumSchLib/Resistors.SchLib）；文件不存在则新建。
    返回 dict(status, message, name)：name 为生成的元件/封装名（用于回填 Ref）。"""
    data = fetch_cad_data(sn)
    if kind == "sch":
        payload = export_schlib(data, sn)
        fmt = "SCHLIB"
        name = str(data.get("title") or "").strip()
    elif kind == "pcb":
        payload = export_pcblib(data, sn, model_assets=None, model_layer=1)
        fmt = "PCBLIB"
        name = str((data.get("packageDetail") or {}).get("title")
                   or data.get("title") or "").strip()
    else:
        return {"status": "err", "message": "未知类型 " + kind, "name": ""}
    if not payload:
        return {"status": "missing",
                "message": "官方库数据无法生成 " + fmt + "（符号/封装数据缺失）", "name": name}

    rel = (rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel.lower().endswith((".schlib", ".pcblib")):
        return {"status": "err", "message": "目标路径不是 .SchLib/.PcbLib：" + rel, "name": name}
    dest = rel.replace("/", os.sep) if os.path.isabs(rel) else \
        os.path.join(lib_root or os.getcwd(), rel.replace("/", os.sep))
    dest = os.path.normpath(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    original = open(dest, "rb").read() if os.path.exists(dest) else b""
    merged, skipped = append_library(original, payload, fmt)
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(merged)
    os.replace(tmp, dest)

    if skipped:
        msg = f"已存在于 {rel}，未重复添加（{len(skipped)} 项）"
    else:
        msg = f"已生成并追加到 {rel}"
    return {"status": "ok", "message": msg, "name": name, "skipped": skipped}
