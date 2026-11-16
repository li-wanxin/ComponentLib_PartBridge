# ComponentLib 维护平台

Altium / Cadence 通用器件库维护工具 —— 让「查立创 SN → 字段带出 → 分类匹配 → 入库 → 规格书 / 3D 模型落盘」一键完成。

面向维护 [`ComponentLib.mdb`](https://github.com/li-wanxin/ComponentLib)（Access 器件库，40 张业务表 / 18 标准字段）的电子工程师，Windows 桌面应用，界面架构移植自 lab-console（HTML/CSS + pywebview）。

## ✨ 功能特性

### 器件库浏览
- 40 张分类表一目了然（含记录数），全字段模糊搜索
- 点击行查看记录详情，分组展示全部字段
- **信息完整度检测**：进度条 + 分条检查（必填项 / 模型字段 / 规格书路径）
- 记录编辑：同表已有值下拉选择，修改日期自动更新

### 添加物料（核心工作流）
1. 输入立创商城 SN（如 `C25704`）
2. 自动带出 12 个字段：器件型号 / 生产商 / 值 / 精度 / 描述 / 供应商 / 规格书链接等
3. 分类自动匹配 DB 表（立创 tags → 表名，可下拉修改 / ＋新增分类）
4. 模型字段按仓库约定自动建议（`AltiumSchLib/`、`AltiumPcbLib/`、`StepModel/`）
5. 确认写入 → 检测结果面板实时校验（必填 / 重复 / 完整度）

### 规格书自动落盘
- 立创商品页直链下载，或「替代文件」本地 PDF 复制更名
- 目标路径遵循仓库约定：`DataSheet/<表名前缀>/<器件型号>.pdf`，已存在保留原文件

### 3D 模型自动下载
- 从立创官方库解析封装的 STEP 模型编号，双镜像直链下载（含 `ISO-10303-21` 文件头校验）
- 落盘 `StepModel/<封装>.STEP`；PCB3D Path 行实时显示「✓ 已存在」状态

## 🏗️ 架构

```
ComponentLibCreat/
├── run.bat              # 启动入口
├── app/
│   ├── desktop.py       # pywebview 原生窗口（WebView2）+ 文件对话框等原生能力
│   ├── server.py        # 本机 HTTP 服务（stdlib ThreadingHTTPServer + JSON API）
│   ├── lcsc.py          # 立创商城查询客户端（官方器件库 / 商品页 / 3D 模型解析）
│   ├── db.py            # pyodbc + ACE ODBC 直连 .mdb（查重 / 插入 / 更新 / 每日备份）
│   ├── conventions.py   # 库目录约定（路径建议、内部编码、分类映射）
│   └── web/             # 前端（index.html + style.css + app.js，双主题 @token 设计）
├── Docs/开发文档.md     # 详细开发文档 + 库文件生态调研
└── test-lib/            # 测试用 mdb
```

数据接口（嘉立创 EDA 官方库，与 LCSC3D 同源）：

| 用途 | 端点 |
|---|---|
| 器件数据（字段 + 封装 + 3D） | `lceda.cn/api/products/{SN}/components` |
| 商品详情（描述 / 规格书直链） | `wmsc.lcsc.com/ftps/wm/product/detail?productCode={SN}` |
| 3D STEP 直链 | `modules.lceda.cn/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}` |

## 🚀 快速开始

```bash
# 依赖：Windows 10/11 + Python 3.x + Access ODBC 驱动 + pywebview
pip install pywebview
run.bat
```

启动后右上角可切换亮 / 暗主题；首次使用在「设置」中选择 `ComponentLib.mdb` 路径（默认尝试 `X:\ComponentLib\DataBase\`）。

## 📚 延伸调研

详见 [`Docs/开发文档.md`](Docs/开发文档.md)：

- **Altium SchLib / PcbLib 读写**：OLE 复合文档格式，参考 [LCSC3D](https://github.com/Travelerrrrrr/LCSC3D)（`library_merge.py` 支持向现有库增量追加元件）与 [AltiumSharp](https://github.com/issus/AltiumSharp)
- **Cadence OLB / DRA / PSM**：只读解析参考 [OpenOrCadParser](https://github.com/Werni2A/OpenOrCadParser) / [OpenAllegroParser](https://github.com/Werni2A/OpenAllegroParser)；写回走官方 Tcl/SKILL
- **封装自动生成**：IPC-7351B 方程（[LandForge](https://github.com/andax/landforge)）+ Allegro SKILL 脚本（`axlPadStackCreate` / `axlDBCreatePin` / `axlDBCreateLine`）

## 📄 许可

内部工具，随 ComponentLib 仓库分发。
