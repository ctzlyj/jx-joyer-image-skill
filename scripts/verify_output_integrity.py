from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def parse_region(value: str) -> tuple[int, int, int, int]:
    parts = tuple(int(part.strip()) for part in value.split(","))
    if len(parts) != 4 or any(part < 0 for part in parts) or parts[2] <= 0 or parts[3] <= 0:
        raise argparse.ArgumentTypeError("region must be x,y,width,height with non-negative coordinates")
    return parts


def percentile_from_histogram(histogram: list[int], percentile: float) -> int:
    target = sum(histogram) * percentile
    cumulative = 0
    for value, count in enumerate(histogram):
        cumulative += count
        if cumulative >= target:
            return value
    return 255


def verify_integrity(
    generated_path: Path,
    final_path: Path,
    allowed_regions: list[tuple[int, int, int, int]],
    mean_threshold: float = 2.0,
    p99_threshold: float = 8.0,
) -> dict[str, object]:
    with Image.open(final_path) as final_source:
        final = final_source.convert("RGB")
    with Image.open(generated_path) as generated_source:
        generated = generated_source.convert("RGB").resize(final.size, Image.Resampling.LANCZOS)
    difference = ImageChops.difference(generated, final).convert("L")
    for left, top, width, height in allowed_regions:
        difference.paste(0, (left, top, min(final.width, left + width), min(final.height, top + height)))
    statistics = ImageStat.Stat(difference)
    mean_difference = float(statistics.mean[0])
    p99_difference = percentile_from_histogram(difference.histogram(), 0.99)
    passed = mean_difference <= mean_threshold and p99_difference <= p99_threshold
    return {
        "status": "passed" if passed else "failed",
        "generated": str(generated_path),
        "final": str(final_path),
        "allowedRegions": [list(region) for region in allowed_regions],
        "meanAbsoluteDifference": round(mean_difference, 4),
        "p99AbsoluteDifference": p99_difference,
        "thresholds": {"mean": mean_threshold, "p99": p99_threshold},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument("--allow-region", action="append", type=parse_region, default=[])
    parser.add_argument("--mean-threshold", type=float, default=2.0)
    parser.add_argument("--p99-threshold", type=float, default=8.0)
    args = parser.parse_args()
    result = verify_integrity(
        args.generated,
        args.final,
        args.allow_region,
        args.mean_threshold,
        args.p99_threshold,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
