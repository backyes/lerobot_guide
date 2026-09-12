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
from typing import List, Tuple, Optional, Dict, Any

from display import (
    FTSCSParser, CalibrationResult,
    show_port_info, show_servo_status, show_frame,
    show_scan_result, show_step, show_step_log,
    show_comparison, show_banner, show_success, show_fail,
    show_warn, show_info, confirm_action, console
)


class FTServo:
    """飞腾串口舵机控制类"""

    INST_PING = 0x01
    INST_READ = 0x02
    INST_WRITE = 0x03
    INST_REG_WRITE = 0x04

    REG_MODEL_L = 3
    REG_ID = 5
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
        self.port = port
        self.baud = baud
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)

    def _checksum(self, data: List[int]) -> int:
        return (~sum(data)) & 0xFF

    def _send(self, id: int, inst: int, params: List[int], verbose: bool = False):
        length = len(params) + 2
        header = [0xFF, 0xFF, id, length, inst] + params
        chk = self._checksum(header[2:])
        frame = bytes(header + [chk])
        self.ser.write(frame)
        if verbose:
            show_frame("TX", frame)
        time.sleep(0.02)

    def _read_response(self, expected_len: int = 6, verbose: bool = False) -> Optional[bytes]:
        time.sleep(0.05)
        if self.ser.in_waiting >= expected_len:
            resp = self.ser.read(self.ser.in_waiting)
            if verbose:
                show_frame("RX", resp)
            return resp
        return None

    def ping(self, id: int, verbose: bool = False) -> bool:
        self._send(id, self.INST_PING, [], verbose=verbose)
        resp = self._read_response(verbose=verbose)
        if resp and len(resp) >= 6:
            if resp[0] == 0xFF and resp[1] == 0xFF:
                if resp[2] == id or id == 0xFE:
                    return True
        return False

    def read_byte(self, id: int, addr: int, verbose: bool = False) -> int:
        self._send(id, self.INST_READ, [addr, 1], verbose=verbose)
        resp = self._read_response(verbose=verbose)
        if resp and len(resp) >= 7 and resp[0] == 0xFF and resp[1] == 0xFF:
            return resp[5]
        return -1

    def read_word(self, id: int, addr: int, verbose: bool = False) -> int:
        self._send(id, self.INST_READ, [addr, 2], verbose=verbose)
        resp = self._read_response(verbose=verbose)
        if resp and len(resp) >= 8 and resp[0] == 0xFF and resp[1] == 0xFF:
            return resp[5] + (resp[6] << 8)
        return -1

    def write_byte(self, id: int, addr: int, val: int, verbose: bool = False):
        self._send(id, self.INST_WRITE, [addr, val & 0xFF], verbose=verbose)

    def write_word(self, id: int, addr: int, val: int, verbose: bool = False):
        lo = val & 0xFF
        hi = (val >> 8) & 0xFF
        self._send(id, self.INST_WRITE, [addr, lo, hi], verbose=verbose)

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

    def scan(self, max_id: int = 253, verbose: bool = False) -> List[int]:
        return [i for i in range(max_id + 1) if self.ping(i, verbose=verbose)]

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ============================================================
# Calibration System (using display module)
# ============================================================

