# -*- coding: utf-8 -*-
"""ComponentLib 物料入库工具 - PySide6 主界面"""
import datetime
import json
import os
import sys

from PySide6.QtCore import Qt, QThread, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QTableView, QHeaderView, QLineEdit, QPushButton, QSplitter, QScrollArea,
    QFormLayout, QComboBox, QPlainTextEdit, QMessageBox, QFileDialog,
    QAbstractItemView, QFrame, QGridLayout, QDialog, QCheckBox, QTableWidget,
    QTableWidgetItem, QSizePolicy,
)

from db import MdbDatabase, MdbError, FIELD_DESC
import conventions as conv
import lcsc

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")

NAV_ADD, NAV_BROWSE = 0, 1  # 左导航行号（添加在上，浏览在下）

# 主题色板（@token 由 build_qss 替换，支持亮/暗两套）
_PALETTES = {
    "light": {
        "@win": "#f7f8fa", "@panel": "#ffffff", "@border": "#d9dee5", "@border2": "#c4cbd4",
        "@text": "#24303c", "@text2": "#5b6875", "@text3": "#8a95a1",
        "@accent": "#2563eb", "@accent_hover": "#1d4fd8", "@accent_soft": "#e8effd",
        "@header": "#f1f4f8", "@grid": "#eef1f5",
        "@navbg": "#212b38", "@navitem": "#2c3949", "@navtext": "#c6d1dd",
        "@tint_model": "#fdf9ef", "@tint_auto": "#f7fcf8",
        "@notebg": "#fdf3e3", "@noteborder": "#f2d9ac", "@notetext": "#92600a",
        "@disabled_btn": "#a8bdf0",
    },
    "dark": {
        "@win": "#1a222c", "@panel": "#222c38", "@border": "#313d4a", "@border2": "#3d4a59",
        "@text": "#dbe3ea", "@text2": "#9fb0c2", "@text3": "#6b7c8e",
        "@accent": "#3b82f6", "@accent_hover": "#60a5fa", "@accent_soft": "#233350",
        "@header": "#1f2833", "@grid": "#2a3440",
        "@navbg": "#141b24", "@navitem": "#202a36", "@navtext": "#c6d1dd",
        "@tint_model": "#2f2b1e", "@tint_auto": "#1e2b22",
        "@notebg": "#33290f", "@noteborder": "#5a4a1e", "@notetext": "#d9a441",
        "@disabled_btn": "#2c3a55",
    },
}

QSS_TEMPLATE = """
QMainWindow, QWidget { background: @win; color: @text; font-family: "Microsoft YaHei"; font-size: 12.5px; }
QListWidget#nav { background: @navbg; border: none; outline: none; padding: 10px 6px; }
QListWidget#nav::item { color: @navtext; padding: 10px 14px; border-radius: 6px; margin: 2px 4px; }
QListWidget#nav::item:hover { background: @navitem; }
QListWidget#nav::item:selected { background: @accent; color: #fff; font-weight: 600; }
QLabel#dbChip { color: @navtext; background: @navitem; border-radius: 6px; padding: 8px; font-size: 11px; }
QPushButton#themeBtn { background: transparent; color: @navtext; border: 1px solid @border2; border-radius: 5px; padding: 6px; font-weight: 400; font-size: 11.5px; }
QPushButton#themeBtn:hover { border-color: @accent; color: #fff; }
QLabel#pathChip { color: @text2; background: @panel; border: 1px solid @border; border-radius: 6px; padding: 6px 10px; font-family: Consolas; font-size: 11.5px; }
QSplitter::handle { background: @border; }
QSplitter::handle:hover { background: @accent; }
QSplitter::handle:horizontal { width: 6px; }
QSplitter::handle:vertical { height: 6px; }
QLineEdit { background: @panel; border: 1px solid @border2; border-radius: 5px; padding: 5px 8px; }
QLineEdit:focus { border-color: @accent; }
QLineEdit#editModel { background: @tint_model; }
QLineEdit#editAuto { background: @tint_auto; }
QPushButton { background: @accent; color: #fff; border: none; border-radius: 5px; padding: 7px 16px; font-weight: 600; }
QPushButton:hover { background: @accent_hover; }
QPushButton:disabled { background: @disabled_btn; }
QPushButton#ghost { background: @panel; color: @text2; border: 1px solid @border2; font-weight: 400; }
QPushButton#ghost:hover { border-color: @accent; color: @accent; }
QTreeWidget, QTableView, QPlainTextEdit { background: @panel; border: 1px solid @border; border-radius: 5px; }
QTreeWidget::item { padding: 4px; }
QTreeWidget::item:selected { background: @accent; color: #fff; }
QHeaderView::section { background: @header; color: @text2; border: none; border-bottom: 1px solid @border2; padding: 6px 8px; font-weight: 600; }
QTableView { gridline-color: @grid; selection-background-color: @accent_soft; selection-color: @text; }
QTableWidget::item { padding: 3px; }
QPlainTextEdit { font-family: Consolas; font-size: 11px; background: #232b36; color: #c9e3ff; border: 1px solid #37424f; }
QComboBox { background: @panel; border: 1px solid @border2; border-radius: 5px; padding: 5px 8px; }
QComboBox QAbstractItemView { background: @panel; color: @text; selection-background-color: @accent; }
QScrollArea { border: none; }
QLabel.k { color: @text3; font-size: 10.5px; }
QLabel.v { background: @panel; border: 1px solid @border; border-radius: 4px; padding: 3px 6px; font-family: Consolas; font-size: 11px; }
QLabel.h1 { font-size: 13px; font-weight: 600; }
QLabel#hint { color: @text3; font-size: 11px; }
QFrame#snCard, QFrame#addCard, QFrame#setCard { background: @panel; border: 1px solid @border; border-radius: 8px; }
QFrame#cardLine { background-color: @border; max-height: 1px; border: none; }
QLabel#numChip { background: @accent_soft; color: @accent; font-weight: 700; font-size: 11px; border-radius: 4px; }
QLabel#aiBadge { background: @accent_soft; color: @accent; font-weight: 600; font-size: 11px; border-radius: 10px; padding: 3px 10px; }
QLabel#modelNote { background: @notebg; color: @notetext; border: 1px solid @noteborder; border-radius: 6px; padding: 8px 11px; font-size: 11.5px; }
QStatusBar { background: @panel; color: @text3; }
"""


