BASE_URL = "http://llm-gw.jd.local/v1"
TEXT_MODEL = "GPT-5.6-Sol-joybuilder"
IMAGE_MODEL = "GPT-image-2-joybuilder"
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
