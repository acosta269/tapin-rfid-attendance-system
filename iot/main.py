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
    """Check if API is reachable using HTTPS directly (avoid redirects)"""
    try:
        # Use HTTPS directly to avoid redirect issues
        url = "https://tapin-api.up.railway.app/api/device-ping"
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "test"}, timeout=5)
        status = response.status_code
        response.close()
        if status == 200:
            return True
        return False
    except:
        # Fallback to HTTP check
        try:
            url = "http://tapin-api.up.railway.app/api/device-ping"
            response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "test"}, timeout=5)
            status = response.status_code
            response.close()
            if status == 200:
                return True
            return False
        except:
            return False

def test_api_connection():
    """Test API connection before starting main loop using HTTPS directly"""
    if not check_wifi_connection():
        return False
        
    # Try HTTPS directly first (this avoids the redirect)
    try:
        url = "https://tapin-api.up.railway.app/api/device-ping"
        tprint(PRINTSTATUS.INFO, f"Testing API connection (HTTPS): {url}")
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "test"}, timeout=5)
        status = response.status_code
        tprint(PRINTSTATUS.INFO, f"API test response: {status}")
        response.close()
        if status == 200:
            tprint(PRINTSTATUS.SUCCESS, "API connection OK (HTTPS)")
            return True
    except Exception as e:
        tprint(PRINTSTATUS.WARN, f"HTTPS test failed: {str(e)}")
    
    # Fallback to HTTP with redirect handling
    try:
        url = "http://tapin-api.up.railway.app/api/device-ping"
        tprint(PRINTSTATUS.INFO, f"Testing API connection (HTTP): {url}")
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "test"}, timeout=5)
        status = response.status_code
        tprint(PRINTSTATUS.INFO, f"API test response: {status}")
        response.close()
        if status == 200:
            tprint(PRINTSTATUS.SUCCESS, "API connection OK (HTTP)")
            return True
    except Exception as e:
        tprint(PRINTSTATUS.WARN, f"HTTP test failed: {str(e)}")
            
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
    
    time.sleep_ms(2000)
    machine.reset()

def send_ping():
    """Send device ping using HTTPS directly (avoids 301 redirect)"""
    if not check_wifi_connection():
        return False
        
    # Try HTTPS first - this avoids the redirect entirely
    url = "https://tapin-api.up.railway.app/api/device-ping"
    headers = {"Content-Type": "application/json"}
    
    try:
        tprint(PRINTSTATUS.INFO, f"Sending ping via HTTPS: {url}")
        response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "alive"}, headers=headers, timeout=10)
        status = response.status_code
        tprint(PRINTSTATUS.INFO, f"Ping response status: {status}")
        response.close()
        if status == 200:
            tprint(PRINTSTATUS.INFO, "Ping sent: Device alive")
            return True
        else:
            tprint(PRINTSTATUS.WARN, f"Ping returned status: {status}")
            return False
    except Exception as e:
        tprint(PRINTSTATUS.WARN, f"HTTPS ping failed: {str(e)}")
        
        # Fallback to HTTP (will get 301 redirect)
        try:
            url = "http://tapin-api.up.railway.app/api/device-ping"
            tprint(PRINTSTATUS.INFO, f"Trying HTTP ping: {url}")
            response = requests.post(url, json={"device_id": param.DEVICE_ID, "status": "alive"}, headers=headers, timeout=10)
            status = response.status_code
            tprint(PRINTSTATUS.INFO, f"HTTP ping response: {status}")
            response.close()
            # Only accept 200 - 301/302 means redirect (data not saved)
            if status == 200:
                tprint(PRINTSTATUS.INFO, "Ping sent via HTTP")
                return True
            return False
        except Exception as e2:
            tprint(PRINTSTATUS.ERROR, f"HTTP ping failed: {str(e2)}")
            return False

def post_data(rfid_str):
    """Send RFID data using HTTPS directly (avoids 301 redirect issues)"""
    if not check_wifi_connection():
        return False
        
    t = time.localtime()
    scanned_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )
    
    data = {
        "rfid": rfid_str,
        "scanned_at": scanned_time
    }
    headers = {"Content-Type": "application/json"}
    
    # Try HTTPS first - this avoids the 301 redirect entirely
    url = "https://tapin-api.up.railway.app/api/receive-rfid"
    
    try:
        tprint(PRINTSTATUS.INFO, f"Sending RFID via HTTPS: {url}")
        tprint(PRINTSTATUS.INFO, f"Data: {json.dumps(data)}")
        r = requests.post(url, json=data, headers=headers, timeout=10)
        status = r.status_code
        tprint(PRINTSTATUS.INFO, f"HTTPS response status: {status}")
        
        # Try to get response
        try:
            response_text = r.text
            if response_text:
                tprint(PRINTSTATUS.INFO, f"Response: {response_text[:200]}")
        except:
            pass
        r.close()
        
        # Only accept 200 - this means the data was actually saved
        if status == 200:
            tprint(PRINTSTATUS.SUCCESS, "RFID sent successfully via HTTPS")
            return True
        else:
            tprint(PRINTSTATUS.WARN, f"HTTPS returned {status} (not 200)")
            return False
    except Exception as e:
        tprint(PRINTSTATUS.WARN, f"HTTPS send failed: {str(e)}")
    
    # Fallback to HTTP - the server will redirect to HTTPS
    try:
        url = "http://tapin-api.up.railway.app/api/receive-rfid"
        tprint(PRINTSTATUS.INFO, f"Trying HTTP fallback: {url}")
        r = requests.post(url, json=data, headers=headers, timeout=10)
        status = r.status_code
        tprint(PRINTSTATUS.INFO, f"HTTP response status: {status}")
        
        try:
            response_text = r.text
            if response_text:
                tprint(PRINTSTATUS.INFO, f"Response: {response_text[:200]}")
        except:
            pass
        r.close()
        
        # Only accept 200 - 301/302 means redirect, data NOT saved
        if status == 200:
            tprint(PRINTSTATUS.SUCCESS, f"RFID sent successfully (status: {status})")
            return True
        else:
            tprint(PRINTSTATUS.WARN, f"RFID send returned: {status} (not 200)")
            return False
    except Exception as e:
        tprint(PRINTSTATUS.ERROR, f"HTTP send failed: {str(e)}")
        return False

