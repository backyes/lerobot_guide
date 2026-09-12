#!/usr/bin/env python3
"""
SerialComm Display | 串口通信数据结构化可视化模块

通用的串口通信数据展示层，将原始字节流转化为结构化可视化输出。
支持帧解析、设备信息、状态表格、操作日志、结果对比等。

Usage:
    from display import CommDisplay
    display = CommDisplay()
    show_frame("TX", raw_bytes)
    show_status(servo_id, status_dict)
    show_result_table("校准", before, after)

Contributors: backyes, hermes
"""

from typing import List, Tuple, Optional, Dict, Any, Union
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.columns import Columns
from rich.rule import Rule
from rich import box
from rich.style import Style


# ============================================================
# Color Theme
# ============================================================

THEME = {
    "tx": "#FFB400",       # yellow - outbound
    "rx": "#00B86B",       # green - inbound
    "info": "#00BFFF",     # cyan - informational
    "warn": "#FFD700",     # gold - warning
    "err": "#FF3333",      # red - error
    "ok": "#00CC66",       # green - success
    "dim": "#888888",      # gray - secondary
    "field": "#CC7832",    # orange - field name
    "value": "#FFFFFF",    # white - value
    "hex_data": "#A9B7C6", # light gray-blue - hex
}


# ============================================================
# Generic Frame Parser
# ============================================================

class FrameParser:
    """通用串口帧解析器

    协议格式: [HEAD1] [HEAD2] [ID] [LEN] [CMD/ERR] [DATA...] [CHK]

    子类可重写 HEADERS、HAS_CHECKSUM 等属性适配不同协议。
    """

    HEADERS = [0xFF, 0xFF]
    HAS_CHECKSUM = True
    CHECKSUM_FN = staticmethod(lambda data: (~sum(data)) & 0xFF)
    LITTLE_ENDIAN = True

    @classmethod
    def parse(cls, raw: bytes) -> Optional[Dict[str, Any]]:
        """解析单帧数据"""
        if len(raw) < len(cls.HEADERS) + 4:
            return None

        # Check header
        for i, h in enumerate(cls.HEADERS):
            if raw[i] != h:
                return None

        frame = {
            'raw': raw,
            'hex': " ".join(f"{b:02X}" for b in raw),
            'header': raw[:len(cls.HEADERS)],
            'id': raw[len(cls.HEADERS)],
            'length': raw[len(cls.HEADERS) + 1],
        }

        # Command or error byte
        cmd_idx = len(cls.HEADERS) + 2
        frame['command'] = raw[cmd_idx]

        # Data payload
        data_len = frame['length'] - 2
        data_start = cmd_idx + 1
        if len(raw) >= data_start + data_len:
            frame['data'] = raw[data_start:data_start + data_len]
            frame['data_hex'] = " ".join(
                f"{b:02X}" for b in frame['data']
            )
        else:
            frame['data'] = b''
            frame['data_hex'] = ''

        # Checksum verification
        if cls.HAS_CHECKSUM and len(raw) >= data_start + data_len + 1:
            expected_chk = cls.CHECKSUM_FN(raw[2:data_start + data_len])
            actual_chk = raw[data_start + data_len]
            frame['checksum_ok'] = expected_chk == actual_chk
            frame['checksum'] = actual_chk
        else:
            frame['checksum_ok'] = None

        return frame

    @classmethod
    def build(cls, id: int, cmd: int, params: List[int]) -> bytes:
        """构造帧"""
        length = len(params) + 2
        payload = list(cls.HEADERS) + [id, length, cmd] + params
        if cls.HAS_CHECKSUM:
            chk = cls.CHECKSUM_FN(payload[2:])
            payload.append(chk)
        return bytes(payload)

    @classmethod
    def parse_multi(cls, raw: bytes) -> List[Dict[str, Any]]:
        """从连续流中解析多帧"""
        frames = []
        i = 0
        while i < len(raw) - len(cls.HEADERS):
            # Look for header
            if raw[i] == cls.HEADERS[0] and raw[i+1] == cls.HEADERS[1]:
                # Find frame length
                if i + 3 < len(raw):
                    frame_len = raw[i + 3] + len(cls.HEADERS) + 2
                    if cls.HAS_CHECKSUM:
                        frame_len += 1
                    frame_data = raw[i:i + frame_len]
                    parsed = cls.parse(frame_data)
                    if parsed:
                        frames.append(parsed)
                    i += frame_data.__len__()
                else:
                    break
            else:
                i += 1
        return frames


