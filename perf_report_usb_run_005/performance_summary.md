# Raspberry Pi Vision Performance Summary

## Case Summary

| Case | Mode | Size | Target FPS | Skip | Video | Camera FPS | Process FPS | Infer FPS | MJPEG FPS | Loop ms | CPU % | Temp Avg | Temp Max | Throttled | Encode ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| opencv_usb_160x120_5fps | opencv | 160x120 | 5.0 | 3 | False | 4.33 | 4.33 | 0.00 | 0.00 | 8.63 | 8.08 | 46.14 | 46.20 | no | 0.00 |
| opencv_usb_320x240_10fps | opencv | 320x240 | 10.0 | 3 | False | 9.77 | 9.77 | 0.00 | 0.00 | 16.96 | 18.34 | 47.51 | 48.30 | no | 0.00 |
| opencv_usb_320x240_5fps | opencv | 320x240 | 5.0 | 3 | False | 4.53 | 4.53 | 0.00 | 0.00 | 22.59 | 13.67 | 46.87 | 47.20 | no | 0.00 |
| opencv_usb_480x360_10fps | opencv | 480x360 | 10.0 | 3 | False | 9.81 | 9.81 | 0.00 | 0.00 | 19.97 | 22.84 | 48.38 | 48.90 | no | 0.00 |
| opencv_usb_640x480_10fps | opencv | 640x480 | 10.0 | 3 | False | 9.46 | 9.46 | 0.00 | 0.00 | 50.35 | 45.62 | 51.67 | 52.60 | no | 0.00 |
| opencv_usb_640x480_10fps_jpeg50 | opencv | 640x480 | 10.0 | 3 | True | 9.79 | 9.79 | 0.00 | 9.79 | 63.59 | 47.34 | 56.81 | 57.50 | yes | 14.60 |
| opencv_usb_640x480_10fps_jpeg70 | opencv | 640x480 | 10.0 | 3 | True | 9.71 | 9.71 | 0.00 | 9.71 | 63.05 | 46.58 | 56.70 | 56.90 | yes | 14.87 |
| opencv_usb_640x480_10fps_jpeg90 | opencv | 640x480 | 10.0 | 3 | True | 9.61 | 9.61 | 0.00 | 9.61 | 64.98 | 47.51 | 56.63 | 56.90 | yes | 15.72 |
| opencv_usb_640x480_15fps | opencv | 640x480 | 15.0 | 3 | False | 14.28 | 14.28 | 0.00 | 0.00 | 48.22 | 63.61 | 55.24 | 56.40 | no | 0.00 |
| opencv_usb_640x480_30fps | opencv | 640x480 | 30.0 | 3 | False | 19.42 | 19.42 | 0.00 | 0.00 | 49.26 | 83.72 | 58.32 | 59.60 | yes | 0.00 |

## Suggested Reading

- Stable OpenCV baseline candidate: `opencv_usb_640x480_30fps` with camera FPS 19.42 and loop time 49.26 ms.

## Report Paragraph Draft

The benchmark compares lightweight OpenCV motion extraction, MediaPipe Hands inference, and a hybrid strategy under different camera resolutions and target frame rates. The results can be used to identify the stable operating region where embedded visual interaction remains responsive while CPU and frame processing time stay within acceptable limits.
