import argparse
import csv
import importlib
import inspect
import math
import os
import statistics
import subprocess
import time

import cv2


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark Raspberry Pi camera, OpenCV motion detection, MJPEG encoding, and optional MediaPipe Hands."
    )
    parser.add_argument("--benchmark", action="store_true", help="Compatibility flag; this script always benchmarks.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index, for example USB camera /dev/video0.")
    parser.add_argument("--width", type=int, default=320, help="Requested camera frame width.")
    parser.add_argument("--height", type=int, default=240, help="Requested camera frame height.")
    parser.add_argument("--fps", type=float, default=10.0, help="Target capture loop FPS.")
    parser.add_argument("--duration", type=float, default=30.0, help="Benchmark recording duration in seconds.")
    parser.add_argument("--warmup", type=float, default=3.0, help="Warmup seconds before recording metrics.")
    parser.add_argument(
        "--mode",
        choices=("opencv", "mediapipe", "hybrid"),
        default="opencv",
        help="opencv: frame-difference only; mediapipe: Hands only; hybrid: OpenCV every frame + Hands every N frames.",
    )
    parser.add_argument("--infer-skip", "--skip", dest="infer_skip", type=int, default=3, help="Run MediaPipe once every N frames.")
    parser.add_argument("--model-complexity", type=int, default=0, help="MediaPipe Hands model_complexity.")
    parser.add_argument("--max-num-hands", type=int, default=1, help="MediaPipe max_num_hands.")
    parser.add_argument("--min-area", type=float, default=1200.0, help="OpenCV motion threshold area.")
    parser.add_argument("--min-scale", type=float, default=0.6, help="Minimum scale mapped from OpenCV area.")
    parser.add_argument("--max-scale", type=float, default=2.0, help="Maximum scale mapped from OpenCV area.")
    parser.add_argument("--max-area", type=float, default=22000.0, help="OpenCV area that maps to maximum scale.")
    parser.add_argument("--mjpeg", dest="video_enabled", action="store_true", help="Benchmark MJPEG/JPEG encoding cost.")
    parser.add_argument("--no-video", dest="video_enabled", action="store_false", help="Disable MJPEG/JPEG encoding benchmark.")
    parser.set_defaults(video_enabled=False)
    parser.add_argument("--jpeg-quality", type=int, default=70, help="JPEG quality used when video is enabled.")
    parser.add_argument("--benchmark-csv", "--csv", dest="benchmark_csv", default="benchmark_results.csv", help="CSV output path.")
    return parser.parse_args()


