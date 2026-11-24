# -*- coding: utf-8 -*-
"""立创商城 SN 查询客户端。

数据源：嘉立创EDA官方器件库接口（LCSC3D 同源思路，自行实现）：
  GET https://lceda.cn/api/products/{SN}/components      （国内优先）
  GET https://easyeda.com/api/products/{SN}/components   （备用镜像）
返回数据含：title(MPN)、description、tags(分类)、packageDetail(封装)、
dataStr.head.c_para（Manufacturer/Value/package/Supplier Part 等）。

注意：商城有货的 SN 不一定在官方器件库中（没有官方符号的元件查不到），
此时如实报告并由 UI 兜底手动填写。
"""
import gzip
import http.client
import json
import random
import re
import socket
import ssl
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

DOMAINS = ["https://lceda.cn", "https://easyeda.com"]

# 3D 模型 STEP 直链（LCSC3D 同源）：国内镜像优先
MODEL_STEP_TPLS = (
    "https://modules.lceda.cn/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}",
    "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}",
)

# 英文分类 → DB 表名（tags 匹配）
TAG_TABLE_MAP = {
    "resistor": "Resistors",
    "current sense": "Resistors-Current Sensor Resistor",
    "mlcc": "Capacitors",
    "multilayer ceramic": "Capacitors",
    "ceramic capacitor": "Capacitors",
    "aluminum electrolytic": "Capacitors-Electrolytic Capacitors",
    "supercapacitor": "Capacitors-Super Capacitors",
    "inductor": "Inductors",
    "ferrite bead": "Beads",
    "schottky": "Diodes",
    "zener": "Diodes",
    "tv": "Circuit Protection-TVS/ESD",
    "esd": "Circuit Protection-TVS/ESD",
    "mosfet": "Transistors-MOSFETs",
    "bjt": "Transistors-BJT",
    "led": "LED/RGB LEDs",
    "crystal": "Oscillators-Crystals",
    "oscillator": "Oscillators-Oscillators",
    "ldo": "ICs-Power",
    "voltage regulator": "ICs-Power",
    "power management": "ICs-Power",
    "buck": "ICs-Power",
    "boost": "ICs-Power",
    "sbd": "Diodes",
    "barrier diode": "Diodes",
    "transceiver": "Modules-2G/3G/4G/5G",
    "wifi": "Modules-2G/3G/4G/5G",
    "bluetooth": "Modules-2G/3G/4G/5G",
    "usb": "Connectors-USB Connectors",
    "header": "Connectors-Headers",
    "connector": "Connectors-Board to Board",
    "push button": "Switches",
    "toggle": "Switches",
    "mcu": "ICs-MCU/MPU/SOC",
    "microcontroller": "ICs-MCU/MPU/SOC",
    "memory": "ICs-Memory",
    "flash": "ICs-Memory",
    "opamp": "ICs-Amplifiers/Comparators",
    "amplifier": "ICs-Amplifiers/Comparators",
    "comparator": "ICs-Amplifiers/Comparators",
    "sensor": "ICs-Sensors",
    "motor": "ICs-Motor Driver",
    "interface": "ICs-Interface",
    "logic": "ICs-Logic",
    "clock": "ICs-Clock/Timing",
    "adc": "ICs-Data Acquisition",
    "dac": "ICs-Data Acquisition",
    "gnss": "Modules-GNSS",
}


class LcscResult:
    def __init__(self):
        self.sn = ""
        self.data = {}          # DB 字段名 -> 值
        self.package = ""       # 封装全名（官方原始 title）
        self.pkg_family = ""    # 封装家族（下划线前的干净段，如 SMA / C0603）
        self.suggest_table = "" # 按 tags 建议的目标表
        self.model3d = None     # 3D 模型信息 {uuid, uuid_3d, name}
        self.source = ""        # 成功通道名
        self.logs = []          # 各通道尝试日志

    @property
    def ok(self):
        return bool(self.data.get("Component Type"))


