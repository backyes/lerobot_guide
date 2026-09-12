#!/usr/bin/env python3
"""
FT Servo Core Library | HLS / SMS_STS / SCS Protocol
面向 LeRobot 机械臂开发的串口舵机控制库
"""

import serial
import time
import argparse
from typing import List, Tuple, Optional


class FTServo:
    """飞腾串口舵机控制类

    支持 HLS、SMS_STS、SCSCL 系列
    协议：FT-SCS (Feetech Servo Communication Protocol)
    """

    # 指令集
    INST_PING = 0x01
    INST_READ = 0x02
    INST_WRITE = 0x03
    INST_REG_WRITE = 0x04
    INST_REG_ACTION = 0x05
    INST_SYNC_READ = 0x82
    INST_SYNC_WRITE = 0x83

    # SMS_STS / HLS 系列寄存器地址
    REG_MODEL_L = 3
    REG_MODEL_H = 4
    REG_VERSION = 5
    REG_ID = 5
    REG_BAUD_RATE = 6
    REG_RETURN_DELAY = 7
    REG_STATUS_LEVEL = 8
    REG_MIN_POS_L = 9
    REG_MIN_POS_H = 10
    REG_MAX_POS_L = 11
    REG_MAX_POS_H = 12
    REG_MAX_TEMP = 13
    REG_MAX_VOLT = 14
    REG_MIN_VOLT = 15
    REG_MAX_TORQUE_L = 16
    REG_MAX_TORQUE_H = 17
    REG_P_GAIN = 21
    REG_D_GAIN = 22
    REG_I_GAIN = 23
    REG_CW_DEAD = 26
    REG_CCW_DEAD = 27
    REG_OVERLOAD_CURRENT_L = 28
    REG_OVERLOAD_CURRENT_H = 29
    REG_POS_OFFSET_L = 31
    REG_POS_OFFSET_H = 32
    REG_MODE = 33
    REG_TORQUE_ENABLE = 40
    REG_GOAL_POS_L = 42
    REG_GOAL_POS_H = 43
    REG_GOAL_SPEED_L = 46
    REG_GOAL_SPEED_H = 47
    REG_TORQUE_LIMIT_L = 48
    REG_TORQUE_LIMIT_H = 49
    REG_LOCK = 55
    REG_PRESENT_POS_L = 56
    REG_PRESENT_POS_H = 57
    REG_PRESENT_SPEED_L = 58
    REG_PRESENT_SPEED_H = 59
    REG_PRESENT_LOAD_L = 60
    REG_PRESENT_LOAD_H = 61
    REG_PRESENT_VOLTAGE = 62
    REG_PRESENT_TEMP = 63
    REG_MOVING = 66
    REG_PRESENT_CURRENT_L = 69
    REG_PRESENT_CURRENT_H = 70

    def __init__(self, port: str, baud: int = 1000000, timeout: float = 0.3):
        """
        初始化舵机控制

        Args:
            port: 串口设备路径
            baud: 波特率（默认 1Mbps）
            timeout: 读取超时（秒）
        """
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)

    def _checksum(self, data: List[int]) -> int:
        """计算校验和"""
        return (~sum(data)) & 0xFF

    def _send(self, id: int, inst: int, params: List[int]):
        """构造并发送指令帧"""
        length = len(params) + 2
        header = [0xFF, 0xFF, id, length, inst] + params
        chk = self._checksum(header[2:])
        self.ser.write(bytes(header + [chk]))
        time.sleep(0.02)

    def _read_response(self, expected_len: int = 6) -> Optional[bytes]:
        """读取响应帧"""
        time.sleep(0.05)
        if self.ser.in_waiting >= expected_len:
            return self.ser.read(self.ser.in_waiting)
        return None

    def ping(self, id: int) -> bool:
        """
        Ping 舵机

        Args:
            id: 舵机 ID

        Returns:
            是否在线
        """
        self._send(id, self.INST_PING, [])
        resp = self._read_response()
        if resp and len(resp) >= 6:
            if resp[0] == 0xFF and resp[1] == 0xFF:
                if resp[2] == id or id == 0xFE:  # 0xFE = 广播
                    return True
        return False

    def read_byte(self, id: int, addr: int) -> int:
        """
        读取单字节寄存器

        Args:
            id: 舵机 ID
            addr: 寄存器地址

        Returns:
            寄存器值（-1 表示失败）
        """
        self._send(id, self.INST_READ, [addr, 1])
        resp = self._read_response()
        if resp and len(resp) >= 7 and resp[0] == 0xFF and resp[1] == 0xFF:
            return resp[5]
        return -1

    def read_word(self, id: int, addr: int) -> int:
        """
        读取双字节寄存器（小端）

        Args:
            id: 舵机 ID
            addr: 寄存器地址

        Returns:
            寄存器值（-1 表示失败）
        """
        self._send(id, self.INST_READ, [addr, 2])
        resp = self._read_response()
        if resp and len(resp) >= 8 and resp[0] == 0xFF and resp[1] == 0xFF:
            return resp[5] + (resp[6] << 8)
        return -1

    def write_byte(self, id: int, addr: int, val: int):
        """
        写入单字节到寄存器

        Args:
            id: 舵机 ID
            addr: 寄存器地址
            val: 写入值
        """
        self._send(id, self.INST_WRITE, [addr, val & 0xFF])

    def write_word(self, id: int, addr: int, val: int):
        """
        写入双字节到寄存器（小端）

        Args:
            id: 舵机 ID
            addr: 寄存器地址
            val: 写入值
        """
        lo = val & 0xFF
        hi = (val >> 8) & 0xFF
        self._send(id, self.INST_WRITE, [addr, lo, hi])

    def set_id(self, old_id: int, new_id: int) -> bool:
        """
        修改舵机 ID

        流程：解锁 → 改 ID → 锁定

        Args:
            old_id: 当前 ID
            new_id: 新 ID

        Returns:
            是否成功
        """
        # 1. 解锁 EPROM
        self.write_byte(old_id, self.REG_LOCK, 0)
        time.sleep(0.1)

        # 2. 写入新 ID
        self.write_byte(old_id, self.REG_ID, new_id)
        time.sleep(0.1)

        # 3. 锁定（用新 ID 发送）
        self.write_byte(new_id, self.REG_LOCK, 1)
        time.sleep(0.2)

        # 验证
        return self.ping(new_id)

    def enable_torque(self, id: int, enable: bool = True):
        """
        开启/关闭扭矩

        Args:
            id: 舵机 ID
            enable: True=开启，False=关闭
        """
        self.write_byte(id, self.REG_TORQUE_ENABLE, 1 if enable else 0)

    def calibrate(self, id: int) -> Tuple[int, int]:
        """
        中位校准

        向扭矩开关寄存器写 128，舵机自动记录当前位置为零点

        Args:
            id: 舵机 ID

        Returns:
            (校准前位置, 校准后位置)
        """
        # 读取当前位置
        before = self.read_word(id, self.REG_PRESENT_POS_L)

        # 中位校准指令
        self.write_byte(id, self.REG_TORQUE_ENABLE, 128)
        time.sleep(0.3)

        # 开启扭矩
        self.enable_torque(id, True)

        # 读取校准后位置
        after = self.read_word(id, self.REG_PRESENT_POS_L)

        return before, after

    def get_position(self, id: int) -> int:
        """获取当前位置"""
        return self.read_word(id, self.REG_PRESENT_POS_L)

    def get_speed(self, id: int) -> int:
        """获取当前速度"""
        return self.read_word(id, self.REG_PRESENT_SPEED_L)

    def get_load(self, id: int) -> int:
        """获取当前负载（PWM 占空比）"""
        return self.read_word(id, self.REG_PRESENT_LOAD_L)

    def get_voltage(self, id: int) -> int:
        """获取电压（单位 0.1V）"""
        return self.read_byte(id, self.REG_PRESENT_VOLTAGE)

    def get_temperature(self, id: int) -> int:
        """获取温度（摄氏度）"""
        return self.read_byte(id, self.REG_PRESENT_TEMP)

    def get_moving(self, id: int) -> int:
        """获取运动状态（0=停止，1=运动中）"""
        return self.read_byte(id, self.REG_MOVING)

    def get_all_status(self, id: int) -> dict:
        """
        获取所有状态信息

        Returns:
            dict: 包含位置、速度、负载、电压、温度、运动状态
        """
        return {
            'position': self.get_position(id),
            'speed': self.get_speed(id),
            'load': self.get_load(id),
            'voltage': self.get_voltage(id),
            'temperature': self.get_temperature(id),
            'moving': self.get_moving(id)
        }

    def set_position(self, id: int, pos: int, speed: int = 0, acc: int = 0):
        """
        设置目标位置

        Args:
            id: 舵机 ID
            pos: 目标位置（0-4095）
            speed: 运行速度（0=最大）
            acc: 加速度（0=最大）
        """
        self.write_byte(id, self.REG_TORQUE_ENABLE, 1)  # 确保扭矩开启
        self.write_byte(id, 41, acc)  # Acceleration
        self.write_word(id, self.REG_GOAL_POS_L, pos)
        self.write_word(id, self.REG_GOAL_SPEED_L, speed)

    def lock_eprom(self, id: int):
        """锁定 EPROM（防止误写）"""
        self.write_byte(id, self.REG_LOCK, 1)

    def unlock_eprom(self, id: int):
        """解锁 EPROM（允许写入）"""
        self.write_byte(id, self.REG_LOCK, 0)

    def scan(self, max_id: int = 253) -> List[int]:
        """
        扫描总线上的所有舵机

        Args:
            max_id: 最大扫描 ID（默认 253）

        Returns:
            在线的舵机 ID 列表
        """
        found = []
        for i in range(max_id + 1):
            if self.ping(i):
                found.append(i)
        return found

    def scan_with_info(self, max_id: int = 253) -> List[dict]:
        """
        扫描并获取每个舵机的信息

        Returns:
            舵机信息列表
        """
        servos = []
        for i in range(max_id + 1):
            if self.ping(i):
                model = self.read_word(i, self.REG_MODEL_L)
                pos = self.read_word(i, self.REG_PRESENT_POS_L)
                servos.append({
                    'id': i,
                    'model': f"0x{model:04X}" if model >= 0 else "Unknown",
                    'position': pos
                })
        return servos

    def close(self):
        """关闭串口"""
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def auto_detect_port() -> Optional[str]:
    """自动检测串口设备"""
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if 'usbmodem' in p.device or 'usbserial' in p.device:
            return p.device
    return None


