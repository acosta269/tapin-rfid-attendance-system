## parameters.py

# Buzzer configuration
BUZZER_PIN = 13
BUZZER_ACTIVE_LOW = False
BUZZER_USE_PWM = True           # set True for passive buzzers that need PWM tone
BUZZER_FREQ = 2000              # default tone frequency in Hz for PWM
BUZZER_DUTY = 512               # default PWM duty (10-bit range typical)

## i2c pinouts
SLC_PINOUT = 22                             # slc pin
SDA_PINOUT = 21                             # sda pin

## pinouts
SLK_PINOUT = 18                             # slk pin
MOSI_PINOUT = 23                            # mosi pin
MISO_PINOUT = 19                            # miso pin
CS_PINOUT = 5                               # cs pin
RST_PINOUT = 22                             # rst pin

## identification
DEVICE_ID = "esp32-rfid-001"                # unique device identifier *version - unit
AUTH_SEED = "12345678"                      # authentication seed

## location
LATITUDE = 17.577784                        # device latitude
LONGITUDE = 120.389451                      # device longitude

## payloads
PAYLOAD = None                              # data to sent
REQUEST_DATA = None                         # received data

## loops
COUNTER = 0                                 # loop counter
MAIN_LOOP = 0                               # main loop counter
MAX_LOOP = 100                              # max loops before restart