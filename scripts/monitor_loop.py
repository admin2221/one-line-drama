# -*- coding: utf-8 -*-
"""Poll execution progress until success or error."""
import json, sys, urllib.request, time
sys.stdout.reconfigure(encoding="utf-8")

PID = sys.argv[1] if len(sys.argv) > 1 else None
if not PID:
    PID = open(r"D:\Comfyui\Comfyui\scripts\last_prompt_id.txt").read().strip()
print(f"monitoring prompt_id={PID}")

def get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:8188{path}", timeout=15) as r:
        return json.loads(r.read().decode())

started_nodes = set()
last_log = None
while True:
    try:
        hist = get("/history")
        h = hist.get(PID)
        if h is None:
            # maybe still queued
            q = get("/queue")
            qr = q.get("queue_running", [])
            qp = q.get("queue_pending", [])
            # find if PID is in queue
            in_queue = any((rq[1] if len(rq) > 1 else "") == PID for rq in qr + qp)
            print(f"[{time.strftime('%H:%M:%S')}] not in history yet (in_queue={in_queue}, running={len(qr)}, pending={len(qp)})")
            time.sleep(10)
            continue

        st = h.get("status", {})
        status = st.get("status_str")
        completed = st.get("completed")
        msgs = st.get("messages", [])
        n_msgs = len(msgs)

        # collect execution_start / execution_error / execution_success events
        new_errors = []
        for m in msgs:
            if m[0] == "execution_start":
                node_id = m[1].get("node_id")
                title = m[1].get("title")
                if node_id not in started_nodes:
                    started_nodes.add(node_id)
                    # only print milestone nodes
                    if title and any(k in str(title) for k in ("剧本", "剧情", "LLM", "分镜", "镜头", "短剧", "Save", "merge", "Merge")):
                        print(f"[{time.strftime('%H:%M:%S')}] START {title} (node {node_id})")
            elif m[0] == "execution_error":
                d = m[1]
                print(f"[{time.strftime('%H:%M:%S')}] ERROR node={d.get('node_id')} [{d.get('node_type')}] {str(d.get('exception_message'))[:300]}")

        if status == "error":
            print(f"\n=== EXECUTION FAILED (completed={completed}, msgs={n_msgs}) ===")
            # print last error detail
            for m in msgs[-5:]:
                if m[0] == "execution_error":
                    d = m[1]
                    print("FATAL:", d.get("node_type"), str(d.get("exception_message"))[:800])
            sys.exit(1)

        if status == "success":
            print(f"\n=== SUCCESS === completed={completed}, total_msgs={n_msgs}, nodes_started={len(started_nodes)}")
            sys.exit(0)

        # still running
        print(f"[{time.strftime('%H:%M:%S')}] running (completed={completed}, msgs={n_msgs}, nodes_started={len(started_nodes)})")
        time.sleep(20)

    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] monitor err: {e}")
        time.sleep(15)
