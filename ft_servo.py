#!/usr/bin/env python3
"""
FT Servo Toolkit | HLS / SMS_STS / SCS Protocol
面向 LeRobot 机械臂开发的串口舵机控制库

Contributors: backyes, hermes
"""

import serial
import time
import argparse
import sys
from typing import List, Tuple, Optional


class FTServo:
    """飞腾串口舵机控制类"""

    INST_PING = 0x01
    INST_READ = 0x02
    INST_WRITE = 0x03
    INST_REG_WRITE = 0x04
    INST_REG_ACTION = 0x05

    # 寄存器地址
    REG_MODEL_L = 3
    REG_ID = 5
    REG_BAUD_RATE = 6
    REG_LOCK = 55
    REG_TORQUE_ENABLE = 40
    REG_GOAL_POS_L = 42
    REG_PRESENT_POS_L = 56
    REG_PRESENT_SPEED_L = 58
    REG_PRESENT_LOAD_L = 60
    REG_PRESENT_VOLTAGE = 62
    REG_PRESENT_TEMP = 63
    REG_MOVING = 66
    REG_POS_OFFSET_L = 31

    def __init__(self, port: str, baud: int = 1000000, timeout: float = 0.3):
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)

    def _checksum(self, data: List[int]) -> int:
        return (~sum(data)) & 0xFF

    def _send(self, id: int, inst: int, params: List[int]):
        length = len(params) + 2
        header = [0xFF, 0xFF, id, length, inst] + params
        chk = self._checksum(header[2:])
        self.ser.write(bytes(header + [chk]))
        time.sleep(0.02)

    def _read_response(self, expected_len: int = 6) -> Optional[bytes]:
        time.sleep(0.05)
        if self.ser.in_waiting >= expected_len:
            return self.ser.read(self.ser.in_waiting)
        return None

    def ping(self, id: int) -> bool:
        self._send(id, self.INST_PING, [])
        resp = self._read_response()
        if resp and len(resp) >= 6:
            if resp[0] == 0xFF and resp[1] == 0xFF:
                if resp[2] == id or id == 0xFE:
                    return True
        return False

    def read_byte(self, id: int, addr: int) -> int:
        self._send(id, self.INST_READ, [addr, 1])
        resp = self._read_response()
        if resp and len(resp) >= 7 and resp[0] == 0xFF and resp[1] == 0xFF:
            return resp[5]
        return -1

    def read_word(self, id: int, addr: int) -> int:
        self._send(id, self.INST_READ, [addr, 2])
        resp = self._read_response()
        if resp and len(resp) >= 8 and resp[0] == 0xFF and resp[1] == 0xFF:
            return resp[5] + (resp[6] << 8)
        return -1

    def write_byte(self, id: int, addr: int, val: int):
        self._send(id, self.INST_WRITE, [addr, val & 0xFF])

    def write_word(self, id: int, addr: int, val: int):
        lo = val & 0xFF
        hi = (val >> 8) & 0xFF
        self._send(id, self.INST_WRITE, [addr, lo, hi])

    def set_id(self, old_id: int, new_id: int) -> bool:
        self.write_byte(old_id, self.REG_LOCK, 0)
        time.sleep(0.1)
        self.write_byte(old_id, self.REG_ID, new_id)
        time.sleep(0.1)
        self.write_byte(new_id, self.REG_LOCK, 1)
        time.sleep(0.2)
        return self.ping(new_id)

    def enable_torque(self, id: int, enable: bool = True):
        self.write_byte(id, self.REG_TORQUE_ENABLE, 1 if enable else 0)

    def get_position(self, id: int) -> int:
        return self.read_word(id, self.REG_PRESENT_POS_L)

    def get_all_status(self, id: int) -> dict:
        return {
            'position': self.get_position(id),
            'speed': self.read_word(id, self.REG_PRESENT_SPEED_L),
            'load': self.read_word(id, self.REG_PRESENT_LOAD_L),
            'voltage': self.read_byte(id, self.REG_PRESENT_VOLTAGE),
            'temperature': self.read_byte(id, self.REG_PRESENT_TEMP),
            'moving': self.read_byte(id, self.REG_MOVING),
        }

    def scan(self, max_id: int = 253) -> List[int]:
        return [i for i in range(max_id + 1) if self.ping(i)]

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ============================================================
# Calibration System
# ============================================================