# FT-SCS Protocol Parser (Feetech Servo)
class FTSCSParser(FrameParser):
    """飞腾舵机 FT-SCS 协议解析器"""
    HEADERS = [0xFF, 0xFF]
    HAS_CHECKSUM = True
    LITTLE_ENDIAN = True

    @classmethod
    def parse(cls, raw: bytes) -> Optional[Dict[str, Any]]:
        frame = super().parse(raw)
        if frame is None:
            return None

        # FT-SCS specific: command 0x02 = response frame, error byte
        if frame['command'] == 0x02 and frame['data']:
            frame['error'] = frame['data'][0] if frame['data'] else 0
            frame['error_text'] = cls._error_text(frame['error'])
            frame['payload'] = frame['data'][1:]
        else:
            frame['payload'] = frame['data']

        return frame

    @staticmethod
    def _error_text(code: int) -> str:
        errors = []
        if code & 0x01:
            errors.append("电压异常")
        if code & 0x02:
            errors.append("编码器异常")
        if code & 0x04:
            errors.append("过温")
        if code & 0x08:
            errors.append("过流")
        if code & 0x20:
            errors.append("过载")
        return ", ".join(errors) if errors else "正常"


class CalibrationResult:
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================
# Display Functions
# ============================================================

console = Console()


def show_rule(title: str, style: str = "cyan") -> None:
    console.rule(f"[bold {style}]{title}[/bold {style}]")


def show_port_info(port: str, baud: int, **kwargs) -> None:
    """展示串口连接信息"""
    chip = kwargs.get('chip', 'CH343P')
    vid = kwargs.get('vid', '1A86')
    pid = kwargs.get('pid', '55D3')
    protocol = kwargs.get('protocol', 'FT-SCS')

    table = Table(
        title="🔌 连接信息",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
        padding=(0, 2),
    )
    table.add_column("属性", style="dim", width=12, no_wrap=True)
    table.add_column("值", style="white")

    table.add_row("端口", f"[bold]{port}[/bold]")
    table.add_row("波特率", f"[bold green]{baud:,} bps[/bold green]")
    table.add_row("USB 芯片", f"[bold yellow]{chip}[/bold yellow]")
    table.add_row("VID:PID", f"[bold]0x{vid}:0x{pid}[/bold]")
    table.add_row("协议", f"[bold cyan]{protocol}[/bold cyan]")

    console.print(table)


