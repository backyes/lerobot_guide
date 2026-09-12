#!/usr/bin/env python3
"""修改舵机 ID"""
import sys
sys.path.insert(0, '.')
from ft_servo import FTServo, auto_detect_port

def main():
    import argparse
    parser = argparse.ArgumentParser(description='修改 FT 舵机 ID')
    parser.add_argument('--port', help='串口路径')
    parser.add_argument('--old', type=int, required=True, help='当前 ID')
    parser.add_argument('--new', type=int, required=True, help='新 ID')
    parser.add_argument('--baud', type=int, default=1000000, help='波特率')
    args = parser.parse_args()

    port = args.port or auto_detect_port()
    if not port:
        print('❌ 未找到串口')
        return

    with FTServo(port, baud=args.baud) as servo:
        print(f'🆔 修改 ID: {args.old} → {args.new}')
        if servo.set_id(args.old, args.new):
            print('  ✅ 成功（断电重启后永久生效）')
        else:
            print('  ❌ 失败')

if __name__ == '__main__':
    main()
