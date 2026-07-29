## main.py

## imports
import machine
import os
import utime as time
import ujson as json
import urequests as requests

from boot import *
from configs.config import *
from configs import parameters as param


## classes
## MFRC522 driver
class MFRC522:
    def __init__(self, sck=param.RFID_SCK_PINOUT, mosi=param.RFID_MOSI_PINOUT, miso=param.RFID_MISO_PINOUT, cs=param.RFID_SDA_PINOUT, rst=param.RFID_RST_PINOUT):
        self.rst = machine.Pin(rst, machine.Pin.OUT)
        self.cs = machine.Pin(cs, machine.Pin.OUT)
        self.rst.value(1)
        self.cs.value(1)
        self.spi = machine.SPI(1, baudrate=1_000_000, sck=machine.Pin(sck), mosi=machine.Pin(mosi), miso=machine.Pin(miso))
        self._init()

    def _write(self, reg, val):
        self.cs.value(0)
        self.spi.write(bytes([(reg << 1) & 0x7E, val]))
        self.cs.value(1)

    def _read(self, reg):
        self.cs.value(0)
        self.spi.write(bytes([((reg << 1) & 0x7E) | 0x80]))
        v = self.spi.read(1)[0]
        self.cs.value(1)
        return v

    def _set_bit(self, r, b): self._write(r, self._read(r) | b)
    def _clr_bit(self, r, b): self._write(r, self._read(r) & ~b)

    def _init(self):
        self._write(0x02, 0x00); self._write(0x04, 0x00)
        self._write(0x0A, 0x6B); self._write(0x2B, 0xFF)
        self._write(0x21, 0x00); self._write(0x13, 0x30)
        self._write(0x26, 0x37); self._write(0x15, 0x40)
        self._write(0x11, 0xA6); self._write(0x0D, 0x3E)
        self._write(0x0C, 0x40); self._set_bit(0x08, 0x80)
        self._write(0x01, 0x0F)

    def _cmd(self, cmd, data):
        self._write(0x0D, 0x00); self._clr_bit(0x04, 0x80)
        for b in data: self._write(0x09, b)
        self._set_bit(0x04, 0x80); self._write(0x0D, cmd)
        for _ in range(100):
            if self._read(0x06) & 0x01: break
        st = self._read(0x04)
        self._clr_bit(0x04, 0x80)
        return st

    def request(self):
        self._write(0x0D, 0x01)
        return self._cmd(0x0C, [0x26]) == 0x00

    def get_uid(self):
        if not self.request():
            return None
        self._write(0x0D, 0x02)
        if self._cmd(0x0C, [0x93, 0x20]) != 0x00:
            return None
        return [self._read(0x09) for _ in range(5)][:4]

## LCD Driver
class I2cLcd:
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

## BUZZER Driver
class Buzzer:
    def __init__(self, pin):
        self.pin = machine.Pin(pin, machine.Pin.OUT)
        self.off()

    def on(self):
        self.pin.value(1)

    def off(self):
        self.pin.value(0)

## functions
def post_data(data):
    url = f"{API_URL}/api/receive-rfid"
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        r.close()
        return r.status_code == 200
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, f"Send error: {e}")
        return False

def fetch_data():
    url = f"{API_URL}/api/get-latest-rfid"
    try:
        r = requests.get(url)
        r.close()
        return r.json()
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, f"Fetch error: {e}")
        return None

"""
## main
def main():
    # Initialize hardware
    rfid = MFRC522()
    i2c = machine.I2C(0, scl=machine.Pin(param.I2C_SCL_PINOUT), sda=machine.Pin(param.I2C_SDA_PINOUT), freq=400000)
    lcd = I2cLcd(i2c, param.LCD_ADDR, rows=2, cols=16)
    buzzer = Buzzer(param.BUZZER_PIN)

    lcd.clear()
    lcd.putstr("System Ready")

    last_uid = None

    while True:
        uid = rfid.get_uid()

        if uid and uid != last_uid:
            uid_str = "".join(f"{b:02X}" for b in uid)
            last_uid = uid_str

            lcd.clear()
            lcd.putstr("Scanned:")
            lcd.move_to(0, 1)
            lcd.putstr(uid_str[:16])

            buzzer.on()
            time.sleep_ms(100)
            buzzer.off()

            # Send to PythonAnywhere API
            success = post_data({"rfid_id": uid_str})
            if success:
                tprint(PRINTSTATUS.SUCCESS, f"Sent: {uid_str}")
            else:
                tprint(PRINTSTATUS.ERROR, f"Send failed: {uid_str}")

        time.sleep_ms(200)
"""

def main():
    # Initialize RFID reader
    rfid = MFRC522()
    tprint(PRINTSTATUS.INFO, "Checking RFID reader...")

    # --- SELF-CHECK BEFORE STARTING ---
    reader_ok = False
    for _ in range(5):  # Try 5 times to confirm
        if rfid.request():
            reader_ok = True
            break
        time.sleep_ms(100)

    if not reader_ok:
        tprint(PRINTSTATUS.ERROR, "RFID reader NOT DETECTED! Check wiring/pins.")
        while True:
            time.sleep_ms(1000)  # Halt if no reader
    else:
        tprint(PRINTSTATUS.SUCCESS, "RFID reader OK - Ready for cards")

    last_uid = None

    # --- MAIN SCAN LOOP ---
    while True:
        uid = rfid.get_uid()

        # Only accept valid 4-byte UIDs
        if uid and len(uid) == 4:
            uid_str = "".join(f"{b:02X}" for b in uid)

            # Only show NEW cards
            if uid_str != last_uid:
                last_uid = uid_str
                tprint(PRINTSTATUS.INFO, f"RFID READ: {uid_str}")
                print(f"--- CARD DETECTED --- UID: {uid_str}")

        time.sleep_ms(200)
