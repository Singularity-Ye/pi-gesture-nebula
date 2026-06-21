#!/usr/bin/env bash
set -u

BENCHMARK_SCRIPT="${BENCHMARK_SCRIPT:-/home/pi/raspberry_perf_benchmark.py}"
BASE_OUT_DIR="${BASE_OUT_DIR:-/home/pi/perf_results_csi}"
RUN_ID="${RUN_ID:-run_010_csi_320x240_30fps_hybrid_matrix}"
OUT_DIR="${OUT_DIR:-$BASE_OUT_DIR/$RUN_ID}"
DURATION="${DURATION:-15}"
WARMUP="${WARMUP:-5}"
CAMERA_INDEX="${CAMERA_INDEX:-0}"
WIDTH="${WIDTH:-320}"
HEIGHT="${HEIGHT:-240}"
TARGET_FPS="${TARGET_FPS:-30}"
JPEG_QUALITY="${JPEG_QUALITY:-70}"

mkdir -p "$OUT_DIR"

prepare_camera() {
  echo "Preparing legacy CSI camera through V4L2..."
  sudo modprobe bcm2835-v4l2 || true
  ls -l /dev/video* || true

  if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl -d "/dev/video$CAMERA_INDEX" \
      --set-fmt-video="width=$WIDTH,height=$HEIGHT,pixelformat=YUYV" \
      --set-parm="$TARGET_FPS" || true
  fi
}

check_dependencies() {
  echo "Checking dependencies..."
  python3 - <<'PY'
import cv2
print("cv2:", getattr(cv2, "__version__", "unknown"))
try:
    import psutil
    print("psutil:", getattr(psutil, "__version__", "unknown"))
except Exception as exc:
    print("psutil unavailable:", exc)
try:
    import mediapipe as mp
    print("mediapipe:", getattr(mp, "__version__", "unknown"))
except Exception as exc:
    print("mediapipe unavailable:", exc)
PY
}

has_mediapipe() {
  python3 - <<'PY'
try:
    import mediapipe  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
}

run_case() {
  name="$1"
  shift

  echo
  echo "===== CSI 30fps matrix: $name ====="
  echo "python3 $BENCHMARK_SCRIPT --camera $CAMERA_INDEX $* --duration $DURATION --warmup $WARMUP --benchmark-csv $OUT_DIR/$name.csv"
  python3 "$BENCHMARK_SCRIPT" \
    --camera "$CAMERA_INDEX" \
    "$@" \
    --duration "$DURATION" \
    --warmup "$WARMUP" \
    --benchmark-csv "$OUT_DIR/$name.csv"
}

echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
echo "camera=/dev/video$CAMERA_INDEX size=${WIDTH}x${HEIGHT} target_fps=$TARGET_FPS jpeg_quality=$JPEG_QUALITY"

prepare_camera
check_dependencies

run_case opencv_csi_${WIDTH}x${HEIGHT}_${TARGET_FPS}fps_no_video \
  --mode opencv --width "$WIDTH" --height "$HEIGHT" --fps "$TARGET_FPS" --no-video

run_case opencv_csi_${WIDTH}x${HEIGHT}_${TARGET_FPS}fps_mjpeg${JPEG_QUALITY} \
  --mode opencv --width "$WIDTH" --height "$HEIGHT" --fps "$TARGET_FPS" --mjpeg --jpeg-quality "$JPEG_QUALITY"

if has_mediapipe; then
  for skip in 15 10 5 3 2 1; do
    run_case hybrid_csi_${WIDTH}x${HEIGHT}_${TARGET_FPS}fps_skip${skip}_mjpeg${JPEG_QUALITY} \
      --mode hybrid \
      --width "$WIDTH" \
      --height "$HEIGHT" \
      --fps "$TARGET_FPS" \
      --infer-skip "$skip" \
      --model-complexity 0 \
      --max-num-hands 1 \
      --mjpeg \
      --jpeg-quality "$JPEG_QUALITY"
  done
else
  echo
  echo "MediaPipe is not installed; skipped hybrid infer_skip matrix."
fi

echo
echo "CSI 30fps matrix done. CSV files saved to: $OUT_DIR"
