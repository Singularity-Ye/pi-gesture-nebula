import argparse
import csv
import glob
import math
import os
import statistics
from collections import defaultdict


METRICS = [
    "camera_fps",
    "process_fps",
    "infer_fps",
    "ws_fps",
    "mjpeg_fps",
    "read_ms",
    "preprocess_ms",
    "inference_ms",
    "encode_ms",
    "loop_ms",
    "cpu_percent",
    "memory_mb",
    "temp_c",
    "area",
    "scale",
    "motion",
    "clients",
    "hand_detected",
    "landmark_count",
    "pinch_distance",
]

CURRENT_THROTTLE_BITS = {
    0: "under_voltage_now",
    1: "frequency_capped_now",
    2: "throttled_now",
    3: "soft_temp_limit_now",
}
HISTORICAL_THROTTLE_BITS = {
    16: "under_voltage_seen",
    17: "frequency_capped_seen",
    18: "throttled_seen",
    19: "soft_temp_limit_seen",
}

ALIASES = {
    "process_fps": ("process_fps", "opencv_fps"),
    "infer_fps": ("infer_fps", "mediapipe_fps"),
    "mjpeg_fps": ("mjpeg_fps", "jpeg_fps"),
    "loop_ms": ("loop_ms", "avg_loop_ms"),
    "preprocess_ms": ("preprocess_ms", "avg_opencv_ms"),
    "inference_ms": ("inference_ms", "avg_mediapipe_ms"),
    "encode_ms": ("encode_ms", "avg_jpeg_ms"),
    "area": ("area", "avg_area"),
    "motion": ("motion", "motion_ratio"),
    "hand_detected": ("hand_detected", "avg_hands"),
}


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize Raspberry Pi benchmark CSV files.")
    parser.add_argument("inputs", nargs="+", help="CSV files or glob patterns.")
    parser.add_argument("--out-dir", default="perf_report", help="Output directory.")
    parser.add_argument("--markdown", default="performance_summary.md", help="Markdown report filename.")
    parser.add_argument("--no-plots", action="store_true", help="Skip optional matplotlib plots.")
    return parser.parse_args()


def expand_inputs(patterns):
    files = []
    for pattern in patterns:
        if os.path.isdir(pattern):
            matches = glob.glob(os.path.join(pattern, "**", "*.csv"), recursive=True)
        else:
            matches = glob.glob(pattern, recursive=True)
        files.extend(matches or [pattern])
    return sorted(dict.fromkeys(files))


def to_float(value):
    if value is None or value == "":
        return None
    try:
        value = float(value)
    except ValueError:
        return None
    if math.isnan(value):
        return None
    return value


