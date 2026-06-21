import argparse
import asyncio
import base64
import hashlib
import importlib
import inspect
import json
import math
import signal
import time

import cv2


WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
DISCONNECT_ERRORS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read Raspberry Pi camera frames with OpenCV and send gesture scale data over WebSocket."
    )
    parser.add_argument("--host", default="0.0.0.0", help="WebSocket bind address.")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket bind port.")
    parser.add_argument("--video-host", default="0.0.0.0", help="MJPEG HTTP bind address.")
    parser.add_argument("--video-port", type=int, default=8080, help="MJPEG HTTP bind port.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--width", type=int, default=480, help="Camera frame width.")
    parser.add_argument("--height", type=int, default=360, help="Camera frame height.")
    parser.add_argument("--fps", type=float, default=10.0, help="Processing frame rate limit.")
    parser.add_argument(
        "--mode",
        choices=("opencv", "hybrid"),
        default="opencv",
        help="opencv: motion-area control only; hybrid: OpenCV control plus low-rate MediaPipe Hands metadata.",
    )
    parser.add_argument("--infer-skip", type=int, default=5, help="In hybrid mode, run MediaPipe once every N frames.")
    parser.add_argument("--model-complexity", type=int, default=0, help="MediaPipe Hands model_complexity when supported.")
    parser.add_argument("--max-num-hands", type=int, default=1, help="MediaPipe max_num_hands in hybrid mode.")
    parser.add_argument("--min-area", type=float, default=1200.0, help="Area below this is treated as no motion.")
    parser.add_argument("--max-area", type=float, default=22000.0, help="Area that maps to maximum scale.")
    parser.add_argument("--min-scale", type=float, default=0.6, help="Minimum sphere scale.")
    parser.add_argument("--max-scale", type=float, default=2.0, help="Maximum sphere scale.")
    parser.add_argument("--smooth", type=float, default=0.2, help="Scale smoothing factor from 0 to 1.")
    parser.add_argument("--jpeg-quality", type=int, default=70, help="MJPEG frame JPEG quality from 1 to 100.")
    parser.add_argument("--no-video", action="store_true", help="Disable MJPEG HTTP video stream.")
    preview_group = parser.add_mutually_exclusive_group()
    preview_group.add_argument(
        "--preview",
        dest="preview",
        action="store_true",
        help="Show OpenCV preview window on the Raspberry Pi desktop.",
    )
    preview_group.add_argument(
        "--no-preview",
        dest="preview",
        action="store_false",
        help="Disable OpenCV preview window.",
    )
    parser.set_defaults(preview=False)
    return parser.parse_args()


async def read_http_headers(reader):
    data = b""
    while b"\r\n\r\n" not in data:
        try:
            chunk = await reader.read(1024)
        except DISCONNECT_ERRORS:
            return None
        if not chunk:
            return None
        data += chunk
    return data.decode("utf-8", errors="ignore")


