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
