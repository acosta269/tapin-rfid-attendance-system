## firmware boot.py

## imports
import machine
import network
import ntptime
import os

import utime as time
import urequests as requests


import main

from configs.config import *
from configs.network_config import *


## classes
class PRINTSTATUS:
    """Status codes for logging messages"""
    
    OK = "OKK"
    INFO = "INF"
    ERROR = "ERR"
    WARN = "WRN"
    SUCCESS = "SCS"
    DEBUG = "DBG"


## call functions
def get_date_string() -> str:
    """Return current date as YYYY_MM_DD."""
    
    year, month, day = time.localtime()[:3]
    return f"{year:04d}_{month:02d}_{day:02d}"

def get_log_filename(log_type: str) -> str:
    """Return log filename for given type."""
    
    date_str = get_date_string()
    return f"{LOG_FOLDER}/{log_type}_{date_str}.log"

def log_to_file(log_type: str, message: str) -> None:
    """Append message to runtime or error log."""
    
    try:
        filename = get_log_filename(log_type)
        
        if log_type == "runtime":
            pass # disable runtime logging
            #with open(filename, "a") as f:
            #    f.write(message + "\n")
        else:
            pass # disable error logging
            #with open(filename, "a") as f:
            #    f.write(message + "\n")
                
    except:
        pass
    
def tprint(printstatus: str, message: str) -> int:
    """Print message with timestamp, append to runtime log, and console."""
    
    rtc = machine.RTC().datetime()
    timestamp = f"{rtc[0]:04d}-{rtc[1]:02d}-{rtc[2]:02d} {rtc[4]:02d}:{rtc[5]:02d}:{rtc[6]:02d}"
    full_message = f"[{timestamp}] - [{printstatus}]: {message}."
    
    print(full_message)  
    log_to_file("runtime", full_message)
    
    return int(time.time())

def eprint(printstatus: str, message: str) -> None:
    """Log error with timestamp, append to error log, and console."""
    
    rtc = machine.RTC().datetime()
    timestamp = f"{rtc[0]:04d}-{rtc[1]:02d}-{rtc[2]:02d} {rtc[4]:02d}:{rtc[5]:02d}:{rtc[6]:02d}"
    full_message = f"[{timestamp}] - [{printstatus}]: {message}."
    
    log_to_file("error", full_message)
    return None


## procedural functions
def startup_logo():
    logo = r"""
                      $$\                     
                      $$ |                    
 $$$$$$\  $$\   $$\ $$$$$$\    $$$$$$\        
 \____$$\ $$ |  $$ |\_$$  _|  $$  __$$\       
 $$$$$$$ |$$ |  $$ |  $$ |    $$ /  $$ |      
$$  __$$ |$$ |  $$ |  $$ |$$\ $$ |  $$ |      
\$$$$$$$ |\$$$$$$  |  \$$$$  |\$$$$$$  |      
 \_______| \______/    \____/  \______/                                    
    """
    print(logo)
    print("        auto firmware\n")

def reset_logs() -> None:
    """Reset runtime and error logs for current date."""
    
    try:
        for log_type in ["runtime", "error"]:
            filename = get_log_filename(log_type)
            with open(filename, "w") as f:
                f.write("")
                
    except:
        pass

def start_wifi() -> bool:
    """Connect to WiFi with retry and timeout."""
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            tprint(PRINTSTATUS.INFO ,f"Connecting to WiFi... (Attempt {retry_count + 1}/{max_retries})")
            
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            wlan.connect(SSID, PASSWORD)
            
            timeout = 30 
            connected = False
            
            for i in range(timeout):
                if wlan.isconnected():
                    connected = True
                    break
                time.sleep(1)
            
            if connected:
                tprint(PRINTSTATUS.SUCCESS, f"Connected to WiFi: {wlan.ifconfig()}")
                return True
            else:
                tprint(PRINTSTATUS.INFO, "WiFi connection timeout")
                retry_count += 1
                if retry_count < max_retries:
                    tprint(PRINTSTATUS.INFO, f"Retrying in 5 seconds...")
                    time.sleep(5)
                    
        except Exception as e:
            error_msg = f"WiFi error: {e}"
            tprint(PRINTSTATUS.ERROR, error_msg)
            eprint(PRINTSTATUS.ERROR, error_msg)
            retry_count += 1
            if retry_count < max_retries:
                tprint(PRINTSTATUS.INFO, f"Retrying in 5 seconds...")
                time.sleep(5)
    
    error_msg = "WiFi connection failed after 3 attempts"
    tprint(PRINTSTATUS.ERROR, error_msg)
    eprint(PRINTSTATUS.ERROR, error_msg)
    error_msg = "Resetting device..."
    tprint(PRINTSTATUS.WARN, error_msg)
    eprint(PRINTSTATUS.WARN, error_msg)
    machine.reset()
    return False