def main():
    parser = argparse.ArgumentParser(description='FT 舵机调试工具')
    sub = parser.add_subparsers(dest='command')

    # scan
    scan_parser = sub.add_parser('scan', help='扫描舵机')
    scan_parser.add_argument('--port', help='串口路径')
    scan_parser.add_argument('--baud', type=int, default=1000000, help='波特率')

    # calibrate
    cal_parser = sub.add_parser('calibrate', help='中位校准')
    cal_parser.add_argument('--port', required=True, help='串口路径')
    cal_parser.add_argument('--id', type=int, required=True, help='舵机 ID')
    cal_parser.add_argument('--baud', type=int, default=1000000, help='波特率')

    # set-id
    id_parser = sub.add_parser('set-id', help='修改 ID')
    id_parser.add_argument('--port', required=True, help='串口路径')
    id_parser.add_argument('--old', type=int, required=True, help='当前 ID')
    id_parser.add_argument('--new', type=int, required=True, help='新 ID')
    id_parser.add_argument('--baud', type=int, default=1000000, help='波特率')

    # status
    status_parser = sub.add_parser('status', help='读取状态')
    status_parser.add_argument('--port', required=True, help='串口路径')
    status_parser.add_argument('--id', type=int, required=True, help='舵机 ID')
    status_parser.add_argument('--baud', type=int, default=1000000, help='波特率')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    port = args.port or auto_detect_port()
    if not port:
        print('❌ 未找到串口设备，请使用 --port 指定')
        return

    with FTServo(port, baud=args.baud) as servo:
        if args.command == 'scan':
            print('🔍 扫描中...')
            servos = servo.scan_with_info()
            if servos:
                for s in servos:
                    print(f"  ID={s['id']:3d}  型号={s['model']}  位置={s['position']}")
            else:
                print('  未找到舵机')

        elif args.command == 'calibrate':
            print(f'🔧 校准 ID={args.id}...')
            before, after = servo.calibrate(args.id)
            print(f'  位置: {before} → {after}')
            print('  ✅ 校准完成')

        elif args.command == 'set-id':
            print(f'🆔 修改 ID: {args.old} → {args.new}')
            if servo.set_id(args.old, args.new):
                print('  ✅ 成功')
            else:
                print('  ❌ 失败')

        elif args.command == 'status':
            status = servo.get_all_status(args.id)
            print(f'📊 ID={args.id} 状态:')
            for k, v in status.items():
                print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