class CalibrationResult:
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


def calibrate_servo(servo: FTServo, id: int, target = "center",
                    confirm_callback=None) -> Tuple[str, dict]:
    """
    系统化的舵机校准流程

    Args:
        servo: FTServo 实例
        id: 舵机 ID
        target: 校准目标 ("center"=中位, "min"=最小, "max"=最大, int=指定位置)
        confirm_callback: 确认回调 fn(preview: dict) -> bool

    Returns:
        (CalibrationResult, details_dict)
    """
    log = []
    details = {'steps': [], 'target': target}

    def step(msg):
        log.append(msg)
        details['steps'].append(msg)
        print(f"  [{len(log):2d}] {msg}")

    print(f"\n{'='*50}")
    print(f"  舵机校准流程 | ID={id}")
    print(f"{'='*50}\n")

    # Phase 1: 预检
    step("预检：Ping 舵机...")
    if not servo.ping(id):
        step("❌ 舵机无响应，中止")
        return CalibrationResult.FAILED, details
    step("✅ 舵机在线")

    # Phase 2: 读取当前状态
    step("读取当前状态...")
    current_pos = servo.get_position(id)
    current_offset = servo.read_word(id, FTServo.REG_POS_OFFSET_L)
    status = servo.get_all_status(id)

    step(f"  当前位置: {current_pos} ({current_pos * 0.087:.1f}°)")
    step(f"  当前偏移: {current_offset}")
    step(f"  电压: {status['voltage']/10:.1f}V")
    step(f"  温度: {status['temperature']}°C")
    step(f"  运动中: {'是' if status['moving'] else '否'}")

    # Phase 3: 确定目标
    if target == "center":
        goal_pos = current_pos  # 当前位置设为零点
        step(f"目标: 中位校准（当前位置 {current_pos} 设为零点）")
    elif target == "min":
        step("目标: 最小位置校准")
        goal_pos = "min"
    elif target == "max":
        step("目标: 最大位置校准")
        goal_pos = "max"
    elif isinstance(target, int):
        step(f"目标: 指定位置 {target}")
        goal_pos = target
    else:
        step(f"❌ 未知目标: {target}")
        return CalibrationResult.FAILED, details

    # Phase 4: 确认
    preview = {
        'id': id,
        'current_pos': current_pos,
        'current_offset': current_offset,
        'target': target,
        'voltage': status['voltage'],
        'temperature': status['temperature'],
    }
    details['preview'] = preview

    if confirm_callback:
        print(f"\n  ⚠️  即将执行校准，请确认：")
        print(f"     舵机 ID: {id}")
        print(f"     当前位置: {current_pos}")
        print(f"     校准后当前位置将成为新的零点")
        if not confirm_callback(preview):
            step("用户取消")
            return CalibrationResult.CANCELLED, details

    # Phase 5: 执行校准
    step("开始校准...")
    step("  → 写 Torque Enable = 128（校准指令）")
    servo.write_byte(id, FTServo.REG_TORQUE_ENABLE, 128)
    time.sleep(0.3)

    step("  → 写 Torque Enable = 1（开启扭矩）")
    servo.enable_torque(id, True)
    time.sleep(0.1)

    # Phase 6: 验证
    new_offset = servo.read_word(id, FTServo.REG_POS_OFFSET_L)
    new_pos = servo.get_position(id)
    new_status = servo.get_all_status(id)

    step(f"  新偏移: {current_offset} → {new_offset}")
    step(f"  新位置: {current_pos} → {new_pos}")
    step(f"  运动中: {'是' if new_status['moving'] else '否'}")

    if new_offset != current_offset:
        step("✅ 校准成功（偏移已更新）")
        result = CalibrationResult.SUCCESS
    else:
        step("⚠️ 校准可能未生效（偏移未变化）")
        result = CalibrationResult.FAILED

    details['result'] = result
    details['before'] = {'pos': current_pos, 'offset': current_offset}
    details['after'] = {'pos': new_pos, 'offset': new_offset}

    print(f"\n{'='*50}")
    print(f"  结果: {result.upper()}")
    print(f"{'='*50}\n")

    return result, details


