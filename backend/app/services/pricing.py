"""Provider price catalog and billing-mode resolution.

Prices are in CNY. Only providers with an explicit catalog entry are priced
automatically; anything else falls back to the manual price in Settings.
"""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")
DEFAULT_CURRENCY = "CNY"
DEFAULT_BILLING = "monthly"

MODES = {
    "monthly": "包月订阅，不计单次费用",
    "payg": "按量计费",
    "free": "本地或免费额度",
    "unpriced": "按量计费，但未配置单价",
}

# DeepSeek 官方价格（2026-11 查询）
# https://api-docs.deepseek.com/zh-cn/quick_start/pricing
DEEPSEEK_TIERS = {
    "deepseek-flash": "flash",
    "deepseek-v4.1-flash": "flash",
    "deepseek-v4-flash": "flash",
    "deepseek-v4-flash-vision-exp": "flash",
    "deepseek-v4-pro": "pro",
    "deepseek-pro": "pro",
}

# CNY per 1M tokens: (input cache miss, output)
DEEPSEEK_TOKEN_PRICE = {
    "flash": {"peak": (2.0, 8.0), "idle": (1.0, 4.0)},
    "pro": {"peak": (9.0, 27.0), "idle": (4.5, 13.5)},
}

# CNY per unit
DEEPSEEK_SERVICE_PRICE = {
    "search": (5.0 / 1000, "call"),
    "fetch": (5.0 / 1000, "call"),
    "ocr": (1.5 / 1000, "page"),
    "asr": (0.39 / 3600, "second"),
    "tts": (3.0 / 10000, "char"),
}

DEEPSEEK_SERVICE_LABEL = {
    "llm": "对话模型",
    "embedding": "向量模型",
    "search": "联网搜索",
    "fetch": "网页抓取",
    "ocr": "OCR 识别",
    "asr": "语音转写",
    "tts": "语音合成",
}


@dataclass(frozen=True)
class CostResult:
    cost: float
    currency: str
    billing_mode: str
    note: str


def provider_from_base(base: str) -> str:
    host = (urlparse(base or "").hostname or "").lower()
    if not host:
        return "unknown"
    if "deepseek.com" in host:
        return "deepseek"
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return "local"
    return host


def provider_label(provider: str) -> str:
    labels = {
        "deepseek": "DeepSeek 官方",
        "local": "本地模型",
        "unknown": "未识别服务",
    }
    return labels.get(provider, provider)


def default_mode(provider: str) -> str:
    if provider == "deepseek":
        return "payg"
    if provider == "local":
        return "free"
    # 平台接入默认按月付费，不单独计算单次费用
    return DEFAULT_BILLING


def resolve_mode(provider: str, billing: dict | None) -> str:
    billing = billing or {}
    overrides = billing.get("providers") or {}
    if provider in overrides:
        mode = str(overrides[provider] or "")
        if mode in MODES:
            return mode
    mode = str(billing.get("default") or "")
    if mode in MODES and provider not in {"deepseek", "local"}:
        return mode
    return default_mode(provider)


def is_peak(moment: datetime | None = None) -> bool:
    now = (moment or datetime.now(BEIJING)).astimezone(BEIJING)
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 12 or 14 <= now.hour < 18


def deepseek_tier(model: str) -> str | None:
    name = (model or "").strip().lower()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return DEEPSEEK_TIERS.get(name)


def llm_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    manual_input: float = 0.0,
    manual_output: float = 0.0,
    moment: datetime | None = None,
) -> CostResult:
    prompt_tokens = max(int(prompt_tokens or 0), 0)
    completion_tokens = max(int(completion_tokens or 0), 0)

    if provider == "deepseek":
        tier = deepseek_tier(model)
        if tier is None:
            return CostResult(0.0, DEFAULT_CURRENCY, "unpriced", "未收录的 DeepSeek 模型")
        window = "peak" if is_peak(moment) else "idle"
        input_price, output_price = DEEPSEEK_TOKEN_PRICE[tier][window]
        cost = (
            prompt_tokens / 1_000_000 * input_price
            + completion_tokens / 1_000_000 * output_price
        )
        peak_label = "高峰" if window == "peak" else "空闲"
        return CostResult(
            round(cost, 6),
            DEFAULT_CURRENCY,
            "payg",
            f"DeepSeek 官方价（{peak_label}时段，缓存未命中）",
        )

    if manual_input <= 0 and manual_output <= 0:
        return CostResult(0.0, DEFAULT_CURRENCY, "unpriced", "未配置单价")

    cost = (
        prompt_tokens / 1_000_000 * max(manual_input, 0.0)
        + completion_tokens / 1_000_000 * max(manual_output, 0.0)
    )
    return CostResult(round(cost, 6), DEFAULT_CURRENCY, "payg", "设置页自定义单价")


def service_cost(provider: str, service: str, units: float) -> CostResult:
    units = max(float(units or 0), 0.0)
    if provider == "deepseek" and service in DEEPSEEK_SERVICE_PRICE:
        unit_price, _unit = DEEPSEEK_SERVICE_PRICE[service]
        note = "DeepSeek 官方价"
        if service == "asr":
            note = "DeepSeek 官方价（限时 5 折，刊例 0.78 元/小时）"
        return CostResult(
            round(units * unit_price, 6),
            DEFAULT_CURRENCY,
            "payg",
            note,
        )
    return CostResult(0.0, DEFAULT_CURRENCY, "unpriced", "未收录该服务价格")


def apply_mode(result: CostResult, mode: str) -> CostResult:
    if mode == "monthly":
        return CostResult(0.0, result.currency, "monthly", MODES["monthly"])
    if mode == "free":
        return CostResult(0.0, result.currency, "free", MODES["free"])
    if mode == "unpriced":
        return CostResult(0.0, result.currency, "unpriced", MODES["unpriced"])
    return result


def format_cost(value: float) -> str:
    if value <= 0:
        return "¥0.00"
    if value < 0.01:
        return f"¥{value:.4f}"
    return f"¥{value:.2f}"