def websocket_accept_key(client_key):
    digest = hashlib.sha1((client_key + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


async def send_text_frame(writer, text):
    payload = text.encode("utf-8")
    header = bytearray([0x81])
    length = len(payload)

    if length < 126:
        header.append(length)
    elif length < 65536:
        header.extend([126, (length >> 8) & 0xFF, length & 0xFF])
    else:
        header.append(127)
        header.extend(length.to_bytes(8, "big"))

    writer.write(bytes(header) + payload)
    await writer.drain()


async def close_writer(writer):
    try:
        writer.close()
        await writer.wait_closed()
    except DISCONNECT_ERRORS:
        pass
    except RuntimeError:
        pass


class GestureState:
    def __init__(self, args):
        self.args = args
        self.clients = set()
        self.scale = 1.0
        self.area = 0.0
        self.motion = False
        self.frame_count = 0
        self.last_payload = {}
        self.latest_jpeg = None
        self.latest_jpeg_at = 0.0
        self.running = True
        self.hand_detected = False
        self.landmark_count = 0
        self.pinch_distance = 0.0
        self.landmarks = []

    def map_area_to_scale(self, area):
        if area < self.args.min_area:
            target = self.args.min_scale
        else:
            normalized = (area - self.args.min_area) / (self.args.max_area - self.args.min_area)
            normalized = max(0.0, min(1.0, normalized))
            target = self.args.min_scale + normalized * (self.args.max_scale - self.args.min_scale)

        smooth = max(0.0, min(1.0, self.args.smooth))
        self.scale = self.scale + (target - self.scale) * smooth
        return self.scale

    def make_payload(self):
        return {
            "source": "raspberry",
            "scale": round(self.scale, 3),
            "motion": self.motion,
            "area": round(self.area),
            "gesture": self.describe_gesture(),
            "mode": self.args.mode,
            "handDetected": self.hand_detected,
            "landmarkCount": self.landmark_count,
            "pinchDistance": round(self.pinch_distance, 4),
            "landmarks": self.landmarks,
            "frame": self.frame_count,
            "timestamp": time.time(),
        }

    def describe_gesture(self):
        if self.args.mode == "hybrid" and self.hand_detected:
            return "hybrid_hand_area"
        if self.motion:
            return "single_hand_area"
        return "none"


def optional_module(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def make_mediapipe_hands(args):
    mp = optional_module("mediapipe")
    if not mp:
        raise RuntimeError("MediaPipe is not installed. Use --mode opencv or install mediapipe first.")

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
        return mp, mp.solutions.hands.Hands(**hands_kwargs)
    except TypeError as error:
        if "model_complexity" not in hands_kwargs:
            raise
        print(f"MediaPipe Hands does not accept model_complexity; retrying without it ({error})")
        hands_kwargs.pop("model_complexity", None)
        return mp, mp.solutions.hands.Hands(**hands_kwargs)


def distance3(point_a, point_b):
    dx = point_a.x - point_b.x
    dy = point_a.y - point_b.y
    dz = point_a.z - point_b.z
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def run_mediapipe(frame, hands):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    hand_detected = bool(results.multi_hand_landmarks)
    landmarks = []
    serialized_landmarks = []
    pinch_distance = 0.0
    if hand_detected:
        landmarks = results.multi_hand_landmarks[0].landmark
        serialized_landmarks = [
            {
                "x": round(point.x, 4),
                "y": round(point.y, 4),
                "z": round(point.z, 4),
            }
            for point in landmarks
        ]
        if len(landmarks) > 8:
            pinch_distance = distance3(landmarks[4], landmarks[8])

    return hand_detected, landmarks, serialized_landmarks, pinch_distance


def draw_landmarks(frame, landmarks):
    if not landmarks:
        return

    height, width = frame.shape[:2]
    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (0, 9), (9, 10), (10, 11), (11, 12),
        (0, 13), (13, 14), (14, 15), (15, 16),
        (0, 17), (17, 18), (18, 19), (19, 20),
        (5, 9), (9, 13), (13, 17),
    ]

    for start_index, end_index in connections:
        if start_index >= len(landmarks) or end_index >= len(landmarks):
            continue
        start = landmarks[start_index]
        end = landmarks[end_index]
        start_xy = (
            int(max(0, min(width - 1, start.x * width))),
            int(max(0, min(height - 1, start.y * height))),
        )
        end_xy = (
            int(max(0, min(width - 1, end.x * width))),
            int(max(0, min(height - 1, end.y * height))),
        )
        cv2.line(frame, start_xy, end_xy, (0, 220, 255), 1)

    for point in landmarks:
        x = int(max(0, min(width - 1, point.x * width)))
        y = int(max(0, min(height - 1, point.y * height)))
        cv2.circle(frame, (x, y), 3, (0, 220, 255), -1)


async def handle_client(reader, writer, state):
    peer = writer.get_extra_info("peername")
    request = await read_http_headers(reader)
    if not request:
        await close_writer(writer)
        return

    key = None
    for line in request.splitlines():
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
            break

    if not key:
        await close_writer(writer)
        return

    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {websocket_accept_key(key)}\r\n"
        "\r\n"
    )
    try:
        writer.write(response.encode("ascii"))
        await writer.drain()
    except DISCONNECT_ERRORS:
        await close_writer(writer)
        return

    state.clients.add(writer)
    print(f"client connected: {peer}")

    try:
        while state.running and not reader.at_eof():
            await asyncio.sleep(1.0)
    except DISCONNECT_ERRORS:
        pass
    finally:
        state.clients.discard(writer)
        await close_writer(writer)
        print(f"client disconnected: {peer}")


async def broadcast_payload(state):
    if not state.clients:
        return

    message = json.dumps(state.make_payload(), separators=(",", ":"))
    disconnected = []
    for writer in list(state.clients):
        try:
            await send_text_frame(writer, message)
        except DISCONNECT_ERRORS:
            disconnected.append(writer)

    for writer in disconnected:
        state.clients.discard(writer)
        await close_writer(writer)


async def handle_mjpeg_client(reader, writer, state):
    peer = writer.get_extra_info("peername")
    request = await read_http_headers(reader)
    if not request:
        await close_writer(writer)
        return

    first_line = request.splitlines()[0] if request.splitlines() else ""
    path = first_line.split(" ")[1] if " " in first_line else "/"

    if path not in ("/", "/video"):
        try:
            writer.write(
                b"HTTP/1.1 404 Not Found\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Content-Length: 9\r\n"
                b"\r\n"
                b"Not Found"
            )
            await writer.drain()
        except DISCONNECT_ERRORS:
            pass
        await close_writer(writer)
        return

    header = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
        "Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n"
        "Pragma: no-cache\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "\r\n"
    )
    try:
        writer.write(header.encode("ascii"))
        await writer.drain()
    except DISCONNECT_ERRORS:
        await close_writer(writer)
        print(f"mjpeg client disconnected: {peer}")
        return
    print(f"mjpeg client connected: {peer}")

    last_sent_at = 0.0
    try:
        while state.running:
            if state.latest_jpeg is None or state.latest_jpeg_at == last_sent_at:
                await asyncio.sleep(0.02)
                continue

            frame = state.latest_jpeg
            last_sent_at = state.latest_jpeg_at
            part_header = (
                f"--frame\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame)}\r\n"
                f"\r\n"
            ).encode("ascii")
            try:
                writer.write(part_header + frame + b"\r\n")
                await writer.drain()
            except DISCONNECT_ERRORS:
                break
    except asyncio.CancelledError:
        pass
    except DISCONNECT_ERRORS:
        pass
    finally:
        await close_writer(writer)
        print(f"mjpeg client disconnected: {peer}")


