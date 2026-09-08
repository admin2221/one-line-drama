# -*- coding: utf-8 -*-
"""短剧生成器 · 安装向导（tkinter 分步安装）。

运行方式：把本 exe 与 InstallFiles 文件夹放在同一目录发布。
InstallFiles 内含：drama-gui.exe、drama-cli.exe、drama_icon.png、使用说明.txt

安装流程：
  欢迎 → 选择安装目录 → 复制文件 + 快捷方式 → 完成
"""
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

APP_NAME = "短剧生成器"
SRC_DIR_NAME = "InstallFiles"


def here():
    """定位本程序目录。PyInstaller onefile 下 __file__ 指向临时解压目录，
    必须用 sys.executable 所在目录（即与 InstallFiles 同目录的发布位置）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def default_install_dir():
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(base, "Programs", APP_NAME)


class SetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} · 安装向导")
        self.geometry("620x430")
        self.resizable(False, False)
        self.src_dir = os.path.join(here(), SRC_DIR_NAME)
        self.install_dir = tk.StringVar(value=default_install_dir())
        self.ico = os.path.join(here(), "drama_icon.png")
        self.desktop_sc = tk.BooleanVar(value=True)

        try:
            if os.path.isfile(self.ico):
                self.iconphoto(False, tk.PhotoImage(file=self.ico))
        except Exception:
            pass

        self._intro = tk.Frame(self); self._steps = tk.Frame(self)
        self._intro.pack(fill="both", expand=True)

        self._build_intro()
        self._cur = self._intro

    # ---------- 欢迎页 ----------
    def _build_intro(self):
        for w in self._intro.winfo_children():
            w.destroy()
        tk.Label(self._intro, text=f"{APP_NAME} · 安装向导", font=("Microsoft YaHei", 18, "bold"),
                 fg="#1565c0").pack(pady=(26, 6))
        tk.Label(self._intro, text="一键生成完整竖屏短剧 · 图形界面 + 命令行引擎",
                 font=("Microsoft YaHei", 11)).pack()
        info = ("本安装程序将把以下内容安装到您的电脑：\n\n"
                "  ▸ drama-gui.exe  图形界面（推荐使用）\n"
                "  ▸ drama-cli.exe  独立引擎（命令行/高级）\n"
                "  ▸ 使用说明.txt    操作手册\n\n"
                "运行前提：本机已启动 ComfyUI（127.0.0.1:8188）")
        tk.Label(self._intro, text=info, justify="left", fg="#333",
                 font=("Microsoft YaHei", 10)).pack(pady=18, padx=40)
        if not os.path.isdir(self.src_dir):
            tk.Label(self._intro, text="⚠ 未找到 InstallFiles 文件夹，请将本程序与它放在同一目录",
                     fg="#c62828").pack()
        tk.Button(self._intro, text="下一步 >", command=self._go_dir, width=14,
                  bg="#2e7d32", fg="white").pack(pady=10)

    # ---------- 选择安装目录 ----------
    def _go_dir(self):
        self._intro.pack_forget()
        self._steps.pack(fill="both", expand=True)
        for w in self._steps.winfo_children():
            w.destroy()
        tk.Label(self._steps, text="选择安装目录", font=("Microsoft YaHei", 14, "bold")).pack(pady=(22, 8))
        tk.Label(self._steps, text="安装位置（所有程序文件将复制到此目录）",
                 font=("Microsoft YaHei", 10), fg="#555").pack()
        row = tk.Frame(self._steps); row.pack(pady=14, padx=30, fill="x")
        self.dir_entry = tk.Entry(self._steps, textvariable=self.install_dir, width=50)
        self.dir_entry.pack(side="left", padx=(30, 6), fill="x", expand=True)
        tk.Button(self._steps, text="浏览…", command=self._browse).pack(side="left", padx=(0, 30))
        tk.Checkbutton(self._steps, text="在桌面创建启动快捷方式", variable=self.desktop_sc,
                       font=("Microsoft YaHei", 10)).pack(anchor="w", padx=40, pady=6)
        btns = tk.Frame(self._steps); btns.pack(pady=24)
        tk.Button(btns, text="< 上一步", command=self._back_intro, width=12).pack(side="left", padx=8)
        tk.Button(btns, text="开始安装 ▶", command=self._install, width=14,
                  bg="#2e7d32", fg="white").pack(side="left", padx=8)

    def _browse(self):
        d = filedialog.askdirectory()
        if d:
            self.install_dir.set(d)
            self.dir_entry.xview("end")

    def _back_intro(self):
        self._steps.pack_forget()
        self._intro.pack(fill="both", expand=True)
        self._build_intro()

    # ---------- 安装 ----------
    def _install(self):
        dest = self.install_dir.get().strip().rstrip("\\/")
        if not dest:
            messagebox.showwarning("提示", "请选择安装目录")
            return
        if not os.path.isdir(self.src_dir):
            messagebox.showerror("错误", "未找到 InstallFiles 文件夹")
            return
        # 确认目录
        if os.path.exists(dest) and os.listdir(dest):
            if not messagebox.askyesno("确认", f"目录已存在且有内容：\n{dest}\n\n仍要继续安装（覆盖）吗？"):
                return

        os.makedirs(dest, exist_ok=True)

        # 复制文件到临时目录展示进度
        prog = tk.Toplevel(self); prog.title("正在安装…"); prog.geometry("380x120")
        prog.transient(self)
        tk.Label(prog, text="正在复制文件…", font=("Microsoft YaHei", 11)).pack(pady=12)
        bar = tk.Label(prog, text="", fg="#2e7d32", font=("Consolas", 9))
        bar.pack()
        self.update_idletasks()

        try:
            files = [f for f in os.listdir(self.src_dir)
                     if os.path.isfile(os.path.join(self.src_dir, f))]
            total = len(files)
            for i, f in enumerate(files, 1):
                shutil.copy2(os.path.join(self.src_dir, f), os.path.join(dest, f))
                bar["text"] = f"[{i}/{total}] 复制 {f}"
                self.update()
            # 写版本信息
            self._write_uninstall(dest)
            # 快捷方式
            self._make_shortcuts(dest)
        except Exception as e:
            prog.destroy()
            messagebox.showerror("错误", f"安装失败：{e}")
            return
        prog.destroy()

        # 完成页
        for w in self._steps.winfo_children():
            w.destroy()
        self._finish_view(dest)

    def _write_uninstall(self, dest):
        lines = [f"{APP_NAME} 已完成安装。", f"安装目录: {dest}", "",
                 "卸载方法：直接删除该文件夹，并移除开始菜单/桌面的快捷方式即可。"]
        try:
            with open(os.path.join(dest, "卸载说明.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception:
            pass

    def _make_shortcuts(self, dest):
        gui = os.path.join(dest, "drama-gui.exe")
        if not os.path.isfile(gui):
            return
        # 开始菜单
        sm = os.path.join(os.environ.get("APPDATA", dest), "Microsoft", "Windows",
                          "Start Menu", "Programs", f"{APP_NAME}.lnk")
        self._run_ps_create(gui, dest, sm)
        # 桌面
        if self.desktop_sc.get():
            desk = os.path.join(os.environ.get("USERPROFILE", dest), "Desktop",
                                f"{APP_NAME}.lnk")
            self._run_ps_create(gui, dest, desk)

    def _run_ps_create(self, target, workdir, lnk_path):
        lnk_path = lnk_path.replace("'", "''")
        target = target.replace("'", "''")
        workdir = workdir.replace("'", "''")
        ps = (f"$s=New-Object -ComObject WScript.Shell;"
              f"$l=$s.CreateShortcut('{lnk_path}');"
              f"$l.TargetPath='{target}';$l.WorkingDirectory='{workdir}';"
              f"$l.Description='{APP_NAME}';$l.Save()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=30)
        except Exception:
            pass

    def _finish_view(self, dest):
        tk.Label(self._steps, text="安装完成！", font=("Microsoft YaHei", 16, "bold"),
                 fg="#2e7d32").pack(pady=(26, 10))
        tk.Label(self._steps, text=f"{APP_NAME} 已安装到：\n{dest}",
                 justify="left", font=("Microsoft YaHei", 10)).pack(pady=8)
        tk.Label(self._steps, text="提示：生成前请先启动 ComfyUI（127.0.0.1:8188）",
                 fg="#555", font=("Microsoft YaHei", 9)).pack()
        btns = tk.Frame(self._steps); btns.pack(pady=22)
        def launch():
            gui = os.path.join(dest, "drama-gui.exe")
            if os.path.isfile(gui):
                subprocess.Popen([gui])
            self.destroy()
        tk.Button(btns, text="立即运行 ▶", command=launch, width=14,
                  bg="#2e7d32", fg="white").pack(side="left", padx=8)
        tk.Button(btns, text="关闭", command=self.destroy, width=10).pack(side="left", padx=8)


def _psq(p):
    return p.replace("'", "''")


if __name__ == "__main__":
    try:
        SetupWizard().mainloop()
    except Exception:
        import traceback
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "setup_crash.log"), "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise
