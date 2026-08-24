from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from jx_joyer.models import EcommerceSpec, TaskManifest


def test_ecommerce_defaults_to_square_2k() -> None:
    spec = EcommerceSpec(product_name="测试商品", prompt="突出商品")
    assert spec.aspect_ratio == "1:1"
    assert spec.quality == "2K"
    assert spec.provider_size == "1024x1024"
    assert spec.final_size == (800, 800)


def test_three_by_four_4k_maps_to_2448_by_3264() -> None:
    spec = EcommerceSpec(product_name="测试商品", prompt="突出商品", aspect_ratio="3:4", quality="4K")
    assert spec.provider_size == "2448x3264"
    assert spec.final_size == (600, 800)


def test_legacy_manifest_without_aspect_ratio_reads_as_square() -> None:
    manifest = TaskManifest.model_validate({
        "id": "task-1",
        "kind": "ecommerce",
        "status": "draft",
        "request": {"product_name": "测试商品"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    assert manifest.request.get("aspect_ratio", "1:1") == "1:1"


@pytest.mark.parametrize("field", ["api_key", "authorization", "cookie", "x_jd_oxygen_key"])
def test_manifest_rejects_credential_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        TaskManifest(kind="generate", request={field: "forbidden"})
