# 任务 JSON

下列示例不包含凭据。Key 只能来自进程环境变量。

## 商品套图

```json
{
  "workflow": "ecommerce",
  "product_name": "轻量保温杯",
  "prompt": "清爽夏日风，突出便携",
  "reference_images": ["./inputs/product.png"],
  "image_types": ["main", "scene", "sellingPoints", "whiteBackground", "certification", "gridScene"],
  "copy_fields": ["sellingPoints", "longTitle", "shortTitle"],
  "product_copy": {"selling_points": ["轻量随行", "", ""], "long_title": "", "short_title": ""},
  "aspect_ratio": "3:4",
  "quality": "2K"
}
```

## 自由工作台

```json
{
  "workflow": "workbench",
  "prompt": "第一张画面要求\n---\n第二张画面要求",
  "prompt_mode": "queue",
  "reference_mode": "shared",
  "references": [],
  "aspect_ratio": "1:1",
  "image_size": "2K"
}
```

### 队列与恢复

工作台队列也接受一行一个提示词；需要保留单条提示词内部换行时继续使用示例中的独立 `---` 分隔行。队列使用共享参考图；逐图参考模式使用一个共同指令，不与队列组合。`1K/2K/4K` 是提交规格，实际输出尺寸读取结果中的 `width/height`，不保证 `2K` 等于 2048 像素。

恢复已有任务不要重建任务 JSON。使用 `workbench --retry TASK_ID --asset image-2 --yes`；程序读取自己的输入快照，不接受手工提供 `generation_snapshot` 来替代原始输入。参见 `recovery.md`。

## 批量修图参数

```json
{
  "workflow": "batch-edit",
  "prompt": "统一为纯白背景并保持商品细节",
  "sources": ["./inputs/a.png", "./inputs/b.png"],
  "common_references": ["./inputs/style.png"],
  "aspect_ratio": "Adaptive",
  "image_size": "2K"
}
```

## 商品详情页

```json
{
  "workflow": "detail",
  "action": "create",
  "name": "保温杯详情页",
  "facts": {"材质": "不锈钢", "容量": "500mL"},
  "references": ["./inputs/product.png"],
  "creative_direction": "清爽、可信"
}
```

后续动作使用同一任务 ID，例如：

```json
{"workflow":"detail","action":"generate","task_id":"task-example","segments":["hero","product"]}
```

## 爆款复刻

```json
{
  "workflow": "replica",
  "action": "analyze",
  "name": "模板复刻",
  "template": "./inputs/template.png",
  "images": {"main": "./inputs/product.png", "detail": "./inputs/detail.png"},
  "facts": {"材质": "棉"}
}
```

后续动作通过 `task_id` 执行 `configure`、`copy`、`generate` 或 `cancel`。
