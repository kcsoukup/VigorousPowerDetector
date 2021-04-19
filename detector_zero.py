r"""
___  ____  _____   ____  _____ ____ _ __ _____
\  \/ (__)/ .___>_/    \/   . >    | |  | ____>
 \    |  | <_<    > <> |     <  <> | |  |___  \
  \   |__|____   |\____|__|\  \____|    |      >
   \_/        `--'          `--'    `---'\____/
        P  R  o  G  R  A  M  M  i  N  G
<========================================[KCS]=>
  Developer: Ken C. Soukup
  Project  : Vigorous Power Detector
  Purpose  : Detects power outage based on relay closing, sends alert.
<=================================[02/28/2021]=>
  Notes:
    . There are 2 types of relays:
      . NC: Normally Closed when No power exists
      . NO: Normally Open when No power exists
    . This project uses Normally Closed relays to trigger a button press.

  Updated 03/29/2021 -- Ken C. Soukup
    . Version bump: 1.5
    . Added Relay Enable/Disable for unused ports
    . Added stdout flushing for background writes to logs (functools)
    . Consolidated GPIO assignments

  Updated 03/23/2021 -- Ken C. Soukup
    . Version bump: 1.4
    . Replaced SQS with SNS (Lambda polls SQS, exceeds Free Tier threshold)
    . Changed some variable names to avoid confusion

  Updated 03/20/2021 -- Ken C. Soukup
    . Version bump: 1.3
    . Added LEDs!
    . Updated Pins to align with RPi Breakout Board circuitry

  Updated 03/19/2021 -- Ken C. Soukup
    . Version bump: 1.2
    . Removed all gpiozero mock statements
    . Split the detection event into 1 per relay
    . Many small adjustments to code

  Updated 03/13/2021 -- Ken C. Soukup
    . Version bump: 1.5
    . Switch to use gpiozero vs RPi.GPIO
    . Configured for mock pin set
    . Cut over all statement for gpiozero module

"""
__project__ = 'Vigorous Power Detector'
__version__ = '1.4'
__author__ = 'Ken C. Soukup'
__company__ = 'Vigorous Programming'
__minted__ = '2021'

import os
import sys
import time
import signal
import socket
import functools
from datetime import datetime
import boto3
from gpiozero import Button
from gpiozero import LED

# Global Constants
BASENAME = os.path.basename(__file__)[0:-3]
FILE_DT = time.strftime('%Y%m%d_%H%M%S')
LOG_PATH = os.path.join(os.getcwd(), 'log')
ETC_PATH = os.path.join(os.getcwd(), 'etc')
LOG_FILE = os.path.join(LOG_PATH, BASENAME + '_' + FILE_DT + '.log')
ERR_FILE = os.path.join(LOG_PATH, BASENAME + '_' + FILE_DT + '.err')
HOSTNAME = socket.gethostname()
ENVIRONMENT = 'dev'
USE_LOG = False
RETENTION_DAYS = '180'
LOG_GHOSTS = False

# AWS Variables
AWS_ACCOUNT_ID = '<GET_YOUR_OWN_AWS_ACCOUNT>'
SNS_ENABLE = True
TOPIC_NAME = 'VigorousPowerDetector'
TOPIC_ARN = 'arn:aws:sns:us-east-2:' + AWS_ACCOUNT_ID + ':' + TOPIC_NAME
PROFILE_NAME = 'Starlight'

# Relay 1 Configs / BCM Pin Numbers
R1_ENABLED = True
R1_RELAY = Button(25)
R1_RED_LED = LED(17)
R1_RED_LED.off()
R1_GREEN_LED = LED(4)
R1_GREEN_LED.off()
R1_NAME = 'Sump Pump Relay'
R1_LAST_STATE = 2

# Relay 2 Configs / BCM Pin Numbers
R2_ENABLED = True
R2_RELAY = Button(5)
R2_RED_LED = LED(27)
R2_RED_LED.off()
R2_GREEN_LED = LED(18)
R2_GREEN_LED.off()
R2_NAME = 'Small Fridge Relay'
R2_LAST_STATE = 2

# Relay 3 Configs / BCM Pin Numbers
R3_ENABLED = False
R3_RELAY = Button(6)
R3_RED_LED = LED(23)
R3_RED_LED.off()
R3_GREEN_LED = LED(22)
R3_GREEN_LED.off()
R3_NAME = 'Garage Fridge Relay'
R3_LAST_STATE = 2


