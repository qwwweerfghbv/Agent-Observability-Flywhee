"""L1 基础设施巡检（SDD §5.4，M2）

探测项：磁盘水位 / 端口存活 / 目录体积 / 进程 CPU-内存 / 百炼探活 / 真流式探针。
汇总写 data/observability/infra.jsonl；命中 critical 触发 Windows 桌面通知（1h 收敛）。

用法：
    python tests/eval/patrol.py                 # 全量巡检
    python tests/eval/patrol.py --no-api        # 跳过百炼探活（省 token）
    python tests/eval/patrol.py --no-stream     # 跳过真流式探针
可挂 Windows 任务计划程序每日执行（见文件末尾注册命令，不自动安装）。
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# sys.path：tests/eval/patrol.py → job-agent 根
_JOB_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _JOB_AGENT_ROOT not in sys.path:
    sys.path.insert(0, _JOB_AGENT_ROOT)

from app.observability.writers import OBS_DIR, _append_jsonl, rotate_if_needed  # noqa: E402

INFRA_PATH = OBS_DIR / "infra.jsonl"
_ALERT_STATE = OBS_DIR / ".alert_state.json"
_HERE = Path(__file__).resolve().parent
_STREAM_PROBE = _HERE / "check_stream_timing.py"
_ALERT_COOLDOWN_S = 3600  # 同类告警 1h 收敛（SDD §5.9）

# 端口 → 服务
_PORTS = {"8000": "backend", "8501": "streamlit", "5173": "vite-dev"}
# 磁盘水位告警阈值（GB）
_DISK_CRITICAL_GB = 2.0
_DISK_WARN_GB = 5.0


def _patrol_drives() -> tuple:
    """巡检盘符：PATROL_DRIVES 环境变量可覆盖（逗号分隔）；
    默认 Windows 取系统盘 + 当前工作盘，非 Windows 取根目录"""
    env = os.environ.get("PATROL_DRIVES", "")
    if env:
        return tuple(d for d in env.split(",") if d.strip())
    if os.name == "nt":
        drives = {os.environ.get("SystemDrive", "C:") + "\\", os.getcwd()[:2] + "\\"}
        return tuple(sorted(drives))
    return ("/",)


# ---------- 探测项 ----------

def check_disk() -> dict:
    """各巡检盘剩余空间（GB）与剩余百分比"""
    out = {}
    for drive in _patrol_drives():
        try:
            du = shutil.disk_usage(drive)
            key = drive[0]
            out[f"{key}_free_gb"] = round(du.free / (1024 ** 3), 1)
            out[f"{key}_free_pct"] = round(du.free / du.total * 100, 1)
        except Exception:
            pass  # 盘符不存在时静默跳过
    return out


def check_ports() -> dict:
    """socket 探活 8000/8501/5173；8000 额外 GET /health"""
    out = {}
    for port in _PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            out[port] = s.connect_ex(("127.0.0.1", int(port))) == 0
        except Exception:
            out[port] = False
        finally:
            s.close()
    # 后端健康端点二次确认
    if out.get("8000"):
        try:
            import requests
            r = requests.get("http://127.0.0.1:8000/health", timeout=3)
            out["8000"] = r.status_code == 200
        except Exception:
            out["8000"] = False
    return out


def check_dirs() -> dict:
    """data/、tests/eval/results/、npm 缓存体积（MB）"""
    def _dir_mb(p: Path) -> int:
        total = 0
        try:
            for f in p.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except OSError:
                        pass
        except Exception:
            return 0
        return round(total / (1024 ** 2))

    out = {
        "data": _dir_mb(Path(_JOB_AGENT_ROOT) / "data"),
        "results": _dir_mb(_HERE / "results"),
    }
    npm_cache = Path.home() / "AppData" / "Local" / "npm-cache"
    if npm_cache.exists():
        out["npm_cache"] = _dir_mb(npm_cache)
    return out


def check_proc() -> dict:
    """当前进程 CPU/内存（psutil 可选，无则返回空 dict → 字段省略）"""
    try:
        import psutil
        p = psutil.Process(os.getpid())
        return {"cpu_pct": p.cpu_percent(interval=0.3), "rss_mb": round(p.memory_info().rss / (1024 ** 2))}
    except Exception:
        return {}  # psutil 未安装：L1 CPU/内存项自动跳过（SDD §3.4）


def check_api() -> dict:
    """百炼探活：进程内直调发一条基准消息，归类 ok/error"""
    try:
        from app.llm.client import get_llm_client
        client = get_llm_client()
        t0 = time.time()
        client.chat_sync([{"role": "user", "content": "ping"}], temperature=0, max_tokens=1)
        return {"bailian": "ok", "bailian_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"bailian": f"error: {type(e).__name__}"}


def stream_probe() -> dict:
    """真流式探针：调用 check_stream_timing.py，退出码 0=真流式"""
    if not _STREAM_PROBE.exists():
        return {"stream": "probe_missing"}
    try:
        r = subprocess.run(
            [sys.executable, str(_STREAM_PROBE)],
            cwd=_JOB_AGENT_ROOT, capture_output=True, text=True, timeout=120,
        )
        return {"stream": "ok" if r.returncode == 0 else "degraded",
                "stream_detail": (r.stdout or r.stderr).strip().splitlines()[-1][:120] if (r.stdout or r.stderr) else ""}
    except Exception as e:
        return {"stream": f"error: {type(e).__name__}"}


# ---------- 告警派生 + 收敛 + 通知 ----------

def derive_alerts(disk: dict, ports: dict, api: dict, stream: dict) -> list:
    """按阈值派生告警标签（critical 前缀 crit:，warning 前缀 warn:）"""
    alerts = []
    for _k, _v in disk.items():
        if not _k.endswith("_free_gb") or _v is None:
            continue
        _letter = _k.split("_")[0]
        if _v < _DISK_CRITICAL_GB:
            alerts.append(f"crit:disk_{_letter}_below_2GB")
        elif _v < _DISK_WARN_GB:
            alerts.append(f"warn:disk_{_letter}_below_5GB")
    if ports.get("8000") is False:
        alerts.append("crit:backend_8000_down")
    if str(api.get("bailian", "")).startswith("error"):
        alerts.append("crit:bailian_api_down")
    if stream.get("stream") == "degraded":
        alerts.append("crit:stream_degraded")
    return alerts


def _load_alert_state() -> dict:
    try:
        return json.loads(_ALERT_STATE.read_text(encoding="utf-8")) if _ALERT_STATE.exists() else {}
    except Exception:
        return {}


def _save_alert_state(state: dict) -> None:
    try:
        _ALERT_STATE.parent.mkdir(parents=True, exist_ok=True)
        _ALERT_STATE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def notify_critical(alerts: list) -> list:
    """critical 告警 → Windows 桌面通知（1h 收敛）；返回本次实际推送的告警"""
    crits = [a for a in alerts if a.startswith("crit:")]
    if not crits:
        return []
    state = _load_alert_state()
    now = time.time()
    fired = []
    for a in crits:
        if now - state.get(a, 0) >= _ALERT_COOLDOWN_S:
            fired.append(a)
            state[a] = now
    _save_alert_state(state)
    if fired:
        _windows_toast("求职Agent 巡检告警", " / ".join(fired))
    return fired


def _windows_toast(title: str, body: str) -> None:
    """best-effort Windows toast（PowerShell），失败静默降级为控制台提示"""
    try:
        ps = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] > $null;"
            f"$t='{title}';$b='{body}';"
            "$x=New-Object Windows.Data.Xml.Dom.XmlDocument;"
            "$x.LoadXml(\"<toast><visual><binding template='ToastText02'><text id='1'>$t</text>"
            "<text id='2'>$b</text></binding></visual></toast>\");"
            "$n=[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JobAgentPatrol');"
            "$n.Show([Windows.UI.Notifications.ToastNotification]::new($x))"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=8)
    except Exception:
        pass
    # 无论 toast 成功与否，控制台可见
    print(f"[CRITICAL ALERT] {body}")


# ---------- 主流程 ----------

def run_patrol(do_api: bool = True, do_stream: bool = True) -> dict:
    disk = check_disk()
    ports = check_ports()
    dirs = check_dirs()
    proc = check_proc()
    api = check_api() if do_api else {}
    # 真流式探针需后端在线
    stream = stream_probe() if (do_stream and ports.get("8000")) else ({"stream": "skipped_backend_down"} if do_stream else {})

    alerts = derive_alerts(disk, ports, api, stream)
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "type": "patrol",
        "disk": disk,
        "ports": ports,
        "dir_size_mb": dirs,
        "api_health": api,
        "stream_probe": stream,
        "alerts": alerts,
    }
    if proc:
        rec["proc"] = proc

    rotate_if_needed(INFRA_PATH)
    _append_jsonl(INFRA_PATH, rec)
    fired = notify_critical(alerts)
    rec["alerts_fired"] = fired
    return rec


def _print_summary(rec: dict) -> None:
    print("=" * 56)
    print("  L1 基础设施巡检报告")
    print("=" * 56)
    d = rec.get("disk", {})
    print(f"  磁盘: C 剩余 {d.get('C_free_gb', '?')}GB ({d.get('C_free_pct', '?')}%)  "
          f"E 剩余 {d.get('E_free_gb', '?')}GB")
    ports = rec.get("ports", {})
    pstr = "  ".join(f"{k}({'UP' if v else 'DOWN'})" for k, v in ports.items())
    print(f"  端口: {pstr}")
    print(f"  目录(MB): {rec.get('dir_size_mb', {})}")
    if rec.get("proc"):
        print(f"  进程: {rec['proc']}")
    if rec.get("api_health"):
        print(f"  百炼: {rec['api_health']}")
    if rec.get("stream_probe"):
        print(f"  真流式: {rec['stream_probe']}")
    alerts = rec.get("alerts", [])
    if alerts:
        print(f"  [!] 告警: {alerts}")
    else:
        print("  [OK] 无告警")
    print("=" * 56)


def main():
    ap = argparse.ArgumentParser(description="L1 基础设施巡检")
    ap.add_argument("--no-api", action="store_true", help="跳过百炼探活（省 token）")
    ap.add_argument("--no-stream", action="store_true", help="跳过真流式探针")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出巡检记录")
    args = ap.parse_args()

    rec = run_patrol(do_api=not args.no_api, do_stream=not args.no_stream)
    if args.json:
        print(json.dumps(rec, ensure_ascii=False))
    else:
        _print_summary(rec)
    # 退出码非零 ⟺ 有 critical 告警
    sys.exit(1 if any(a.startswith("crit:") for a in rec.get("alerts", [])) else 0)


if __name__ == "__main__":
    main()

# Windows 任务计划程序注册（手动执行，不自动装）：
#   schtasks /Create /TN "JobAgentPatrol" /TR "python E:\求职&晋升\job-agent\tests\eval\patrol.py --no-stream" /SC DAILY /ST 09:00