def _http_json(url, timeout=15, prefer_ip=False):
    h = {
        "Accept-Encoding": "gzip",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": UA,
        "Referer": "https://easyeda.com/",
    }
    try:
        if prefer_ip:
            with urlopen_smart(url, timeout=timeout, headers=h, prefer_ip=True) as r:
                raw = r.read()
        else:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                raw = r.read()
    except Exception:
        raw = _http_get_ip_fallback(url, timeout, h)
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", "replace"))


# ---------- DNS 兜底与 IP 直连（2026-11-17：本地 DNS 解析 wmsc.lcsc.com 失败时自愈） ----------
_DNS_SERVERS = ("223.5.5.5", "114.114.114.114")   # 阿里 / 114 公共 DNS
_RESOLVE_CACHE = {}                                # domain -> (ips, expire_ts)


def _dns_query_a(name, server, timeout=3):
    """向指定 DNS 服务器查 A 记录（stdlib UDP 最小实现，返回 IP 列表）。"""
    tid = random.randint(0, 0xFFFF)
    header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(header + q + struct.pack(">HH", 1, 1), (server, 53))
        data, _ = s.recvfrom(4096)
    finally:
        s.close()
    if len(data) < 12 or struct.unpack(">H", data[:2])[0] != tid:
        return []
    ancount = struct.unpack(">H", data[6:8])[0]
    i = 12                                   # 跳过问题区
    while data[i] != 0:
        i += data[i] + 1
    i += 5
    ips = []
    for _ in range(ancount):
        if data[i] & 0xC0 == 0xC0:
            i += 2                           # 压缩指针
        else:
            while data[i] != 0:
                i += data[i] + 1
            i += 1
        rtype, _, _, rdlen = struct.unpack(">HHIH", data[i:i + 10])
        i += 10
        if rtype == 1 and rdlen == 4:
            ips.append(".".join(str(b) for b in data[i:i + 4]))
        i += rdlen
    return ips


def _getaddrinfo_fast(host, timeout=2.0):
    """带超时的系统 DNS 解析：本地 DNS 故障时 getaddrinfo 可能阻塞 5-10s，超时即放弃。"""
    result = []

    def _run():
        try:
            result.extend([ai[4][0] for ai in
                           socket.getaddrinfo(host, 443, socket.AF_INET)][:4])
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    deadline = time.time() + timeout
    while not result and time.time() < deadline:
        time.sleep(0.05)
    return result


def resolve_host(name):
    """域名解析：系统 DNS（2s 快速失败）→ 公共 DNS 兜底。
    成功缓存 300s，失败负缓存 30s（避免每次查询都等 DNS 超时）。"""
    now = time.time()
    hit = _RESOLVE_CACHE.get(name)
    if hit and hit[1] > now:
        return hit[0]
    ips = _getaddrinfo_fast(name)
    if not ips:
        for srv in _DNS_SERVERS:
            try:
                ips = _dns_query_a(name, srv)
                if ips:
                    break
            except Exception:
                continue
    _RESOLVE_CACHE[name] = (ips, now + (300 if ips else 30))
    return ips


def urlopen_smart(url, timeout=15, headers=None, prefer_ip=False):
    """增强版 GET：默认先常规请求、失败走 IP 直连兜底；
    prefer_ip=True 时跳过常规请求直接 IP 直连（用于已知本地 DNS 故障的域名）。
    返回响应对象（含 .read()/.status）。"""
    if isinstance(url, urllib.request.Request):
        headers = {k: v for k, v in url.header_items()} or (headers or {})
        url = url.full_url
    if not prefer_ip:
        try:
            req = urllib.request.Request(url, headers=headers or {})
            return urllib.request.urlopen(req, timeout=timeout, context=CTX)
        except urllib.error.HTTPError:
            raise
        except Exception:
            pass                                    # DNS/代理/超时 → IP 直连兜底
    u = urllib.parse.urlparse(url)
    host = u.hostname
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    ips = resolve_host(host)
    if not ips:
        raise RuntimeError(f"无法解析 {host}（系统与公共 DNS 均失败）")
    last = None
    for ip in ips:
        try:
            s = socket.create_connection((ip, 443), timeout=timeout)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ss = ctx.wrap_socket(s, server_hostname=host)
            h = {"Host": host, "User-Agent": UA, "Accept": "*/*",
                 "Connection": "close"}   # 不带 gzip：保证二进制（如 PDF）原样落盘
            h.update(headers or {})
            conn = http.client.HTTPSConnection(host)
            conn.sock = ss                      # 复用带 SNI 的握手连接
            conn.request("GET", path, headers=h)
            return conn.getresponse()
        except Exception as e:
            last = e
    raise last if last else RuntimeError("IP 直连兜底失败")


