## main.py

## Imports
import machine
import utime as time
import ujson as json
import urequests as requests
import ntptime
import network
import sys

from boot import *
from configs.config import *
from configs import parameters as param
from driver import BUZZER, PCF8574, PN532

## Global hardware objects
buzzer = None
lcd = None
rfid = None

## Functions
def check_wifi_connection():
    """Check if WiFi is connected and reconnect if needed"""
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        tprint(PRINTSTATUS.WARN, "WiFi disconnected, attempting to reconnect...")
        wlan.active(True)
        wlan.connect(param.WIFI_SSID, param.WIFI_PASSWORD)
        timeout = 30
        while not wlan.isconnected() and timeout > 0:
            time.sleep_ms(500)
            timeout -= 1
        if wlan.isconnected():
            tprint(PRINTSTATUS.SUCCESS, "WiFi reconnected!")
            tprint(PRINTSTATUS.INFO, "IP Address: " + wlan.ifconfig()[0])
            return True
        else:
            tprint(PRINTSTATUS.ERROR, "WiFi reconnection failed")
            return False
    return True

def check_internet_connection():
    """Check if device has internet access by pinging a reliable server"""
    try:
        import socket
        socket.getaddrinfo("8.8.8.8", 53)
        return True
    except:
        try:
            socket.getaddrinfo("google.com", 80)
            return True
        except:
            return False

def check_api_connectivity():
    """Check if API is reachable - with SSL disabled"""
    try:
        url = API_URL.rstrip("/") + "/api/device-ping"
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "test"}, timeout=5)
        response.close()
        return True
    except:
        return False

def test_api_connection():
    """Test API connection before starting main loop - with SSL disabled"""
    if not check_wifi_connection():
        return False
        
    try:
        url = API_URL.rstrip("/") + "/api/device-ping"
        tprint(PRINTSTATUS.INFO, f"Testing API connection: {url}")
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "test"}, timeout=5)
        tprint(PRINTSTATUS.INFO, f"API test response: {response.status_code}")
        response.close()
        return True
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, f"API connection test failed: {str(e)}")
        return False

def restart_device():
    """Restart the device"""
    tprint(PRINTSTATUS.WARN, "RESTARTING: No internet connection...")
    
    # Show restart message on LCD
    try:
        if lcd:
            lcd.clear()
            lcd.putstr("NO INTERNET!")
            lcd.move_to(0, 1)
            lcd.putstr("RESTARTING...")
    except:
        pass
    
    # Beep pattern - 3 beeps for restart
    try:
        if buzzer:
            for _ in range(3):
                buzzer.on()
                time.sleep_ms(200)
                buzzer.off()
                time.sleep_ms(200)
    except:
        pass
    
    time.sleep_ms(2000)  # Give time to see the message
    machine.reset()

def send_ping():
    """Send device ping with SSL disabled"""
    if not check_wifi_connection():
        return False
        
    url = API_URL.rstrip("/") + "/api/device-ping"
    headers = {"Content-Type": "application/json"}
    try:
        # Using HTTP request without SSL verification
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "alive"}, headers=headers, timeout=10)
        status = response.status_code
        response.close()
        # Accept 200, 301, 302 as success (redirects are fine)
        if status in [200, 301, 302]:
            tprint(PRINTSTATUS.INFO, "Ping sent: Device alive")
            return True
        else:
            tprint(PRINTSTATUS.WARN, f"Ping returned status: {status}")
            return False
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, f"Ping failed: {str(e)}")
        return False

def post_data(rfid_str):
    """Send RFID data with SSL disabled - handles redirects"""
    if not check_wifi_connection():
        return False
        
    url = API_URL.rstrip("/") + "/api/receive-rfid"
    headers = {"Content-Type": "application/json"}   
    t = time.localtime()
    scanned_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )
    
    data = {
        "rfid": rfid_str,
        "scanned_at": scanned_time
    }
    
    try:
        tprint(PRINTSTATUS.INFO, f"Sending RFID to: {url}")
        r = requests.post(url, json=data, headers=headers, timeout=10)
        status = r.status_code
        tprint(PRINTSTATUS.INFO, f"RFID response status: {status}")
        
        # Try to get response content for debugging
        try:
            response_text = r.text
            if response_text:
                tprint(PRINTSTATUS.INFO, f"Response: {response_text[:100]}")
        except:
            pass
            
        r.close()
        
        # Accept 200, 301, 302 as success (redirects are fine)
        # 301/302 means Railway is redirecting HTTP to HTTPS
        if status in [200, 301, 302]:
            return True
        else:
            tprint(PRINTSTATUS.WARN, f"RFID send returned status: {status}")
            return False
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, f"Send error: {str(e)}")
        return False

def sync_manila_time():
    """Sync time from internet and adjust to Manila (UTC+8)"""
    if not check_wifi_connection():
        return False
        
    try:
        ntptime.host = "pool.ntp.org"
        ntptime.settime()
        t = time.localtime(time.time() + 8 * 3600)
        machine.RTC().datetime((t[0], t[1], t[2], t[6] + 1, t[3], t[4], t[5], 0))
        tprint(PRINTSTATUS.SUCCESS, "Manila Time Synced")
        return True
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, f"Time Sync Failed: {str(e)}")
        return False

