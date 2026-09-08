# -*- coding: utf-8 -*-
"""测试 GUI 能创建并销毁，无导入/布局错误。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama\gui")
try:
    drama_gui = __import__("drama_gui")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("GUI_IMPORT_FAIL", e)
    sys.exit(1)

# 用 after 1ms 自动关闭，避免阻塞
import tkinter as tk
app = drama_gui.DramaGUI()
app.after(1500, app.destroy)
app.mainloop()
print("GUI_OK window created and closed cleanly")
