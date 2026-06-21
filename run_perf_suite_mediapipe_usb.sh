#!/usr/bin/env bash
set -u

BENCHMARK_SCRIPT="${BENCHMARK_SCRIPT:-/home/pi/raspberry_perf_benchmark.py}"
BASE_OUT_DIR="${BASE_OUT_DIR:-/home/pi/perf_results_usb}"
RUN_ID="${RUN_ID:-run_006_mediapipe_test}"
OUT_DIR="${OUT_DIR:-$BASE_OUT_DIR/$RUN_ID}"
DURATION="${DURATION:-10}"
WARMUP="${WARMUP:-8}"
CAMERA_INDEX="${CAMERA_INDEX:-1}"

mkdir -p "$OUT_DIR"

run_case() {
  name="$1"
  shift

  echo
  echo "===== MediaPipe USB: $name ====="
  echo "python3 $BENCHMARK_SCRIPT --camera $CAMERA_INDEX $* --duration $DURATION --warmup $WARMUP --benchmark-csv $OUT_DIR/$name.csv"
  python3 "$BENCHMARK_SCRIPT" --camera "$CAMERA_INDEX" "$@" --duration "$DURATION" --warmup "$WARMUP" --benchmark-csv "$OUT_DIR/$name.csv"
}

echo "Preparing USB MediaPipe benchmark..."
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
ls -l /dev/video* || true

if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl -d "/dev/video$CAMERA_INDEX" --set-ctrl=power_line_frequency=0 || true
fi

python3 - <<'PY'
import cv2
print("cv2:", cv2.__version__)
try:
    import psutil
    print("psutil:", psutil.__version__)
except Exception as exc:
    print("psutil unavailable:", exc)
try:
    import mediapipe as mp
    print("mediapipe:", getattr(mp, "__version__", "unknown"))
except ImportError as exc:
    print("mediapipe unavailable:", exc)
    raise SystemExit(1)
PY

run_case mediapipe_usb_320x240_10fps_skip5 \
  --mode mediapipe --width 320 --height 240 --fps 10 --infer-skip 5 --model-complexity 0 --max-num-hands 1

run_case mediapipe_usb_320x240_10fps_skip3 \
  --mode mediapipe --width 320 --height 240 --fps 10 --infer-skip 3 --model-complexity 0 --max-num-hands 1

run_case mediapipe_usb_320x240_10fps_skip1 \
  --mode mediapipe --width 320 --height 240 --fps 10 --infer-skip 1 --model-complexity 0 --max-num-hands 1

run_case hybrid_usb_320x240_10fps_skip5 \
  --mode hybrid --width 320 --height 240 --fps 10 --infer-skip 5 --model-complexity 0 --max-num-hands 1

run_case hybrid_usb_320x240_10fps_skip3 \
  --mode hybrid --width 320 --height 240 --fps 10 --infer-skip 3 --model-complexity 0 --max-num-hands 1

echo
echo "MediaPipe USB suite done. CSV files saved to: $OUT_DIR"
