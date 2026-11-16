# -*- coding: utf-8 -*-
"""ComponentLib 物料入库工具入口"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui_main import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ComponentLib 物料入库工具")
    f = QFont("Microsoft YaHei", 10)
    app.setFont(f)
    win = MainWindow()  # 主题样式由 MainWindow 按设置（亮/暗）应用
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
