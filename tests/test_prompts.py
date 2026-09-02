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


def test_ecommerce_main_prompt_focuses_copy_and_requires_grounded_evidence() -> None:
    prompt = build_ecommerce_prompt(
        task_type="main",
        product_name="清风抽纸 24包 129mm",
        user_prompt="",
        selling_points=["匠心工艺", "亲肤材质", "高级质感"],
        long_title="清风抽纸家庭装",
        short_title="柔韧亲肤",
        aspect_ratio="1:1",
    )
    assert "只选择一个" in prompt
    assert "1 条主标题" in prompt
    assert "1 条解释性副标题" in prompt
    assert "最多 2 个可信证据标签" in prompt
    assert "商品标题、参考图或已有卖点" in prompt
    assert "禁止虚构数字、参数、倍率、效果、认证或竞品差异" in prompt


def test_ecommerce_prompts_separate_scene_selling_point_and_grid_roles() -> None:
    common = {
        "product_name": "山茶花面霜",
        "user_prompt": "",
        "selling_points": ["匠心工艺", "亲肤材质", "高级质感"],
        "long_title": "山茶花补水面霜女保湿修护",
        "short_title": "山茶花面霜",
        "aspect_ratio": "1:1",
    }
    scene = build_ecommerce_prompt(task_type="scene", **common)
    selling_points = build_ecommerce_prompt(task_type="sellingPoints", **common)
    grid = build_ecommerce_prompt(task_type="gridScene", **common)
    assert "谁在什么场景下如何使用商品" in scene
    assert "不确定具体人群或场景时" in scene
    assert "卖点解释图" in selling_points
    assert "视觉证据" in selling_points
    assert "不要简单重复主图文案" in selling_points
    assert "购买疑问" in grid
    assert "四格信息不得重复" in grid


def test_ecommerce_selling_point_prompt_does_not_invent_missing_copy() -> None:
    prompt = build_ecommerce_prompt(
        task_type="sellingPoints",
        product_name="山茶花面霜",
        user_prompt="",
        selling_points=[],
        long_title="",
        short_title="",
        aspect_ratio="1:1",
    )
    assert "没有已有卖点时" in prompt
    assert "不要新增营销文字" in prompt
    assert "选择一个需要进一步说明的重点卖点" not in prompt


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