def build_qss(dark: bool) -> str:
    pal = _PALETTES["dark" if dark else "light"]
    qss = QSS_TEMPLATE
    for k, v in pal.items():
        qss = qss.replace(k, v)
    return qss


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            return json.load(open(SETTINGS_PATH, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_settings(s):
    try:
        json.dump(s, open(SETTINGS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


# 浏览表格仅展示的核心列（其余字段点击行后在右侧详情查看）
GRID_SHOW_COLS = [
    "Part Number",      # 内部编码
    "Component Type",   # 器件型号
    "Vendor",           # 生产商
    "Value",            # 值
    "Tolerance",        # 精度
    "Type",             # 器件具体类别
    "Description",      # 描述
]

# ================= 表格数据模型 =================
class RecordsModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.cols, self.rows, self.filter = [], [], ""
        self.view_cols = []

    def set_data(self, cols, rows):
        self.beginResetModel()
        self.cols, self.rows = cols, rows
        # 只显示核心列（保持 DB 列序）
        self.view_cols = [c for c in cols if c in GRID_SHOW_COLS]
        self.endResetModel()

    def set_filter(self, text):
        self.beginResetModel()
        self.filter = (text or "").lower()
        self.endResetModel()

    def visible_rows(self):
        if not self.filter:
            return self.rows
        return [r for r in self.rows if any(
            self.filter in str(v).lower() for v in r.values())]

    def rowCount(self, parent=QModelIndex()):
        return len(self.visible_rows())

    def columnCount(self, parent=QModelIndex()):
        return len(self.view_cols)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.visible_rows()[index.row()]
        col = self.view_cols[index.column()]
        if role == Qt.DisplayRole:
            return str(row.get(col, ""))
        return None

    def headerData(self, sec, orient, role=Qt.DisplayRole):
        if orient == Qt.Horizontal and role == Qt.DisplayRole and sec < len(self.view_cols):
            c = self.view_cols[sec]
            desc = FIELD_DESC.get(c, "")
            return f"{c}\n({desc})" if desc else c
        return None

    def raw_row(self, vis_idx):
        return self.visible_rows()[vis_idx]


# ================= SN 查询线程 =================
class FetchWorker(QThread):
    done = Signal(object)

    def __init__(self, sn):
        super().__init__()
        self.sn = sn

    def run(self):
        self.done.emit(lcsc.fetch(self.sn))


# ================= 主窗口 =================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ComponentLib 物料入库工具 v0.3")
        self.resize(1380, 820)
        self.db = None
        self.lib_root = ""
        self.tables = []
        self.workers = []
        self.field_inputs = {}  # 字段名 -> QLineEdit/QComboBox（添加页）
        self.dark = bool(load_settings().get("dark", False))  # 主题状态

        self._build_ui()
        QApplication.instance().setStyleSheet(build_qss(self.dark))
        self._update_theme_btn()
        # 启动时是否自动载入数据库（设置页可改）
        if load_settings().get("auto_load", True):
            self._connect_db()
        else:
            self.pathChip.setText("未载入 —— 请到「设置」选择数据库文件后保存")

    # ---------- UI 搭建 ----------
    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左导航（宽度可通过与页面栈之间的分割条拖拽调整）
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setMinimumWidth(150)
        self.nav.setMaximumWidth(320)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for label in ["＋  添加物料", "▤  器件库浏览", "⇪  批量导入（后续）"]:
            QListWidgetItem(label, self.nav)
        self.nav.item(2).setFlags(Qt.NoItemFlags)  # 批量导入暂未开放
        # 弹性空隙：把「设置」和主题切换推到导航底部
        spacer_item = QListWidgetItem()
        spacer_item.setFlags(Qt.NoItemFlags)
        self.nav.addItem(spacer_item)
        spacer_w = QWidget()
        # 透明背景：否则会继承全局底色，在深色导航上显成白块
        spacer_w.setStyleSheet("background: transparent;")
        spacer_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.nav.setItemWidget(spacer_item, spacer_w)
        QListWidgetItem("⚙  设置", self.nav)
        self.nav.setCurrentRow(NAV_BROWSE)
        self.nav.currentRowChanged.connect(self._on_nav)

        # 导航底部：库信息 + 主题切换
        navwrap = QWidget()
        nv = QVBoxLayout(navwrap)
        nv.setContentsMargins(0, 0, 0, 0)
        nv.setSpacing(6)
        nv.addWidget(self.nav, 1)
        self.dbChip = QLabel("未连接数据库")
        self.dbChip.setObjectName("dbChip")
        self.dbChip.setWordWrap(True)
        nv.addWidget(self.dbChip)
        self.themeBtn = QPushButton()
        self.themeBtn.setObjectName("themeBtn")
        self.themeBtn.setCursor(Qt.PointingHandCursor)
        self.themeBtn.clicked.connect(self._toggle_theme)
        nv.addWidget(self.themeBtn)

        # 右侧页面栈
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_browse_page())   # 0
        self.stack.addWidget(self._build_add_page())      # 1
        self.stack.addWidget(self._build_settings_page()) # 2
        # 导航 | 页面 用可拖拽分割条连接
        mainSplit = QSplitter(Qt.Horizontal)
        mainSplit.setHandleWidth(6)
        mainSplit.addWidget(navwrap)
        mainSplit.addWidget(self.stack)
        mainSplit.setStretchFactor(0, 0)
        mainSplit.setStretchFactor(1, 1)
        mainSplit.setChildrenCollapsible(False)
        root.addWidget(mainSplit)
        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪")

    def _build_browse_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(12, 10, 12, 8)
        v.setSpacing(8)

        top = QHBoxLayout()
        self.pathChip = QLabel("未载入")
        self.pathChip.setObjectName("pathChip")
        top.addWidget(self.pathChip)
        top.addStretch(1)
        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("筛选当前表记录…（全部字段模糊匹配）")
        self.searchEdit.setFixedWidth(260)
        self.searchEdit.textChanged.connect(self._on_search)
        top.addWidget(self.searchEdit)
        reloadBtn = QPushButton("⟳ 重新载入")
        reloadBtn.setObjectName("ghost")
        reloadBtn.setToolTip("重新打开数据库并刷新表列表与记录。\n数据库路径可在设置中修改，默认自动探测 X:\\ComponentLib\\DataBase\\ComponentLib.mdb。")
        reloadBtn.clicked.connect(self._connect_db)
        top.addWidget(reloadBtn)
        v.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(6)
        # 表树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("数据表（分类）")
        self.tree.setMinimumWidth(230)
        self.tree.currentItemChanged.connect(self._on_tree_change)
        split.addWidget(self.tree)
        # 记录表
        self.model = RecordsModel()
        self.tableView = QTableView()
        self.tableView.setModel(self.model)
        self.tableView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableView.verticalHeader().setVisible(False)
        self.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tableView.horizontalHeader().setStretchLastSection(True)
        self.tableView.clicked.connect(self._on_row_click)
        split.addWidget(self.tableView)
        # 详情栏
        self.detailArea = QScrollArea()
        self.detailArea.setWidgetResizable(True)
        self.detailArea.setMinimumWidth(270)
        self.detailPlaceholder = QLabel("点击表格行\n查看该物料的全部字段")
        self.detailPlaceholder.setAlignment(Qt.AlignCenter)
        self.detailPlaceholder.setObjectName("hint")
        self.detailArea.setWidget(self.detailPlaceholder)
        split.addWidget(self.detailArea)
        split.setSizes([230, 720, 280])
        v.addWidget(split, 1)
        return page

    def _make_card(self, num: str, title: str, hint: str = ""):
        """仿网页 Demo 的编号卡片：圆角卡 + 编号角标 + 标题 + 右侧提示（样式走主题 QSS）。"""
        card = QFrame()
        card.setObjectName("addCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        hd = QWidget()
        hh = QHBoxLayout(hd)
        hh.setContentsMargins(13, 8, 13, 8)
        numLbl = QLabel(num)
        numLbl.setObjectName("numChip")
        numLbl.setFixedSize(18, 18)
        numLbl.setAlignment(Qt.AlignCenter)
        hh.addWidget(numLbl)
        t = QLabel(title)
        t.setStyleSheet("font-weight:600; font-size:12.5px; background:transparent;")
        hh.addWidget(t)
        hh.addStretch(1)
        if hint:
            h = QLabel(hint)
            h.setObjectName("hint")
            hh.addWidget(h)
        outer.addWidget(hd)
        line = QFrame()
        line.setObjectName("cardLine")
        line.setFrameShape(QFrame.HLine)
        outer.addWidget(line)
        body = QWidget()
        bd = QVBoxLayout(body)
        bd.setContentsMargins(13, 10, 13, 10)
        bd.setSpacing(8)
        outer.addWidget(body)
        return card, bd

    def _build_add_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(12, 10, 12, 8)
        v.setSpacing(8)

        # SN 卡片（无编号，对应网页 Demo 顶部查询卡；样式走主题 QSS）
        snCard = QFrame()
        snCard.setObjectName("snCard")
        sv = QHBoxLayout(snCard)
        sv.setContentsMargins(12, 10, 12, 10)
        self.snEdit = QLineEdit()
        self.snEdit.setPlaceholderText("输入立创商城 SN（如 C25704）后回车，或直接手动录入")
        self.snEdit.setMinimumWidth(220)  # 随卡片伸缩，不写死宽度
        self.snEdit.setToolTip("立创商城商品编号，C 开头 + 数字。\n查询成功会自动带出品牌 / 值 / 精度 / 描述等字段，均可手动修改。")
        self.snEdit.returnPressed.connect(self._fetch_sn)
        sv.addWidget(self.snEdit)
        self.fetchBtn = QPushButton("查询立创数据")
        self.fetchBtn.setToolTip(
            "调用嘉立创EDA官方器件库接口（lceda.cn → easyeda.com）查询该 SN 的\n"
            "品牌、型号、值、精度、封装等数据并自动填入下方表单。\n"
            "官方库中不存在的编号会提示手动填写，不影响入库。")
        self.fetchBtn.clicked.connect(self._fetch_sn)
        sv.addWidget(self.fetchBtn)
        skipBtn = QPushButton("跳过查询，手动录入")
        skipBtn.setObjectName("ghost")
        skipBtn.setToolTip("不查询立创，直接在下方表单手动填写所有字段后入库。")
        skipBtn.clicked.connect(self._manual_mode)
        sv.addWidget(skipBtn)
        self.snStatus = QLabel("")
        self.snStatus.setObjectName("hint")
        sv.addWidget(self.snStatus, 1)
        v.addWidget(snCard)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(6)
        # 左：卡片1 目标数据表 + 卡片2 物料参数
        leftw = QWidget()
        lv = QVBoxLayout(leftw)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)

        self.aiBadge = QLabel("⚡ 已按立创分类自动匹配")
        self.aiBadge.setStyleSheet(
            "background:#e8effd; color:#2563eb; font-weight:600; font-size:11px;"
            "border-radius:10px; padding:3px 10px;")
        self.aiBadge.setVisible(False)
        card1, body1 = self._make_card("1", "目标数据表（分类）", "未选择")
        self.card1Hint = self._card_hint_label(card1)
        row1 = QHBoxLayout()
        row1.addWidget(self.aiBadge)
        self.tableCombo = QComboBox()
        self.tableCombo.currentTextChanged.connect(self._on_table_change)
        row1.addWidget(self.tableCombo, 1)
        body1.addLayout(row1)
        lv.addWidget(card1)

        card2, body2 = self._make_card("2", "物料参数（对应 DB 字段，均可手动修改）",
                                       "绿=带出 · 橙=模型 · *=必填")
        self.card2Hint = self._card_hint_label(card2)
        self.formScroll = QScrollArea()
        self.formScroll.setWidgetResizable(True)
        self.formScroll.setFrameShape(QFrame.NoFrame)
        self.formWidget = QWidget()
        self.formGrid = QGridLayout(self.formWidget)
        self.formGrid.setContentsMargins(0, 0, 0, 0)
        self.formGrid.setHorizontalSpacing(12)
        self.formGrid.setVerticalSpacing(8)
        self.formScroll.setWidget(self.formWidget)
        body2.addWidget(self.formScroll, 1)
        # 橙色模型联动提示条（对应网页 Demo 底部 banner；样式走主题 QSS）
        self.modelNote = QLabel(
            "💡 模型文件联动：Library/Footprint/PCB3D 的 Ref 与 Path 会根据目标表和封装，"
            "按仓库实际目录结构（AltiumSchLib / AltiumPcbLib / StepModel）自动建议，均可手动修改。")
        self.modelNote.setObjectName("modelNote")
        self.modelNote.setWordWrap(True)
        body2.addWidget(self.modelNote)
        lv.addWidget(card2, 1)
        split.addWidget(leftw)

        # 右：SQL 预览 + 写入按钮 + 检查清单（对应网页 Demo 右栏）
        rightw = QWidget()
        rv = QVBoxLayout(rightw)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        pvTitle = QLabel("📝 写入预览（实时 SQL）")
        pvTitle.setObjectName("h1")
        rv.addWidget(pvTitle)
        self.sqlPreview = QPlainTextEdit()
        self.sqlPreview.setReadOnly(True)
        self.sqlPreview.setPlaceholderText("输入 SN 获取信息后\n这里实时展示将写入 DB 的记录")
        rv.addWidget(self.sqlPreview, 1)
        self.addBtn = QPushButton("✔ 确认写入 ComponentLib.mdb")
        self.addBtn.setToolTip(
            "先做查重校验（mdb 中 [Component Type] 有唯一索引），\n"
            "通过后弹出 SQL 确认框再真正写入。")
        self.addBtn.setEnabled(False)
        self.addBtn.clicked.connect(self._confirm_add)
        rv.addWidget(self.addBtn)
        self.chkLabel = QLabel("")
        self.chkLabel.setObjectName("hint")
        rv.addWidget(self.chkLabel)
        split.addWidget(rightw)
        split.setSizes([820, 480])
        v.addWidget(split, 1)
        return page

    @staticmethod
    def _card_hint_label(card):
        """取卡片标题行最右侧的 hint QLabel（_make_card 中最后一个无 objectName 的 QLabel）。"""
        for lbl in card.findChildren(QLabel):
            if lbl.objectName() == "hint":
                return lbl
        return None

    # ---------- 数据库连接 ----------
    def _connect_db(self):
        s = load_settings()
        candidates = [s.get("db_path"),
                      r"X:\ComponentLib\DataBase\ComponentLib.mdb",
                      os.path.join(APP_DIR, "..", "test-lib", "ComponentLib.mdb")]
        path = None
        for c in candidates:
            if c and os.path.exists(c):
                path = os.path.normpath(os.path.abspath(c))  # 规范化，消除 \app\.. 之类的段
                break
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择 ComponentLib.mdb", "", "Access 数据库 (*.mdb *.accdb)")
            if not path:
                self.statusBar().showMessage("未选择数据库，请通过 ⟳ 重新载入 指定")
                return
            path = os.path.normpath(os.path.abspath(path))
        try:
            if self.db:
                self.db.close()
            self.db = MdbDatabase(path)
            self.lib_root = os.path.dirname(path)
            s["db_path"] = path
            save_settings(s)
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法打开数据库：\n{e}")
            return
        self.tables = self.db.get_tables()
        counts = {}
        for t in self.tables:
            try:
                counts[t] = self.db.count(t)
            except Exception:
                counts[t] = -1
        total = sum(n for n in counts.values() if n >= 0)
        self._fill_tree(counts)
        self._fill_table_combo()
        # 显示时缩短路径：完整路径放 tooltip
        short = self._short_path(path)
        self.pathChip.setText(short + f"    ｜  {len(self.tables)} 张表 · {total} 条记录")
        self.pathChip.setToolTip(path)
        self.dbChip.setText(f"● 已载入\n{short}\n{len(self.tables)} 张表 · {total} 条")
        self.dbChip.setToolTip(path)
        self.statusBar().showMessage(f"已载入 {path}（{total} 条记录）")
        # 默认选中第一张有数据的表
        for t in self.tables:
            if counts.get(t, 0) > 0:
                self._select_table(t)
                break

    @staticmethod
    def _short_path(path: str, max_len: int = 42) -> str:
        """路径过长时省略中段，避免左下角信息卡换行难看。"""
        if len(path) <= max_len:
            return path
        head, tail = path[:14], path[-(max_len - 17):]
        return head + "…" + tail

    def _fill_tree(self, counts):
        self.tree.blockSignals(True)
        self.tree.clear()
        groups = {}
        for t in self.tables:
            grp = t.split("-")[0] if not t.startswith("ICs") else "ICs"
            if t.startswith("ICs"):
                grp = "IC"
            elif t.startswith("Capacitors"):
                grp = "电容"
            elif t.startswith("Resistors"):
                grp = "电阻"
            elif t.startswith("Connectors"):
                grp = "连接器"
            elif t.startswith("Transistors"):
                grp = "三极管"
            elif t.startswith("Oscillators"):
                grp = "时钟"
            elif t.startswith("Modules"):
                grp = "模组"
            else:
                grp = "其他"
            groups.setdefault(grp, []).append(t)
        for grp in ["电阻", "电容", "IC", "连接器", "三极管", "时钟", "模组", "其他"]:
            if grp not in groups:
                continue
            top = QTreeWidgetItem([grp])
            top.setFlags(top.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(top)
            for t in groups[grp]:
                n = counts.get(t, -1)
                it = QTreeWidgetItem([f"{t}    ({n})" if n >= 0 else t])
                it.setData(0, Qt.UserRole, t)
                top.addChild(it)
            top.setExpanded(True)
        self.tree.blockSignals(False)

    def _fill_table_combo(self):
        self.tableCombo.blockSignals(True)
        self.tableCombo.clear()
        self.tableCombo.addItems(self.tables)
        self.tableCombo.blockSignals(False)

    # ---------- 浏览页 ----------
    def _select_table(self, t):
        items = self.tree.findItems(t, Qt.MatchRecursive | Qt.MatchContains)
        for it in items:
            if it.data(0, Qt.UserRole) == t:
                self.tree.setCurrentItem(it)
                return
        # 兜底：直接加载
        self._load_table(t)

    def _on_tree_change(self, cur, prev):
        if cur and cur.data(0, Qt.UserRole):
            self._load_table(cur.data(0, Qt.UserRole))

    def _load_table(self, t):
        try:
            cols, rows = self.db.read_table(t, self.searchEdit.text().strip())
            self.model.set_data(cols, rows)
            self.statusBar().showMessage(f"[{t}] {len(rows)} 条记录")
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"[{t}]\n{e}")

    def _on_search(self, text):
        self.model.set_filter(text)

    def _on_row_click(self, index):
        row = self.model.raw_row(index.row())
        table = None
        it = self.tree.currentItem()
        if it:
            table = it.data(0, Qt.UserRole)
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        title = QLabel(f"📋 {table or ''} · 记录详情")
        title.setObjectName("h1")
        v.addWidget(title)
        # 两列表格：字段 | 值
        tw = QTableWidget(len(self.model.cols), 2)
        tw.setHorizontalHeaderLabels(["字段", "值"])
        tw.verticalHeader().setVisible(False)
        tw.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tw.setSelectionMode(QAbstractItemView.NoSelection)
        for i, c in enumerate(self.model.cols):
            name_item = QTableWidgetItem(c + (f"（{FIELD_DESC[c]}）" if c in FIELD_DESC else ""))
            name_item.setToolTip(c)
            val_item = QTableWidgetItem(str(row.get(c, "")) or "")
            val_item.setToolTip(str(row.get(c, "")))
            tw.setItem(i, 0, name_item)
            tw.setItem(i, 1, val_item)
        tw.setColumnWidth(0, 148)
        tw.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        v.addWidget(tw, 1)
        self.detailArea.setWidget(w)

    # ---------- 添加页 ----------
    def _on_nav(self, idx):
        mapping = {NAV_BROWSE: 0, NAV_ADD: 1, 3: 2}  # 导航行 → 页面栈
        if idx in mapping:
            self.stack.setCurrentIndex(mapping[idx])
            if idx == NAV_ADD:
                self._rebuild_form()
            elif idx == 3:
                self._load_settings_page()

    # ---------- 主题切换 ----------
    def _toggle_theme(self):
        self.dark = not self.dark
        QApplication.instance().setStyleSheet(build_qss(self.dark))
        s = load_settings()
        s["dark"] = self.dark
        save_settings(s)
        self._update_theme_btn()
        self.statusBar().showMessage("已切换到" + ("深色模式" if self.dark else "浅色模式"), 3000)

    def _update_theme_btn(self):
        self.themeBtn.setText("☀ 切换浅色模式" if self.dark else "🌙 切换深色模式")

    # ---------- 设置页 ----------
    def _build_settings_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(16, 14, 16, 10)
        v.setSpacing(10)
        title = QLabel("⚙ 设置")
        title.setObjectName("h1")
        v.addWidget(title)

        card = QFrame()
        card.setObjectName("setCard")
        f = QVBoxLayout(card)
        f.setContentsMargins(16, 14, 16, 14)
        f.setSpacing(10)

        l1 = QLabel("器件库文件（ComponentLib.mdb）")
        l1.setObjectName("h1")
        f.addWidget(l1)
        row = QHBoxLayout()
        self.dbPathEdit = QLineEdit()
        self.dbPathEdit.setPlaceholderText(r"例如 X:\ComponentLib\DataBase\ComponentLib.mdb")
        row.addWidget(self.dbPathEdit, 1)
        browseBtn = QPushButton("浏览…")
        browseBtn.setObjectName("ghost")
        browseBtn.clicked.connect(self._browse_db_path)
        row.addWidget(browseBtn)
        f.addLayout(row)
        self.libRootHint = QLabel("库根目录（模型路径建议用）= mdb 所在目录")
        self.libRootHint.setObjectName("hint")
        f.addWidget(self.libRootHint)

        line = QFrame()
        line.setObjectName("cardLine")
        line.setFrameShape(QFrame.HLine)
        f.addWidget(line)

        self.autoLoadCheck = QCheckBox("进入软件时自动载入数据库并刷新浏览数据")
        self.autoLoadCheck.setChecked(True)
        f.addWidget(self.autoLoadCheck)
        self.backupCheck = QCheckBox("写入前自动备份数据库（按天，存入库目录 backups\\ 下）")
        self.backupCheck.setChecked(True)
        self.backupCheck.setToolTip(
            ".mdb 是二进制文件，写入不可撤销。开启后每天首次写入前\n"
            "会把整库复制一份到 mdb 所在目录的 backups\\ 文件夹。")
        f.addWidget(self.backupCheck)

        saveBtn = QPushButton("保存并立即重新载入")
        saveBtn.clicked.connect(self._save_settings)
        f.addWidget(saveBtn)
        v.addWidget(card)
        v.addStretch(1)
        return page

    def _load_settings_page(self):
        s = load_settings()
        cur = self.dbPathEdit.text().strip()
        if not cur:
            self.dbPathEdit.setText(s.get("db_path") or (self.db.path if self.db else ""))
        self.autoLoadCheck.setChecked(s.get("auto_load", True))
        self.backupCheck.setChecked(s.get("backup_write", True))
        if self.db:
            self.libRootHint.setText(f"库根目录（模型路径建议用）= {self.lib_root}")

    def _browse_db_path(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 ComponentLib.mdb", self.dbPathEdit.text() or "",
            "Access 数据库 (*.mdb *.accdb)")
        if path:
            self.dbPathEdit.setText(os.path.normpath(os.path.abspath(path)))
            self.libRootHint.setText(
                f"库根目录（模型路径建议用）= {os.path.dirname(self.dbPathEdit.text())}")

    def _save_settings(self):
        s = load_settings()
        p = self.dbPathEdit.text().strip()
        if p:
            p = os.path.normpath(os.path.abspath(p))
            if not os.path.exists(p):
                QMessageBox.warning(self, "路径无效", f"文件不存在：\n{p}")
                return
            s["db_path"] = p
        s["auto_load"] = self.autoLoadCheck.isChecked()
        s["backup_write"] = self.backupCheck.isChecked()
        save_settings(s)
        self._connect_db()
        QMessageBox.information(self, "设置已保存",
                                f"已按新设置重新载入数据库：\n{self.db.path if self.db else '(未变更)'}")

    def _rebuild_form(self):
        """按当前表的字段动态重建三列网格表单（销毁旧 widget 重建）。"""
        table = self.tableCombo.currentText()
        old = self.formScroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.formWidget = QWidget()
        self.formGrid = QGridLayout(self.formWidget)
        self.formGrid.setContentsMargins(0, 0, 0, 0)
        self.formGrid.setHorizontalSpacing(12)
        self.formGrid.setVerticalSpacing(8)
        self.field_inputs = {}
        if not table or not self.db:
            self.formScroll.setWidget(self.formWidget)
            return
        cols = self.db.get_columns(table)
        row, col = 0, 0
        for c in cols:
            desc = FIELD_DESC.get(c, "")
            # 富文本标签：字段名 + 中文说明 + 角标（对应网页 Demo 的 带出/模型 徽章）
            badges = ""
            if c in conv.REQUIRED_KEYS:
                badges += ' <span style="color:#dc2626;font-weight:bold;">*</span>'
            if c in conv.MODEL_KEYS:
                badges += (' <span style="background-color:#fdf3e3;color:#d97706;'
                           'font-size:9px;">模型</span>')
            elif c in conv.LCSC_AUTOFILL_KEYS:
                badges += (' <span style="background-color:#e7f6ec;color:#16a34a;'
                           'font-size:9px;">带出</span>')
            name_html = c + (f' <span style="color:#8a95a1;font-size:10px;">({desc})</span>'
                             if desc else "")
            lbl = QLabel(f"{name_html}{badges}")
            lbl.setTextFormat(Qt.RichText)
            # 控件：具体类别用可编辑下拉（带出该表已有值），其余用输入框
            if c == "Type":
                combo = QComboBox()
                combo.setEditable(True)
                combo.setInsertPolicy(QComboBox.NoInsert)
                existing = self.db.distinct_values(table, c)
                combo.addItem("")  # 允许留空
                combo.addItems(existing)
                combo.setToolTip(
                    f"[{table}] 表中已有的 {len(existing)} 个具体类别，下拉选择；\n"
                    "也可直接输入新类别（入库后即可供下次下拉选择）。")
                combo.editTextChanged.connect(self._on_field_change)
                edit = combo
            else:
                line = QLineEdit()
                if c == "LatestRevisionDate":
                    line.setText(datetime.date.today().isoformat())  # 修改日期=写入当天，可改
                if c in conv.MODEL_KEYS:
                    line.setObjectName("editModel")   # 着色走主题 QSS（亮/暗自适应）
                elif c in conv.LCSC_AUTOFILL_KEYS:
                    line.setObjectName("editAuto")
                line.textChanged.connect(self._on_field_change)
                edit = line
            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)
            cl.addWidget(lbl)
            cl.addWidget(edit)
            self.field_inputs[c] = edit
            # 长文本字段独占一行（对应网页 Demo 的 full 样式）
            span = 3 if c in ("Description", "ComponentLink2URL") else 1
            if col + span > 3:
                row += 1
                col = 0
            self.formGrid.addWidget(cell, row, col, 1, span)
            if span == 3:
                row += 1
                col = 0
            else:
                col += 1
        self.formScroll.setWidget(self.formWidget)

    def _on_table_change(self):
        # 手动换表时取消"自动匹配"角标（查询流程随后会重新点亮）
        self.aiBadge.setVisible(False)
        if self.card1Hint:
            self.card1Hint.setText("手动选择")
        self._rebuild_form()
        self._update_preview()

    def _fetch_sn(self):
        sn = self.snEdit.text().strip().upper()
        if not sn:
            QMessageBox.information(self, "提示", "请输入立创商城 SN")
            return
        self.fetchBtn.setEnabled(False)
        self.snStatus.setText("查询中…（多通道尝试）")
        w = FetchWorker(sn)
        w.done.connect(self._on_fetch_done)
        self.workers.append(w)
        w.start()

    def _on_fetch_done(self, res):
        self.fetchBtn.setEnabled(True)
        if res.ok:
            self.snStatus.setStyleSheet("color:#16a34a; font-weight:600;")
            self.snStatus.setText(
                f"✓ 已带出 {len(res.data)} 个字段（来源：{res.source}）"
                + (f" ｜ 建议表：{res.suggest_table}" if res.suggest_table else ""))
            self.snStatus.setToolTip("\n".join(res.logs))
            # 自动匹配表（优先官方 tags 匹配，其次关键词猜测）
            t = res.suggest_table or self._guess_table(res)
            if t:
                self.tableCombo.setCurrentText(t)
                self.aiBadge.setVisible(True)
                if self.card1Hint:
                    self.card1Hint.setText(f"立创分类 → {t}")
            # 填充字段
            for k, v in res.data.items():
                if k in self.field_inputs:
                    el = self.field_inputs[k]
                    if isinstance(el, QComboBox):
                        el.setCurrentText(str(v))
                    else:
                        el.setText(str(v))
            # 模型字段建议
            self._suggest_model_fields(res, res.data.get("Component Type", ""))
            # 内部编码建议
            if "Part Number" in self.field_inputs and not self.field_inputs["Part Number"].text():
                self.field_inputs["Part Number"].setText(
                    conv.suggest_part_number(self.tableCombo.currentText(),
                                             res.data.get("Component Type", ""), res.pkg_family))
        else:
            self.snStatus.setStyleSheet("color:#dc2626;")
            self.snStatus.setText("✗ 未查到（官方库无此编号或网络失败），可手动填写 —— 鼠标悬停本提示查看详情")
            self.snStatus.setToolTip(f"SN: {res.sn}\n\n" + "\n".join(res.logs))
            self.aiBadge.setVisible(False)
            if self.card1Hint:
                self.card1Hint.setText("未匹配")

    def _guess_table(self, res):
        """按封装 + 描述关键词猜目标表。"""
        pkg = (res.package or "").upper()
        desc = (res.data.get("Description", "") + res.data.get("Type", "")).upper()
        if "TYPE-C" in pkg or "USB" in pkg:
            return "Connectors-USB Connectors"
        if any(k in desc for k in ["电阻", "RESISTOR"]):
            return "Resistors"
        if any(k in desc for k in ["电容", "CAPACIT", "MLCC"]):
            return "Capacitors"
        if "LDO" in desc or "稳压" in desc or "REGULATOR" in desc:
            return "ICs-Power"
        if "MOSFET" in desc:
            return "Transistors-MOSFETs"
        if "二极管" in desc or "SCHOTTKY" in desc or "DIODE" in desc:
            return "Diodes"
        if "晶振" in desc or "CRYSTAL" in desc:
            return "Oscillators-Crystals"
        if "磁珠" in desc or "BEAD" in desc:
            return "Beads"
        return ""

    def _suggest_model_fields(self, res, mpn):
        table = self.tableCombo.currentText()
        pkg = res.pkg_family or res.package
        sug = conv.suggest_library_fields(table, pkg, self.lib_root)
        for k, v in sug.items():
            if k not in self.field_inputs:
                continue
            cur = self.field_inputs[k].text()
            if not cur:
                self.field_inputs[k].setText(v)
        # IC 类约定 Library Ref = 器件型号
        if table.startswith("ICs") and "Library Ref" in self.field_inputs \
                and not self.field_inputs["Library Ref"].text() and mpn:
            self.field_inputs["Library Ref"].setText(mpn)

    def _manual_mode(self):
        self.snStatus.setText("手动录入模式")
        self._rebuild_form()
        self._update_preview()

    def _on_field_change(self):
        self._update_preview()

    def _collect_fields(self):
        out = {}
        for k, e in self.field_inputs.items():
            if isinstance(e, QComboBox):
                out[k] = e.currentText().strip()
            else:
                out[k] = e.text().strip()
        return out

    def _update_preview(self):
        table = self.tableCombo.currentText()
        if not table or not self.db or not self.field_inputs:
            self.sqlPreview.setPlainText("")
            self._update_checks(None)
            return
        data = self._collect_fields()
        cols = self.db.get_columns(table)
        self.sqlPreview.setPlainText(conv.build_sql_preview(table, cols, data))
        self._update_checks(data)

    def _update_checks(self, data):
        if not data:
            self.chkLabel.setText("✗ 未选择目标表")
            self.addBtn.setEnabled(False)
            return
        missing = [k for k in conv.REQUIRED_KEYS if not data.get(k)]
        table = self.tableCombo.currentText()
        # 查重
        dup = None
        try:
            dup = self.db.check_duplicate(table, data)
        except Exception:
            pass
        parts = []
        if missing:
            parts.append("✗ 缺必填: " + ", ".join(missing))
        else:
            parts.append("✓ 必填齐全")
        if dup:
            parts.append("✗ " + dup)
        else:
            parts.append("✓ 无重复")
        self.chkLabel.setText("    ｜    ".join(parts))
        self.addBtn.setEnabled(not missing and not dup)

    def _confirm_add(self):
        table = self.tableCombo.currentText()
        data = self._collect_fields()
        dup = self.db.check_duplicate(table, data)
        if dup:
            QMessageBox.warning(self, "查重拦截", dup)
            return
        sql = conv.build_sql_preview(table, self.db.get_columns(table), data)
        ret = QMessageBox.question(
            self, "确认写入",
            f"将向 [{table}] 写入 1 条记录：\n\n{sql[:600]}\n\n确认写入？",
            QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        # 写入前按天备份（设置页可关）
        backup_note = ""
        if load_settings().get("backup_write", True):
            try:
                bk = self.db.backup_daily()
                backup_note = f"\n已自动备份: {bk}" if bk else ""
            except Exception:
                backup_note = "\n（自动备份失败，本次写入继续）"
        try:
            self.db.insert(table, data)
        except MdbError as e:
            QMessageBox.critical(self, "写入失败", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "写入失败", f"{type(e).__name__}\n{e}")
            return
        QMessageBox.information(self, "写入成功",
                                f"已写入 [{table}]\n器件型号: {data.get('Component Type')}{backup_note}")
        self.nav.setCurrentRow(NAV_BROWSE)
        self._select_table(table)
        self.snEdit.clear()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
