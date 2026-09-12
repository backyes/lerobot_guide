#!/usr/bin/env python3
"""实时监控舵机状态"""
import sys
import time
sys.path.insert(0, '.')
from ft_servo import FTServo, auto_detect_port

def main():
    import argparse
    parser = argparse.ArgumentParser(description='实时监控 FT 舵机')
    parser.add_argument('--port', help='串口路径')
    parser.add_argument('--id', type=int, required=True, help='舵机 ID')
    parser.add_argument('--baud', type=int, default=1000000, help='波特率')
    parser.add_argument('--interval', type=float, default=0.1, help='采样间隔（秒）')
    args = parser.parse_args()

    port = args.port or auto_detect_port()
    if not port:
        print('❌ 未找到串口')
        return

    with FTServo(port, baud=args.baud) as servo:
        print(f'📊 监控 ID={args.id}（Ctrl+C 停止）...')
        print(f'{"位置":>6} {"速度":>6} {"负载":>6} {"电压":>6} {"温度":>6} {"运动":>6}')
        try:
            while True:
                status = servo.get_all_status(args.id)
                print(f'{status["position"]:>6} {status["speed"]:>6} {status["load"]:>6} '
                      f'{status["voltage"]/10:>5.1f}V {status["temperature"]:>5}°C {status["moving"]:>6}',
                      end='\r', flush=True)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print('\n停止')

if __name__ == '__main__':
    main()