def sync_time() -> None:
    """Sync device time using NTP."""
    
    tprint(PRINTSTATUS.INFO, "Syncing time via NTP...")
    
    try:
        ntptime.settime()
        tprint(PRINTSTATUS.INFO, "Time synced using NTP")
        
    except:
        tprint(PRINTSTATUS.ERROR, "NTP sync failed")

def fech_old_version_info() -> tuple[str | None, str | None]:
    """Read local version file and return (PRINTSTATUS, version)."""
    
    tprint(PRINTSTATUS.INFO, "Reading old version...")
    
    try:
        with open(VERSION_FILE, "r") as f:
            version_info = f.read().strip()
            
            if version_info:
                old_status = version_info[0:4]
                old_version = version_info[7:]
                tprint(PRINTSTATUS.OK, "Successfully read old version")
                return old_status, old_version
            
        return None, None
    
    except Exception as e:
        error_msg = f"Error reading old version: {e}"
        tprint(PRINTSTATUS.ERROR, error_msg)
        eprint(PRINTSTATUS.ERROR, error_msg)
        return None, None

def fech_version_info() -> tuple[str | None, str | None]:
    """Fetch remote version info and return (PRINTSTATUS, version)."""
    
    tprint(PRINTSTATUS.INFO, "Fetching latest version...")
    
    try:
        response = requests.get(VERSION_URL, timeout=10)
        
        if response.status_code == 200:
            response_text = response.text.strip()
            
            if response_text:
                response_status = response_text[0:4]
                response_version = response_text[7:]
                tprint(PRINTSTATUS.INFO, f"Response version: {response_text}")
                tprint(PRINTSTATUS.OK, "Successfully fetched version")
                return response_status, response_version
                
        return None, None
    
    except Exception as e:
        error_msg = f"Error fetching version: {e}"
        tprint(PRINTSTATUS.ERROR, error_msg)
        eprint(PRINTSTATUS.ERROR, error_msg)
        return None, None

def check_for_updates() -> bool:
    """Check for firmware updates and apply if available."""
    
    tprint(PRINTSTATUS.INFO, "Checking for updates...")
    
    try:
        old_status, old_version = fech_old_version_info()
        status, version = fech_version_info()

        if not status or not version or not old_version:
            error_msg = "Could not fetch version info properly"
            tprint(PRINTSTATUS.ERROR, error_msg)
            eprint(PRINTSTATUS.ERROR, error_msg)
            return False
            
        old_version_patch = old_version.rsplit('.', 1)[-1]
        version_patch = version.rsplit('.', 1)[-1]
        
        if status in ("live", "test") and int(version_patch) > int(old_version_patch):
            tprint(PRINTSTATUS.SUCCESS, f"New version available: {version}")
            
            tprint(PRINTSTATUS.INFO, "Updating version...")
            with open(VERSION_FILE, "w") as f:
                f.write(f"{status} - {version}")
            
            tprint(PRINTSTATUS.INFO, "Downloading main.py...")
            response = requests.get(MAIN_URL, timeout=30)
            
            if response.status_code == 200:
                with open("main.py", "w") as f:
                    f.write(response.text)
                tprint(PRINTSTATUS.SUCCESS, f"main.py updated to version {version}")
                machine.reset()
            else:
                error_msg = "Failed to download main.py"
                tprint(PRINTSTATUS.ERROR, error_msg)
                eprint(PRINTSTATUS.ERROR, error_msg)
                return False
        else:
            tprint(PRINTSTATUS.INFO, "No updates available")
            return True
        
    except Exception as e:
        error_msg = f"Error: {e}"
        tprint(PRINTSTATUS.ERROR, error_msg)
        eprint(PRINTSTATUS.ERROR, error_msg)
        return False
    
def fail_safe():
    time.sleep(10000)
    # buzzer
    

## main process loop
def process() -> None:
    """Boot process: WiFi, updates, run main.py with retry on error."""
    
    reset_logs()
    fail_safe_counter = 0
    
    while True:
        try:
            startup_logo()
            tprint(PRINTSTATUS.INFO, "Starting up...")
            
            start_wifi()
            sync_time()
            check_for_updates()
            
            if fail_safe_counter >= 10:
                tprint(PRINTSTATUS.WARN, "Fail-safe triggered!")
                fail_safe()
            
            else:
                tprint(PRINTSTATUS.INFO, "Running main.py...")
                main.main()
                     
            fail_safe_counter += 1
            
        except Exception as e:
            error_msg = f"Startup error: {e}"
            tprint(PRINTSTATUS.ERROR, error_msg)
            eprint(PRINTSTATUS.ERROR, error_msg)
            tprint(PRINTSTATUS.WARN, "Retrying in 10 seconds...")
            eprint(PRINTSTATUS.WARN, "Retrying in 10 seconds...")
            
            time.sleep(10)
            machine.reset()
            

if __name__ == "__main__":
    process()
    