def calibrate_servo(servo, id: int, target="center",
                    confirm_callback=None, verbose=False):
    """系统化校准流程"""
    steps = []
    details = {'steps': steps, 'target': target}

    show_banner(f"🔧 舵机校准流程 | ID={id}", "cyan")

    show_step(steps, "预检：Ping 舵机...")
    if not servo.ping(id, verbose=verbose):
        show_step(steps, "❌ 舵机无响应，中止")
        return CalibrationResult.FAILED, details
    show_step(steps, "✅ 舵机在线")

    show_step(steps, "读取当前状态...")
    current_pos = servo.get_position(id)
    current_offset = servo.read_word(id, servo.REG_POS_OFFSET_L)
    status = servo.get_all_status(id)
    show_servo_status(id, status, "校准前")

    if target == "center":
        show_step(steps, f"目标：中位校准（位置 {current_pos} 设为零点）")
    elif isinstance(target, int):
        show_step(steps, f"目标：指定位置 {target}")

    # Confirm
    preview = {
        'id': id,
        'current_pos': current_pos,
        'current_offset': current_offset,
        'target': target,
    }
    if confirm_callback and not confirm_callback(preview):
        show_step(steps, "⏹ 用户取消")
        return CalibrationResult.CANCELLED, details

    # Execute
    show_banner("执行校准", "yellow")
    show_step(steps, "写 Torque Enable = 128（校准指令）")
    servo.write_byte(id, servo.REG_TORQUE_ENABLE, 128, verbose=verbose)
    time.sleep(0.3)

    show_step(steps, "写 Torque Enable = 1（开启扭矩）")
    servo.enable_torque(id, True)
    time.sleep(0.1)

    # Verify
    show_banner("验证结果", "green")
    new_offset = servo.read_word(id, servo.REG_POS_OFFSET_L)
    new_pos = servo.get_position(id)
    new_status = servo.get_all_status(id)
    show_servo_status(id, new_status, "校准后")

    show_comparison("校准结果",
                    {'位置': current_pos, '偏移': current_offset},
                    {'位置': new_pos, '偏移': new_offset},
                    field_config={
                        '位置': ('位置', str),
                        '偏移': ('偏移', str),
                    })

    result = CalibrationResult.SUCCESS if new_offset != current_offset else CalibrationResult.FAILED
    details['before'] = {'pos': current_pos, 'offset': current_offset}
    details['after'] = {'pos': new_pos, 'offset': new_offset}
    details['result'] = result

    show_banner(f"{'✅ 校准成功' if result == 'success' else '⚠️ 校准未生效'}",
                "green" if result == 'success' else "red")

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
    parser.add_argument('--verbose', '-v', action='store_true', help='显示通信帧')
    sub = parser.add_subparsers(dest='command')

    scan_p = sub.add_parser('scan', help='扫描舵机')
    scan_p.add_argument('--port')
    scan_p.add_argument('--baud', type=int, default=1000000)

    cal_p = sub.add_parser('calibrate', help='系统化校准')
    cal_p.add_argument('--port', required=True)
    cal_p.add_argument('--id', type=int, required=True)
    cal_p.add_argument('--baud', type=int, default=1000000)
    cal_p.add_argument('--target', default='center')
    cal_p.add_argument('--yes', '-y', action='store_true')

    id_p = sub.add_parser('set-id', help='修改 ID')
    id_p.add_argument('--port', required=True)
    id_p.add_argument('--old', type=int, required=True)
    id_p.add_argument('--new', type=int, required=True)
    id_p.add_argument('--baud', type=int, default=1000000)

    st_p = sub.add_parser('status', help='读取状态')
    st_p.add_argument('--port', required=True)
    st_p.add_argument('--id', type=int, required=True)
    st_p.add_argument('--baud', type=int, default=1000000)

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
        console.print('[red]❌ 未找到串口[/red]')
        return

    verbose = args.verbose
    show_port_info(port, args.baud, chip='CH343P', protocol='FT-SCS')

    with FTServo(port, baud=args.baud) as servo:
        if args.command == 'scan':
            show_banner('🔍 扫描舵机', 'cyan')
            found = []
            for i in range(254):
                if servo.ping(i, verbose=verbose):
                    found.append(i)
                    model = servo.read_word(i, 3)
                    pos = servo.get_position(i)
                    console.print(f"  [green]✅ ID={i:3d}[/green]  型号=0x{model:04X}  位置={pos}")
            show_scan_result([{'id': i, 'model': 0, 'position': 0} for i in found])
            console.print(f"[bold]共 {len(found)} 个舵机: {found}[/bold]")

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
                return confirm_action(f"校准 ID={preview['id']}, 位置={preview['current_pos']}")

            result, details = calibrate_servo(servo, args.id, target, confirm, verbose)
            if result == CalibrationResult.CANCELLED:
                sys.exit(1)

        elif args.command == 'set-id':
            show_banner('🆔 修改舵机 ID', 'cyan')
            if servo.set_id(args.old, args.new):
                show_success(f"成功（断电后生效）")
            else:
                show_fail("失败")

        elif args.command == 'status':
            show_servo_status(args.id, servo.get_all_status(args.id))

        elif args.command == 'monitor':
            console.print(f"📊 监控 ID={args.id}（Ctrl+C 停止）...")
            try:
                while True:
                    s = servo.get_all_status(args.id)
                    console.print(
                        f"\r  [bold]pos[/bold]={s['position']:5d}  "
                        f"[bold]spd[/bold]={s['speed']:5d}  "
                        f"[bold]load[/bold]={s['load']:5d}  "
                        f"[bold]volt[/bold]={s['voltage']/10:.1f}V  "
                        f"[bold]temp[/bold]={s['temperature']}°C  "
                        f"[bold]moving[/bold]={s['moving']}",
                        end='', style="cyan"
                    )
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                console.print("\n[yellow]停止[/yellow]")


if __name__ == '__main__':
    main()
