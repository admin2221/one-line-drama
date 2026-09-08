# -*- coding: utf-8 -*-
"""任务状态持久化（意外中断保留 / 继续任务）。

每个任务（输出目录）内保存 task_state.json：
  {
    "version": 1,
    "done": false,               # 成片成功产出后置 true
    "phase": "shots",            # script/refs/images_ready/shots/concat/done
    "title": "剧名", "total_shots": 12, "done_shots": 5,
    "pid": 12345,                # 最近一次写入状态的引擎进程（用于判断任务是否正在运行）
    "created_at": "...", "updated_at": "...",
    "params": {...}              # 引擎参数快照，继续任务时据此还原命令行
  }

本模块只依赖标准库，供 GUI / CLI（drama_factory）双方使用：
- 引擎在任务推进/每镜完成时写状态（done=false），成功成片后置 done=true；
- GUI 扫描输出目录中 done != true 的任务，提供「继续任务」一键续跑；
- 进程被杀/崩溃/断电后状态仍在磁盘上，随时可继续。
"""
import json
import os
import time

STATE_FILE = "task_state.json"

# 阶段 → 中文名（GUI 展示用）
PHASE_NAMES = {
    "script": "写剧本",
    "refs": "生成参考图",
    "images_ready": "参考图已生成",
    "shots": "生成镜头视频",
    "concat": "拼接成片",
    "done": "已完成",
}


def state_path(output_dir):
    return os.path.join(output_dir, STATE_FILE)


def load(output_dir):
    """读取任务状态；不存在/损坏返回 None。"""
    try:
        with open(state_path(output_dir), "r", encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else None
    except Exception:
        return None


def save(output_dir, **kw):
    """合并写入任务状态（原子替换，尽量不因写状态本身失败影响主流程）。"""
    st = load(output_dir) or {"version": 1}
    st.update(kw)
    st.setdefault("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    st["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    st["pid"] = os.getpid()
    tmp = state_path(output_dir) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
        os.replace(tmp, state_path(output_dir))
    except Exception:
        pass
    return st


def pid_alive(pid):
    """判断进程是否真正存活（排除已退出的残留句柄对象）。

    注意：仅 OpenProcess 成功不够——进程退出后只要还有句柄（如父进程的 Popen）
    未关闭，对象仍在，OpenProcess 依然成功；必须再用 GetExitCodeProcess 检查
    退出码是否为 STILL_ACTIVE，否则被杀/崩溃的引擎会被误判为“运行中”，
    任务永远不进入「继续任务」列表。
    """
    try:
        pid = int(pid or 0)
    except Exception:
        return False
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        # PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
        h = k32.OpenProcess(0x1000 | 0x100000, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            if k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return code.value == 0x103  # STILL_ACTIVE
            return True  # 退出码查询失败时保守认为存活
        finally:
            k32.CloseHandle(h)
    except Exception:
        return False


def phase_name(phase):
    return PHASE_NAMES.get(str(phase or ""), str(phase or "未知"))


def is_incomplete(output_dir, pid_check=True):
    """目录是否为一个可继续的未完成任务（有状态文件且 done != true，且进程不在跑）。"""
    st = load(output_dir)
    if not st or st.get("done"):
        return False
    if pid_check and pid_alive(st.get("pid")):
        return False
    return True


def brief(st, task_dir=None):
    """一行摘要（GUI 列表展示用）。"""
    prog = ""
    try:
        total = int(st.get("total_shots") or 0)
        done = int(st.get("done_shots") or 0)
        if total > 0:
            prog = f"镜头 {done}/{total} · "
    except Exception:
        pass
    title = str(st.get("title") or "").strip()
    parts = [f"《{title}》" if title else "", phase_name(st.get("phase")), prog,
             str(st.get("updated_at") or "")]
    return " ".join(p for p in parts if p)