def mean(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return statistics.mean(values)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def throttled_seen(rows):
    for row in rows:
        raw = (row.get("throttled_raw") or "").strip().lower()
        flags = (row.get("throttled_flags") or "").strip().lower()
        if raw and raw not in ("0x0", "0"):
            return True
        if flags == "throttled":
            return True
    return False


def parse_throttled_raw(raw):
    raw = (raw or "").strip().lower()
    if not raw:
        return set()
    if raw.startswith("throttled="):
        raw = raw.split("=", 1)[1]
    try:
        value = int(raw, 16)
    except ValueError:
        return set()

    flags = set()
    for bit, name in {**CURRENT_THROTTLE_BITS, **HISTORICAL_THROTTLE_BITS}.items():
        if value & (1 << bit):
            flags.add(name)
    return flags


def throttled_flags_summary(rows):
    all_flags = set()
    for row in rows:
        all_flags.update(parse_throttled_raw(row.get("throttled_raw")))
    current = sorted(flag for flag in all_flags if flag.endswith("_now"))
    historical = sorted(flag for flag in all_flags if flag.endswith("_seen"))
    return current, historical


def row_value(row, metric):
    for key in ALIASES.get(metric, (metric,)):
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def summarize_file(path):
    rows = read_csv(path)
    summary = {
        "case": os.path.splitext(os.path.basename(path))[0],
        "file": path,
        "samples": len(rows),
    }

    first = rows[0] if rows else {}
    for key in ("mode", "width", "height", "target_fps", "infer_skip", "model_complexity", "max_num_hands", "video_enabled", "jpeg_quality"):
        summary[key] = first.get(key, "")
    if not summary.get("infer_skip"):
        summary["infer_skip"] = first.get("skip", "")

    for metric in METRICS:
        summary[metric] = mean(to_float(row_value(row, metric)) for row in rows)
        values = [to_float(row_value(row, metric)) for row in rows]
        values = [value for value in values if value is not None]
        if values:
            summary[f"{metric}_min"] = min(values)
            summary[f"{metric}_max"] = max(values)
            summary[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0

    temps = [to_float(row_value(row, "temp_c")) for row in rows]
    temps = [value for value in temps if value is not None]
    summary["temp_c_mean"] = statistics.mean(temps) if temps else None
    summary["temp_c_max"] = max(temps) if temps else None
    summary["throttled_seen"] = throttled_seen(rows)
    current_flags, historical_flags = throttled_flags_summary(rows)
    summary["throttled_current_seen"] = bool(current_flags)
    summary["throttled_historical_seen"] = bool(historical_flags)
    summary["throttled_current_flags"] = ",".join(current_flags)
    summary["throttled_historical_flags"] = ",".join(historical_flags)

    return summary


def fmt(value, digits=2):
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    return f"{value:.{digits}f}"


def make_markdown(summaries):
    lines = [
        "# Raspberry Pi Vision Performance Summary",
        "",
        "## Case Summary",
        "",
        "| Case | Mode | Size | Target FPS | Skip | Video | Camera FPS | Process FPS | Infer FPS | MJPEG FPS | Loop ms | CPU % | Temp Avg | Temp Max | Throttled | Encode ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in summaries:
        size = f"{item.get('width', '')}x{item.get('height', '')}"
        lines.append(
            "| {case} | {mode} | {size} | {target_fps} | {skip} | {video_enabled} | {camera_fps} | "
            "{process_fps} | {infer_fps} | {mjpeg_fps} | {loop_ms} | {cpu_percent} | "
            "{temp_c_mean} | {temp_c_max} | {throttled_seen} | {encode_ms} |".format(
                case=item["case"],
                mode=item.get("mode", ""),
                size=size,
                target_fps=item.get("target_fps", ""),
                skip=item.get("infer_skip", ""),
                video_enabled=item.get("video_enabled", ""),
                camera_fps=fmt(item.get("camera_fps")),
                process_fps=fmt(item.get("process_fps")),
                infer_fps=fmt(item.get("infer_fps")),
                mjpeg_fps=fmt(item.get("mjpeg_fps")),
                loop_ms=fmt(item.get("loop_ms")),
                cpu_percent=fmt(item.get("cpu_percent")),
                temp_c_mean=fmt(item.get("temp_c_mean")),
                temp_c_max=fmt(item.get("temp_c_max")),
                throttled_seen="yes" if item.get("throttled_seen") else "no",
                encode_ms=fmt(item.get("encode_ms")),
            )
        )

    lines.extend(["", "## Suggested Reading", ""])
    best_opencv = pick_best(summaries, mode="opencv")
    best_hybrid = pick_best(summaries, mode="hybrid")
    best_mp = pick_best(summaries, mode="mediapipe")

    if best_opencv:
        lines.append(
            f"- Stable OpenCV baseline candidate: `{best_opencv['case']}` "
            f"with camera FPS {fmt(best_opencv.get('camera_fps'))} and loop time {fmt(best_opencv.get('loop_ms'))} ms."
        )
    if best_mp:
        lines.append(
            f"- MediaPipe boundary candidate: `{best_mp['case']}` "
            f"with inference FPS {fmt(best_mp.get('infer_fps'))} and loop time {fmt(best_mp.get('loop_ms'))} ms."
        )
    if best_hybrid:
        lines.append(
            f"- Hybrid candidate: `{best_hybrid['case']}` "
            f"with camera FPS {fmt(best_hybrid.get('camera_fps'))}, "
            f"inference FPS {fmt(best_hybrid.get('infer_fps'))}, and loop time {fmt(best_hybrid.get('loop_ms'))} ms."
        )

    lines.extend(
        [
            "",
            "## Report Paragraph Draft",
            "",
            "The benchmark compares lightweight OpenCV motion extraction, MediaPipe Hands inference, "
            "and a hybrid strategy under different camera resolutions and target frame rates. "
            "The results can be used to identify the stable operating region where embedded visual "
            "interaction remains responsive while CPU and frame processing time stay within acceptable limits.",
            "",
        ]
    )
    return "\n".join(lines)


def pick_best(summaries, mode):
    candidates = [item for item in summaries if item.get("mode") == mode]
    if not candidates:
        return None

    def score(item):
        camera_fps = item.get("camera_fps") or 0
        loop_ms = item.get("loop_ms") or 9999
        cpu = item.get("cpu_percent") if item.get("cpu_percent") is not None else 75
        return camera_fps - loop_ms * 0.03 - cpu * 0.02

    return max(candidates, key=score)


def group_skip_summaries(summaries):
    groups = defaultdict(list)
    for item in summaries:
        if item.get("mode") != "hybrid":
            continue
        skip = to_float(item.get("infer_skip"))
        if skip is None:
            continue
        key = (
            item.get("mode", ""),
            item.get("width", ""),
            item.get("height", ""),
            item.get("target_fps", ""),
            int(skip),
            item.get("video_enabled", ""),
            item.get("jpeg_quality", ""),
        )
        groups[key].append(item)

    rows = []
    for (mode, width, height, target_fps, skip, video_enabled, jpeg_quality), items in groups.items():
        trial_items = [item for item in items if "_trial" in item["case"]]
        aggregate_items = trial_items or items
        row = {
            "group": f"{mode}_{width}x{height}_{target_fps}fps_skip{skip}_mjpeg{jpeg_quality}",
            "mode": mode,
            "width": width,
            "height": height,
            "target_fps": target_fps,
            "infer_skip": skip,
            "video_enabled": video_enabled,
            "jpeg_quality": jpeg_quality,
            "trials": len(aggregate_items),
            "cases": ";".join(item["case"] for item in aggregate_items),
            "ignored_cases": ";".join(item["case"] for item in items if item not in aggregate_items),
            "throttled_seen": any(item.get("throttled_seen") for item in aggregate_items),
            "throttled_current_seen": any(item.get("throttled_current_seen") for item in aggregate_items),
            "throttled_historical_seen": any(item.get("throttled_historical_seen") for item in aggregate_items),
        }

        current_flags = sorted(
            {
                flag
                for item in aggregate_items
                for flag in str(item.get("throttled_current_flags", "")).split(",")
                if flag
            }
        )
        historical_flags = sorted(
            {
                flag
                for item in aggregate_items
                for flag in str(item.get("throttled_historical_flags", "")).split(",")
                if flag
            }
        )
        row["throttled_current_flags"] = ",".join(current_flags)
        row["throttled_historical_flags"] = ",".join(historical_flags)

        for metric in (
            "camera_fps",
            "process_fps",
            "infer_fps",
            "mjpeg_fps",
            "loop_ms",
            "cpu_percent",
            "temp_c_mean",
            "temp_c_max",
            "inference_ms",
            "encode_ms",
        ):
            values = [item.get(metric) for item in aggregate_items if item.get(metric) is not None]
            if not values:
                row[f"{metric}_mean"] = None
                row[f"{metric}_std"] = None
                row[f"{metric}_min"] = None
                row[f"{metric}_max"] = None
                continue
            row[f"{metric}_mean"] = statistics.mean(values)
            row[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0
            row[f"{metric}_min"] = min(values)
            row[f"{metric}_max"] = max(values)

        # Max loop across all per-second samples, not just the max trial mean.
        loop_max_values = [item.get("loop_ms_max") for item in aggregate_items if item.get("loop_ms_max") is not None]
        row["loop_ms_sample_max"] = max(loop_max_values) if loop_max_values else row.get("loop_ms_max")

        rows.append(row)

    return sorted(rows, key=lambda row: row["infer_skip"], reverse=True)


def write_skip_summary_csv(path, rows):
    if not rows:
        return False

    fieldnames = [
        "group",
        "mode",
        "width",
        "height",
        "target_fps",
        "infer_skip",
        "video_enabled",
        "jpeg_quality",
        "trials",
        "camera_fps_mean",
        "camera_fps_std",
        "process_fps_mean",
        "process_fps_std",
        "infer_fps_mean",
        "infer_fps_std",
        "mjpeg_fps_mean",
        "mjpeg_fps_std",
        "loop_ms_mean",
        "loop_ms_std",
        "loop_ms_sample_max",
        "cpu_percent_mean",
        "cpu_percent_std",
        "temp_c_mean_mean",
        "temp_c_max_max",
        "inference_ms_mean",
        "encode_ms_mean",
        "throttled_seen",
        "throttled_current_seen",
        "throttled_historical_seen",
        "throttled_current_flags",
        "throttled_historical_flags",
        "cases",
        "ignored_cases",
    ]
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return True


def make_skip_markdown(rows):
    if not rows:
        return ""

    lines = [
        "",
        "## Skip Aggregation",
        "",
        "| Skip | Trials | Process FPS | Infer FPS | MJPEG FPS | Loop Avg ms | Loop Max ms | CPU % | Temp Max | Current Throttle | Historical Flags |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {skip} | {trials} | {process_fps} | {infer_fps} | {mjpeg_fps} | {loop_ms} | {loop_max} | "
            "{cpu} | {temp_max} | {current} | {historical} |".format(
                skip=row["infer_skip"],
                trials=row["trials"],
                process_fps=fmt(row.get("process_fps_mean")),
                infer_fps=fmt(row.get("infer_fps_mean")),
                mjpeg_fps=fmt(row.get("mjpeg_fps_mean")),
                loop_ms=fmt(row.get("loop_ms_mean")),
                loop_max=fmt(row.get("loop_ms_sample_max")),
                cpu=fmt(row.get("cpu_percent_mean")),
                temp_max=fmt(row.get("temp_c_max_max")),
                current="yes" if row.get("throttled_current_seen") else "no",
                historical=row.get("throttled_historical_flags") or "-",
            )
        )

    best = pick_best_skip(rows)
    if best:
        lines.extend(
            [
                "",
                "Suggested skip setting:",
                "",
                f"- Recommended enhanced mode: `infer_skip={best['infer_skip']}` "
                f"with process FPS {fmt(best.get('process_fps_mean'))}, "
                f"inference FPS {fmt(best.get('infer_fps_mean'))}, "
                f"and average loop time {fmt(best.get('loop_ms_mean'))} ms.",
            ]
        )
    return "\n".join(lines)


def pick_best_skip(rows):
    if not rows:
        return None

    balanced = [
        row
        for row in rows
        if (row.get("process_fps_mean") or 0) >= 15
        and (row.get("infer_fps_mean") or 0) >= 1.8
        and (row.get("loop_ms_mean") or 9999) <= 60
        and (row.get("loop_ms_sample_max") or 9999) <= 100
    ]
    if balanced:
        return max(
            balanced,
            key=lambda row: (
                row.get("infer_fps_mean") or 0,
                row.get("process_fps_mean") or 0,
                -(row.get("loop_ms_mean") or 9999),
            ),
        )

    def score(row):
        process_fps = row.get("process_fps_mean") or 0
        infer_fps = row.get("infer_fps_mean") or 0
        loop_ms = row.get("loop_ms_mean") or 9999
        loop_max = row.get("loop_ms_sample_max") or loop_ms
        cpu = row.get("cpu_percent_mean") or 50
        # Prefer smooth main loop first, then enough landmark refresh.
        return process_fps * 2.2 + infer_fps * 3.0 - loop_ms * 0.35 - loop_max * 0.06 - cpu * 0.04

    return max(rows, key=score)


def write_summary_csv(path, summaries):
    fieldnames = [
        "case",
        "file",
        "samples",
        "mode",
        "width",
        "height",
        "target_fps",
        "infer_skip",
        "model_complexity",
        "max_num_hands",
        "video_enabled",
        "jpeg_quality",
        "temp_c_mean",
        "temp_c_max",
        "throttled_seen",
        "throttled_current_seen",
        "throttled_historical_seen",
        "throttled_current_flags",
        "throttled_historical_flags",
    ] + METRICS
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in summaries:
            writer.writerow(item)


def try_make_plots(out_dir, summaries):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    by_mode = defaultdict(list)
    for item in summaries:
        by_mode[item.get("mode", "unknown")].append(item)

    for metric, ylabel, filename in [
        ("camera_fps", "Camera FPS", "camera_fps.png"),
        ("loop_ms", "Average Loop Time (ms)", "loop_time.png"),
        ("cpu_percent", "CPU Percent", "cpu_percent.png"),
        ("temp_c", "Temperature (C)", "temperature.png"),
        ("infer_fps", "Inference FPS", "infer_fps.png"),
        ("mjpeg_fps", "MJPEG FPS", "mjpeg_fps.png"),
    ]:
        plt.figure(figsize=(10, 5))
        any_points = False
        for mode, items in by_mode.items():
            x = []
            y = []
            for item in items:
                value = item.get(metric)
                if value is None:
                    continue
                x.append(item["case"])
                y.append(value)
            if not y:
                continue
            any_points = True
            plt.plot(x, y, marker="o", label=mode)

        if not any_points:
            plt.close()
            continue

        plt.ylabel(ylabel)
        plt.xticks(rotation=35, ha="right")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, filename), dpi=160)
        plt.close()

    return True


def try_make_combined_plot(out_dir, summaries):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    labels = [item["case"] for item in summaries]
    camera_fps = [item.get("camera_fps") for item in summaries]
    cpu = [item.get("cpu_percent") for item in summaries]
    temp = [item.get("temp_c_mean") for item in summaries]

    if not any(value is not None for value in camera_fps + cpu + temp):
        return False

    x = list(range(len(labels)))
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(x, [value or 0 for value in camera_fps], marker="o", label="Camera FPS", color="#1f77b4")
    ax1.set_ylabel("FPS")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(x, [value or 0 for value in cpu], marker="s", label="CPU %", color="#ff7f0e")
    ax2.plot(x, [value or 0 for value in temp], marker="^", label="Temp C", color="#d62728")
    ax2.set_ylabel("CPU % / Temperature C")

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=35, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "cpu_temp_fps.png"), dpi=160)
    plt.close(fig)
    return True