def show_frame(direction: str, raw: bytes,
               parser: type = FTSCSParser,
               show_fields: bool = True) -> Optional[Dict]:
    """展示通信帧（通用）

    Args:
        direction: "TX" 或 "RX"
        raw: 原始字节数据
        parser: 解析器类（默认 FTSCSParser）
        show_fields: 是否显示字段解析

    Returns:
        解析后的帧字典
    """
    parsed = parser.parse(raw)
    if parsed is None:
        console.print(f"[red]⚠️ 无法解析帧: {raw.hex()}[/red]")
        return None

    is_tx = direction.upper() == "TX"
    theme_color = THEME["tx"] if is_tx else THEME["rx"]
    icon = "📤" if is_tx else "📥"
    title = f"[bold {theme_color}]{icon} {direction.upper()}[/bold {theme_color}]"

    # Hex dump
    hex_lines = []
    for i in range(0, len(raw), 16):
        chunk = raw[i:i+16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(
            chr(b) if 32 <= b < 127 else "." for b in chunk
        )
        hex_lines.append(f"[dim]{i:04x}[/dim]  {hex_part:<48s} │[dim]{ascii_part}[/dim]")

    hex_text = "\n".join(hex_lines)

    # Field breakdown
    if show_fields:
        fields = _build_field_table(parsed)
        content = f"{hex_text}\n\n{fields}"
    else:
        content = hex_text

    panel = Panel(
        content,
        title=title,
        border_style=theme_color,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)

    return parsed


def _build_field_table(parsed: dict) -> Table:
    """构建字段解析表格"""
    t = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
        expand=False,
    )
    t.add_column("字段", style="dim", width=10)
    t.add_column("Hex", style=THEME["hex_data"])
    t.add_column("含义", style="white")

    if 'header' in parsed:
        hex_val = " ".join(f"{b:02X}" for b in parsed['header'])
        t.add_row("帧头", hex_val, "同步字节")

    if 'id' in parsed:
        name = "广播" if parsed['id'] == 0xFE else f"0x{parsed['id']:02X} ({parsed['id']})"
        t.add_row("ID", f"{parsed['id']:02X}", name)

    if 'length' in parsed:
        t.add_row("长度", f"{parsed['length']:02X}", f"{parsed['length']} 字节")

    if 'command' in parsed:
        cmd = parsed['command']
        cmd_name = _cmd_name(cmd)
        t.add_row("指令", f"{cmd:02X}", cmd_name)

    if parsed.get('error_text') is not None:
        err = parsed['error_text']
        style = "green" if err == "正常" else "red"
        t.add_row("状态", "", f"[{style}]{err}[/{style}]")

    if parsed.get('data_hex'):
        t.add_row("数据", parsed['data_hex'], f"{len(parsed['data'])} bytes")

    if parsed.get('checksum_ok') is not None:
        ok = parsed['checksum_ok']
        t.add_row("校验", f"{parsed['checksum']:02X}",
                  "✅ 通过" if ok else "❌ 失败")

    return t


def _cmd_name(cmd: int) -> str:
    """指令码转名称"""
    cmds = {
        0x01: "Ping",
        0x02: "Read",
        0x03: "Write",
        0x04: "RegWrite",
        0x05: "RegAction",
        0x82: "SyncRead",
        0x83: "SyncWrite",
    }
    return cmds.get(cmd, f"Unknown(0x{cmd:02X})")


def show_servo_status(id: int, status: dict, title: str = None) -> None:
    """展示舵机状态表格

    Args:
        id: 舵机 ID
        status: {
            'position': int,    # raw value (0-4095)
            'speed': int,       # raw value
            'load': int,        # raw value
            'voltage': int,     # 0.1V units
            'temperature': int, # °C
            'moving': int,      # 0/1
        }
        title: 表格标题
    """
    title = title or f"ID={id} 状态"

    # Field configs: (key, name, unit_fn, thresholds)
    # thresholds: (ok_range, warn_range)
    fields = [
        ('position', '位置', lambda v: f"{v * 0.087:.1f}°",
         ((1800, 2300), None)),
        ('speed', '速度', lambda v: f"{v * 0.732:.1f} RPM",
         ((0, 10), None)),
        ('load', '负载', lambda v: f"{v * 0.1:.1f}%",
         ((0, 500), (500, 800))),
        ('voltage', '电压', lambda v: f"{v / 10.0:.1f}V",
         ((45, 84), (40, 90))),
        ('temperature', '温度', lambda v: f"{v}°C",
         ((0, 60), (60, 75))),
        ('moving', '运动', lambda v: "🔄 运动" if v else "⏹ 停止",
         None),
    ]

    table = Table(
        title=f"📊 {title}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
        padding=(0, 2),
    )
    table.add_column("参数", style="dim", width=10, justify="center")
    table.add_column("原始值", justify="right", width=8)
    table.add_column("物理量", justify="right", width=14)
    table.add_column("状态", justify="center", width=8)

    for key, name, unit_fn, thresholds in fields:
        if key not in status:
            continue
        val = status[key]
        phys = unit_fn(val)

        # Determine status
        icon = ""
        if thresholds:
            ok_range, warn_range = thresholds
            if ok_range and ok_range[0] <= val <= ok_range[1]:
                icon = "✅"
            elif warn_range and warn_range[0] <= val <= warn_range[1]:
                icon = "⚠️"
            else:
                icon = "❌"
        elif key == 'moving':
            icon = "🔄" if val else ""

        table.add_row(name, str(val), phys, icon)

    console.print(table)


