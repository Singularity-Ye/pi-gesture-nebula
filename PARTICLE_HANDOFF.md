# 粒子特效与比心手势交接说明

本文档供后续负责 Three.js 粒子视觉的 agent 使用。现有树莓派采集、MediaPipe、WebSocket、MJPEG 和控制模式已经联调完成，视觉改造应建立在现有控制链路之上。

## 必须保留的边界

1. 保留 `controlState` 作为唯一渲染控制入口。
2. 不要删除 Browser / Raspberry / Simulate 三种输入模式。
3. 不要删除 Area / Pinch / Hybrid 三种控制模式。
4. Raspberry 模式继续读取 WebSocket landmarks，视频背景继续使用 MJPEG。
5. 默认运行配置保持 CSI 320x240、Hybrid、`infer_skip=10`。
6. 粒子动画只读取状态，不应反向耦合摄像头、MediaPipe 或 WebSocket 实现。

## 建议的粒子状态

在现有状态旁新增独立的视觉状态：

```js
const visualState = {
  shape: "sphere",
  targetShape: "sphere",
  morphProgress: 0,
  heartGesture: false,
  heartConfidence: 0,
  gestureHoldMs: 0,
};
```

粒子几何建议预先生成等量采样点：

- `spherePositions`：球面或球体内部采样点。
- `heartPositions`：三维心形参数方程、GLB/STL 表面采样点，或二维心形加厚后的点集。
- 两组点数量与索引必须一致。
- 顶点着色器或 CPU 插值使用同一 `morphProgress` 在两组位置间过渡。

不要在每帧重新创建 `BufferGeometry`。复用 attribute、材质和 Points 对象，避免垃圾回收抖动。

## “交叉式比心”手势判定思路

这里的比心指单手拇指和食指在指尖附近交叉，形成小型手指心。仅靠 landmark 4 与 8 的距离会把普通捏合误判为比心，因此建议组合多个条件。

关键点：

- 拇指指尖：4
- 拇指第二关节：3
- 食指指尖：8
- 食指第二关节：7
- 食指根部：5
- 手腕：0

### 1. 距离归一化

用手掌尺度归一化，避免手离摄像头远近影响阈值：

```js
const palmSize = distance(landmarks[0], landmarks[9]);
const tipDistance = distance(landmarks[4], landmarks[8]) / palmSize;
```

候选条件可从 `tipDistance < 0.35` 开始标定，最终阈值以实际 CSI 数据为准。

### 2. 线段交叉检测

把拇指末节视为线段 `3 -> 4`，食指末节视为线段 `7 -> 8`，在图像 XY 平面检测两条线段是否相交或距离足够小：

```js
const crossed = segmentsIntersect(
  landmarks[3], landmarks[4],
  landmarks[7], landmarks[8]
);
```

MediaPipe 点位有抖动，实际实现建议接受“相交”或“两线段最短距离小于阈值”两种情况。

### 3. 指尖方向约束

普通捏合通常是两指尖相对靠近，比心则末节方向存在交叉。可计算两个末节向量的二维叉积、夹角和左右关系，排除仅靠近但未交叉的情况。

```text
heartCandidate = tipsClose
              AND segmentsCrossOrNear
              AND fingertipDirectionsValid
              AND handDetected
```

### 4. 时间防抖

不要单帧触发形态变化：

- 连续满足约 300 至 500 ms 后进入心形。
- 连续不满足约 500 至 800 ms 后恢复球形。
- 使用进入阈值和退出阈值形成迟滞，避免在边界反复切换。
- MediaPipe 在 `skip10` 下更新较慢，应按消息时间累计，而不是按帧数累计。

### 5. 置信度融合

可将距离、线段接近程度和方向约束映射为 0 到 1，再进行指数平滑：

```js
visualState.heartConfidence +=
  (rawHeartConfidence - visualState.heartConfidence) * 0.2;
```

当平滑置信度超过进入阈值并满足保持时间后，将 `targetShape` 设置为 `heart`。

## 交互建议

- Area：继续控制整体粒子模型缩放。
- Pinch：继续使用拇指与食指距离控制缩放。
- Hybrid：有可靠骨架时使用 Pinch，无骨架时回退 Area。
- Heart：作为独立视觉手势叠加，不替代上述缩放控制模式。
- 比心触发后，粒子从球形平滑聚合为心形，并使用一次短促的颜色脉冲。
- 手势解除后恢复球形；不要让用户必须点击按钮复位。

## 验收标准

1. 原有三种输入模式和三种控制模式全部可用。
2. Raspberry Hybrid `skip10` 下仍能稳定运行。
3. 普通 Pinch 不会频繁误触发 Heart。
4. Heart 触发和退出均有防抖，不闪烁。
5. 粒子形变过程不重建场景，不出现明显掉帧或内存持续增长。
6. 桌面和移动视口中 HUD、摄像头背景、骨架层与粒子层不互相遮挡。
7. 使用 Playwright 截图检查 Browser、Raspberry 和 Simulate 三种模式的层级与布局。

