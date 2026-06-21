# Raspberry Pi Vision Performance Experiment

This experiment measures the practical boundary of Raspberry Pi camera-based gesture control.

The goal is not to prove that the Pi can always run a heavy model. The goal is to find a stable parameter region:

```text
resolution + target FPS + inference frequency + model complexity
-> camera FPS + OpenCV FPS + MediaPipe FPS + CPU + latency-related loop time
```

## 1. Copy Benchmark Script To Raspberry Pi

From Windows PowerShell in this project directory:

```powershell
scp .\raspberry_perf_benchmark.py pi@10.196.36.213:/home/pi/
scp .\run_perf_suite_csi.sh pi@10.196.36.213:/home/pi/
scp .\run_perf_suite_usb.sh pi@10.196.36.213:/home/pi/
```

On the Raspberry Pi:

```bash
sudo modprobe bcm2835-v4l2
ls /dev/video*
```

Optional CPU/memory metrics:

```bash
python3 -m pip install psutil
```

If `psutil` is not installed, the benchmark still runs; CPU and memory columns are left blank.

## 2. Baseline OpenCV Test

This measures the current lightweight motion-area route.

```bash
python3 /home/pi/raspberry_perf_benchmark.py --mode opencv --width 160 --height 120 --fps 5 --duration 30 --csv opencv_160x120_5fps.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode opencv --width 320 --height 240 --fps 10 --duration 30 --csv opencv_320x240_10fps.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode opencv --width 480 --height 360 --fps 10 --duration 30 --csv opencv_480x360_10fps.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode opencv --width 640 --height 480 --fps 10 --duration 30 --csv opencv_640x480_10fps.csv
```

## 3. MJPEG Encoding Pressure Test

This estimates the cost of also producing a browser background video.

```bash
python3 /home/pi/raspberry_perf_benchmark.py --mode opencv --width 480 --height 360 --fps 10 --mjpeg --jpeg-quality 50 --duration 30 --csv opencv_480x360_10fps_jpeg50.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode opencv --width 480 --height 360 --fps 10 --mjpeg --jpeg-quality 70 --duration 30 --csv opencv_480x360_10fps_jpeg70.csv
```

## 4. MediaPipe Hands Boundary Test

Install MediaPipe first if it is not available:

```bash
python3 -c "import mediapipe as mp; print(mp.__version__)"
```

Recommended first MediaPipe tests:

```bash
python3 /home/pi/raspberry_perf_benchmark.py --mode mediapipe --width 160 --height 120 --fps 5 --model-complexity 0 --max-num-hands 1 --duration 30 --csv mp_160x120_5fps.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode mediapipe --width 320 --height 240 --fps 5 --model-complexity 0 --max-num-hands 1 --duration 30 --csv mp_320x240_5fps.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode mediapipe --width 320 --height 240 --fps 10 --model-complexity 0 --max-num-hands 1 --duration 30 --csv mp_320x240_10fps.csv
```

## 5. Hybrid Test

This is the engineering route:

```text
OpenCV every frame + MediaPipe every N frames
```

```bash
python3 /home/pi/raspberry_perf_benchmark.py --mode hybrid --width 320 --height 240 --fps 10 --skip 3 --model-complexity 0 --max-num-hands 1 --duration 30 --csv hybrid_320x240_10fps_skip3.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode hybrid --width 320 --height 240 --fps 10 --skip 5 --model-complexity 0 --max-num-hands 1 --duration 30 --csv hybrid_320x240_10fps_skip5.csv
python3 /home/pi/raspberry_perf_benchmark.py --mode hybrid --width 480 --height 360 --fps 10 --skip 5 --model-complexity 0 --max-num-hands 1 --duration 30 --csv hybrid_480x360_10fps_skip5.csv
```

## 6. CSV Columns

Important columns:

- `camera_fps`: actual captured/processed loop FPS.
- `opencv_fps`: OpenCV motion detection runs per second.
- `mediapipe_fps`: MediaPipe Hands inference runs per second.
- `avg_loop_ms`: average time per loop; a proxy for responsiveness.
- `p95_loop_ms`: high-percentile loop time; useful for judging stutter.
- `avg_opencv_ms`: OpenCV cost per run.
- `avg_mediapipe_ms`: MediaPipe cost per run.
- `avg_jpeg_ms`: MJPEG encoding cost per frame.
- `cpu_percent`: CPU usage if `psutil` is installed.
- `memory_mb`: process memory usage if `psutil` is installed.

## 7. Copy Results Back To Windows

```powershell
scp pi@10.196.36.213:/home/pi/*.csv .
```

If using the full suite:

```powershell
mkdir .\perf_results
scp pi@10.196.36.213:/home/pi/perf_results/*.csv .\perf_results\
```

Then summarize:

```powershell
python .\analyze_perf_results.py .\perf_results\*.csv --out-dir .\perf_report
```

For a no-plot summary:

```powershell
python .\analyze_perf_results.py .\perf_results\*.csv --out-dir .\perf_report --no-plots
```

## 8. One-Command Suites

USB camera suite:

```bash
chmod +x /home/pi/run_perf_suite_usb.sh
RUN_ID=run_002_temp_added DURATION=30 WARMUP=3 /home/pi/run_perf_suite_usb.sh
```

CSI camera suite:

```bash
chmod +x /home/pi/run_perf_suite_csi.sh
RUN_ID=run_002_temp_added DURATION=30 WARMUP=3 /home/pi/run_perf_suite_csi.sh
```

Short rehearsal:

```bash
RUN_ID=run_002_temp_added DURATION=10 WARMUP=2 /home/pi/run_perf_suite_usb.sh
```

If the USB camera is not `/dev/video0`, override the camera index:

```bash
CAMERA_INDEX=1 RUN_ID=run_002_temp_added DURATION=30 WARMUP=3 /home/pi/run_perf_suite_usb.sh
```

MediaPipe-only USB suite:

```bash
chmod +x /home/pi/run_perf_suite_mediapipe_usb.sh
CAMERA_INDEX=1 RUN_ID=run_006_mediapipe_test DURATION=10 WARMUP=8 /home/pi/run_perf_suite_mediapipe_usb.sh
```

If `RUN_ID` is omitted, the suite creates a timestamped directory such as:

```text
/home/pi/perf_results_usb/20260615_183012
```

## 9. Report Conclusion Template

The system does not maximize model complexity. Instead, it searches for a stable embedded vision configuration by adjusting image resolution, target FPS, inference frequency, and model complexity. The benchmark results show the trade-off between recognition capability and real-time responsiveness on Raspberry Pi.
