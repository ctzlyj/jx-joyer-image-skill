BASE_URL = "http://llm-gw.jd.local/v1"
TEXT_MODEL = "GPT-5.6-Sol-joybuilder"
IMAGE_MODEL = "GPT-Image-2.5-Flare-joybuilder"
# 三款网关生图模型（2026-10-09 /images/generations 与 /images/edits 均线上实测可用）：
# - GPT-Image-2.5-Flare-joybuilder：快速通用；支持透明背景，最高 4K*。
# - GPT-Image-2.5-Sunburst-joybuilder：专业精细；支持高精度参考图编辑，支持透明背景，最高 4K*。
# - Oxygen-Product-Pro：电商专用，免费快速；商品主体保持与中文文字渲染专项优化，稳定 2K。
# 完整对比表见 README.md《生图模型》与 references/capabilities.md。
#
# 主模型报额度/限流/权限/模型不可用类错误时，按顺位自动降级；
# 同一把网关 Key 对三款模型通用。降级链：Flare -> Sunburst -> Oxygen-Product-Pro。
# GPT-Image-2.5 系列返回 b64_json；末位 Oxygen-Product-Pro 返回图片 URL
# （data[0].url，京东 CDN）；客户端两种格式都兼容。
IMAGE_FALLBACK_MODELS = ("GPT-Image-2.5-Sunburst-joybuilder", "Oxygen-Product-Pro")
# /images/edits 参考图编辑：三款模型均实测可用，沿用同一降级链。
IMAGE_EDIT_FALLBACK_MODELS = ("GPT-Image-2.5-Sunburst-joybuilder", "Oxygen-Product-Pro")
# Oxygen-Product-Pro 实测可用的尺寸；请求其它尺寸时按宽高比就近映射。
# GPT-Image-2.5 系列按请求尺寸透传（最高 4K*）。
OXYGEN_PRODUCT_PRO_SIZES = ("1024x1024", "1024x1536", "1536x1024")
MODEL_SIZE_CONSTRAINTS = {"Oxygen-Product-Pro": OXYGEN_PRODUCT_PRO_SIZES}
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