def auto_detect_port() -> Optional[str]:
    import serial.tools.list_ports
    for p in serial.tools.list_ports.comports():
        if 'usbmodem' in p.device or 'usbserial' in p.device:
            return p.device
    return None


def main():
    parser = argparse.ArgumentParser(
        description='FT 舵机调试工具 | Contributors: backyes, hermes'
    )
    sub = parser.add_subparsers(dest='command')

    # scan
    scan_p = sub.add_parser('scan', help='扫描总线上的舵机')
    scan_p.add_argument('--port', help='串口路径（自动检测）')
    scan_p.add_argument('--baud', type=int, default=1000000)

    # calibrate
    cal_p = sub.add_parser('calibrate', help='系统化校准流程')
    cal_p.add_argument('--port', required=True)
    cal_p.add_argument('--id', type=int, required=True)
    cal_p.add_argument('--baud', type=int, default=1000000)
    cal_p.add_argument('--target', default='center',
                       help='校准目标: center/min/max/具体数值')
    cal_p.add_argument('--yes', '-y', action='store_true',
                       help='跳过确认，直接执行')

    # set-id
    id_p = sub.add_parser('set-id', help='修改舵机 ID')
    id_p.add_argument('--port', required=True)
    id_p.add_argument('--old', type=int, required=True)
    id_p.add_argument('--new', type=int, required=True)
    id_p.add_argument('--baud', type=int, default=1000000)

    # status
    st_p = sub.add_parser('status', help='读取状态')
    st_p.add_argument('--port', required=True)
    st_p.add_argument('--id', type=int, required=True)
    st_p.add_argument('--baud', type=int, default=1000000)

    # monitor
    mon_p = sub.add_parser('monitor', help='实时监控')
    mon_p.add_argument('--port', required=True)
    mon_p.add_argument('--id', type=int, required=True)
    mon_p.add_argument('--baud', type=int, default=1000000)
    mon_p.add_argument('--interval', type=float, default=0.1)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    port = getattr(args, 'port', None) or auto_detect_port()
    if not port:
        print('❌ 未找到串口')
        return

    with FTServo(port, baud=args.baud) as servo:
        if args.command == 'scan':
            print('🔍 扫描中...')
            for i in range(254):
                if servo.ping(i):
                    model = servo.read_word(i, 3)
                    pos = servo.get_position(i)
                    print(f"  ID={i:3d}  型号=0x{model:04X}  位置={pos}")

        elif args.command == 'calibrate':
            target = args.target
            if target not in ('center', 'min', 'max'):
                try:
                    target = int(target)
                except ValueError:
                    pass

            def confirm(preview):
                if args.yes:
                    return True
                ans = input(f"\n  确认校准 ID={preview['id']}? [y/N] ")
                return ans.lower() == 'y'

            result, details = calibrate_servo(servo, args.id, target, confirm)
            if result == CalibrationResult.CANCELLED:
                print("已取消")
                sys.exit(1)

        elif args.command == 'set-id':
            print(f"🆔 修改 ID: {args.old} → {args.new}")
            if servo.set_id(args.old, args.new):
                print("  ✅ 成功（断电后永久生效）")
            else:
                print("  ❌ 失败")

        elif args.command == 'status':
            s = servo.get_all_status(args.id)
            print(f"📊 ID={args.id}:")
            for k, v in s.items():
                print(f"  {k}: {v}")

        elif args.command == 'monitor':
            print(f"📊 监控 ID={args.id}（Ctrl+C 停止）...")
            try:
                while True:
                    s = servo.get_all_status(args.id)
                    print(f"\r  pos={s['position']:5d}  spd={s['speed']:5d}  "
                          f"load={s['load']:5d}  {s['voltage']/10:.1f}V  "
                          f"{s['temperature']}°C  moving={s['moving']}", end='', flush=True)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n停止")


if __name__ == '__main__':
    main()