def _http_get_ip_fallback(url, timeout, headers):
    with urlopen_smart(url, timeout=timeout, headers=headers) as r:
        return r.read()


def _provider_easyeda(sn, res: LcscResult):
    for dom in DOMAINS:
        try:
            obj = _http_json(f"{dom}/api/products/{sn}/components")
        except Exception as e:
            res.logs.append(f"✗ {dom}: {type(e).__name__} {e}")
            continue
        if not obj.get("success") or not obj.get("result"):
            res.logs.append(f"✗ {dom}: 官方器件库中无该编号（success={obj.get('success')}）")
            continue
        r = obj["result"]
        cpara = ((r.get("dataStr") or {}).get("head") or {}).get("c_para") or {}
        d = res.data

        mpn = str(cpara.get("Manufacturer Part") or r.get("title") or "").strip()
        d["Component Type"] = mpn
        d["Vendor"] = str(cpara.get("Manufacturer") or "").strip()
        d["Value"] = str(cpara.get("Value") or "").strip()
        d["Description"] = str(r.get("description") or "").strip()
        d["Suppiler"] = "立创商城"
        d["Suppiler Number"] = sn
        d["ComponentLink2Description"] = "DataSheet"
        # 商品页链接（lcsc / szlcsc 子对象）
        link = ""
        for sub in ("lcsc", "szlcsc"):
            u = ((r.get(sub) or {}).get("url") or "").strip()
            if u:
                link = u if u.startswith("http") else "https:" + u
                break
        d["ComponentLink2URL"] = link

        # 封装：官方 title 常带尺寸后缀，如 SMA_L4.3-W2.6-LS5.2-RD / USB-C_SMD-..._1
        pkg = str((r.get("packageDetail") or {}).get("title") or cpara.get("package") or "").strip()
        res.package = pkg
        res.pkg_family = pkg.split("_")[0].strip()

        # 3D 模型编号（复用同一次请求，零额外开销）
        res.model3d = parse_model3d(r)

        # 精度：从描述里抓 ±x%
        m = re.search(r"±\s*[\d.]+\s*%", d["Description"])
        if m:
            d["Tolerance"] = m.group(0)

        # 具体类别：Value 补充（如描述带电压等）——保守留空给用户，tags 只用于选表
        tags = r.get("tags") or []
        if tags:
            res.suggest_table = _tags_to_table(tags[0])

        res.source = f"嘉立创EDA官方库（{dom.replace('https://','')}）"
        res.logs.append(f"✓ {dom}: 命中（MPN={mpn}）")
        return
    raise RuntimeError("两个官方库镜像均未命中")


def parse_model3d(result: dict):
    """从官方器件数据 result 中解析 3D 模型编号（LCSC3D model_reference 同源思路）：
    遍历封装 dataStr.shape 找 SVGNODE~ 节点（c_etype 空或 outline3D）取 attrs.uuid；
    兜底 head.uuid_3d（官方 3D 库记录编号，可经 resolve_library_model_uuid 解析）。"""
    pkg = result.get("packageDetail") or {}
    ds = pkg.get("dataStr")
    if isinstance(ds, str):
        try:
            ds = json.loads(ds)
        except ValueError:
            ds = {}
    if not isinstance(ds, dict):
        ds = {}
    head = ds.get("head") or {}
    uuid_3d = str(head.get("uuid_3d") or "").strip()
    cpara = head.get("c_para") or {}
    fallback_name = str(cpara.get("3DModel") or pkg.get("title") or "").strip()
    for shape in ds.get("shape") or []:
        if not isinstance(shape, str) or not shape.startswith("SVGNODE~"):
            continue
        try:
            node = json.loads(shape.partition("~")[2])
            attrs = node.get("attrs") or {}
        except ValueError:
            continue
        if attrs.get("c_etype") not in (None, "outline3D") or not attrs.get("uuid"):
            continue
        return {"uuid": str(attrs["uuid"]),
                "uuid_3d": uuid_3d,
                "name": str(attrs.get("title") or fallback_name).strip()}
    if uuid_3d:
        return {"uuid": "", "uuid_3d": uuid_3d, "name": fallback_name}
    return None


