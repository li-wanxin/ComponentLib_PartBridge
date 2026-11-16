# -*- coding: utf-8 -*-
"""ComponentLib.mdb 数据层：读表结构、读记录、查重、写入。"""
import os
import datetime
import pyodbc

# 字段中文说明（来自 mdb 真实 schema，ODBC 读不到列描述，内置映射）
FIELD_DESC = {
    "Part Number": "内部编码",
    "Component Type": "器件型号",
    "Vendor": "生产商",
    "Value": "值",
    "Tolerance": "精度",
    "Type": "器件具体类别",
    "Description": "描述",
    "Suppiler": "供应商",
    "Suppiler Number": "供应商编码",
    "Library Ref": "器件SCH封装名称",
    "Library Path": "器件SCH库路径(Altium引用)",
    "Footprint Ref": "器件PCB封装名称",
    "Footprint Path": "器件PCB库路径(Altium引用)",
    "PCB3D Ref": "器件3D PCB封装名称",
    "PCB3D Path": "器件3D PCB库路径(Altium引用)",
    "Schematic_Part": "Cadence原理图",
    "PCB_Footprint": "Cadence封装",
    "ComponentLink2Description": "器件参考文件,默认DataSheet",
    "ComponentLink2URL": "器件参考文件路径",
    "LatestRevisionDate": "修改日期",
}

SYSTEM_TABLES = {"TMPPRTS"}


class MdbError(Exception):
    pass


