#!/usr/bin/env python3
"""
测试套件 | 验证核心功能

运行: python -m pytest test/ -v
或者: python test/test_servo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ft_servo import FTServo, calibrate_servo, CalibrationResult
from core.display import (
    FTSCSParser, FrameParser, CalibrationResult as CR,
    show_port_info, show_frame, show_servo_status,
    show_scan_result, show_step, show_step_log,
    show_comparison, show_banner, show_success,
    console, THEME, CommDisplay
)


def test_parser():
    """测试 FT-SCS 协议解析"""
    print("\n=== 测试 FTSCSParser ===")

    # Build a Ping frame
    frame = FTSCSParser.build(1, 0x01, [])
    print(f"Ping TX: {frame.hex()}")
    assert len(frame) == 6

    # Parse it
    parsed = FTSCSParser.parse(frame)
    assert parsed is not None
    assert parsed['id'] == 1
    assert parsed['command'] == 0x01
    assert parsed['checksum_ok'] == True

    # Parse a response (FF FF ID LEN ERROR CHK)
    # Checksum: ~(01+02+00) = FC
    rx = bytes([0xFF, 0xFF, 0x01, 0x02, 0x00, 0xFC])
    parsed = FTSCSParser.parse(rx)
    assert parsed is not None
    assert parsed['id'] == 1
    assert parsed['checksum_ok'] == True
    print("✅ 解析测试通过")


def test_display_functions():
    """测试可视化函数（仅验证不报错）"""
    print("\n=== 测试 Display 函数 ===")

    show_port_info("/dev/cu.usbmodem5B790502931", 1000000)

    tx = FTSCSParser.build(1, 0x01, [])
    show_frame("TX", tx)

    status = {
        'position': 2048,
        'speed': 0,
        'load': 120,
        'voltage': 53,
        'temperature': 27,
        'moving': 0,
    }
    show_servo_status(1, status)

    servos = [
        {'id': 1, 'model': 0x0903, 'position': 2048},
        {'id': 2, 'model': 0x0903, 'position': 100},
    ]
    show_scan_result(servos)

    steps = []
    show_step(steps, "扫描端口")
    show_step(steps, "找到 ID=1 ✅")
    show_step_log(steps)

    show_comparison("校准结果",
                    {'位置': 2, '偏移': 0},
                    {'位置': 2048, '偏移': 4093})

    show_banner("测试完成", "green")
    show_success("全部测试通过")
    print("✅ Display 测试通过")


def test_comm_display():
    """测试 CommDisplay 一站式接口"""
    print("\n=== 测试 CommDisplay ===")

    disp = CommDisplay()
    disp.banner("CommDisplay 测试")
    disp.port("/dev/cu.usbmodem5B790502931", 1000000)

    tx = FTSCSParser.build(1, 0x01, [])
    disp.frame("TX", tx)

    status = {
        'position': 2048,
        'speed': 0,
        'load': 120,
        'voltage': 53,
        'temperature': 27,
        'moving': 0,
    }
    disp.status(1, status, "测试")
    disp.ok("CommDisplay 测试通过")


def test_real_hardware():
    """测试真实硬件（如果连接）"""
    print("\n=== 真实硬件测试 ===")

    import serial.tools.list_ports
    port = None
    for p in serial.tools.list_ports.comports():
        if 'usbmodem' in p.device:
            port = p.device
            break

    if not port:
        print("⚠️ 未找到串口设备，跳过硬件测试")
        return

    print(f"使用端口: {port}")

    with FTServo(port) as servo:
        # Scan
        found = servo.scan()
        print(f"找到舵机: {found}")

        if found:
            for sid in found:
                status = servo.get_all_status(sid)
                show_servo_status(sid, status)
        else:
            print("⚠️ 未找到舵机")


if __name__ == '__main__':
    test_parser()
    test_display_functions()
    test_comm_display()
    test_real_hardware()
    print("\n" + "="*50)
    print("全部测试完成")
