"""
Core module: FT Servo communication + visualization
"""
from .ft_servo import FTServo, calibrate_servo, auto_detect_port
from .display import (
    FTSCSParser, FrameParser, CalibrationResult,
    show_port_info, show_frame, show_servo_status,
    show_scan_result, show_step, show_step_log,
    show_comparison, show_banner, show_success, show_fail,
    show_warn, show_info, confirm_action,
    CommDisplay, console, THEME,
)

__all__ = [
    'FTServo', 'calibrate_servo', 'auto_detect_port',
    'FTSCSParser', 'FrameParser', 'CalibrationResult',
    'show_port_info', 'show_frame', 'show_servo_status',
    'show_scan_result', 'show_step', 'show_step_log',
    'show_comparison', 'show_banner', 'show_success', 'show_fail',
    'show_warn', 'show_info', 'confirm_action',
    'CommDisplay', 'console', 'THEME',
]