class MdbDatabase:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        if not os.path.exists(self.path):
            raise MdbError(f"数据库文件不存在: {self.path}")
        self.conn = pyodbc.connect(
            r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + self.path + ";",
            autocommit=True,
        )

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ---------- 结构 ----------
    def get_tables(self):
        """返回业务表名列表（排除系统表）。"""
        cur = self.conn.cursor()
        names = [r[2] for r in cur.tables(tableType="TABLE")]
        cur.close()
        return sorted(
            n for n in names if not n.startswith("MSys") and n not in SYSTEM_TABLES
        )

    def get_columns(self, table: str):
        """返回表的字段名列表（按列序）。
        用 SELECT TOP 1 的 cursor.description 获取（空表也能取到字段名，
        且避免 ODBC 目录扫描遇到个别表的坏字符导致 UnicodeDecodeError）。"""
        cur = self.conn.cursor()
        cur.execute(f"SELECT TOP 1 * FROM [{table}]")
        cols = [d[0] for d in cur.description]
        cur.close()
        return cols

    def count(self, table: str) -> int:
        cur = self.conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM [{table}]")
        n = cur.fetchone()[0]
        cur.close()
        return n

    def distinct_values(self, table: str, column: str, limit: int = 500):
        """取某列的已有非空去重值（供下拉选择），按出现顺序返回。"""
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"SELECT DISTINCT [{column}] FROM [{table}] "
                f"WHERE [{column}] IS NOT NULL AND [{column}] <> ''"
            )
            return [str(r[0]) for r in cur.fetchall()[:limit]]
        except Exception:
            return []
        finally:
            cur.close()

    # ---------- 读取 ----------
    def read_table(self, table: str, search: str = None, limit: int = 5000):
        """读取整表记录，返回 (columns, rows)。search 在全部字段中做模糊过滤。"""
        cols = self.get_columns(table)
        cur = self.conn.cursor()
        if search:
            cond = " OR ".join(
                f"[{c}] LIKE ?" for c in cols
            )
            args = [f"%{search}%"] * len(cols)
            cur.execute(
                f"SELECT TOP {limit} * FROM [{table}] WHERE {cond}", args
            )
        else:
            cur.execute(f"SELECT TOP {limit} * FROM [{table}]")
        rows = []
        for r in cur.fetchall():
            rows.append(
                {c: ("" if v is None else str(v)) for c, v in zip(cols, r)}
            )
        cur.close()
        return cols, rows

    # ---------- 查重 / 写入 ----------
    def check_duplicate(self, table: str, data: dict):
        """mdb 中 [Component Type] 有唯一索引；提前查重给出友好提示。
        返回 None 或提示字符串。"""
        ct = (data.get("Component Type") or "").strip()
        if not ct:
            return None
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM [{table}] WHERE [Component Type] = ?", ct
        )
        n = cur.fetchone()[0]
        cur.close()
        if n:
            return f"[{table}] 中已存在器件型号 '{ct}'（{n} 条），mdb 对该字段有唯一索引"
        return None

    def backup_daily(self):
        """按天备份整库到 mdb 所在目录 backups\\ 下；当天已有备份则跳过。
        返回备份文件路径，或 None（今日已有）。"""
        import shutil
        root = os.path.dirname(self.path)
        bdir = os.path.join(root, "backups")
        os.makedirs(bdir, exist_ok=True)
        today = datetime.date.today().strftime("%Y%m%d")
        stem = os.path.splitext(os.path.basename(self.path))[0]
        target = os.path.join(bdir, f"{stem}_{today}.mdb")
        if os.path.exists(target):
            return None
        shutil.copy2(self.path, target)
        return target

    def _match_cond(self, cols: list, old: dict):
        """构造定位旧行的条件。优先用 [Component Type] 唯一索引；
        型号为空时退化为按全部字段精确匹配（兼容 NULL 与空串）。"""
        old_ct = str(old.get("Component Type") or "").strip()
        if old_ct:
            return "[Component Type] = ?", [old_ct]
        conds, args = [], []
        for c in cols:
            v = str(old.get(c) or "")
            conds.append(f"([{c}] = ? OR ([{c}] IS NULL AND ? = ''))")
            args += [v, v]
        return " AND ".join(conds), args

    def update(self, table: str, old: dict, data: dict):
        """更新一条记录。old 为该行修改前的完整快照（用于定位），
        data 为修改后的全字段值。LatestRevisionDate 由系统自动更新为当天。"""
        cols = self.get_columns(table)
        cond, args = self._match_cond(cols, old)
        cur = self.conn.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM [{table}] WHERE {cond}", args)
            n = cur.fetchone()[0]
        finally:
            cur.close()
        if n == 0:
            raise MdbError("未找到要修改的记录（可能已被其他程序改动），请刷新后重试")
        if n > 1:
            raise MdbError(f"定位到 {n} 条相同记录，无法唯一确定要修改的行（该表可能无唯一型号）")
        # 新型号与旧行不同时查重（唯一索引保护）
        old_ct = str(old.get("Component Type") or "").strip()
        new_ct = str(data.get("Component Type") or "").strip()
        if new_ct and new_ct != old_ct:
            dup = self.check_duplicate(table, data)
            if dup:
                raise MdbError(dup)
        values = []
        for c in cols:
            if c == "LatestRevisionDate":
                # 修改日期不手动输入：只要有更新就自动写入当天
                values.append(datetime.date.today().isoformat())
                continue
            v = data.get(c)
            if v is None:
                v = ""
            values.append(str(v))
        set_sql = ",".join(f"[{c}] = ?" for c in cols)
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"UPDATE [{table}] SET {set_sql} WHERE {cond}", values + args
            )
        except pyodbc.IntegrityError as e:
            raise MdbError("更新被拒绝（唯一索引冲突，多为器件型号与其他记录重复）：" + str(e))
        finally:
            cur.close()

    def insert(self, table: str, data: dict):
        """向表写入一条记录。data: {字段名: 值}，缺失字段按该表实际列补空。"""
        cols = self.get_columns(table)
        dup = self.check_duplicate(table, data)
        if dup:
            raise MdbError(dup)
        values = []
        for c in cols:
            v = data.get(c)
            if v is None:
                v = ""
            if c == "LatestRevisionDate" and not str(v).strip():
                v = datetime.date.today().isoformat()
            values.append(str(v))
        ph = ",".join("?" * len(cols))
        sql = (
            f"INSERT INTO [{table}] "
            f"({','.join('[' + c + ']' for c in cols)}) VALUES ({ph})"
        )
        cur = self.conn.cursor()
        try:
            cur.execute(sql, values)
        except pyodbc.IntegrityError as e:
            raise MdbError(
                "写入被拒绝（唯一索引冲突，多为器件型号重复）：" + str(e)
            )
        finally:
            cur.close()
