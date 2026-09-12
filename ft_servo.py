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
from typing import List, Tuple, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.syntax import Syntax
from rich.columns import Columns
from rich import box
from io import StringIO


# ============================================================
# Display Layer
# ============================================================

console = Console()


def show_device_info(port: str, baud: int, vid: str = "1A86", pid: str = "55D3",
                     chip: str = "CH343P") -> None:
    """展示 USB 设备信息"""
    table = Table(
        title="[bold cyan]🔌 设备信息[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
    )
    table.add_column("属性", style="dim", width=12)
    table.add_column("值", style="white")

    table.add_row("端口", f"[bold]{port}[/bold]")
    table.add_row("波特率", f"[bold green]{baud:,} bps[/bold green]")
    table.add_row("USB 芯片", f"[bold yellow]{chip}[/bold yellow]")
    table.add_row("VID:PID", f"[bold]0x{vid}:0x{pid}[/bold]")
    table.add_row("协议", "[bold]FT-SCS[/bold]")

    console.print(table)


def show_frame_breakdown(direction: str, raw: bytes) -> None:
    """展示通信帧解析"""
    if len(raw) < 6:
        return

    hex_str = " ".join(f"{b:02X}" for b in raw)

    if direction == "TX":
        title = "[bold yellow]📤 TX 发送帧[/bold yellow]"
        color = "yellow"
    else:
        title = "[bold green]📥 RX 响应帧[/bold green]"
        color = "green"

    # Parse fields
    fields = []
    if raw[0] == 0xFF and raw[1] == 0xFF:
        fields.append(("FF FF", "帧头", raw[0:2]))
        fields.append((f"{raw[2]:02X}", "ID", raw[2:3]))
        fields.append((f"{raw[3]:02X}", "长度", raw[3:4]))
        fields.append((f"{raw[4]:02X}", "指令/错误", raw[4:5]))

        data_len = raw[3] - 2
        if len(raw) >= 5 + data_len:
            data = raw[5:5 + data_len]
            data_hex = " ".join(f"{b:02X}" for b in data)
            fields.append((data_hex, "数据", data))

        if len(raw) >= 5 + data_len + 1:
            chk = raw[5 + data_len]
            fields.append((f"{chk:02X}", "校验和", bytes([chk])))

    field_text = "\n".join(
        f"  [dim]{name:10s}[/dim] {val}" for val, name, _ in fields
    )

    syntax = Syntax(hex_str, "hex", theme="monokai", padding=(0, 2))

    panel = Panel(
        f"{syntax}\n\n{field_text}",
        title=title,
        border_style=color,
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def show_status_table(id: int, status: dict, title: str = "当前状态") -> None:
    """展示舵机状态表格"""
    table = Table(
        title=f"[bold cyan]📊 ID={id} {title}[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
    )
    table.add_column("参数", style="dim", width=14)
    table.add_column("原始值", justify="right", style="bold")
    table.add_column("物理量", justify="right", style="green")
    table.add_column("状态", justify="center", width=8)

    # Position
    pos = status.get('position', 0)
    deg = pos * 0.087
    pos_style = "green" if 1900 < pos < 2200 else "yellow"
    table.add_row(
        "位置", f"[bold]{pos}[/bold]", f"{pos_style}°",
        "✅" if 1900 < pos < 2200 else "⚠️"
    )

    # Speed
    speed = status.get('speed', 0)
    table.add_row("速度", f"{speed}", f"{speed * 0.732:.1f} RPM",
                  "✅" if speed == 0 else "🔄")

    # Load
    load = status.get('load', 0)
    table.add_row("负载", f"{load}", f"{load * 0.1:.1f}%",
                  "✅" if abs(load) < 500 else "⚠️")

    # Voltage
    volt = status.get('voltage', 0)
    volt_v = volt / 10.0
    volt_style = "green" if 45 < volt < 84 else "red"
    table.add_row("电压", f"{volt}", f"[{volt_style}]{volt_v:.1f}V[/{volt_style}]",
                  "✅" if 45 < volt < 84 else "❌")

    # Temperature
    temp = status.get('temperature', 0)
    temp_style = "green" if temp < 60 else "red" if temp > 75 else "yellow"
    table.add_row("温度", f"{temp}", f"[{temp_style}]{temp}°C[/{temp_style}]",
                  "✅" if temp < 60 else "⚠️")

    # Moving
    moving = status.get('moving', 0)
    table.add_row("运动状态", f"{moving}",
                  "🔄 运动中" if moving else "⏹ 停止",
                  "")

    console.print(table)


def show_calibration_preview(id: int, preview: dict) -> None:
    """校准前预览"""
    table = Table(
        title="[bold yellow]⚠️  校准确认[/bold yellow]",
        box=box.HEAVY_EDGE,
        show_header=True,
        header_style="bold yellow",
        border_style="yellow",
    )
    table.add_column("项目", style="dim")
    table.add_column("值", style="white")

    table.add_row("舵机 ID", f"[bold]{id}[/bold]")
    table.add_row("当前位置", f"[bold]{preview['current_pos']}[/bold]")
    table.add_row("当前偏移", f"{preview['current_offset']}")
    table.add_row("校准目标", f"[bold cyan]{preview['target']}[/bold cyan]")
    table.add_row("校准效果", "[red]当前位置将成为新的零点[/red]")

    console.print()
    console.print(table)
    console.print()


def show_calibration_result(result: str, details: dict) -> None:
    """展示校准结果"""
    if result == "success":
        title = "✅ 校准成功"
        color = "green"
    elif result == "failed":
        title = "❌ 校准失败"
        color = "red"
    else:
        title = "⏹ 已取消"
        color = "yellow"

    before = details.get('before', {})
    after = details.get('after', {})

    table = Table(
        title=f"[bold {color}]{title}[/bold {color}]",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {color}",
        border_style=color,
    )
    table.add_column("参数", style="dim", width=12)
    table.add_column("校准前", justify="right")
    table.add_column("", justify="center", width=4)
    table.add_column("校准后", justify="right", style="bold green")

    table.add_row(
        "位置",
        str(before.get('pos', 'N/A')),
        "→",
        str(after.get('pos', 'N/A'))
    )
    table.add_row(
        "偏移",
        str(before.get('offset', 'N/A')),
        "→",
        str(after.get('offset', 'N/A'))
    )

    console.print()
    console.print(table)
    console.print()


def show_step_log(steps: List[str], title: str = "校准日志") -> None:
    """展示步骤日志"""
    table = Table(
        title=f"[bold cyan]📋 {title}[/bold cyan]",
        box=box.SIMPLE,
        show_header=False,
        border_style="dim",
        padding=(0, 2),
    )
    table.add_column("步骤", style="dim", width=4)
    table.add_column("描述", style="white")

    for i, step in enumerate(steps, 1):
        icon = "✅" if "成功" in step or "完成" in step else \
               "❌" if "失败" in step or "中止" in step else \
               "➡️" if i < len(steps) else "⏹"
        table.add_row(f"[dim]{i:2d}[/dim]", step)

    console.print(table)


# ============================================================
# Core Library
# ============================================================

class FTServo:
    """飞腾串口舵机控制类"""

    INST_PING = 0x01
    INST_READ = 0x02
    INST_WRITE = 0x03
    INST_REG_WRITE = 0x04

    # 寄存器地址
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
        self._last_tx = b''
        self._last_rx = b''

    def _checksum(self, data: List[int]) -> int:
        return (~sum(data)) & 0xFF

    def _send(self, id: int, inst: int, params: List[int], verbose: bool = False):
        length = len(params) + 2
        header = [0xFF, 0xFF, id, length, inst] + params
        chk = self._checksum(header[2:])
        frame = bytes(header + [chk])
        self._last_tx = frame
        self.ser.write(frame)
        if verbose:
            show_frame_breakdown("TX", frame)
        time.sleep(0.02)

    def _read_response(self, expected_len: int = 6, verbose: bool = False) -> Optional[bytes]:
        time.sleep(0.05)
        if self.ser.in_waiting >= expected_len:
            resp = self.ser.read(self.ser.in_waiting)
            self._last_rx = resp
            if verbose:
                show_frame_breakdown("RX", resp)
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
        found = []
        for i in range(max_id + 1):
            if self.ping(i, verbose=verbose):
                found.append(i)
        return found

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ============================================================
# Calibration System with Visualization
# ============================================================

class CalibrationResult:
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


def calibrate_servo(servo: FTServo, id: int, target: str = "center",
                    confirm_callback=None, verbose: bool = False) -> Tuple[str, dict]:
    """
    系统化的舵机校准流程（带可视化）
    """
    steps = []
    details = {'steps': steps, 'target': target, 'verbose': verbose}

    console.print()
    console.rule(f"[bold cyan]🔧 舵机校准流程 | ID={id}[/bold cyan]")

    # Phase 1: 预检
    step_msg = "预检：Ping 舵机..."
    console.print(f"[dim]  [{len(steps)+1:2d}][/dim] {step_msg}")
    steps.append(step_msg)

    if not servo.ping(id, verbose=verbose):
        msg = "❌ 舵机无响应，中止"
        console.print(f"  [red]{msg}[/red]")
        steps.append(msg)
        return CalibrationResult.FAILED, details
    msg = "✅ 舵机在线"
    console.print(f"  [green]{msg}[/green]")
    steps.append(msg)

    # Phase 2: 读取当前状态
    msg = "读取当前状态..."
    console.print(f"[dim]  [{len(steps)+1:2d}][/dim] {msg}")
    steps.append(msg)

    current_pos = servo.get_position(id)
    current_offset = servo.read_word(id, FTServo.REG_POS_OFFSET_L)
    status = servo.get_all_status(id)

    details['before_raw'] = {'pos': current_pos, 'offset': current_offset}
    show_status_table(id, status, "校准前")

    # Phase 3: 确定目标
    if target == "center":
        msg = f"目标：中位校准（位置 {current_pos} 设为零点）"
    elif isinstance(target, int):
        msg = f"目标：指定位置 {target}"
    else:
        msg = f"目标：{target}"
    console.print(f"[dim]  [{len(steps)+1:2d}][/dim] [cyan]{msg}[/cyan]")
    steps.append(msg)

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
    show_calibration_preview(id, preview)

    if confirm_callback:
        if not confirm_callback(preview):
            msg = "⏹ 用户取消"
            console.print(f"[yellow]{msg}[/yellow]")
            steps.append(msg)
            return CalibrationResult.CANCELLED, details

    # Phase 5: 执行校准
    console.rule("[bold yellow]执行校准[/bold yellow]")

    msg = "写 Torque Enable = 128（校准指令）"
    console.print(f"[dim]  [{len(steps)+1:2d}][/dim] → {msg}")
    steps.append(msg)
    servo.write_byte(id, FTServo.REG_TORQUE_ENABLE, 128, verbose=verbose)
    time.sleep(0.3)

    msg = "写 Torque Enable = 1（开启扭矩）"
    console.print(f"[dim]  [{len(steps)+1:2d}][/dim] → {msg}")
    steps.append(msg)
    servo.enable_torque(id, True)
    time.sleep(0.1)

    # Phase 6: 验证
    console.rule("[bold green]验证结果[/bold green]")

    new_offset = servo.read_word(id, FTServo.REG_POS_OFFSET_L)
    new_pos = servo.get_position(id)
    new_status = servo.get_all_status(id)

    details['after_raw'] = {'pos': new_pos, 'offset': new_offset}

    show_status_table(id, new_status, "校准后")

    console.print(f"[dim]  [{len(steps)+1:2d}][/dim] 偏移: {current_offset} → [bold]{new_offset}[/bold]")
    console.print(f"[dim]  [{len(steps)+2:2d}][/dim] 位置: {current_pos} → [bold]{new_pos}[/bold]")

    if new_offset != current_offset:
        result = CalibrationResult.SUCCESS
        msg = "✅ 校准成功"
    else:
        result = CalibrationResult.FAILED
        msg = "⚠️ 校准可能未生效（偏移未变化）"

    console.print()
    console.rule(f"[bold {'green' if result == 'success' else 'red'}]{msg}[/bold {'green' if result == 'success' else 'red'}]")

    details['result'] = result
    details['before'] = details['before_raw']
    details['after'] = details['after_raw']

    show_calibration_result(result, details)

    return result, details


# ============================================================
# CLI Entry
# ============================================================

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
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示通信帧详情')
    sub = parser.add_subparsers(dest='command')

    # scan
    scan_p = sub.add_parser('scan', help='扫描总线上的舵机')
    scan_p.add_argument('--port', help='串口路径')
    scan_p.add_argument('--baud', type=int, default=1000000)

    # calibrate
    cal_p = sub.add_parser('calibrate', help='系统化校准流程')
    cal_p.add_argument('--port', required=True)
    cal_p.add_argument('--id', type=int, required=True)
    cal_p.add_argument('--baud', type=int, default=1000000)
    cal_p.add_argument('--target', default='center')
    cal_p.add_argument('--yes', '-y', action='store_true', help='跳过确认')

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
        console.print('[red]❌ 未找到串口[/red]')
        return

    verbose = args.verbose

    # Show device info for all commands
    show_device_info(port, args.baud)

    with FTServo(port, baud=args.baud) as servo:
        if args.command == 'scan':
            console.rule("[bold cyan]🔍 扫描舵机[/bold cyan]")
            found = []
            with console.status("[dim]扫描中...[/dim]", spinner="dots"):
                for i in range(254):
                    if servo.ping(i, verbose=verbose):
                        found.append(i)
                        model = servo.read_word(i, 3)
                        pos = servo.get_position(i)
                        console.print(f"  [green]✅ ID={i:3d}[/green]  型号=0x{model:04X}  位置={pos}")

            console.print(f"\n[bold]共找到 {len(found)} 个舵机:[/bold] {found}")

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
                ans = console.input("\n  [bold yellow]确认校准?[/bold yellow] [y/N] ")
                return ans.lower() == 'y'

            result, details = calibrate_servo(servo, args.id, target, confirm, verbose)
            if result == CalibrationResult.CANCELLED:
                sys.exit(1)

        elif args.command == 'set-id':
            console.rule("[bold cyan]🆔 修改舵机 ID[/bold cyan]")
            console.print(f"  [dim]从 {args.old} 改为 {args.new}[/dim]")
            if servo.set_id(args.old, args.new):
                console.print("  [green]✅ 成功（断电后永久生效）[/green]")
            else:
                console.print("  [red]❌ 失败[/red]")

        elif args.command == 'status':
            status = servo.get_all_status(args.id)
            show_status_table(args.id, status)

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
