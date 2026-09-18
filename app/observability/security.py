"""安全扫描（SDD §4.8 / §5.7 security，M4）

- 输入侧：提示注入 / 越狱样式规则扫描
- 输出侧：敏感信息（PII / 密钥）泄露扫描
- 纯函数、无副作用、无 IO；命中结果由 quality.py 组装进 quality.jsonl，
  再经 M3 flywheel 的 `security_hit` 规则回流评审队列。
- 静默降级：任何异常返回“未命中”，绝不抛出影响主链路。
"""
import re
from typing import Dict, List

# ---- 输入侧：注入 / 越狱样式（中英） ----
INJECTION_PATTERNS = [
    ("ignore_instructions", re.compile(
        r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?"
        r"(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)", re.I)),
    ("system_prompt_leak", re.compile(
        r"(reveal|show|print|repeat|output)\s+(me\s+)?(your\s+|the\s+)?"
        r"(system\s+prompt|system\s+instructions?|hidden\s+prompt|initial\s+prompt)", re.I)),
    ("role_override", re.compile(
        r"(you\s+are\s+now\s+|pretend\s+to\s+be\s+|act\s+as\s+(an?\s+)?"
        r"(unrestricted|jailbroken|developer\s+mode|dan\b))", re.I)),
    ("delimiter_break", re.compile(r"(<\s*/?\s*system\s*>|\[\s*INST\s*\]|###\s*(system|instruction))", re.I)),
    ("zh_ignore", re.compile(r"(忽略|无视|忘记|抛弃)(以上|上述|之前|前面|先前)(的)?(所有)?(指令|提示|规则|设定|内容)")),
    ("zh_role", re.compile(r"(你现在是|从现在开始你是|从现在起你是|扮演一个不受限|进入开发者模式|越狱模式)")),
    ("zh_sys", re.compile(r"(输出|告诉我|重复|打印|显示)(你的|系统的)?(系统提示|系统指令|隐藏指令|初始提示|prompt)")),
]

# ---- 输出侧：敏感信息泄露 ----
SENSITIVE_PATTERNS = [
    ("api_key", re.compile(
        r"(sk-[A-Za-z0-9]{16,}|api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"
        r"|Bearer\s+[A-Za-z0-9._\-]{16,}|AKIA[0-9A-Z]{16})", re.I)),
    ("id_card", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("bank_card", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
    ("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
]

# 脱敏替换（写日志/预览时用，避免二次泄露）
_MASKS = {
    "api_key": "***KEY***",
    "id_card": "***ID***",
    "bank_card": "***CARD***",
    "phone": "***PHONE***",
    "email": "***EMAIL***",
}


def scan_input(text: str) -> Dict:
    """输入侧注入样式扫描 → {injection_hit, patterns}"""
    try:
        if not text:
            return {"injection_hit": False, "patterns": []}
        hits: List[str] = [name for name, pat in INJECTION_PATTERNS if pat.search(text)]
        return {"injection_hit": bool(hits), "patterns": hits}
    except Exception:
        return {"injection_hit": False, "patterns": []}


def scan_output(text: str) -> Dict:
    """输出侧敏感信息扫描 → {sensitive_hit, types}"""
    try:
        if not text:
            return {"sensitive_hit": False, "types": []}
        hits: List[str] = [name for name, pat in SENSITIVE_PATTERNS if pat.search(text)]
        return {"sensitive_hit": bool(hits), "types": hits}
    except Exception:
        return {"sensitive_hit": False, "types": []}


def mask_pii(text: str, limit: int = 200) -> str:
    """对文本中的敏感信息脱敏并截断（用于安全落预览，绝不含明文 PII）"""
    try:
        if not text:
            return ""
        out = text
        for name, pat in SENSITIVE_PATTERNS:
            out = pat.sub(_MASKS.get(name, "***"), out)
        return out[:limit]
    except Exception:
        return (text or "")[:limit]