def main():
    """ Main program where all of the primary calls are made. """
    print (f'\n {__project__} v{__version__}')
    print (f' {__company__}')
    print (f' Crafted by {__author__} ({__minted__})\n')
    start_time = time.time()

    header('Runtime Environment')
    print(f'[+] Hostnane          : {HOSTNAME}')
    print(f'[+] Environment       : {ENVIRONMENT}')
    print(f'[+] Script Name       : {BASENAME}')
    print(f'[+] Logging Enabled   : {USE_LOG}')
    print(f'[+] Retention Days    : {RETENTION_DAYS}')
    print(f'[+] Log Directory     : {LOG_PATH}')
    print(f'[+] AWS User Id       : {PROFILE_NAME}')
    print(f'[+] SNS Topic Name    : {TOPIC_NAME}')
    print(f'[+] SNS Push Enabled  : {SNS_ENABLE}')
    print(f'[+] Relay 1 Name      : {R1_NAME}')
    print(f'[+] Relay 1 Enabled   : {R1_ENABLED}')
    print(f'[+] Relay 2 Name      : {R2_NAME}')
    print(f'[+] Relay 2 Enabled   : {R2_ENABLED}')
    print(f'[+] Relay 3 Name      : {R3_NAME}')
    print(f'[+] Relay 3 Enabled   : {R3_ENABLED}')
    print()

    header('NOTICE')
    print(f'[*] The relays are using Normally Closed states, circuit is closed, i.e. button pushed.')
    print(f'[*] When they have NO POWER they CLOSE which changes state to GPIO.HIGH (1).')
    print(f'[*] When they have POWER they OPEN which changes state to GPIO.LOW (0).')
    print(f'[*] "Power On" means the relays are OPEN, circuit is open, i.e. button released.')
    print()

    header('System Status')
    if R1_ENABLED:
        print(f'[+] Checking {R1_NAME} for current state...')
        r1_gpio_event_detected(R1_RELAY)
        # Attach callbacks for trigger events
        R1_RELAY.when_held = r1_gpio_event_detected
        R1_RELAY.when_released = r1_gpio_event_detected

    if R2_ENABLED:
        print(f'[+] Checking {R2_NAME} for current state...')
        r2_gpio_event_detected(R2_RELAY)
        # Attach callbacks for trigger events
        R2_RELAY.when_held = r2_gpio_event_detected
        R2_RELAY.when_released = r2_gpio_event_detected

    if R3_ENABLED:
        print(f'[+] Checking {R3_NAME} for current state...')
        r3_gpio_event_detected(R3_RELAY)
        # Attach callbacks for trigger events
        R3_RELAY.when_held = r3_gpio_event_detected
        R3_RELAY.when_released = r3_gpio_event_detected

    try:
        print()
        header('Monitoring')
        # input('[+] Press ENTER or CTRL-C to terminate script.\n')  # This is for Windows
        signal.pause()  # This is for Linux
    except KeyboardInterrupt:
        event_time = str(datetime.now().isoformat()).replace('T', ' ')
        print(f'[!] {event_time}, CTRL-C interrupt detected, terminating script...')
    except Exception as ex:
        event_time = str(datetime.now().isoformat()).replace('T', ' ')
        print(f'[!] {event_time}, Exception trapped: {ex}')
    finally:
        header('Cleaning up GPIO and exiting...')
        R1_RELAY.close()
        R2_RELAY.close()
        R3_RELAY.close()
        R1_RED_LED.close()
        R2_RED_LED.close()
        R1_GREEN_LED.close()
        R2_GREEN_LED.close()

    # Close Script
    script_run_time = (time.time()) - (start_time)
    print('\nElapsed Time : {0:02d} hrs. {1:02d} mins. {2:02d} secs. {3:06d} ms.'.format(
        int(script_run_time / 3600), (int(script_run_time / 60) % 60),
        int(script_run_time % 60), int((script_run_time * 1000) % 1000)))
    print('Mission Complete!!')


