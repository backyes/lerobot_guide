#!/usr/bin/env python3
"""扫描总线上的舵机"""
import sys
sys.path.insert(0, '.')
from ft_servo import FTServo, auto_detect_port

def main():
    import argparse
    parser = argparse.ArgumentParser(description='扫描 FT 舵机')
    parser.add_argument('--port', help='串口路径（自动检测）')
    parser.add_argument('--baud', type=int, default=1000000, help='波特率')
    parser.add_argument('--max-id', type=int, default=253, help='最大扫描 ID')
    args = parser.parse_args()

    port = args.port or auto_detect_port()
    if not port:
        print('❌ 未找到串口')
        return

    with FTServo(port, baud=args.baud) as servo:
        print(f'🔍 扫描 {port} @ {args.baud}bps...')
        servos = servo.scan_with_info(args.max_id)
        if servos:
            for s in servos:
                print(f"  ID={s['id']:3d}  型号={s['model']}  位置={s['position']}")
            print(f'\n共 {len(servos)} 个舵机')
        else:
            print('  未找到')

if __name__ == '__main__':
    main()