def monitor_internet_and_restart():
    """Monitor internet and restart if no connection"""
    global no_internet_count
    
    # Check WiFi
    if not check_wifi_connection():
        tprint(PRINTSTATUS.ERROR, "No WiFi connection!")
        no_internet_count += 1
        if no_internet_count >= 3:
            restart_device()
        return False
    
    # Check internet connectivity
    if not check_internet_connection():
        tprint(PRINTSTATUS.ERROR, "No internet connection!")
        no_internet_count += 1
        if no_internet_count >= 3: 
            restart_device()
        return False
    
    # Check API connectivity
    if not check_api_connectivity():
        tprint(PRINTSTATUS.ERROR, "API not reachable!")
        no_internet_count += 1
        if no_internet_count >= 3:
            restart_device()
        return False
    
    # Reset counter if all checks pass
    no_internet_count = 0
    return True

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
    global buzzer, lcd, rfid, no_internet_count
    
    # Initialize counter
    no_internet_count = 0

    # Check WiFi first
    tprint(PRINTSTATUS.INFO, "Checking WiFi connection...")
    if not check_wifi_connection():
        tprint(PRINTSTATUS.ERROR, "WiFi not connected! Restarting...")
        time.sleep_ms(2000)
        machine.reset()

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

    # Sync Manila Time
    sync_manila_time()

    # Test API connection - restart if fails
    tprint(PRINTSTATUS.INFO, "Testing API connection...")
    if not test_api_connection():
        tprint(PRINTSTATUS.ERROR, "API connection failed! Restarting...")
        time.sleep_ms(2000)
        machine.reset()

    # NORMAL OPERATION
    last_rfid = None
    last_ping = time.ticks_ms()
    last_time_update = time.ticks_ms()
    last_internet_check = time.ticks_ms()
    ping_retry_count = 0
    max_ping_retries = 3

    tprint(PRINTSTATUS.SUCCESS, "Device Ready.")
    
    # Display initial status on LCD
    try:
        lcd.clear()
        lcd.putstr("TAPIN READY")
        lcd.move_to(0, 1)
        lcd.putstr("Scan RFID Card")
    except:
        pass
    
    # --- MAIN LOOP ---
    while True:
        current_time = time.ticks_ms()
        
        # 1. Check internet connectivity every 30 seconds - RESTART IF NO INTERNET
        if time.ticks_diff(current_time, last_internet_check) >= 30000:  # 30 seconds
            last_internet_check = current_time
            monitor_internet_and_restart()  # This will restart if no internet

        # 2. Send ping
        if time.ticks_diff(current_time, last_ping) >= param.PING_INTERVAL:
            last_ping = current_time
            if not send_ping():
                ping_retry_count += 1
                if ping_retry_count >= max_ping_retries:
                    tprint(PRINTSTATUS.WARN, "Multiple ping failures - restarting...")
                    time.sleep_ms(1000)
                    machine.reset()
            else:
                ping_retry_count = 0

        # 3. Update Time — AM/PM format
        if time.ticks_diff(current_time, last_time_update) >= 1000:
            last_time_update = current_time
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
            try:
                lcd.move_to(0, 0)
                lcd.putstr(time_str)
            except:
                pass

        # 4. Read RFID
        try:
            uid = rfid.get_uid()
            if uid and len(uid) >= 4:
                rfid_str = "".join("{:02X}".format(b) for b in uid)

                if rfid_str != last_rfid:
                    last_rfid = rfid_str
                    tprint(PRINTSTATUS.INFO, "RFID: " + rfid_str)

                    # Buzzer beep after successful scan
                    try:
                        buzzer.on()
                        time.sleep_ms(150)
                        buzzer.off()
                    except:
                        pass

                    # Display RFID on LCD
                    display_str = "RFID:" + rfid_str
                    while len(display_str) < 14:
                        display_str = display_str + " "
                    try:
                        lcd.move_to(0, 1)
                        lcd.putstr(display_str)
                    except:
                        pass

                    # Send RFID data to API - Show status on LCD
                    if check_wifi_connection() and check_internet_connection():
                        if post_data(rfid_str):
                            # Success - show OK
                            try:
                                lcd.move_to(14, 1)
                                lcd.putstr("OK")
                            except:
                                pass
                            tprint(PRINTSTATUS.SUCCESS, "RFID sent successfully")
                        else:
                            # Failed - show ER
                            try:
                                lcd.move_to(14, 1)
                                lcd.putstr("ER")
                            except:
                                pass
                            tprint(PRINTSTATUS.ERROR, "RFID send failed")
                    else:
                        tprint(PRINTSTATUS.ERROR, "Cannot send RFID - No internet")
                        try:
                            lcd.move_to(14, 1)
                            lcd.putstr("! ")
                        except:
                            pass

        except Exception as e:
            tprint(PRINTSTATUS.ERROR, f"RFID read error: {str(e)}")

        time.sleep_ms(200)

main()