def try_make_skip_plots(out_dir, rows):
    if not rows:
        return False
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    rows = sorted(rows, key=lambda row: row["infer_skip"], reverse=True)
    labels = [f"skip{row['infer_skip']}" for row in rows]
    x = list(range(len(labels)))

    def values(key):
        return [row.get(key) or 0 for row in rows]

    def errors(key):
        return [row.get(key) or 0 for row in rows]

    plt.figure(figsize=(8, 4.8))
    plt.errorbar(x, values("process_fps_mean"), yerr=errors("process_fps_std"), marker="o", capsize=4, label="Process FPS")
    plt.errorbar(x, values("mjpeg_fps_mean"), yerr=errors("mjpeg_fps_std"), marker="s", capsize=4, label="MJPEG FPS")
    plt.errorbar(x, values("infer_fps_mean"), yerr=errors("infer_fps_std"), marker="^", capsize=4, label="Infer FPS")
    plt.xticks(x, labels)
    plt.xlabel("MediaPipe infer_skip")
    plt.ylabel("FPS")
    plt.title("FPS vs MediaPipe Inference Frequency")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "skip_vs_fps.png"), dpi=180)
    plt.close()

    plt.figure(figsize=(8, 4.8))
    plt.errorbar(x, values("loop_ms_mean"), yerr=errors("loop_ms_std"), marker="o", capsize=4, label="Average Loop ms")
    plt.plot(x, values("loop_ms_sample_max"), marker="x", linestyle="--", label="Max Sample Loop ms")
    plt.axhline(33.3, color="#999999", linestyle=":", linewidth=1.5, label="30 FPS budget (33.3 ms)")
    plt.axhline(66.7, color="#cccccc", linestyle=":", linewidth=1.2, label="15 FPS budget (66.7 ms)")
    plt.xticks(x, labels)
    plt.xlabel("MediaPipe infer_skip")
    plt.ylabel("Loop Time (ms)")
    plt.title("Loop Time vs MediaPipe Inference Frequency")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "skip_vs_loop.png"), dpi=180)
    plt.close()

    fig, ax1 = plt.subplots(figsize=(8, 4.8))
    ax1.plot(x, values("temp_c_max_max"), marker="o", color="#d62728", label="Max Temp C")
    ax1.set_ylabel("Temperature (C)")
    ax1.set_xlabel("MediaPipe infer_skip")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.errorbar(x, values("cpu_percent_mean"), yerr=errors("cpu_percent_std"), marker="s", capsize=4, color="#ff7f0e", label="CPU %")
    ax2.set_ylabel("CPU Percent")

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")
    plt.title("Temperature and CPU vs MediaPipe Inference Frequency")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "skip_vs_temp_cpu.png"), dpi=180)
    plt.close(fig)

    return True


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    files = expand_inputs(args.inputs)
    summaries = [summarize_file(path) for path in files if os.path.exists(path)]
    if not summaries:
        raise SystemExit("No CSV files found.")

    summary_csv = os.path.join(args.out_dir, "performance_summary.csv")
    write_summary_csv(summary_csv, summaries)
    skip_rows = group_skip_summaries(summaries)
    skip_summary_csv = os.path.join(args.out_dir, "skip_summary.csv")
    wrote_skip_summary = write_skip_summary_csv(skip_summary_csv, skip_rows)

    markdown_path = os.path.join(args.out_dir, args.markdown)
    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write(make_markdown(summaries))
        skip_markdown = make_skip_markdown(skip_rows)
        if skip_markdown:
            markdown_file.write(skip_markdown)
            markdown_file.write("\n")

    made_plots = False
    if not args.no_plots:
        made_plots = try_make_plots(args.out_dir, summaries)
        made_plots = try_make_combined_plot(args.out_dir, summaries) or made_plots
        made_plots = try_make_skip_plots(args.out_dir, skip_rows) or made_plots

    print(f"summary csv: {summary_csv}")
    if wrote_skip_summary:
        print(f"skip summary csv: {skip_summary_csv}")
    print(f"markdown: {markdown_path}")
    print(f"plots: {'created' if made_plots else 'skipped'}")


if __name__ == "__main__":
    main()
