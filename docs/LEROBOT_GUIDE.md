# LeRobot 机械臂 FT 舵机集成调试指南

## 概述

本文介绍如何在 HuggingFace LeRobot 框架下使用飞腾（FEETech）FT 系列舵机，完成从硬件接线到校准控制的完整流程。

## 硬件兼容性

| 机械臂 | 兼容舵机 | 协议 |
|--------|---------|------|
| Koch v1.1 | FT HLS 系列 (0903, 1217) | FT-SCS |
| So100 | FT STS/SMS 系列 | FT-SCS |
| ALServo | FT SCS 系列 | FT-SCS |

## 调试流程

### 1. 硬件准备

- [ ] CH343P/CH340 USB 转串口模块
- [ ] FT 舵机独立电源（6V-7.4V，USB 供电不足）
- [ ] 杜邦线：TX→舵机 SIG，共地

### 2. 安装工具包

```bash
git clone https://github.com/backyes/lerobot_guide.git
cd lerobot_guide
pip install pyserial
```

### 3. 扫描舵机

```bash
python ft_servo.py scan --port /dev/cu.usbmodem5B790502931
```

### 4. 设置 ID

机械臂每个舵机必须有唯一 ID，通常按关节顺序分配：

```
底座 → ID=1
肩关节 → ID=2
肘关节 → ID=3
腕关节 → ID=4
夹爪 → ID=5
```

修改方法：

```bash
python ft_servo.py set-id --port /dev/cu.usbmodem5B790502931 --old 1 --new 3
```

### 5. 中位校准

```bash
python ft_servo.py calibrate --port /dev/cu.usbmodem5B790502931 --id 1
```

### 6. 实时监控

```bash
python ft_servo.py status --port /dev/cu.usbmodem5B790502931 --id 1
```

## LeRobot 配置

### Koch v1.1 示例

在 LeRobot 配置文件中指定舵机参数：

```python
from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobot
from lerobot.common.robot_devices.motors.feetech import FeetechMotorsBus

motors = {
    "shoulder_pan": (1, "sts3215"),
    "shoulder_lift": (2, "sts3215"),
    "elbow_flex": (3, "sts3215"),
    "wrist_flex": (4, "sts3215"),
    "wrist_roll": (5, "sts3215"),
    "gripper": (6, "sts3215"),
}

robot = ManipulatorRobot(
    robot_type="so100",
    motors_bus=FeetechMotorsBus(
        port="/dev/cu.usbmodem5B790502931",
        motors=motors,
    ),
)
```

## 校准流程（LeRobot 内）

```python
from lerobot.common.robot_devices.robots.utils import RobotCalibration

# 执行校准
robot.calibrate()

# 校准步骤：
# 1. 移动到中位
# 2. 记录偏移量
# 3. 验证行程范围
```

## 常见问题

### Q: 扫描不到舵机
- 检查波特率（默认 1Mbps）
- 检查独立供电（USB 带不动舵机）
- 检查共地

### Q: 改 ID 后不生效
- 修改后断电重启一次
- 锁定必须用新 ID 发送

### Q: 中位校准后位置不对
- HLS 系列校准指令是写 128 到扭矩寄存器，不是写偏移量
- 校准后需要再写 1 开启扭矩

## 参考

- [HLS 内存表](memory_table.md)
- [ft_servo.py 源码](ft_servo.py)
