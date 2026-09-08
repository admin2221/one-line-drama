# -*- coding: utf-8 -*-
"""用 WMI Win32_Process.Create 启动进程（独立于调用方 Job）。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
try:
    import win32com.client
except ImportError:
    print("NO_WIN32COM")
    sys.exit(0)

cmdline = sys.argv[1] if len(sys.argv) > 1 else None
if not cmdline:
    print("usage: launch_wmi.py <cmdline>")
    sys.exit(1)

wmi = win32com.client.Dispatch("WbemScripting.SWbemLocator")
service = wmi.ConnectServer(".", "root\\cimv2")
proc = service.Get("Win32_Process")
r = proc.Create(cmdline, None, None, 0)
print("Create return:", r[0], "PID:", r[1])