def optional_module(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def mean(values):
    values = [value for value in values if value is not None]
    if not values:
        return 0.0
    return statistics.mean(values)


def mean_ms(values):
    return round(mean(values) * 1000, 3)


def safe_div(numerator, denominator):
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def get_memory_mb(psutil_module):
    if not psutil_module:
        return ""
    process = psutil_module.Process(os.getpid())
    return round(process.memory_info().rss / (1024 * 1024), 1)


def run_vcgencmd(args):
    try:
        result = subprocess.run(
            ["vcgencmd"] + args,
            check=True,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def read_thermal_state():
    temp_output = run_vcgencmd(["measure_temp"])
    throttled_output = run_vcgencmd(["get_throttled"])

    temp_c = ""
    if temp_output and temp_output.startswith("temp="):
        temp_text = temp_output.split("=", 1)[1].split("'", 1)[0]
        try:
            temp_c = round(float(temp_text), 1)
        except ValueError:
            temp_c = ""

    throttled_raw = ""
    throttled_flags = "unavailable"
    if throttled_output and throttled_output.startswith("throttled="):
        throttled_raw = throttled_output.split("=", 1)[1].strip()
        try:
            throttled_value = int(throttled_raw, 16)
            throttled_flags = "ok" if throttled_value == 0 else "throttled"
        except ValueError:
            throttled_flags = "unknown"

    return temp_c, throttled_raw, throttled_flags


def clamp(value, min_value, max_value):
    return min(max(value, min_value), max_value)


def map_area_to_scale(area, args):
    if area < args.min_area:
        return args.min_scale
    normalized = (area - args.min_area) / max(1.0, args.max_area - args.min_area)
    normalized = clamp(normalized, 0.0, 1.0)
    return args.min_scale + normalized * (args.max_scale - args.min_scale)


def run_opencv_motion(frame, previous_gray, min_area):
    preprocess_started = time.time()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    preprocess_elapsed = time.time() - preprocess_started

    inference_started = time.time()
    area = 0.0
    motion = False
    if previous_gray is not None:
        diff = cv2.absdiff(previous_gray, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            area = float(cv2.contourArea(max(contours, key=cv2.contourArea)))
            motion = area >= min_area
    inference_elapsed = time.time() - inference_started
    return gray, area, motion, preprocess_elapsed, inference_elapsed


def make_mediapipe_hands(args):
    mp = optional_module("mediapipe")
    if not mp:
        raise RuntimeError("MediaPipe is not installed. Run --mode opencv or install mediapipe first.")

    hands_kwargs = {
        "static_image_mode": False,
        "max_num_hands": args.max_num_hands,
        "min_detection_confidence": 0.5,
        "min_tracking_confidence": 0.5,
    }

    try:
        signature = inspect.signature(mp.solutions.hands.Hands)
        if "model_complexity" in signature.parameters:
            hands_kwargs["model_complexity"] = args.model_complexity
    except (TypeError, ValueError):
        hands_kwargs["model_complexity"] = args.model_complexity

    try:
        return mp.solutions.hands.Hands(**hands_kwargs)
    except TypeError as error:
        if "model_complexity" not in hands_kwargs:
            raise
        print(f"MediaPipe Hands does not accept model_complexity; retrying without it ({error})")
        hands_kwargs.pop("model_complexity", None)
        return mp.solutions.hands.Hands(**hands_kwargs)


def distance3(point_a, point_b):
    dx = point_a.x - point_b.x
    dy = point_a.y - point_b.y
    dz = point_a.z - point_b.z
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def run_mediapipe(frame, hands):
    preprocess_started = time.time()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    preprocess_elapsed = time.time() - preprocess_started

    inference_started = time.time()
    results = hands.process(rgb)
    inference_elapsed = time.time() - inference_started

    hand_detected = bool(results.multi_hand_landmarks)
    landmark_count = 0
    pinch_distance = 0.0
    if hand_detected:
        landmarks = results.multi_hand_landmarks[0].landmark
        landmark_count = len(landmarks)
        if len(landmarks) > 8:
            pinch_distance = distance3(landmarks[4], landmarks[8])

    return {
        "preprocess_elapsed": preprocess_elapsed,
        "inference_elapsed": inference_elapsed,
        "hand_detected": hand_detected,
        "landmark_count": landmark_count,
        "pinch_distance": pinch_distance,
        "confidence": "",
    }


def make_fieldnames():
    return [
        "timestamp",
        "second",
        "camera_index",
        "width",
        "height",
        "target_fps",
        "mode",
        "infer_skip",
        "model_complexity",
        "max_num_hands",
        "jpeg_quality",
        "video_enabled",
        "camera_fps",
        "process_fps",
        "infer_fps",
        "ws_fps",
        "mjpeg_fps",
        "cpu_percent",
        "memory_mb",
        "temp_c",
        "throttled_raw",
        "throttled_flags",
        "read_ms",
        "preprocess_ms",
        "inference_ms",
        "encode_ms",
        "loop_ms",
        "area",
        "scale",
        "motion",
        "clients",
        "frame_shape",
        "hand_detected",
        "landmark_count",
        "pinch_distance",
        "confidence",
    ]


def empty_bucket():
    return {
        "camera_frames": 0,
        "process_runs": 0,
        "infer_runs": 0,
        "ws_messages": 0,
        "mjpeg_frames": 0,
        "read_times": [],
        "preprocess_times": [],
        "inference_times": [],
        "encode_times": [],
        "loop_times": [],
        "areas": [],
        "scales": [],
        "motion_hits": 0,
        "hand_hits": 0,
        "landmark_counts": [],
        "pinch_distances": [],
        "frame_shape": "",
    }


def bucket_row(bucket, args, psutil_module, second_index, interval):
    infer_runs = bucket["infer_runs"]
    temp_c, throttled_raw, throttled_flags = read_thermal_state()
    row = {
        "timestamp": round(time.time(), 3),
        "second": second_index,
        "camera_index": args.camera,
        "width": args.width,
        "height": args.height,
        "target_fps": args.fps,
        "mode": args.mode,
        "infer_skip": args.infer_skip,
        "model_complexity": args.model_complexity,
        "max_num_hands": args.max_num_hands,
        "jpeg_quality": args.jpeg_quality,
        "video_enabled": args.video_enabled,
        "camera_fps": round(safe_div(bucket["camera_frames"], interval), 3),
        "process_fps": round(safe_div(bucket["process_runs"], interval), 3),
        "infer_fps": round(safe_div(infer_runs, interval), 3),
        "ws_fps": round(safe_div(bucket["ws_messages"], interval), 3),
        "mjpeg_fps": round(safe_div(bucket["mjpeg_frames"], interval), 3),
        "cpu_percent": psutil_module.cpu_percent(interval=None) if psutil_module else "",
        "memory_mb": get_memory_mb(psutil_module),
        "temp_c": temp_c,
        "throttled_raw": throttled_raw,
        "throttled_flags": throttled_flags,
        "read_ms": mean_ms(bucket["read_times"]),
        "preprocess_ms": mean_ms(bucket["preprocess_times"]),
        "inference_ms": mean_ms(bucket["inference_times"]),
        "encode_ms": mean_ms(bucket["encode_times"]),
        "loop_ms": mean_ms(bucket["loop_times"]),
        "area": round(mean(bucket["areas"]), 3),
        "scale": round(mean(bucket["scales"]), 3),
        "motion": round(safe_div(bucket["motion_hits"], max(1, bucket["process_runs"])), 3),
        "clients": 0,
        "frame_shape": bucket["frame_shape"],
        "hand_detected": round(safe_div(bucket["hand_hits"], max(1, infer_runs)), 3) if infer_runs else 0,
        "landmark_count": round(mean(bucket["landmark_counts"]), 3),
        "pinch_distance": round(mean(bucket["pinch_distances"]), 6),
        "confidence": "",
    }
    return row


def run_benchmark(args):
    psutil_module = optional_module("psutil")
    if psutil_module:
        psutil_module.cpu_percent(interval=None)

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    if not cap.isOpened():
        raise RuntimeError(
            "Could not open camera. Check /dev/video*, run sudo modprobe bcm2835-v4l2 for CSI legacy cameras, or use --camera N."
        )

    hands = None
    if args.mode in ("mediapipe", "hybrid"):
        hands = make_mediapipe_hands(args)

    os.makedirs(os.path.dirname(args.benchmark_csv) or ".", exist_ok=True)
    fieldnames = make_fieldnames()
    previous_gray = None
    frame_index = 0
    frame_delay = 1.0 / max(1.0, args.fps)
    started_at = time.time()
    record_started_at = started_at + max(0.0, args.warmup)
    end_at = record_started_at + max(0.0, args.duration)
    next_report_at = record_started_at + 1.0
    second_index = 0
    bucket = empty_bucket()
    last_mp = {
        "hand_detected": False,
        "landmark_count": 0,
        "pinch_distance": 0.0,
        "confidence": "",
    }

    print(
        f"benchmark mode={args.mode}, camera={args.camera}, size={args.width}x{args.height}, "
        f"target_fps={args.fps}, infer_skip={args.infer_skip}, video={args.video_enabled}, "
        f"duration={args.duration}s, warmup={args.warmup}s"
    )

    with open(args.benchmark_csv, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        try:
            while time.time() < end_at:
                loop_started = time.time()
                read_started = time.time()
                ok, frame = cap.read()
                read_elapsed = time.time() - read_started
                if not ok or frame is None:
                    time.sleep(frame_delay)
                    continue

                frame_index += 1
                recording = time.time() >= record_started_at
                frame_shape = "x".join(str(part) for part in frame.shape)
                area = 0.0
                scale = args.min_scale
                motion = False

                if args.mode in ("opencv", "hybrid"):
                    previous_gray, area, motion, preprocess_elapsed, inference_elapsed = run_opencv_motion(
                        frame, previous_gray, args.min_area
                    )
                    scale = map_area_to_scale(area, args)
                    process_ran = True
                    if recording:
                        bucket["preprocess_times"].append(preprocess_elapsed)
                        bucket["inference_times"].append(inference_elapsed)
                else:
                    process_ran = True
                    previous_gray = None

                should_infer = args.mode in ("mediapipe", "hybrid") and frame_index % max(1, args.infer_skip) == 0
                if should_infer and hands:
                    mp_result = run_mediapipe(frame, hands)
                    last_mp = {
                        "hand_detected": mp_result["hand_detected"],
                        "landmark_count": mp_result["landmark_count"],
                        "pinch_distance": mp_result["pinch_distance"],
                        "confidence": mp_result["confidence"],
                    }
                    if args.mode == "mediapipe":
                        scale = clamp(0.4 + last_mp["pinch_distance"] * 6.0, args.min_scale, args.max_scale)
                    if recording:
                        bucket["infer_runs"] += 1
                        bucket["preprocess_times"].append(mp_result["preprocess_elapsed"])
                        bucket["inference_times"].append(mp_result["inference_elapsed"])
                        bucket["hand_hits"] += int(last_mp["hand_detected"])
                        bucket["landmark_counts"].append(last_mp["landmark_count"])
                        bucket["pinch_distances"].append(last_mp["pinch_distance"])

                if args.mode == "mediapipe":
                    scale = clamp(0.4 + last_mp["pinch_distance"] * 6.0, args.min_scale, args.max_scale)
                    if recording and not should_infer:
                        bucket["hand_hits"] += int(last_mp["hand_detected"])
                        bucket["landmark_counts"].append(last_mp["landmark_count"])
                        bucket["pinch_distances"].append(last_mp["pinch_distance"])

                if args.video_enabled:
                    encode_started = time.time()
                    quality = clamp(args.jpeg_quality, 1, 100)
                    ok, _ = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
                    encode_elapsed = time.time() - encode_started
                    if recording and ok:
                        bucket["mjpeg_frames"] += 1
                        bucket["encode_times"].append(encode_elapsed)

                loop_elapsed = time.time() - loop_started
                if recording:
                    bucket["camera_frames"] += 1
                    bucket["process_runs"] += int(process_ran)
                    bucket["ws_messages"] += 1
                    bucket["read_times"].append(read_elapsed)
                    bucket["loop_times"].append(loop_elapsed)
                    bucket["areas"].append(area)
                    bucket["scales"].append(scale)
                    bucket["motion_hits"] += int(motion)
                    bucket["frame_shape"] = frame_shape

                now = time.time()
                if recording and now >= next_report_at:
                    interval = max(0.001, now - (next_report_at - 1.0))
                    second_index += 1
                    row = bucket_row(bucket, args, psutil_module, second_index, interval)
                    writer.writerow(row)
                    csv_file.flush()
                    print(
                        f"{second_index:03d}s camera={row['camera_fps']} process={row['process_fps']} "
                        f"infer={row['infer_fps']} mjpeg={row['mjpeg_fps']} cpu={row['cpu_percent']} "
                        f"temp={row['temp_c']}C throttled={row['throttled_raw']} "
                        f"loop_ms={row['loop_ms']} shape={row['frame_shape']}"
                    )
                    bucket = empty_bucket()
                    next_report_at += 1.0

                sleep_time = frame_delay - (time.time() - loop_started)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            cap.release()
            if hands:
                hands.close()

    print(f"benchmark saved: {args.benchmark_csv}")


if __name__ == "__main__":
    run_benchmark(parse_args())
