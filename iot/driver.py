## driver.py

import machine
import utime as time
from configs import parameters as param

## BUZZER Driver
class BUZZER:
    def __init__(self, pin):
        self.pin = machine.Pin(pin, machine.Pin.OUT)
        self.off()

    def on(self):
        self.pin.value(1)

    def off(self):
        self.pin.value(0)

## PCF8574 Driver
class PCF8574:
    LCD_CLR = 0x01
    LCD_ENTRY_MODE = 0x04
    LCD_DISPLAY_CTRL = 0x08
    LCD_FUNCTION = 0x20
    LCD_SET_DDRAM = 0x80

    def __init__(self, i2c, addr, rows=2, cols=16, rs_mask=0x01, rw_mask=0x02, en_mask=0x04, bl_mask=0x08):
        self.i2c = i2c
        self.addr = addr
        self.rows = rows
        self.cols = cols
        self.backlight = True

        self.RS = rs_mask
        self.RW = rw_mask
        self.EN = en_mask
        self.BL = bl_mask

        time.sleep_ms(50)
        self._write4(0x03 << 4)
        time.sleep_ms(5)
        self._write4(0x03 << 4)
        time.sleep_ms(1)
        self._write4(0x03 << 4)
        self._write4(0x02 << 4)

        self._cmd(self.LCD_FUNCTION | 0x08)
        self._cmd(self.LCD_DISPLAY_CTRL | 0x04)
        self.clear()
        self._cmd(self.LCD_ENTRY_MODE | 0x02)

    def _pcf_write(self, data):
        if self.backlight:
            data |= self.BL
        try:
            self.i2c.writeto(self.addr, bytes([data & 0xFF]))
        except:
            pass

    def _pulse(self, data):
        self._pcf_write(data | self.EN)
        time.sleep_us(1)
        self._pcf_write(data & ~self.EN)
        time.sleep_us(50)

    def _write4(self, data):
        self._pcf_write(data)
        self._pulse(data)

    def _send(self, value, mode=0):
        high = value & 0xF0
        low = (value << 4) & 0xF0
        self._write4(high | mode)
        self._write4(low | mode)

    def _cmd(self, cmd):
        self._send(cmd, 0)

    def _write_char(self, char):
        self._send(ord(char), self.RS)

    def clear(self):
        self._cmd(self.LCD_CLR)
        time.sleep_ms(2)

    def move_to(self, col, row):
        row_offsets = [0x00, 0x40]
        addr = col + row_offsets[row]
        self._cmd(self.LCD_SET_DDRAM | addr)

    def putstr(self, string):
        for ch in string:
            self._write_char(ch)

## PN532 driver
class PN532:
    def __init__(self, sda=param.I2C_SDA_PINOUT, scl=param.I2C_SCL_PINOUT, address=0x24):
        self.address = address
        self.i2c = machine.SoftI2C(scl=machine.Pin(scl), sda=machine.Pin(sda), freq=100000)
        self.wakeup()
        self._init()

    def wakeup(self):
        try:
            self.i2c.writeto(self.address, b'\x00\x00\x00\x00\x00\x00\x00\x00')
        except OSError:
            pass
        time.sleep_ms(100)

    def _wait_ready(self, timeout=1000):
        start = time.ticks_ms()
        status = bytearray(1)
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            try:
                self.i2c.readfrom_into(self.address, status)
                if status[0] & 0x01:
                    return True
            except OSError:
                pass
            time.sleep_ms(10)
        return False

    def _write_command(self, cmd, params=b''):
        length = len(params) + 2
        checksum = (0xD4 + cmd + sum(params)) & 0xFF
        dcs = (0x100 - checksum) & 0xFF

        frame = bytearray([
            0x00, 0x00, 0xFF,
            length, (~length + 1) & 0xFF,
            0xD4, cmd
        ])
        frame.extend(params)
        frame.extend([dcs, 0x00])

        self.wakeup()
        self.i2c.writeto(self.address, frame)

        if not self._wait_ready(timeout=500):
            return False

        try:
            ack_buf = self.i2c.readfrom(self.address, 7)[1:]
            return ack_buf == b'\x00\x00\xff\x00\xff\x00'
        except OSError:
            return False

    def _read_response(self, expected_len, timeout=1000):
        if not self._wait_ready(timeout):
            return None
        try:
            raw = self.i2c.readfrom(self.address, expected_len + 1)[1:]
            return raw
        except OSError:
            return None

    def _init(self):
        if self._write_command(0x14, b'\x01\x14\x01'):
            self._read_response(8)

    def request(self):
        try:
            if self._write_command(0x02):
                resp = self._read_response(12)
                return resp is not None and len(resp) >= 10 and resp[0:3] == b'\x00\x00\xff'
        except Exception:
            pass
        return False

    def get_uid(self):
        try:
            if not self._write_command(0x4A, b'\x01\x00'):
                return None
            resp = self._read_response(20, timeout=200)
            if resp and len(resp) >= 14 and resp[0:3] == b'\x00\x00\xff':
                tags_found = resp[7]
                if tags_found > 0:
                    uid_len = resp[12]
                    return list(resp[13:13 + uid_len])
        except Exception:
            pass
        return None
