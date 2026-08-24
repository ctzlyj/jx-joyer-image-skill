from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .constants import ECOMMERCE_FINAL_SIZES, ECOMMERCE_IMAGE_TYPES, ECOMMERCE_PROVIDER_SIZES


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _contains_credentials(value: Any) -> bool:
    forbidden = {"api_key", "apikey", "authorization", "cookie", "x_jd_oxygen_key", "x-jd-oxygen-key"}
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).strip().lower() in forbidden or _contains_credentials(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_credentials(item) for item in value)
    return False


class ProductCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selling_points: list[str] = Field(default_factory=lambda: ["", "", ""], max_length=3)
    long_title: str = ""
    short_title: str = ""


class EcommerceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_name: str = Field(min_length=1)
    prompt: str = ""
    reference_images: list[str] = Field(default_factory=list, max_length=3)
    image_types: list[Literal["main", "scene", "sellingPoints", "whiteBackground", "certification", "gridScene"]] = Field(default_factory=lambda: ["main", "scene"])
    copy_fields: list[Literal["sellingPoints", "longTitle", "shortTitle"]] = Field(default_factory=list)
    product_copy: ProductCopy = Field(default_factory=ProductCopy)
    aspect_ratio: Literal["1:1", "3:4"] = "1:1"
    quality: Literal["1K", "2K", "4K"] = "2K"

    @model_validator(mode="after")
    def normalize_image_types(self) -> "EcommerceSpec":
        selected = set(self.image_types)
        self.image_types = [item for item in ECOMMERCE_IMAGE_TYPES if item in selected]
        if not self.image_types:
            raise ValueError("at least one ecommerce image type is required")
        return self

    @property
    def provider_size(self) -> str:
        return ECOMMERCE_PROVIDER_SIZES[(self.aspect_ratio, self.quality)]

    @property
    def final_size(self) -> tuple[int, int]:
        return ECOMMERCE_FINAL_SIZES[self.aspect_ratio]


class OutputAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"] = "pending"
    path: str | None = None
    prompt: str = ""
    width: int | None = None
    height: int | None = None
    revision: int = 1
    error: str | None = None


class TaskManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: f"task-{uuid4().hex}")
    kind: str
    status: Literal["draft", "running", "succeeded", "partial", "failed", "cancelled"] = "draft"
    request: dict[str, Any] = Field(default_factory=dict)
    assets: list[OutputAsset] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    text_requests: int = 0
    image_requests: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def reject_credentials(self) -> "TaskManifest":
        if _contains_credentials(self.model_dump(exclude={"request"})) or _contains_credentials(self.request):
            raise ValueError("credential fields are forbidden in task manifests")
        return self
