BASE_URL = "http://llm-gw.jd.local/v1"
TEXT_MODEL = "GPT-5.6-Sol-joybuilder"
IMAGE_MODEL = "GPT-image-2-joybuilder"
# 付费模型额度经常被砍/耗尽：GPT-image-2 报额度/限流/权限类错误时，
# 按此顺位自动降级。同一把网关 Key 对三个模型通用（2026-09-28 实测）。
# 注意：Oxygen 两个模型返回的是图片 URL（data[0].url，京东 CDN），不是 b64_json。
IMAGE_FALLBACK_MODELS = ("Oxygen-Product-Pro", "Oxygen-Imagen")
# /images/edits 图生图编辑只确认 Oxygen-Product-Pro 支持
IMAGE_EDIT_FALLBACK_MODELS = ("Oxygen-Product-Pro",)
# Oxygen 系列实测可用的尺寸；请求其它尺寸时按宽高比就近映射
OXYGEN_FALLBACK_SIZES = ("1024x1024", "1024x1536", "1536x1024")
TEXT_CONCURRENCY = 20
IMAGE_CONCURRENCY = 4
IMAGE_STARTS_PER_SECOND = 1
TIMEOUT_SECONDS = 600.0
MAX_ATTEMPTS = 4

ECOMMERCE_IMAGE_TYPES = (
    "main",
    "scene",
    "sellingPoints",
    "whiteBackground",
    "certification",
    "gridScene",
)
ECOMMERCE_PROVIDER_SIZES = {
    ("1:1", "1K"): "1024x1024",
    ("1:1", "2K"): "1024x1024",
    ("1:1", "4K"): "2880x2880",
    ("3:4", "1K"): "1152x1536",
    ("3:4", "2K"): "1152x1536",
    ("3:4", "4K"): "2448x3264",
}
ECOMMERCE_FINAL_SIZES = {"1:1": (800, 800), "3:4": (600, 800)}