def r1_gpio_event_detected(channel):
    """ GPIO Event Detected, reviewing pin state and processing outcome. """
    # Relay 1 Handling
    global R1_LAST_STATE
    r1_state = channel.value
    event_time = str(datetime.now().isoformat()).replace('T', ' ')
    if r1_state == 1:
        # Check last state to be sure this is a true event
        description = 'Power is Off'
        R1_GREEN_LED.off()
        R1_RED_LED.on()
        if R1_LAST_STATE == 0:
            # header(R1_NAME)
            status = 'Failure'
            print(f'[!] {event_time}, {status}, {R1_NAME}, {description}, Pin State = {r1_state}, {HOSTNAME}, {ENVIRONMENT}')
            publish_sns_alert(event_time, R1_NAME, status, description, r1_state)
            R1_LAST_STATE = r1_state
        elif R1_LAST_STATE == 1 and LOG_GHOSTS:
            status = 'Ghost Trigger'
            print(f'[-] {event_time}, {status}, {R1_NAME}, {description}, Pin State = {r1_state}, {HOSTNAME}, {ENVIRONMENT}')
        elif R1_LAST_STATE == 2:
            status = 'Script Initializing'
            print(f'[+] {event_time}, {status}, {R1_NAME}, {description}, Pin State = {r1_state}, {HOSTNAME}, {ENVIRONMENT}')
            R1_LAST_STATE = r1_state
    if r1_state == 0:
        # Check last state to be sure this is a true event
        description = 'Power is On'
        R1_RED_LED.off()
        R1_GREEN_LED.on()
        if R1_LAST_STATE == 1:
            # header(R1_NAME)
            status = 'Success'
            print(f'[+] {event_time}, {status}, {R1_NAME}, {description}, Pin State = {r1_state}, {HOSTNAME}, {ENVIRONMENT}')
            publish_sns_alert(event_time, R1_NAME, status, description, r1_state)
            R1_LAST_STATE = r1_state
        elif R1_LAST_STATE == 0 and LOG_GHOSTS:
            status = 'Ghost Trigger'
            print(f'[-] {event_time}, {status}, {R1_NAME}, {description}, Pin State = {r1_state}, {HOSTNAME}, {ENVIRONMENT}')
        elif R1_LAST_STATE == 2:
            status = 'Script Initializing'
            print(f'[+] {event_time}, {status}, {R1_NAME}, {description}, Pin State = {r1_state}, {HOSTNAME}, {ENVIRONMENT}')
            R1_LAST_STATE = r1_state


def r2_gpio_event_detected(channel):
    """ GPIO Event Detected, reviewing pin state and processing outcome. """
    # Relay 2 Handling
    global R2_LAST_STATE
    r2_state = channel.value
    event_time = str(datetime.now().isoformat()).replace('T', ' ')
    if r2_state == 1:
        # Check last state to be sure this is a true event
        description = 'Power is Off'
        R2_GREEN_LED.off()
        R2_RED_LED.on()
        if R2_LAST_STATE == 0:
            # header(R2_NAME)
            status = 'Failure'
            print(f'[!] {event_time}, {status}, {R2_NAME}, {description}, Pin State = {r2_state}, {HOSTNAME}, {ENVIRONMENT}')
            publish_sns_alert(event_time, R2_NAME, status, description, r2_state)
            R2_LAST_STATE = r2_state
        elif R2_LAST_STATE == 1 and LOG_GHOSTS:
            status = 'Ghost Trigger'
            print(f'[-] {event_time}, {status}, {R2_NAME}, {description}, Pin State = {r2_state}, {HOSTNAME}, {ENVIRONMENT}')
        elif R2_LAST_STATE == 2:
            status = 'Script Initializing'
            print(f'[+] {event_time}, {status}, {R2_NAME}, {description}, Pin State = {r2_state}, {HOSTNAME}, {ENVIRONMENT}')
            R2_LAST_STATE = r2_state
    if r2_state == 0:
        # Check last state to be sure this is a true event
        description = 'Power is On'
        R2_RED_LED.off()
        R2_GREEN_LED.on()
        if R2_LAST_STATE == 1:
            # header(R2_NAME)
            status = 'Success'
            print(f'[+] {event_time}, {status}, {R2_NAME}, {description}, Pin State = {r2_state}, {HOSTNAME}, {ENVIRONMENT}')
            publish_sns_alert(event_time, R2_NAME, status, description, r2_state)
            R2_LAST_STATE = r2_state
        elif R2_LAST_STATE == 0 and LOG_GHOSTS:
            status = 'Ghost Trigger'
            print(f'[-] {event_time}, {status}, {R2_NAME}, {description}, Pin State = {r2_state}, {HOSTNAME}, {ENVIRONMENT}')
        elif R2_LAST_STATE == 2:
            status = 'Script Initializing'
            print(f'[+] {event_time}, {status}, {R2_NAME}, {description}, Pin State = {r2_state}, {HOSTNAME}, {ENVIRONMENT}')
            R2_LAST_STATE = r2_state


