## parameters.py

# Buzzer configuration
BUZZER_PIN = 13
BUZZER_ACTIVE_LOW = False
BUZZER_USE_PWM = True           # set True for passive buzzers that need PWM tone
BUZZER_FREQ = 2000              # default tone frequency in Hz for PWM
BUZZER_DUTY = 512               # default PWM duty (10-bit range typical)

## lcd configuration
LCD_ADDR = 0x27                 # I2C address of the LCD

## i2c pinouts
I2C_SDA_PINOUT = 21                         # sda pin
I2C_SCL_PINOUT = 22                         # scl pin 

## rfid pinouts
RFID_RST_PINOUT = 4                       # rst pin
RFID_MISO_PINOUT = 19                       # miso pin
RFID_MOSI_PINOUT = 23                       # mosi pin
RFID_SCK_PINOUT = 18                        # sck pin
RFID_SDA_PINOUT = 5                         # sda pin

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
PING_INTERVAL = 30000                       # 30 seconds
TEST_INTERVAL = 10000                       # 10 seconds