def resolve_library_model_uuid(uuid_3d: str) -> str:
    """官方 3D 库备用链（LCSC3D component_step_payload 同源思路）：
    uuid_3d → docType=16 官方 3D 库记录 → 真实模型文件 uuid。失败返回空串。"""
    uuid_3d = (uuid_3d or "").strip()
    if not uuid_3d:
        return ""
    for dom in DOMAINS:
        try:
            obj = _http_json(f"{dom}/api/components/{uuid_3d}")
        except Exception:
            continue
        r = obj.get("result")
        if not obj.get("success") or not isinstance(r, dict):
            continue
        if str(r.get("docType")) != "16":
            continue
        ds = r.get("dataStr")
        if isinstance(ds, str):
            try:
                ds = json.loads(ds)
            except ValueError:
                ds = {}
        u = ((ds or {}).get("head") or {}).get("uuid") or ""
        if u:
            return str(u).strip()
    return ""


def _tags_to_table(tag: str) -> str:
    t = (tag or "").lower()
    for kw, table in TAG_TABLE_MAP.items():
        if kw in t:
            return table
    # 直接同名匹配
    if t in ("resistors", "capacitors", "inductors", "beads", "diodes", "switches",
             "displays", "speakers", "transformers"):
        return {"resistors": "Resistors", "capacitors": "Capacitors",
                "inductors": "Inductors", "beads": "Beads", "diodes": "Diodes",
                "switches": "Switches", "displays": "Displays",
                "speakers": "Speakers", "transformers": "Transformers"}[t]
    return ""


_WMSC_CACHE = {}   # sn -> (result dict 或 None, expire_ts)；成功 600s / 失败 20s（避免同 SN 重复慢查询拖累）


def _fetch_wmsc_detail(sn: str) -> dict:
    """LCSC 商品详情（wmsc 接口）：pdfUrl / productDescEn / productNameEn 等。
    DNS 故障时走公共 DNS 兜底直连；同 SN 结果进程内缓存，避免一次查询调两次拖慢。"""
    sn = (sn or "").strip().upper()
    if not re.fullmatch(r"C\d{3,10}", sn):
        return {}
    now = time.time()
    hit = _WMSC_CACHE.get(sn)
    if hit and hit[1] > now:
        return hit[0] or {}
    detail = {}
    try:
        obj = _http_json(
            f"https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={sn}",
            timeout=6, prefer_ip=True,   # wmsc 域名本地 DNS 常态故障：直接 IP 直连
        )
        detail = obj.get("result") or {}
    except Exception:
        detail = {}
    _WMSC_CACHE[sn] = (detail, now + (600 if detail else 20))
    return detail


def fetch_datasheet_url(sn: str) -> str:
    """立创商城规格书 PDF 直链（datasheet.lcsc.com）。
    数据源：LCSC 商品详情接口 result.pdfUrl；无规格书返回空串。"""
    return str(_fetch_wmsc_detail(sn).get("pdfUrl") or "").strip()