def show_scan_result(servos: list) -> None:
    """展示扫描结果"""
    if not servos:
        console.print("[dim]未找到舵机[/dim]")
        return

    table = Table(
        title="🔍 扫描结果",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
        padding=(0, 2),
    )
    table.add_column("#", style="dim", width=4, justify="center")
    table.add_column("ID", justify="right", style="bold")
    table.add_column("型号", style="cyan")
    table.add_column("位置", justify="right")
    table.add_column("状态", justify="center")

    for i, s in enumerate(servos, 1):
        sid = s.get('id', '?')
        model = s.get('model', '?')
        pos = s.get('position', '?')
        table.add_row(
            str(i),
            f"{sid}",
            f"0x{model}" if isinstance(model, int) else str(model),
            str(pos),
            "✅"
        )

    console.print(table)
    console.print(f"[bold]共 {len(servos)} 个舵机[/bold]\n")


def show_step(steps: list, message: str, icon: str = "➡️") -> list:
    """记录并展示步骤日志

    Args:
        steps: 步骤列表（原地修改）
        message: 步骤描述
        icon: 前置图标

    Returns:
        更新后的步骤列表
    """
    steps.append(message)
    num = len(steps)
    console.print(f"[dim]  [{num:2d}][/dim] {icon} {message}")
    return steps


def show_step_log(steps: list, title: str = "操作日志") -> None:
    """展示完整步骤日志"""
    if not steps:
        return

    table = Table(
        title=f"📋 {title}",
        box=box.SIMPLE,
        show_header=False,
        border_style="dim",
        padding=(0, 2),
    )
    table.add_column("#", style="dim", width=4, justify="center")
    table.add_column("步骤", style="white")

    for i, step in enumerate(steps, 1):
        icon = "✅" if "成功" in step or "完成" in step else \
               "❌" if "失败" in step or "中止" in step else \
               "⏹" if "取消" in step else ""
        table.add_row(str(i), f"{icon} {step}" if icon else step)

    console.print(table)


def show_comparison(title: str, before: dict, after: dict,
                    field_config: dict = None) -> None:
    """展示对比表格（校准/修改前后）

    Args:
        title: 表格标题
        before: {field: value}
        after:  {field: value}
        field_config: {field: (display_name, unit_fn)}
    """
    if field_config is None:
        field_config = {
            'pos': ('位置', str),
            'offset': ('偏移', str),
            'position': ('位置', str),
            'speed': ('速度', str),
        }

    table = Table(
        title=f"📊 {title}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
        padding=(0, 2),
    )
    table.add_column("参数", style="dim", width=12, justify="center")
    table.add_column("之前", justify="right", style="white")
    table.add_column("", width=4, justify="center")
    table.add_column("之后", justify="right", style="bold green")
    table.add_column("变化", justify="right", width=12)

    for field, (name, unit_fn) in field_config.items():
        if field not in before and field not in after:
            continue
        b = before.get(field, '-')
        a = after.get(field, '-')
        b_str = unit_fn(b) if b != '-' else '-'
        a_str = unit_fn(a) if a != '-' else '-'

        # Delta
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            delta = a - b
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            delta_color = "green" if delta != 0 else "dim"
            table.add_row(name, b_str, "→", a_str, f"[{delta_color}]{delta_str}[/{delta_color}]")
        else:
            table.add_row(name, b_str, "→", a_str, "")

    console.print(table)


def show_banner(text: str, style: str = "cyan") -> None:
    """展示装饰性横幅"""
    console.print()
    console.rule(f"[bold {style}]{text}[/bold {style}]")


def show_success(text: str) -> None:
    """展示成功信息"""
    console.print(f"  [bold green]✅ {text}[/bold green]")


def show_fail(text: str) -> None:
    """展示失败信息"""
    console.print(f"  [bold red]❌ {text}[/bold red]")


def show_warn(text: str) -> None:
    """展示警告信息"""
    console.print(f"  [bold yellow]⚠️  {text}[/bold yellow]")


