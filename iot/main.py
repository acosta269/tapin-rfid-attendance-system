## main.py

## Imports
import machine
import utime as time
import ujson as json
import urequests as requests
import ntptime

from boot import *
from configs.config import *
from configs import parameters as param
from driver import BUZZER, PCF8574, PN532

## Global hardware objects
buzzer = None
lcd = None
rfid = None

## Functions
def send_ping():
    url = API_URL.rstrip("/") + "/api/device-ping"
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "alive"}, headers=headers, timeout=10)
        response.close()
        tprint(PRINTSTATUS.INFO, "Ping sent - Device alive")
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, "Ping failed: " + str(e))

def post_data(rfid_str):
    url = API_URL.rstrip("/") + "/api/receive-rfid"
    headers = {"Content-Type": "application/json"}
    scanned_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    data = {
        "rfid": rfid_str,
        "scanned_at": scanned_time
    }
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        success = r.status_code == 200
        r.close()
        return success
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, "Send error: " + str(e))
        return False

def sync_manila_time():
    """Sync time from internet and adjust to Manila (UTC+8)"""
    try:
        ntptime.host = "pool.ntp.org"
        ntptime.settime()
        t = time.localtime(time.time() + 8 * 3600)
        machine.RTC().datetime((t[0], t[1], t[2], t[6] + 1, t[3], t[4], t[5], 0))
        tprint(PRINTSTATUS.SUCCESS, "Manila Time Synced")
        return True
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, "Time Sync Failed: " + str(e))
        return False

## Initialize Hardware Drivers FIRST
def init_drivers():
    global buzzer, lcd, rfid

    # Scan I2C bus
    tprint(PRINTSTATUS.INFO, "Scanning I2C bus...")
    i2c_bus = machine.SoftI2C(scl=machine.Pin(param.I2C_SCL_PINOUT), sda=machine.Pin(param.I2C_SDA_PINOUT), freq=100000)
    devices = i2c_bus.scan()
    tprint(PRINTSTATUS.INFO, "I2C Found: " + str([hex(d) for d in devices]))

    # INIT BUZZER
    try:
        buzzer = BUZZER(param.BUZZER_PIN)
        # Startup melody
        buzzer.on()
        time.sleep_ms(300)
        buzzer.off()
        time.sleep_ms(80)
        buzzer.on()
        time.sleep_ms(80)
        buzzer.off()
        tprint(PRINTSTATUS.SUCCESS, "BUZZER OK")
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, "BUZZER INIT FAILED: " + str(e))
        buzzer = None
        raise

    # INIT LCD
    try:
        if param.LCD_ADDR in devices:
            lcd = PCF8574(i2c_bus, param.LCD_ADDR, rows=2, cols=16)
            lcd.clear()
            tprint(PRINTSTATUS.SUCCESS, "LCD OK")
        else:
            raise Exception("LCD missing")
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, "LCD INIT FAILED: " + str(e))
        lcd = None
        raise

    # INIT RFID
    try:
        rfid = PN532()
        tprint(PRINTSTATUS.SUCCESS, "RFID OK")
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, "RFID INIT FAILED: " + str(e))
        rfid = None
        raise

    tprint(PRINTSTATUS.SUCCESS, "ALL DRIVERS INITIALIZED OK")
    return True

## Hardware Fail-Safe Indicator (when boot.py triggers fail-safe)
def hardware_failsafe_indicator():
    tprint(PRINTSTATUS.WARN, ">>> HARDWARE FAIL-SAFE INDICATOR <<<")
    for _ in range(10):
        try:
            if buzzer:
                buzzer.on()
            if lcd:
                lcd.clear()
                lcd.putstr("!!! FAILSAFE !!!")
                lcd.move_to(0, 1)
                lcd.putstr("TOO MANY RESTARTS")
        except:
            pass
        time.sleep_ms(200)
        try:
            if buzzer:
                buzzer.off()
        except:
            pass
        time.sleep_ms(200)
    try:
        if lcd:
            lcd.clear()
            lcd.putstr("WAITING...")
            lcd.move_to(0, 1)
            lcd.putstr("RETRYING LATER")
    except:
        pass

## Main function
def main():
    global buzzer, lcd, rfid

    # Sync Manila Time first
    sync_manila_time()

    # INIT ALL DRIVERS FIRST
    try:
        init_drivers()
    except Exception as err:
        tprint(PRINTSTATUS.ERROR, "DRIVER INIT FAILED: " + str(err))
        # Buzzer 3 beeps error - NO RESET
        try:
            if buzzer:
                buzzer.on()
                time.sleep_ms(80)
                buzzer.off()
                time.sleep_ms(300)
        except:
            pass
        # LCD show error - stays visible
        try:
            if lcd:
                lcd.clear()
                lcd.putstr("INIT FAILED")
                lcd.move_to(0, 1)
                lcd.putstr("Check Wiring")
        except:
            pass
        # Return to boot.py to count up
        return

    # NORMAL OPERATION
    last_rfid = None
    last_ping = time.ticks_ms()
    last_time_update = time.ticks_ms()

    tprint(PRINTSTATUS.SUCCESS, "Device Ready.")
    # --- MAIN LOOP ---
    while True:
        # 1. Send ping
        if time.ticks_diff(time.ticks_ms(), last_ping) >= param.PING_INTERVAL:
            last_ping = time.ticks_ms()
            send_ping()

        # 2. Update Time — AM/PM format
        if time.ticks_diff(time.ticks_ms(), last_time_update) >= 1000:
            last_time_update = time.ticks_ms()
            t = time.localtime()
            hour24 = t[3]
            if hour24 == 0:
                hour12 = 12
                period = "AM"
            elif hour24 < 12:
                hour12 = hour24
                period = "AM"
            elif hour24 == 12:
                hour12 = 12
                period = "PM"
            else:
                hour12 = hour24 - 12
                period = "PM"
            time_str = "Time:{:02d}:{:02d}:{:02d} {}".format(hour12, t[4], t[5], period)
            lcd.move_to(0, 0)
            lcd.putstr(time_str)

        # 3. Read RFID
        uid = rfid.get_uid()
        if uid and len(uid) >= 4:
            rfid_str = "".join("{:02X}".format(b) for b in uid)
            if rfid_str != last_rfid:
                last_rfid = rfid_str
                tprint(PRINTSTATUS.INFO, "RFID: " + rfid_str)
                post_data(rfid_str)
                display_str = "RFID:" + rfid_str
                while len(display_str) < 16:
                    display_str = display_str + " "
                lcd.move_to(0, 1)
                lcd.putstr(display_str)

                # Buzzer beep after successful scan
                buzzer.on()
                time.sleep_ms(150)
                buzzer.off()

        time.sleep_ms(200)

main()