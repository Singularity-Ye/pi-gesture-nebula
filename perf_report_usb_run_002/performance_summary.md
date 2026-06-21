# Raspberry Pi Vision Performance Summary

## Case Summary

| Case | Mode | Size | Target FPS | Skip | Video | Camera FPS | Process FPS | Infer FPS | MJPEG FPS | Loop ms | CPU % | Temp Avg | Temp Max | Throttled | Encode ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| opencv_usb_160x120_5fps | opencv | 160x120 | 5.0 | 3 | False | 4.91 | 4.91 | 0.00 | 0.00 | 8.61 | 7.70 | 45.21 | 45.60 | no | 0.00 |
| opencv_usb_320x240_10fps | opencv | 320x240 | 10.0 | 3 | False | 7.87 | 7.87 | 0.00 | 0.00 | 108.88 | 19.19 | 46.13 | 46.70 | no | 0.00 |
| opencv_usb_320x240_5fps | opencv | 320x240 | 5.0 | 3 | False | 4.53 | 4.53 | 0.00 | 0.00 | 18.07 | 11.99 | 46.06 | 46.70 | no | 0.00 |
| opencv_usb_480x360_10fps | opencv | 480x360 | 10.0 | 3 | False | 7.01 | 7.01 | 0.00 | 0.00 | 120.80 | 20.00 | 47.00 | 47.20 | no | 0.00 |
| opencv_usb_640x480_10fps | opencv | 640x480 | 10.0 | 3 | False | 8.02 | 8.02 | 0.00 | 0.00 | 112.53 | 39.12 | 49.71 | 50.50 | no | 0.00 |
| opencv_usb_640x480_10fps_jpeg50 | opencv | 640x480 | 10.0 | 3 | True | 7.94 | 7.94 | 0.00 | 7.94 | 113.15 | 37.80 | 52.72 | 53.20 | no | 14.95 |
| opencv_usb_640x480_10fps_jpeg70 | opencv | 640x480 | 10.0 | 3 | True | 7.93 | 7.93 | 0.00 | 7.93 | 113.28 | 39.87 | 53.16 | 53.70 | no | 15.28 |
| opencv_usb_640x480_10fps_jpeg90 | opencv | 640x480 | 10.0 | 3 | True | 7.86 | 7.86 | 0.00 | 7.86 | 114.07 | 36.31 | 53.80 | 54.20 | no | 15.19 |
| opencv_usb_640x480_15fps | opencv | 640x480 | 15.0 | 3 | False | 7.84 | 7.84 | 0.00 | 0.00 | 115.64 | 38.58 | 50.74 | 51.50 | no | 0.00 |
| opencv_usb_640x480_30fps | opencv | 640x480 | 30.0 | 3 | False | 8.03 | 8.03 | 0.00 | 0.00 | 116.02 | 37.48 | 51.80 | 52.60 | no | 0.00 |

## Suggested Reading

- Stable OpenCV baseline candidate: `opencv_usb_160x120_5fps` with camera FPS 4.91 and loop time 8.61 ms.

## Report Paragraph Draft

The benchmark compares lightweight OpenCV motion extraction, MediaPipe Hands inference, and a hybrid strategy under different camera resolutions and target frame rates. The results can be used to identify the stable operating region where embedded visual interaction remains responsive while CPU and frame processing time stay within acceptable limits.