def _res_type_autofill(res: LcscResult):
    """电阻表 Type 字段按库惯例自动生成：{封装}/{系列}/{精度}%（如 0402/E96/1%）。
    - 封装：package 去掉 R 前缀取数字（R0603 → 0603）
    - 系列：精度 ≥±5% 恒为 E24；±1% 及更精时按阻值有效位数判
      （数值有效位 ≥3 位 → E96，如 4.75kΩ；否则 E24，如 10kΩ/1MΩ）
    库内真实样例：0402/E24/1%、0402/E96/1%、0603/E24/1%、0805/E96/1% …"""
    tol = str(res.data.get("Tolerance") or "")
    m = re.fullmatch(r"±\s*([\d.]+)\s*%", tol)
    pkg_num = (res.package or "").upper().strip().lstrip("R")
    if not m or not pkg_num.isdigit():
        return
    pct = m.group(1)
    try:
        pct_f = float(pct)
    except ValueError:
        return
    if pct_f >= 5:
        series = "E24"
    else:
        mm = re.match(r"([\d.]+)", str(res.data.get("Value") or ""))
        digits = mm.group(1).replace(".", "").lstrip("0") if mm else ""
        series = "E96" if len(digits) >= 3 else "E24"
    res.data["Type"] = f"{pkg_num}/{series}/{pct}%"


def _fmt_resistor_value(v) -> str:
    """阻值转库惯例写法（字母作小数点、英文字母大写，库内 619 个既有值零小数点）：
    5.4Ω→5R4，10Ω→10R，5.1kΩ→5K1，10kΩ→10K，1.02MΩ→1M02，1MΩ→1M。
    K/M 值不带 R 后缀（与库内 10K/1M 惯例一致）。"""
    s = str(v or "").strip().replace("µ", "u").replace("μ", "u")
    m = re.fullmatch(r"([\d.]+)\s*(kΩ|KΩ|mΩ|MΩ|uΩ|Ω|k|K|m|M|R)?", s, re.IGNORECASE)
    if not m:
        return str(v)
    num, unit = m.group(1), m.group(2) or "Ω"
    if unit[0].lower() == "m" and unit not in ("M", "MΩ"):
        mult = 1e-3            # mΩ（毫欧，小写 m）
    elif unit[0].lower() == "k":
        mult = 1e3
    elif unit[0].upper() == "M":
        mult = 1e6
    else:
        mult = 1.0
    try:
        ohms = float(num) * mult
    except ValueError:
        return str(v)
    if ohms >= 1e6:
        letter, base = "M", ohms / 1e6
    elif ohms >= 1e3:
        letter, base = "K", ohms / 1e3
    else:
        letter, base = "R", ohms
    text = f"{base:.6f}".rstrip("0").rstrip(".")
    if not text or text == "0":
        text = "0"
    # 有小数点 → 字母作小数点（5.1→5K1）；整数 → 字母作单位后缀（10→10K，欧姆值 10→10R）
    if "." in text:
        return text.replace(".", letter)
    return text + letter


def _fmt_capacitor_value(v, desc) -> str:
    """电容值转「10uF/50V」风格：µ→u，电压从商品页描述抓取（无则不带电压）。"""
    s = str(v or "").strip().replace("µ", "u").replace("μ", "u")
    m = re.match(r"([\d.]+)\s*(uF|nF|pF|mF|F)\b", s, re.IGNORECASE)
    if not m:
        return str(v)
    unit = m.group(2)
    prefix = unit[0].lower() if unit.upper() != "F" else ""
    out = f"{m.group(1)}{prefix}F"
    vm = re.search(r"(\d+(?:\.\d+)?)\s*V\b", str(desc or ""))
    if vm:
        out += f"/{vm.group(1)}V"
    return out


def resolve_suggest_table(suggested: str, tables):
    """把理想表名动态解析为库中真实存在的表——表结构可能被用户合并/改名，
    不能写死映射（如 BJT/MOSFET 已并入统一的 Transistors 表）。

    匹配顺序（返回 (表名或"", 候选列表)）：
    1. 大小写不敏感精确匹配
    2. 第二段模糊：Transistors-MOSFETs → 库中含 "mosfet" 的表
    3. 顶层大类唯一：Transistors-* → 库中 Transistors 开头的表只有一张则命中
    解析失败时返回候选列表，交前端提示用户手选。"""
    suggested = (suggested or "").strip()
    names = [t for t in (tables or []) if t]
    if not suggested or not names:
        return "", []
    low = {t.casefold(): t for t in names}
    # 1. 精确（大小写不敏感）
    if suggested.casefold() in low:
        return low[suggested.casefold()], []
    # 2. 第二段模糊（mosfets → mosfet 包含于表名）
    parts = suggested.split("-", 1)
    if len(parts) == 2 and parts[1].strip():
        seg2 = parts[1].strip().casefold().rstrip("s")
        cands = sorted(t for t in names if seg2 and seg2 in t.casefold())
        if len(cands) == 1:
            return cands[0], []
        if cands:
            return "", cands
    # 3. 顶层大类（Transistors-* → Transistors 开头的表）
    prefix = parts[0].strip().casefold()
    cands = sorted(t for t in names if t.casefold().startswith(prefix))
    if len(cands) == 1:
        return cands[0], []
    if cands:
        return "", cands
    return "", []


