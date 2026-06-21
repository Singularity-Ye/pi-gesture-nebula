# Raspberry Pi Gesture WebSocket Setup

This project now supports two control inputs:

- Browser mode: local browser camera + MediaPipe.
- Raspberry mode: Raspberry Pi OpenCV motion/area detection + WebSocket, plus Raspberry camera MJPEG background.

The first Raspberry version uses a single-hand motion area as the control feature. It sends small JSON messages such as:

```json
{"source":"raspberry","scale":1.32,"motion":true,"area":6800,"gesture":"single_hand_area"}
```

It also exposes the same processed camera frame as an MJPEG stream:

```text
http://10.196.36.213:8080/video
```

## 1. Copy The Server To Raspberry Pi

From Windows PowerShell, in the project directory:

```powershell
scp -i .\raspberry .\raspberry_gesture_server.py pi@10.196.36.213:/home/pi/
```

If mDNS is stable, this also works:

```powershell
scp -i .\raspberry .\raspberry_gesture_server.py pi@raspberrypi.local:/home/pi/
```

## 2. Prepare Camera Device

On the Raspberry Pi:

```bash
sudo modprobe bcm2835-v4l2
ls /dev/video0
```

If `/dev/video0` exists, OpenCV can read the CSI camera through V4L2.

## 3. Run The Raspberry Server

Headless mode:

```bash
python3 /home/pi/raspberry_gesture_server.py --host 0.0.0.0 --port 8765 --width 480 --height 360 --fps 10
```

Explicit headless mode:

```bash
python3 /home/pi/raspberry_gesture_server.py --width 480 --height 360 --fps 10 --no-preview
```

VNC preview mode:

```bash
python3 /home/pi/raspberry_gesture_server.py --host 0.0.0.0 --port 8765 --width 480 --height 360 --fps 10 --preview
```

Press `q` in the preview window to quit.

Do not run `--preview False`. `--preview` is a switch, so adding it means preview is enabled. To disable preview, omit it or use `--no-preview`.

## 4. Open The Web Page On Windows

Start the web page from this project directory:

```powershell
python -m http.server 8000
```

Open:

```text
http://localhost:8000/
```

Choose `Raspberry`, keep the WebSocket URL as:

```text
ws://10.196.36.213:8765
```

Keep the MJPEG URL as:

```text
http://10.196.36.213:8080/video
```

Then click `Connect`.

## 5. Tuning

If the sphere barely changes, lower `--max-area`:

```bash
python3 /home/pi/raspberry_gesture_server.py --max-area 12000 --preview
```

If tiny movements trigger too easily, raise `--min-area`:

```bash
python3 /home/pi/raspberry_gesture_server.py --min-area 2500 --preview
```

If the sphere shakes, lower `--smooth`:

```bash
python3 /home/pi/raspberry_gesture_server.py --smooth 0.12 --preview
```

Recommended first test:

```bash
sudo modprobe bcm2835-v4l2
python3 /home/pi/raspberry_gesture_server.py --width 480 --height 360 --fps 10 --min-area 1200 --max-area 22000 --smooth 0.2 --preview
```

If the MJPEG background is too heavy, lower JPEG quality:

```bash
python3 /home/pi/raspberry_gesture_server.py --jpeg-quality 50 --preview
```

If you only want WebSocket control and no background video:

```bash
python3 /home/pi/raspberry_gesture_server.py --no-video --preview
```