def show_info(text: str) -> None:
    """展示信息"""
    console.print(f"  [bold cyan]ℹ️  {text}[/bold cyan]")


def show_json(data: dict, title: str = None) -> None:
    """展示 JSON 格式数据"""
    import json
    text = json.dumps(data, indent=2, ensure_ascii=False)
    syntax = Syntax(text, "json", theme="monokai", padding=(1, 2))
    if title:
        panel = Panel(syntax, title=title, box=box.ROUNDED)
        console.print(panel)
    else:
        console.print(syntax)


def confirm_action(message: str, default: bool = False) -> bool:
    """请求用户确认"""
    suffix = " [Y/n]" if default else " [y/N]"
    ans = console.input(f"  [bold yellow]⚠️  {message}{suffix}[/bold yellow] ")
    if not ans.strip():
        return default
    return ans.lower().startswith('y')


# ============================================================
# Convenience: CommDisplay class (all-in-one)
# ============================================================

class CommDisplay:
    """串口通信可视化展示器（一站式接口）

    封装所有 display 函数，可实例化后直接使用。

    Usage:
        disp = CommDisplay()
        disp.info("连接成功")
        disp.frame("TX", raw_bytes)
        disp.status(1, status_dict)
        disp.comparison("校准", before, after)
    """

    def __init__(self, console: Console = None):
        self.console = console or globals()['console']
        self._steps = []

    def rule(self, title: str, style: str = "cyan"):
        show_rule(title, style)

    def port(self, port: str, baud: int, **kwargs):
        show_port_info(port, baud, **kwargs)

    def frame(self, direction: str, raw: bytes, parser=FTSCSParser, **kwargs):
        return show_frame(direction, raw, parser, **kwargs)

    def status(self, id: int, status: dict, title: str = None):
        show_servo_status(id, status, title)

    def scan(self, servos: list):
        show_scan_result(servos)

    def step(self, message: str, icon: str = "➡️") -> list:
        return show_step(self._steps, message, icon)

    def step_log(self, title: str = "操作日志"):
        show_step_log(self._steps, title)

    def reset_steps(self):
        self._steps.clear()

    def comparison(self, title: str, before: dict, after: dict, **kwargs):
        show_comparison(title, before, after, **kwargs)

    def banner(self, text: str, style: str = "cyan"):
        show_banner(text, style)

    def ok(self, text: str):
        show_success(text)

    def fail(self, text: str):
        show_fail(text)

    def warn(self, text: str):
        show_warn(text)

    def info(self, text: str):
        show_info(text)

    def json(self, data: dict, title: str = None):
        show_json(data, title)

    def confirm(self, message: str, default: bool = False) -> bool:
        return confirm_action(message, default)


# ============================================================
# Quick self-test
# ============================================================

if __name__ == '__main__':
    disp = CommDisplay()

    show_banner("串口通信可视化模块自检", "cyan")

    show_port_info("/dev/cu.usbmodem5B790502931", 1000000,
                   chip="CH343P", protocol="FT-SCS")

    # TX frame
    tx = FTSCSParser.build(1, 0x01, [])
    show_frame("TX", tx)

    # RX frame
    rx = bytes([0xFF, 0xFF, 0x01, 0x02, 0x00, 0xFB])
    show_frame("RX", rx)

    # Status
    status = {
        'position': 2048,
        'speed': 0,
        'load': 120,
        'voltage': 53,
        'temperature': 27,
        'moving': 0,
    }
    show_servo_status(1, status)

    # Scan
    scan_result = [
        {'id': 1, 'model': 0x0903, 'position': 2048},
        {'id': 2, 'model': 0x0903, 'position': 100},
    ]
    show_scan_result(scan_result)

    # Steps
    steps = []
    show_step(steps, "扫描端口")
    show_step(steps, "找到 ID=1 ✅")
    show_step(steps, "校准中...")
    show_step(steps, "✅ 校准完成")
    show_step_log(steps)

    # Comparison
    show_comparison("校准结果",
                    {'position': 2, 'offset': 0},
                    {'position': 2048, 'offset': 4093})

    console.print("\n[bold green]自检完成[/bold green]")
