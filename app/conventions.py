# -*- coding: utf-8 -*-
"""库目录约定：路径建议、内部编码建议、字段分组。
依据真实仓库数据约定（正斜杠路径、IC 的 Library Ref=器件型号等）。"""

# 立创带出字段 → DB 字段
LCSC_AUTOFILL_KEYS = [
    "Component Type",  # 器件型号(MPN)
    "Vendor",          # 生产商
    "Value",           # 值
    "Tolerance",       # 精度
    "Type",            # 具体类别
    "Description",     # 描述
    "Suppiler",        # 供应商
    "ComponentLink2Description",
    "ComponentLink2URL",
]

REQUIRED_KEYS = ["Component Type"]  # 仅器件型号必填（其余均可留空）
MODEL_KEYS = [
    "Library Ref", "Library Path", "Footprint Ref", "Footprint Path",
    "PCB3D Ref", "PCB3D Path", "Schematic_Part", "PCB_Footprint",
]

# 表 → 默认库路径建议（与仓库 AltiumSchLib / AltiumPcbLib 实际文件对应）
LIB_MAP = {
    "Resistors":                       {"sch": "AltiumSchLib/Resistors.SchLib", "pcb": "AltiumPcbLib/Resistors.PcbLib", "ref": "RES"},
    "Resistors-Current Sensor Resistor":{"sch": "AltiumSchLib/Resistors.SchLib", "pcb": "AltiumPcbLib/Resistors.PcbLib", "ref": "RES"},
    "Capacitors":                      {"sch": "AltiumSchLib/Capacitors.SchLib", "pcb": "AltiumPcbLib/Capacitors.PcbLib", "ref": "CAP"},
    "Capacitors-Electrolytic Capacitors": {"sch": "AltiumSchLib/Capacitors.SchLib", "pcb": "AltiumPcbLib/Capacitors.PcbLib", "ref": "CAP-ELEC"},
    "Capacitors-Super Capacitors":     {"sch": "AltiumSchLib/Capacitors.SchLib", "pcb": "AltiumPcbLib/Capacitors.PcbLib", "ref": "CAP-SUPER"},
    "Inductors":                       {"sch": "AltiumSchLib/Inductors.SchLib", "pcb": "AltiumPcbLib/Capacitors.PcbLib", "ref": "IND"},
    "Beads":                           {"sch": "AltiumSchLib/Inductors.SchLib", "pcb": "AltiumPcbLib/Beads.PcbLib", "ref": "BEAD"},
    "Diodes":                          {"sch": "AltiumSchLib/Diodes.SchLib", "pcb": "AltiumPcbLib/Diodes-SOD.PcbLib", "ref": "DIODE"},
    "Transistors-BJT":                 {"sch": "AltiumSchLib/Transistors-BJT.SchLib", "pcb": "AltiumPcbLib/IC-SOT.PcbLib"},
    "Transistors-MOSFETs":             {"sch": "AltiumSchLib/Transistors-BJT.SchLib", "pcb": "AltiumPcbLib/IC-SOT.PcbLib"},
    "LED/RGB LEDs":                    {"sch": "AltiumSchLib/Diodes.SchLib", "pcb": "AltiumPcbLib/LED.PcbLib", "ref": "LED"},
    "Oscillators-Crystals":            {"sch": "AltiumSchLib/CrystalOscillator.SchLib", "pcb": "AltiumPcbLib/CrystalOscillator.PcbLib", "ref": "XTAL-2P"},
    "Oscillators-Oscillators":         {"sch": "AltiumSchLib/CrystalOscillator.SchLib", "pcb": "AltiumPcbLib/CrystalOscillator.PcbLib", "ref": "OSC"},
    "ICs-Power":                       {"sch": "AltiumSchLib/IC/LDO.SchLib", "pcb": "AltiumPcbLib/IC-SOT.PcbLib"},
    "ICs-MCU/MPU/SOC":                 {"sch": "AltiumSchLib/ICs-MCU.SchLib", "pcb": "AltiumPcbLib/IC-LQFP.PcbLib"},
    "ICs-Interface":                   {"sch": "AltiumSchLib/ICs-Interface.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "ICs-Memory":                      {"sch": "AltiumSchLib/ICs-Memory.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "ICs-Sensors":                     {"sch": "AltiumSchLib/ICs-Sensor.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "ICs-Amplifiers/Comparators":      {"sch": "AltiumSchLib/Ics-Amplifiers.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "ICs-Clock/Timing":                {"sch": "AltiumSchLib/ICs-Interface.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "ICs-Data Acquisition":            {"sch": "AltiumSchLib/ICs-Interface.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "ICs-Embedded Processors/Controllers": {"sch": "AltiumSchLib/ICs-MCU.SchLib", "pcb": "AltiumPcbLib/IC-LQFP.PcbLib"},
    "ICs-Logic":                       {"sch": "AltiumSchLib/ICs-Interface.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "ICs-Motor Driver":                {"sch": "AltiumSchLib/ICs-Motor.SchLib", "pcb": "AltiumPcbLib/IC-SOP.PcbLib"},
    "Connectors-USB Connectors":       {"sch": "AltiumSchLib/Connectors-usb.SchLib", "pcb": "AltiumPcbLib/Connectors-usb.PcbLib"},
    "Connectors-Headers":              {"sch": "AltiumSchLib/Connectors-Headers.SchLib", "pcb": "AltiumPcbLib/Connectors-Headers.PcbLib"},
    "Connectors-Battery":              {"sch": "AltiumSchLib/Battery.SchLib", "pcb": "AltiumPcbLib/Connectors-Battery.PcbLib"},
    "Connectors-Board to Board":       {"sch": "AltiumSchLib/Connector/BoardToBoard.SchLib", "pcb": "AltiumPcbLib/Connectors-EdgeBoard.PcbLib"},
    "Connectors-EdgeBoard":            {"sch": "AltiumSchLib/Connectors-EdgeBoard.SchLib", "pcb": "AltiumPcbLib/Connectors-EdgeBoard.PcbLib"},
    "Connectors-FFC/FPC":              {"sch": "AltiumSchLib/Connectors-FFC_FPC.SchLib", "pcb": "AltiumPcbLib/Connectors-FFC_FPC.PcbLib"},
    "Connectors-Plug":                 {"sch": "AltiumSchLib/Connectors-Plug.SchLib", "pcb": "AltiumPcbLib/Connectors-Plug.PcbLib"},
    "Connectors-Wire to Board":        {"sch": "AltiumSchLib/Connector/WireToBoard.SchLib", "pcb": "AltiumPcbLib/Connectors-w2b.PcbLib"},
    "Connectors-DIN41612":             {"sch": "AltiumSchLib/Connector/DIN41612.SchLib", "pcb": "AltiumPcbLib/Connector/DIN41612.PcbLib"},
    "Switches":                        {"sch": "AltiumSchLib/Miscellaneous/Switch.SchLib", "pcb": "AltiumPcbLib/Switch.PcbLib", "ref": "SW"},
    "Displays":                        {"sch": "AltiumSchLib/Displays.SchLib", "pcb": "AltiumPcbLib/Displays.PcbLib"},
    "Speakers":                        {"sch": "AltiumSchLib/Miscellaneous/Speaker.SchLib", "pcb": "AltiumPcbLib/Speaker.PcbLib"},
    "Transformers":                    {"sch": "AltiumSchLib/Other/Transformer.SchLib", "pcb": "AltiumPcbLib/Other/Transformer.PcbLib"},
    "Modules-GNSS":                    {"sch": "AltiumSchLib/Modules-GNSS.SchLib", "pcb": "AltiumPcbLib/Modules.PcbLib"},
    "Modules-2G/3G/4G/5G":             {"sch": "AltiumSchLib/Module/Cellular.SchLib", "pcb": "AltiumPcbLib/Modules.PcbLib"},
    "Circuit Protection-TVS/ESD":      {"sch": "AltiumSchLib/Diodes.SchLib", "pcb": "AltiumPcbLib/Diodes-SOD.PcbLib", "ref": "TVS"},
}

# 内部编码前缀（按表）
PART_PREFIX = {
    "Resistors": "R", "Resistors-Current Sensor Resistor": "RCS",
    "Capacitors": "C", "Capacitors-Electrolytic Capacitors": "CE", "Capacitors-Super Capacitors": "CS",
    "Inductors": "L", "Beads": "FB",
    "Diodes": "D", "Transistors-BJT": "Q", "Transistors-MOSFETs": "Q",
    "LED/RGB LEDs": "LED", "Oscillators-Crystals": "Y", "Oscillators-Oscillators": "OSC",
    "Circuit Protection-TVS/ESD": "TVS",
    "Switches": "SW", "Displays": "LCD", "Speakers": "SPK", "Transformers": "T",
}

# 封装字符串 → PcbLib 家族文件（模糊匹配用）
PKG_TO_PCB_FAM = [
    ("QFN", "IC-QFN"), ("UFQFPN", "IC-UFQFPN"), ("VFQFPN", "IC-VFQFPN"), ("WQFN", "IC-WQFN"),
    ("LQFP", "IC-LQFP"), ("TQFP", "IC-TQFP"), ("PQFP", "IC-TQFP"), ("MQFP", "IC-MQFP"),
    ("SOP", "IC-SOP"), ("SSOP", "IC-SSOP"), ("TSSOP", "IC-TSSOP"), ("MSOP", "IC-MSOP"),
    ("QSOP", "IC-SSOP"), ("HSOP", "IC-HSOP"), ("HTSSOP", "IC-HTSSOP"), ("TVSOP", "IC-TVSOP"), ("TSOP", "IC-TSOP"),
    ("TSOT", "IC-TSOT"), ("SOT", "IC-SOT"),
    ("DFN", "IC-DFN"), ("uDFN", "IC-uDFN"), ("VSON", "IC-VSON"), ("WSON", "IC-WSON"),
    ("DSON", "IC-DSON"), ("XSON", "IC-XSON"), ("VQFN", "IC-VQFN"), ("TQFN", "IC-TQFN"),
    ("LGA", "IC-LGA"), ("LFCSP", "IC-LFCSP"),
    ("BGA", "IC-BGA"), ("PBGA", "IC-s-PBGA"), ("TFBGA", "IC-TFBGA"), ("NFBGA", "IC-NFBGA"),
    ("VFBGA", "IC-VFBGA"), ("WFBGA", "IC-WBGA"), ("FBGA", "IC-FBGA"),
    ("PLCC", "IC-PLCC"), ("DIP", "IC-DIP"), ("TO", "IC-TO"),
    ("SMA", "Diodes-SMA"), ("SMB", "Diodes-SMB"), ("SMC", "Diodes-SMC"),
    ("SOD", "Diodes-SOD"), ("DO-214", "Diodes-SMA"),
]


def suggest_library_fields(table: str, package: str = "", lib_root: str = ""):
    """按表名 + 封装给出模型字段建议 dict（可能部分为空）。
    lib_root 为 mdb 所在目录，若存在则用真实存在的库文件校验建议路径。"""
    s = {"Library Ref": "", "Library Path": "", "Footprint Ref": "",
         "Footprint Path": "", "PCB3D Ref": "", "PCB3D Path": ""}
    m = LIB_MAP.get(table, {})
    pkg = (package or "").upper()
    ref = m.get("ref", "")

    # SCH 库
    sch = m.get("sch", f"AltiumSchLib/{table}.SchLib")
    s["Library Path"] = sch
    if not ref:
        s["Library Ref"] = ""  # IC 类约定为器件型号，由调用方填 MPN
    else:
        s["Library Ref"] = ref

    # PCB 库：先按封装家族猜文件
    pcb = m.get("pcb", "")
    pkg_clean = pkg.replace(" ", "")
    for key, fam in PKG_TO_PCB_FAM:
        if key in pkg_clean:
            pcb = f"AltiumPcbLib/{fam}.PcbLib"
            break
    s["Footprint Path"] = pcb
    s["Footprint Ref"] = package or ""

    # 3D：仓库实际为平铺 StepModel/<封装>.STEP；PCB3D Path 只存目录，文件名由封装名决定
    if package:
        s["PCB3D Ref"] = package
        s["PCB3D Path"] = "StepModel"

    # 用真实目录校验：若库根存在且建议的文件不存在，则扫描目录找匹配文件
    if lib_root:
        import os
        sch_full = os.path.join(lib_root, sch.replace("/", os.sep))
        if not os.path.exists(sch_full):
            alt = _find_file(os.path.join(lib_root, "AltiumSchLib"), ".SchLib", table)
            if alt:
                s["Library Path"] = alt.replace(os.sep, "/")
        pcb_full = os.path.join(lib_root, pcb.replace("/", os.sep)) if pcb else None
        if pcb and pcb_full and not os.path.exists(pcb_full):
            alt = _find_file(os.path.join(lib_root, "AltiumPcbLib"), ".PcbLib", pkg_clean)
            if alt:
                s["Footprint Path"] = alt.replace(os.sep, "/")
    return s


def _find_file(dirpath, ext, *keywords):
    """在目录（含一层子目录）中按关键词找第一个匹配文件，返回相对 dirpath 上层的路径。"""
    import os
    if not os.path.isdir(dirpath):
        return ""
    kws = [k.lower() for k in keywords if k]
    cands = []
    for root, dirs, files in os.walk(dirpath):
        for f in files:
            if f.lower().endswith(ext):
                cands.append(os.path.join(root, f))
        # 只进一层子目录
        if root != dirpath and root.count(os.sep) > dirpath.count(os.sep) + 1:
            dirs[:] = []
    base = os.path.dirname(dirpath)
    # 优先含关键词的
    for c in cands:
        cl = c.lower()
        if all(k in cl for k in kws):
            return os.path.relpath(c, base)
    if cands:
        # 同名前缀（如 Resistors）
        for c in cands:
            if os.path.basename(c).lower().startswith((kws[0] if kws else "")):
                return os.path.relpath(c, base)
        return os.path.relpath(cands[0], base)
    return ""


def suggest_part_number(table: str, component_type: str, package: str = ""):
    """内部编码建议：<前缀>-<封装>-<型号>。真实库中该字段多为空，仅作提示。"""
    pfx = PART_PREFIX.get(table)
    if not pfx:
        return ""
    parts = [pfx]
    if package:
        parts.append(package.replace(" ", ""))
    if component_type:
        parts.append(component_type)
    return "-".join(parts)


def build_sql_preview(table: str, cols: list, data: dict) -> str:
    esc = lambda s: "'" + str(s or "").replace("'", "''") + "'"
    col_sql = ", ".join(f"[{c}]" for c in cols)
    val_sql = ",\n   ".join(esc(data.get(c, "")) for c in cols)
    return f"INSERT INTO [{table}]\n  ({col_sql})\nVALUES\n  ({val_sql});"
