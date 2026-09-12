# lerobot_guide

FT 舵机调试优化工具包 | 面向 HuggingFace LeRobot 机械臂开发

## 功能

- 🔍 自动扫描串口设备 + 波特率
- 🆔 修改舵机 ID（解决冲突）
- 📐 中位校准（一键归零）
- 📊 实时状态读取（位置/速度/扭矩/温度）
- 🔧 寄存器读写（调试 PID、死区等）
- 🤖 LeRobot 集成指南

## 支持型号

| 系列 | 型号 | 协议 |
|------|------|------|
| HLS | FT 0903, FT 1217, FT 1532 等 | FT-SCS |
| SMS/STS | SMS_STS, STS3032, STS3215 等 | FT-SCS |
| SCS | SCS15, SCS315, SCS45 等 | FT-SCS |

## 快速开始

```bash
pip install pyserial
```

### 1. 扫描舵机

```bash
python scan.py --port /dev/cu.usbmodem5B790502931
```

### 2. 一键校准

```bash
python calibrate.py --port /dev/cu.usbmodem5B790502931 --id 1
```

### 3. 串接第二台：改 ID 再校准

```bash
python set_id.py --port /dev/cu.usbmodem5B790502931 --old 1 --new 2
python calibrate.py --port /dev/cu.usbmodem5B790502931 --id 2
```

## 文件结构

```
lerobot_guide/
├── ft_servo.py        # 核心库
├── scan.py            # 扫描工具
├── calibrate.py       # 校准脚本
├── set_id.py          # 修改 ID
├── monitor.py         # 实时监控
├── memory_table.md    # 内存表参考
├── LEROBOT_GUIDE.md   # LeRobot 集成指南
└── README.md
```

## LeRobot 集成

详见 [LEROBOT_GUIDE.md](LEROBOT_GUIDE.md)，包含：

- So100 / Koch 机械臂 FT 舵机配置
- 校准流程（归零 → 设限位 → 验证）
- 实时控制参数调优

## 硬件准备

- USB 转串口模块：CH343P / CH340 / FT232
- FT 舵机独立供电：6V-7.4V（必须！）
- 杜邦线：TX→舵机 SIG，GND 共地

## 许可

MIT
