# Test Day Checklist

Use this checklist when the Raspberry Pi is available.

## 1. Upload Scripts

From Windows PowerShell in this project directory:

```powershell
scp .\raspberry_perf_benchmark.py pi@10.196.36.213:/home/pi/
scp .\run_perf_suite_csi.sh pi@10.196.36.213:/home/pi/
scp .\run_perf_suite_usb.sh pi@10.196.36.213:/home/pi/
scp .\run_perf_suite_mediapipe_usb.sh pi@10.196.36.213:/home/pi/
```

If using `raspberrypi.local`:

```powershell
scp .\raspberry_perf_benchmark.py pi@raspberrypi.local:/home/pi/
scp .\run_perf_suite_csi.sh pi@raspberrypi.local:/home/pi/
scp .\run_perf_suite_usb.sh pi@raspberrypi.local:/home/pi/
scp .\run_perf_suite_mediapipe_usb.sh pi@raspberrypi.local:/home/pi/
```

## 2. Prepare Raspberry Pi

```bash
sudo modprobe bcm2835-v4l2
chmod +x /home/pi/run_perf_suite_csi.sh /home/pi/run_perf_suite_usb.sh /home/pi/run_perf_suite_mediapipe_usb.sh
ls /dev/video*
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "import psutil; print(psutil.__version__)" || echo "psutil missing; CPU/memory columns will be blank"
python3 -c "import mediapipe as mp; print(mp.__version__)" || echo "mediapipe missing; MediaPipe tests will be skipped"
vcgencmd measure_temp || echo "vcgencmd unavailable; temperature columns will be blank"
vcgencmd get_throttled || echo "vcgencmd unavailable; throttling columns will be unavailable"
```

## 3. Quick Smoke Test

Run one short OpenCV test first:

```bash
python3 /home/pi/raspberry_perf_benchmark.py --mode opencv --width 320 --height 240 --fps 10 --duration 5 --warmup 1 --csv smoke_opencv.csv
```

If it prints per-second rows and saves CSV, continue.

## 4. Run Full Suite

Short suite for classroom debugging:

```bash
RUN_ID=run_002_temp_added DURATION=10 WARMUP=2 /home/pi/run_perf_suite_usb.sh
```

Formal USB suite:

```bash
RUN_ID=run_002_temp_added DURATION=30 WARMUP=3 /home/pi/run_perf_suite_usb.sh
```

Formal CSI suite:

```bash
RUN_ID=run_002_temp_added DURATION=30 WARMUP=3 /home/pi/run_perf_suite_csi.sh
```

If the USB camera is not `/dev/video0`, pass another index:

```bash
CAMERA_INDEX=1 RUN_ID=run_002_temp_added DURATION=30 WARMUP=3 /home/pi/run_perf_suite_usb.sh
```

MediaPipe-only USB suite:

```bash
CAMERA_INDEX=1 RUN_ID=run_006_mediapipe_test DURATION=10 WARMUP=8 /home/pi/run_perf_suite_mediapipe_usb.sh
```

Results are saved in:

```text
/home/pi/perf_results_usb/<RUN_ID>
/home/pi/perf_results_csi/<RUN_ID>
```

## 5. Copy CSV Results Back

From Windows PowerShell:

```powershell
mkdir .\perf_results
scp pi@10.196.36.213:/home/pi/perf_results_usb/run_002_temp_added/*.csv .\perf_results\
scp pi@10.196.36.213:/home/pi/perf_results_csi/run_002_temp_added/*.csv .\perf_results\
```

If you let the script auto-generate `RUN_ID`, read the printed `OUT_DIR=...` line and use that directory name when copying files.

## 6. Analyze On Windows

```powershell
python .\analyze_perf_results.py .\perf_results\*.csv --out-dir .\perf_report
```

Outputs:

```text
perf_report/performance_summary.csv
perf_report/performance_summary.md
perf_report/*.png
```

If matplotlib is not installed, run:

```powershell
python .\analyze_perf_results.py .\perf_results\*.csv --out-dir .\perf_report --no-plots
```

## 7. What To Photograph Or Screenshot

- Terminal running the benchmark.
- `perf_results` CSV file list.
- `performance_summary.md`.
- Generated charts if available.
- Browser demo running Raspberry mode with MJPEG background.

## 8. First Interpretation Rule

Prioritize stable configurations:

```text
camera_fps close to target FPS
avg_loop_ms below frame interval
p95_loop_ms not much larger than avg_loop_ms
CPU preferably below 70%
temp_c preferably stable
throttled_raw should remain 0x0
```

For 10 FPS, one frame interval is about 100 ms.
