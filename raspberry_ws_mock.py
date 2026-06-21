import asyncio
import base64
import hashlib
import json
import math
import time


HOST = "0.0.0.0"
PORT = 8765
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


async def read_http_headers(reader):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = await reader.read(1024)
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


async def handle_client(reader, writer):
    request = await read_http_headers(reader)
    if not request:
        writer.close()
        await writer.wait_closed()
        return

    key = None
    for line in request.splitlines():
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
            break

    if not key:
        writer.close()
        await writer.wait_closed()
        return

    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {websocket_accept_key(key)}\r\n"
        "\r\n"
    )
    writer.write(response.encode("ascii"))
    await writer.drain()

    phase = 0.0
    peer = writer.get_extra_info("peername")
    print(f"client connected: {peer}")

    try:
        while True:
            phase += 0.12
            scale = 1.1 + math.sin(phase) * 0.8
            message = {
                "source": "raspberry",
                "scale": round(scale, 3),
                "motion": True,
                "area": round(8000 + max(0, math.sin(phase)) * 12000),
                "rotateY": round(math.cos(phase) * 0.01, 4),
                "gesture": "mock_single_hand_area",
                "timestamp": time.time(),
            }
            await send_text_frame(writer, json.dumps(message))
            await asyncio.sleep(0.08)
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        print(f"client disconnected: {peer}")
        writer.close()
        await writer.wait_closed()


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    print(f"mock websocket server: ws://{HOST}:{PORT}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