def sync_manila_time():
    """Sync time from internet and adjust to Manila (UTC+8)"""
    if not check_wifi_connection():
        return False
        
    try:
        # Try multiple NTP servers
        ntp_servers = ["pool.ntp.org", "time.google.com", "time.windows.com", "ntp.aliyun.com"]
        for server in ntp_servers:
            try:
                tprint(PRINTSTATUS.INFO, f"Trying NTP: {server}")
                ntptime.host = server
                ntptime.settime()
                t = time.localtime(time.time() + 8 * 3600)
                machine.RTC().datetime((t[0], t[1], t[2], t[6] + 1, t[3], t[4], t[5], 0))
                tprint(PRINTSTATUS.SUCCESS, f"Manila Time Synced via {server}")
                return True
            except Exception as e:
                tprint(PRINTSTATUS.WARN, f"NTP {server} failed: {str(e)}")
                continue
        
        tprint(PRINTSTATUS.ERROR, "All NTP servers failed")
        return False
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

def clear_status():
    """Clear only the status indicators (OK/ER/!) from LCD row 1, positions 14-15"""
    try:
        lcd.move_to(14, 1)
        lcd.putstr("  ")  # Two spaces to clear OK/ER/!
    except:
        pass

def reset_lcd_to_ready():
    """Reset LCD second row to 'Scan RFID Card'"""
    try:
        lcd.move_to(0, 1)
        lcd.putstr("Scan RFID Card")
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
    last_rfid = None                                # Track last scanned RFID to prevent duplicates
    last_rfid_time = 0                              # Track last time a specific RFID was scanned
    last_scan_time = 0                              # Track last time ANY RFID was scanned (for clearing status)
    last_status_time = 0                            # Track when status (OK/ER) was shown
    ping_retry_count = 0                            # Track consecutive ping failures
    max_ping_retries = 3                            # Max retries before restart
    timer_delay = 8000                              # 8 seconds for status clear, cooldown, and display reset

    last_ping = time.ticks_ms()                     # Track last ping time
    last_time_update = time.ticks_ms()              # Track last time update for LCD
    last_internet_check = time.ticks_ms()           # Track last internet check time

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
            
            # Check if we need to clear status after 8 seconds
            if last_status_time > 0:
                time_since_status = time.ticks_diff(current_time, last_status_time)
                if time_since_status >= timer_delay:
                    clear_status()
                    last_status_time = 0
            
            # Check if we need to reset display after 8 seconds of no scan
            if last_scan_time > 0:
                time_since_last_scan = time.ticks_diff(current_time, last_scan_time)
                if time_since_last_scan >= timer_delay:
                    reset_lcd_to_ready()
                    last_scan_time = 0  # Reset so we don't keep resetting
                    # Reset last_rfid so the next scan shows as new
                    last_rfid = None

        # 4. Read RFID
        try:
            uid = rfid.get_uid()
            if uid and len(uid) >= 4:
                rfid_str = "".join("{:02X}".format(b) for b in uid)

                # Check if this is a new RFID or same RFID but cooldown expired
                is_new_rfid = (rfid_str != last_rfid)
                is_cooldown_expired = False
                
                if not is_new_rfid:
                    # Same RFID - check cooldown
                    time_since_last_scan = time.ticks_diff(current_time, last_rfid_time)
                    if time_since_last_scan >= timer_delay:
                        is_cooldown_expired = True
                        tprint(PRINTSTATUS.INFO, f"Cooldown expired for RFID: {rfid_str}")
                    else:
                        remaining = (timer_delay - time_since_last_scan) // 1000
                        tprint(PRINTSTATUS.INFO, f"Cooldown active for RFID: {rfid_str} ({remaining}s remaining)")
                
                # Process RFID if it's new OR cooldown expired
                if is_new_rfid or is_cooldown_expired:
                    last_rfid = rfid_str
                    last_rfid_time = current_time
                    last_scan_time = current_time  # Update last scan time for display reset
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
                            # Success - show OK (only when status 200)
                            try:
                                lcd.move_to(14, 1)
                                lcd.putstr("OK")
                                last_status_time = current_time  # Track when status was shown
                            except:
                                pass
                            tprint(PRINTSTATUS.SUCCESS, "RFID sent successfully (200 OK)")
                        else:
                            # Failed - show ER (for 301, 302, or any error)
                            try:
                                lcd.move_to(14, 1)
                                lcd.putstr("ER")
                                last_status_time = current_time  # Track when status was shown
                            except:
                                pass
                            tprint(PRINTSTATUS.ERROR, "RFID send failed (not 200)")
                    else:
                        tprint(PRINTSTATUS.ERROR, "Cannot send RFID - No internet")
                        try:
                            lcd.move_to(14, 1)
                            lcd.putstr("! ")
                            last_status_time = current_time  # Track when status was shown
                        except:
                            pass

        except Exception as e:
            tprint(PRINTSTATUS.ERROR, f"RFID read error: {str(e)}")

        time.sleep_ms(200)

main()