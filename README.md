# lerobot_guide

FT 舵机调试优化工具包 | 面向 HuggingFace LeRobot 机械臂开发

## 快速开始

```bash
pip install -r requirements.txt
```

### 扫描舵机

```bash
python -m core scan --port /dev/cu.usbmodem5B790502931
```

### 中位校准

```bash
python -m core calibrate --port /dev/cu.usbmodem5B790502931 --id 1 -y
```

### 修改 ID

```bash
python -m core set-id --port /dev/cu.usbmodem5B790502931 --old 1 --new 2
```

## 目录结构

```
lerobot_guide/
├── core/                    # 核心库
│   ├── __init__.py          # 统一导出
│   ├── ft_servo.py          # 舵机控制 + CLI (scan/calibrate/set-id/status/monitor)
│   └── display.py           # 通用可视化模块 (帧解析/状态表格/步骤日志)
├── docs/                    # 文档
│   ├── memory_table.md      # HLS/SMS_STS 寄存器内存表
│   └── LEROBOT_GUIDE.md     # LeRobot 集成指南
├── skills/                  # 调试经验
│   └── AI_DEBUG_SKILL.md    # AI 驱动调试方法论
├── tutorial/                # 教程
│   └── 调试舵机.md          # 从零开始调试舵机
├── test/                    # 测试
│   └── test_servo.py        # 核心功能 + 可视化 + 硬件测试
├── requirements.txt         # pyserial, rich
└── README.md
```

## 支持型号

| 系列 | 型号 | 协议 |
|------|------|------|
| HLS | FT 0903, FT 1217, FT 1532 等 | FT-SCS |
| SMS/STS | SMS_STS, STS3032, STS3215 等 | FT-SCS |
| SCS | SCS15, SCS315, SCS45 等 | FT-SCS |

## 测试

```bash
python test/test_servo.py
```

## Contributors

- backyes
- hermes

## License

MIT
