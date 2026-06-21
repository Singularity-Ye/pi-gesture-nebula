# Raspberry Pi Vision Performance Summary

## Case Summary

| Case | Mode | Size | Target FPS | Skip | Video | Camera FPS | Process FPS | Infer FPS | MJPEG FPS | Loop ms | CPU % | Temp Avg | Temp Max | Throttled | Encode ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| opencv_csi_320x240_30fps_mjpeg70 | opencv | 320x240 | 30.0 | 3 | True | 28.97 | 28.97 | 0.00 | 28.97 | 16.27 | 36.17 | 50.35 | 51.50 | yes | 3.97 |
| hybrid_csi_320x240_30fps_skip10_trial1_mjpeg70 | hybrid | 320x240 | 30.0 | 10 | True | 19.23 | 19.23 | 1.92 | 19.23 | 34.43 | 33.87 | 54.06 | 54.80 | yes | 3.96 |
| hybrid_csi_320x240_30fps_skip10_trial2_mjpeg70 | hybrid | 320x240 | 30.0 | 10 | True | 19.04 | 19.04 | 1.89 | 19.04 | 33.91 | 34.11 | 54.94 | 55.80 | yes | 4.00 |
| hybrid_csi_320x240_30fps_skip10_trial3_mjpeg70 | hybrid | 320x240 | 30.0 | 10 | True | 19.46 | 19.46 | 1.93 | 19.46 | 31.14 | 34.16 | 55.50 | 55.80 | yes | 4.02 |
| hybrid_csi_320x240_30fps_skip15_trial1_mjpeg70 | hybrid | 320x240 | 30.0 | 15 | True | 21.96 | 21.96 | 1.47 | 21.96 | 26.75 | 34.60 | 51.06 | 52.10 | yes | 4.00 |
| hybrid_csi_320x240_30fps_skip15_trial2_mjpeg70 | hybrid | 320x240 | 30.0 | 15 | True | 22.44 | 22.44 | 1.50 | 22.44 | 26.94 | 34.86 | 52.62 | 53.70 | yes | 3.99 |
| hybrid_csi_320x240_30fps_skip15_trial3_mjpeg70 | hybrid | 320x240 | 30.0 | 15 | True | 22.36 | 22.36 | 1.52 | 22.36 | 26.64 | 34.39 | 53.44 | 53.70 | yes | 4.00 |
| hybrid_csi_320x240_30fps_skip1_trial1_mjpeg70 | hybrid | 320x240 | 30.0 | 1 | True | 4.57 | 4.57 | 4.57 | 4.57 | 194.44 | 29.87 | 58.54 | 59.10 | yes | 3.92 |
| hybrid_csi_320x240_30fps_skip1_trial2_mjpeg70 | hybrid | 320x240 | 30.0 | 1 | True | 4.61 | 4.61 | 4.61 | 4.61 | 202.56 | 30.17 | 58.07 | 59.10 | yes | 4.78 |
| hybrid_csi_320x240_30fps_skip1_trial3_mjpeg70 | hybrid | 320x240 | 30.0 | 1 | True | 3.00 | 3.00 | 3.00 | 3.00 | 322.76 | 29.29 | 57.13 | 58.00 | yes | 5.47 |
| hybrid_csi_320x240_30fps_skip3_trial1_mjpeg70 | hybrid | 320x240 | 30.0 | 3 | True | 7.74 | 7.74 | 2.58 | 7.74 | 100.07 | 30.39 | 57.34 | 58.00 | yes | 3.91 |
| hybrid_csi_320x240_30fps_skip3_trial2_mjpeg70 | hybrid | 320x240 | 30.0 | 3 | True | 10.03 | 10.03 | 3.33 | 10.03 | 78.84 | 31.19 | 57.79 | 58.50 | yes | 3.96 |
| hybrid_csi_320x240_30fps_skip3_trial3_mjpeg70 | hybrid | 320x240 | 30.0 | 3 | True | 11.42 | 11.42 | 3.80 | 11.42 | 71.36 | 32.80 | 57.89 | 58.50 | yes | 4.26 |
| hybrid_csi_320x240_30fps_skip5_trial1_mjpeg70 | hybrid | 320x240 | 30.0 | 5 | True | 15.30 | 15.30 | 3.01 | 15.30 | 45.25 | 32.95 | 56.27 | 56.90 | yes | 4.01 |
| hybrid_csi_320x240_30fps_skip5_trial2_mjpeg70 | hybrid | 320x240 | 30.0 | 5 | True | 12.63 | 12.63 | 2.52 | 12.63 | 56.01 | 32.31 | 56.66 | 56.90 | yes | 3.97 |
| hybrid_csi_320x240_30fps_skip5_trial3_mjpeg70 | hybrid | 320x240 | 30.0 | 5 | True | 11.44 | 11.44 | 2.27 | 11.44 | 66.47 | 31.45 | 56.99 | 58.00 | yes | 3.95 |

## Suggested Reading

- Stable OpenCV baseline candidate: `opencv_csi_320x240_30fps_mjpeg70` with camera FPS 28.97 and loop time 16.27 ms.
- Hybrid candidate: `hybrid_csi_320x240_30fps_skip15_trial2_mjpeg70` with camera FPS 22.44, inference FPS 1.50, and loop time 26.94 ms.

## Report Paragraph Draft

The benchmark compares lightweight OpenCV motion extraction, MediaPipe Hands inference, and a hybrid strategy under different camera resolutions and target frame rates. The results can be used to identify the stable operating region where embedded visual interaction remains responsive while CPU and frame processing time stay within acceptable limits.

## Skip Aggregation

| Skip | Trials | Process FPS | Infer FPS | MJPEG FPS | Loop Avg ms | Loop Max ms | CPU % | Temp Max | Current Throttle | Historical Flags |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 15 | 3 | 22.25 | 1.49 | 22.25 | 26.78 | 39.03 | 34.62 | 53.70 | no | soft_temp_limit_seen,throttled_seen,under_voltage_seen |
| 10 | 3 | 19.24 | 1.92 | 19.24 | 33.16 | 55.60 | 34.05 | 55.80 | no | soft_temp_limit_seen,throttled_seen,under_voltage_seen |
| 5 | 3 | 13.12 | 2.60 | 13.12 | 55.91 | 89.90 | 32.24 | 58.00 | no | soft_temp_limit_seen,throttled_seen,under_voltage_seen |
| 3 | 3 | 9.73 | 3.23 | 9.73 | 83.42 | 181.24 | 31.46 | 58.50 | yes | soft_temp_limit_seen,throttled_seen,under_voltage_seen |
| 1 | 3 | 4.06 | 4.06 | 4.06 | 239.92 | 603.56 | 29.78 | 59.10 | yes | soft_temp_limit_seen,throttled_seen,under_voltage_seen |

Suggested skip setting:

- Recommended enhanced mode: `infer_skip=10` with process FPS 19.24, inference FPS 1.92, and average loop time 33.16 ms.