def fetch(sn: str) -> LcscResult:
    sn = sn.strip().upper()
    res = LcscResult()
    res.sn = sn
    if not re.fullmatch(r"C\d{3,10}", sn):
        res.logs.append(f"SN 格式不符（应为 C+数字，如 C25704）：{sn}")
        return res
    try:
        _provider_easyeda(sn, res)
        # 描述/封装升级：立创商品页详情（productDescEn → productIntroEn → productNameEn）
        detail = _fetch_wmsc_detail(sn)
        page_desc = (str(detail.get("productDescEn") or "").strip()
                     or str(detail.get("productIntroEn") or "").strip()
                     or str(detail.get("productNameEn") or "").strip())
        if page_desc and len(page_desc) >= len(res.data.get("Description", "")):
            res.data["Description"] = page_desc
        # 官方库缺封装时用商品页 encapStandard 兜底（如 DFN1006-2L）
        if not res.package:
            enc = str(detail.get("encapStandard") or "").strip()
            if enc:
                res.package = enc
                res.pkg_family = enc.split("_")[0].split(",")[0].strip()
        # 分类建议兜底：官方 tags 未命中时用商品页分类名匹配
        if not res.suggest_table:
            for cand in (str(detail.get("catalogName") or ""),
                         str(detail.get("parentCatalogName") or "")):
                t = _tags_to_table(cand)
                if t:
                    res.suggest_table = t
                    break

        # 精度兜底：所有描述增强完成后再抓一次——官方描述为空的 SN，
        # 只有商品页描述（覆盖 Description 之后）才含 ±x%，原抓取时机会漏
        if not res.data.get("Tolerance"):
            m = re.search(r"±\s*[\d.]+\s*%", res.data.get("Description", ""))
            if m:
                res.data["Tolerance"] = m.group(0)

        # Type 带出：电阻表按库惯例生成「封装/系列/精度」（如 0603/E96/1%）
        if res.suggest_table == "Resistors":
            _res_type_autofill(res)

        # Value 规范化（在 Type 计算之后：Type 的有效位数判定用的是原始数值写法）
        if res.suggest_table == "Resistors":
            res.data["Value"] = _fmt_resistor_value(res.data.get("Value"))
        elif str(res.suggest_table or "").startswith("Capacitors"):
            res.data["Value"] = _fmt_capacitor_value(
                res.data.get("Value"), res.data.get("Description"))
    except Exception as e:
        res.logs.append(f"✗ {e}")
        res.logs.append("全部通道失败或官方库无此编号，可手动填写（不影响入库）")
    return res


if __name__ == "__main__":
    import sys
    for sn in (sys.argv[1:] or ["C25704"]):
        r = fetch(sn)
        print(f"\n=== {sn} | OK: {r.ok} | source: {r.source} | package: {r.package} | table: {r.suggest_table}")
        if r.model3d:
            print(f"  3D 模型: uuid={r.model3d['uuid']} uuid_3d={r.model3d['uuid_3d']} name={r.model3d['name']}")
        for k, v in r.data.items():
            print(f"  {k}: {str(v)[:70]}")
        for l in r.logs:
            print("  [log]", l)


# ================= 关键字搜索（器件名称/型号 → 候选列表） =================
# 立创商城搜索页有 JS 反爬挑战，普通 HTTP 拿不到数据；
# 但页面内嵌 __NEXT_DATA__ 结构化商品数据（productCode/productModel/品牌/封装），
# 用系统自带 Edge 无头渲染（真实 Chromium 自动过挑战）后解析即可 —— 稳定可靠。

