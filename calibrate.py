#!/usr/bin/env python3
"""中位校准脚本"""
import sys
sys.path.insert(0, '.')
from ft_servo import FTServo, auto_detect_port

def main():
    import argparse
    parser = argparse.ArgumentParser(description='FT 舵机中位校准')
    parser.add_argument('--port', help='串口路径')
    parser.add_argument('--id', type=int, required=True, help='舵机 ID')
    parser.add_argument('--baud', type=int, default=1000000, help='波特率')
    args = parser.parse_args()

    port = args.port or auto_detect_port()
    if not port:
        print('❌ 未找到串口')
        return

    with FTServo(port, baud=args.baud) as servo:
        print(f'🔧 校准 ID={args.id}...')
        before, after = servo.calibrate(args.id)
        print(f'  位置: {before} → {after}')
        print('  ✅ 校准完成')

if __name__ == '__main__':
    main()
