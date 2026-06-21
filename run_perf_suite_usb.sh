#!/usr/bin/env bash
set -u

BENCHMARK_SCRIPT="${BENCHMARK_SCRIPT:-/home/pi/raspberry_perf_benchmark.py}"
BASE_OUT_DIR="${BASE_OUT_DIR:-/home/pi/perf_results_usb}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
OUT_DIR="${OUT_DIR:-$BASE_OUT_DIR/$RUN_ID}"
DURATION="${DURATION:-30}"
WARMUP="${WARMUP:-3}"
CAMERA_INDEX="${CAMERA_INDEX:-0}"

mkdir -p "$OUT_DIR"

run_case() {
  name="$1"
  shift

  echo
  echo "===== USB: $name ====="
  echo "python3 $BENCHMARK_SCRIPT --camera $CAMERA_INDEX $* --duration $DURATION --warmup $WARMUP --benchmark-csv $OUT_DIR/$name.csv"
  python3 "$BENCHMARK_SCRIPT" --camera "$CAMERA_INDEX" "$@" --duration "$DURATION" --warmup "$WARMUP" --benchmark-csv "$OUT_DIR/$name.csv"
}

echo "Preparing USB camera benchmark..."
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
ls -l /dev/video* || true

echo "Checking optional dependencies..."
python3 - <<'PY'
for name in ("cv2", "psutil", "mediapipe"):
    try:
        module = __import__(name)
        print(f"{name}: ok {getattr(module, '__version__', '')}")
    except Exception as exc:
        print(f"{name}: unavailable ({exc})")
PY

run_case opencv_usb_160x120_5fps \
  --mode opencv --width 160 --height 120 --fps 5

run_case opencv_usb_320x240_5fps \
  --mode opencv --width 320 --height 240 --fps 5

run_case opencv_usb_320x240_10fps \
  --mode opencv --width 320 --height 240 --fps 10

run_case opencv_usb_480x360_10fps \
  --mode opencv --width 480 --height 360 --fps 10

run_case opencv_usb_640x480_10fps \
  --mode opencv --width 640 --height 480 --fps 10

run_case opencv_usb_640x480_15fps \
  --mode opencv --width 640 --height 480 --fps 15

run_case opencv_usb_640x480_30fps \
  --mode opencv --width 640 --height 480 --fps 30

run_case opencv_usb_640x480_10fps_jpeg50 \
  --mode opencv --width 640 --height 480 --fps 10 --mjpeg --jpeg-quality 50

run_case opencv_usb_640x480_10fps_jpeg70 \
  --mode opencv --width 640 --height 480 --fps 10 --mjpeg --jpeg-quality 70

run_case opencv_usb_640x480_10fps_jpeg90 \
  --mode opencv --width 640 --height 480 --fps 10 --mjpeg --jpeg-quality 90

if python3 - <<'PY'
try:
    import mediapipe  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
then
  run_case mp_usb_320x240_5fps \
    --mode mediapipe --width 320 --height 240 --fps 5 --model-complexity 0 --max-num-hands 1 --infer-skip 1

  run_case mp_usb_320x240_10fps \
    --mode mediapipe --width 320 --height 240 --fps 10 --model-complexity 0 --max-num-hands 1 --infer-skip 1

  run_case hybrid_usb_320x240_10fps_skip3 \
    --mode hybrid --width 320 --height 240 --fps 10 --infer-skip 3 --model-complexity 0 --max-num-hands 1

  run_case hybrid_usb_320x240_10fps_skip5 \
    --mode hybrid --width 320 --height 240 --fps 10 --infer-skip 5 --model-complexity 0 --max-num-hands 1

  run_case hybrid_usb_480x360_10fps_skip3 \
    --mode hybrid --width 480 --height 360 --fps 10 --infer-skip 3 --model-complexity 0 --max-num-hands 1

  run_case hybrid_usb_640x480_10fps_skip3 \
    --mode hybrid --width 640 --height 480 --fps 10 --infer-skip 3 --model-complexity 0 --max-num-hands 1
else
  echo
  echo "MediaPipe is not installed; skipped USB MediaPipe and hybrid cases."
fi

echo
echo "USB suite done. CSV files saved to: $OUT_DIR"
