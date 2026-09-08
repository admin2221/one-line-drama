# -*- coding: utf-8 -*-
"""测试安装向导能创建并销毁。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama\deploy")
try:
    import drama_setup
except Exception as e:
    import traceback
    traceback.print_exc()
    print("SETUP_IMPORT_FAIL", e)
    sys.exit(1)

app = drama_setup.SetupWizard()
app.after(1200, app.destroy)
app.mainloop()
print("SETUP_OK")