async def process_camera(state):
    args = state.args
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        raise RuntimeError(
            "Could not open camera. On Raspberry Pi legacy camera stack, run: sudo modprobe bcm2835-v4l2"
        )

    previous_gray = None
    hands = None
    last_landmarks = []
    if args.mode == "hybrid":
        _, hands = make_mediapipe_hands(args)

    frame_delay = 1.0 / max(args.fps, 1.0)
    preview_enabled = args.preview
    print(
        f"camera opened: index={args.camera}, size={args.width}x{args.height}, "
        f"fps_limit={args.fps}, mode={args.mode}, infer_skip={args.infer_skip}, preview={preview_enabled}"
    )

    try:
        while state.running:
            start = time.time()
            ok, frame = cap.read()
            if not ok:
                await asyncio.sleep(frame_delay)
                continue

            state.frame_count += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            display_frame = frame
            max_area = 0.0

            if previous_gray is not None:
                diff = cv2.absdiff(previous_gray, gray)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                if contours:
                    largest = max(contours, key=cv2.contourArea)
                    max_area = float(cv2.contourArea(largest))
                    if max_area >= args.min_area:
                        x, y, w, h = cv2.boundingRect(largest)
                        cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            previous_gray = gray
            state.area = max_area
            state.motion = max_area >= args.min_area
            state.map_area_to_scale(max_area)

            if hands and (state.frame_count - 1) % max(1, args.infer_skip) == 0:
                state.hand_detected, last_landmarks, state.landmarks, state.pinch_distance = run_mediapipe(frame, hands)
                state.landmark_count = len(last_landmarks)

            if args.mode == "hybrid" and last_landmarks:
                draw_landmarks(display_frame, last_landmarks)

            state.last_payload = state.make_payload()

            if state.frame_count % max(1, int(args.fps)) == 0:
                print(
                    f"frame={state.frame_count} clients={len(state.clients)} "
                    f"area={state.area:.0f} scale={state.scale:.2f} motion={state.motion} "
                    f"hand={state.hand_detected} landmarks={state.landmark_count}"
                )

            await broadcast_payload(state)

            if not args.no_video:
                quality = max(1, min(100, args.jpeg_quality))
                ok, jpeg = cv2.imencode(".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if ok:
                    state.latest_jpeg = jpeg.tobytes()
                    state.latest_jpeg_at = time.time()

            if preview_enabled:
                cv2.putText(
                    display_frame,
                    f"area={state.area:.0f} scale={state.scale:.2f} hand={state.hand_detected}",
                    (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
                try:
                    cv2.imshow("Raspberry Gesture Control", display_frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        state.running = False
                        break
                except cv2.error as error:
                    preview_enabled = False
                    print(f"preview disabled: {error}")

            elapsed = time.time() - start
            await asyncio.sleep(max(0.0, frame_delay - elapsed))
    finally:
        cap.release()
        if hands:
            close = getattr(hands, "close", None)
            if close:
                close()
        if preview_enabled:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass


async def main():
    args = parse_args()
    state = GestureState(args)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, setattr, state, "running", False)
        except NotImplementedError:
            pass

    server = await asyncio.start_server(lambda r, w: handle_client(r, w, state), args.host, args.port)
    print(f"gesture websocket server: ws://{args.host}:{args.port}")
    mjpeg_server = None
    if not args.no_video:
        mjpeg_server = await asyncio.start_server(
            lambda r, w: handle_mjpeg_client(r, w, state), args.video_host, args.video_port
        )
        print(f"mjpeg video stream: http://{args.video_host}:{args.video_port}/video")

    async with server:
        if mjpeg_server:
            await mjpeg_server.start_serving()
        camera_task = asyncio.create_task(process_camera(state))
        try:
            while state.running:
                await asyncio.sleep(0.2)
        finally:
            state.running = False
            camera_task.cancel()
            await asyncio.gather(camera_task, return_exceptions=True)
            if mjpeg_server:
                mjpeg_server.close()
                await mjpeg_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
