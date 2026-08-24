from pathlib import Path

from jx_joyer.prompts.common import build_derivative_prompt
from jx_joyer.prompts.detail import build_detail_prompt
from jx_joyer.prompts.ecommerce import build_copy_prompt, build_ecommerce_prompt, missing_copy_fields
from jx_joyer.prompts.replica import build_replica_prompt, select_replica_references
from jx_joyer.prompts.workbench import build_workbench_prompt


def test_ecommerce_prompt_contains_task_manual_copy_and_ratio() -> None:
    prompt = build_ecommerce_prompt(
        task_type="sellingPoints",
        product_name="测试商品",
        user_prompt="清爽夏日风",
        selling_points=["轻量", "耐用", "易清洁"],
        long_title="测试长标题",
        short_title="测试短标题",
        aspect_ratio="3:4",
    )
    assert "卖点图" in prompt
    assert "轻量" in prompt
    assert "测试长标题" in prompt
    assert "3:4" in prompt


def test_copy_prompt_requests_only_missing_selected_fields() -> None:
    missing = missing_copy_fields(
        selected=["sellingPoints", "longTitle", "shortTitle"],
        selling_points=["手工卖点", "", ""],
        long_title="手工长标题",
        short_title="",
    )
    prompt = build_copy_prompt("测试商品", missing)
    assert missing == ["sellingPoints", "shortTitle"]
    assert "selling_points" in prompt
    assert "short_title" in prompt
    assert "long_title" not in prompt


def test_detail_prompt_contains_facts_copy_and_dimensions() -> None:
    prompt = build_detail_prompt(
        segment="hero",
        facts={"材质": "棉"},
        copy={"headline": "舒适体验"},
        creative_direction="清新",
        width=800,
        height=1000,
    )
    assert "hero" in prompt
    assert "棉" in prompt
    assert "舒适体验" in prompt
    assert "800x1000" in prompt


def test_workbench_prompt_contains_ratio_and_reference_roles() -> None:
    prompt = build_workbench_prompt("换成蓝色背景", ratio="4:5", reference_roles=["商品", "风格"])
    assert "4:5" in prompt
    assert "参考图1（商品）" in prompt
    assert "参考图2（风格）" in prompt


def test_derivative_prompt_preserves_ratio() -> None:
    prompt = build_derivative_prompt("增加柔和阴影", aspect_ratio="3:4")
    assert "增加柔和阴影" in prompt
    assert "保持原图 3:4" in prompt


def test_replica_references_put_template_then_product(tmp_path: Path) -> None:
    template = tmp_path / "template.png"
    product = tmp_path / "product.png"
    detail = tmp_path / "detail.png"
    refs = select_replica_references(template, {"main": product, "detail": detail}, purpose="detail")
    assert refs == [template, product, detail]
    prompt = build_replica_prompt(
        purpose="detail",
        layout_summary="左图右文",
        facts={"颜色": "红色"},
        exact_text=["新品上市"],
        width=800,
        height=1000,
    )
    assert "替换模板中的商品" in prompt
    assert "新品上市" in prompt