_EDGE_PATHS = (
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    r"C:/Users/%USERNAME%/AppData/Local/Microsoft/Edge/Application/msedge.exe",
)


def _find_edge() -> str:
    import os
    import shutil
    for p in _EDGE_PATHS:
        if os.path.exists(p):
            return p
    found = shutil.which("msedge") or shutil.which("chrome")
    if found:
        return found
    raise RuntimeError("未找到系统 Edge/Chrome 浏览器，无法进行关键字搜索")


def search_keyword(keyword: str, limit: int = 20) -> list:
    """关键字搜索立创商城在售器件，返回候选列表：
    [{sn, model, brand, encap, desc, ptype}]；失败抛 RuntimeError。"""
    import os
    import subprocess
    import urllib.parse

    kw = (keyword or "").strip()
    if not kw:
        return []
    edge = _find_edge()
    url = "https://so.szlcsc.com/global.html?k=" + urllib.parse.quote(kw)
    # 每次搜索用全新临时 profile：复用 profile 会被立创风控标记后强制跳登录页；
    # 全新匿名会话可通过 JS 挑战正常出结果，用完即删
    import random
    tmpdir = os.path.join(os.environ.get("TEMP", "."),
                          f"pbridge_srch_{random.randint(10 ** 8, 10 ** 9)}")
    # 搜索页要先过 JS 反爬挑战再渲染真实结果，时机有波动：
    # 三级重试递增虚拟时间预算；挑战页（_xvasu 标记）或登录页视为未渲染完成
    html = ""
    items: dict = {}
    try:
        for budget in (20000, 35000, 50000):
            cmd = [edge, "--headless=new", "--disable-gpu", "--no-first-run",
                   f"--user-data-dir={tmpdir}", f"--virtual-time-budget={budget}",
                   "--timeout=60000", "--dump-dom", url]
            try:
                cp = subprocess.run(cmd, capture_output=True, timeout=120,
                                    encoding="utf-8", errors="replace")
                html = cp.stdout or ""
            except Exception as exc:
                raise RuntimeError(f"搜索页渲染失败: {exc}") from exc
            if "用户登录中心" in html[:12000]:
                continue                     # 风控跳登录页 → 换更大预算的全新会话重试
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
                          html, re.S)
            if not m:
                continue                     # 挑战页或渲染未完成 → 提高预算重试
            try:
                data = json.loads(m.group(1))
            except ValueError:
                continue

            def _walk(o, depth=0):
                if depth > 30:
                    return
                if isinstance(o, dict):
                    code = o.get("productCode")
                    if code and re.fullmatch(r"C\d{3,10}", str(code)):
                        items[str(code)] = o
                    for v in o.values():
                        _walk(v, depth + 1)
                elif isinstance(o, list):
                    for v in o:
                        _walk(v, depth + 1)

            items.clear()
            _walk(data)
            if items:
                break                        # 拿到候选即止
            # NEXT_DATA 正常但无商品 → 可能真无结果，再试一轮确认
    finally:
        # 清理临时 profile（延迟删除，避免句柄未释放）
        import threading
        def _cleanup():
            import shutil as _sh
            _sh.rmtree(tmpdir, ignore_errors=True)
        threading.Timer(3.0, _cleanup).start()
    if not html or ("__NEXT_DATA__" not in html and "用户登录中心" not in html[:12000]
                    and "_xvasu" in html[:8000]):
        raise RuntimeError("搜索页加载失败（网络波动），请重试")
    out = []
    for code, o in items.items():
        out.append({
            "sn": code,
            "model": str(o.get("productModel") or o.get("productName") or "").strip(),
            "brand": str(o.get("productGradePlateName") or "").strip(),
            "encap": str(o.get("encapsulationModel") or "").strip(),
            "desc": str(o.get("productName") or "").strip()[:60],
            "ptype": str(o.get("productType") or "").strip(),
        })
    out.sort(key=lambda x: x["sn"])
    return out[:limit]