def r3_gpio_event_detected(channel):
    """ GPIO Event Detected, reviewing pin state and processing outcome. """
    # Relay 2 Handling
    global R3_LAST_STATE
    r3_state = channel.value
    event_time = str(datetime.now().isoformat()).replace('T', ' ')
    if r3_state == 1:
        # Check last state to be sure this is a true event
        description = 'Power is Off'
        R3_GREEN_LED.off()
        R3_RED_LED.on()
        if R3_LAST_STATE == 0:
            # header(R3_NAME)
            status = 'Failure'
            print(f'[!] {event_time}, {status}, {R3_NAME}, {description}, Pin State = {r3_state}, {HOSTNAME}, {ENVIRONMENT}')
            publish_sns_alert(event_time, R3_NAME, status, description, r3_state)
            R3_LAST_STATE = r3_state
        elif R3_LAST_STATE == 1 and LOG_GHOSTS:
            status = 'Ghost Trigger'
            print(f'[-] {event_time}, {status}, {R3_NAME}, {description}, Pin State = {r3_state}, {HOSTNAME}, {ENVIRONMENT}')
        elif R3_LAST_STATE == 2:
            status = 'Script Initializing'
            print(f'[+] {event_time}, {status}, {R3_NAME}, {description}, Pin State = {r3_state}, {HOSTNAME}, {ENVIRONMENT}')
            R3_LAST_STATE = r3_state
    if r3_state == 0:
        # Check last state to be sure this is a true event
        description = 'Power is On'
        R3_RED_LED.off()
        R3_GREEN_LED.on()
        if R3_LAST_STATE == 1:
            # header(R3_NAME)
            status = 'Success'
            print(f'[+] {event_time}, {status}, {R3_NAME}, {description}, Pin State = {r3_state}, {HOSTNAME}, {ENVIRONMENT}')
            publish_sns_alert(event_time, R3_NAME, status, description, r3_state)
            R3_LAST_STATE = r3_state
        elif R3_LAST_STATE == 0 and LOG_GHOSTS:
            status = 'Ghost Trigger'
            print(f'[-] {event_time}, {status}, {R3_NAME}, {description}, Pin State = {r3_state}, {HOSTNAME}, {ENVIRONMENT}')
        elif R3_LAST_STATE == 2:
            status = 'Script Initializing'
            print(f'[+] {event_time}, {status}, {R3_NAME}, {description}, Pin State = {r3_state}, {HOSTNAME}, {ENVIRONMENT}')
            R3_LAST_STATE = r3_state


def publish_sns_alert(event_time, relay_name, status, description, pin_state):
    """ Sends SNS message to AWS when GPIO event is detected. """
    # Message Payload
    message = f'{__project__} Notification'
    msg_attrs = {
        'eventTime': {
            'DataType': 'String',
            'StringValue': str(event_time)
        },
        'relayName': {
            'DataType': 'String',
            'StringValue': relay_name
        },
        'status': {
            'DataType': 'String',
            'StringValue': status
        },
        'description': {
            'DataType': 'String',
            'StringValue': description
        },
        'pinState': {
            'DataType': 'String',
            'StringValue': str(pin_state)
        },
        'environment': {
            'DataType': 'String',
            'StringValue': ENVIRONMENT
        },
        'hostname': {
            'DataType': 'String',
            'StringValue': HOSTNAME
        }
    }

    event_time = event_time = str(datetime.now().isoformat()).replace('T', ' ')
    if SNS_ENABLE:
        print(f'[+] {event_time}, Sending {relay_name} alert to SNS topic {TOPIC_NAME}...')
        session = boto3.Session(profile_name=PROFILE_NAME)
        client = session.client('sns')
        response = client.publish(TopicArn=TOPIC_ARN,
                               Message=message,
                               MessageAttributes=msg_attrs)
        print('[+] {}, SQS Response: {}'.format(event_time, response['ResponseMetadata']['HTTPStatusCode']))


def header(note):
    """ Standardized quick header. """
    print('[+] --- ' + note + ' ' + ('-' * ((79-9)-len(note))))


def remove_old_data(dir_name, days_back=90):
    """ Deletes files older than X days from supplied directory. """
    purge_time = time.time()-(int(days_back) * 86400)
    for curr_dir, _, files in os.walk(dir_name):
        for file_name in files:
            if os.path.isfile(os.path.join(curr_dir, file_name)):
                m_time = os.path.getmtime(os.path.join(curr_dir, file_name))
                if m_time < purge_time:
                    try:
                        print(f'[+] Expunge {dir_name} data older than {days_back} days...')
                        os.remove(os.path.join(curr_dir, file_name))
                        print('[+] Deleted {}'.format(os.path.join(curr_dir, file_name)))
                    except Exception as ex:
                        print(f'[-] {ex}')


if __name__ == '__main__':
    # Basic file system maintenance
    if not os.path.exists(LOG_PATH):
        os.makedirs(LOG_PATH)
    if not os.path.exists(ETC_PATH):
        os.makedirs(ETC_PATH)
    remove_old_data(LOG_PATH, RETENTION_DAYS)

    if USE_LOG:
        # Allow all STDOUT/STDERR to be redirected to log files instead of the console.
        SAVE_STD_OUT = sys.stdout
        SAVE_STD_ERR = sys.stderr
        LOG_WRITE = open(LOG_FILE, 'w')
        ERR_WRITE = open(ERR_FILE, 'w')
        sys.stdout = LOG_WRITE
        sys.stderr = ERR_WRITE
        print = functools.partial(print, flush=True)
        # Logged MAIN
        main()
        # Clean up logging if used.
        sys.stdout = SAVE_STD_OUT
        sys.stderr = SAVE_STD_ERR
        LOG_WRITE.close()
        ERR_WRITE.close()
    else:
        # Standard MAIN
        main()
