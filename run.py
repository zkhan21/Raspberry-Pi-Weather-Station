from __future__ import print_function

import datetime
import logging
import os
import sys
import time
import traceback
from urllib.parse import urlencode

import urllib.request
from sense_hat import SenseHat

from config import Config

DEBUG_MODE = True
# specifies how often to measure values from the Sense HAT (in minutes)
MEASUREMENT_INTERVAL = 10  # minutes
# Set to False when testing the code and/or hardware
# Set to True to enable upload of weather data to Weather Underground
WEATHER_UPLOAD = True
# the weather underground URL used to upload weather data
WU_URL = 'https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php'
# some string constants
SINGLE_HASH = '#'
HASHES = '############################################'


b = [0, 0, 255]  # blue
r = [255, 0, 0]  # red
e = [0, 0, 0]  # empty
# create images for up and down arrows
arrow_up = [
    e, e, e, r, r, e, e, e,
    e, e, r, r, r, r, e, e,
    e, r, e, r, r, e, r, e,
    r, e, e, r, r, e, e, r,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e
]
arrow_down = [
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    b, e, e, b, b, e, e, b,
    e, b, e, b, b, e, b, e,
    e, e, b, b, b, b, e, e,
    e, e, e, b, b, e, e, e
]
bars = [
    e, e, e, e, e, e, e, e,
    e, e, e, e, e, e, e, e,
    r, r, r, r, r, r, r, r,
    r, r, r, r, r, r, r, r,
    b, b, b, b, b, b, b, b,
    b, b, b, b, b, b, b, b,
    e, e, e, e, e, e, e, e,
    e, e, e, e, e, e, e, e
]

# Initialize some global variables
# last_temp = 0
wu_station_id = ''
wu_station_key = ''
sense = None


def c_to_f(input_temp):
    # convert input_temp from Celsius to Fahrenheit
    return (input_temp * 1.8) + 32


def get_cpu_temp():

    res = os.popen('vcgencmd measure_temp').readline()
    return float(res.replace("temp=", "").replace("'C\n", ""))


# use moving average to smooth readings
def get_smooth(x):
    # do we have the t object?
    if not hasattr(get_smooth, 't'):
        # then create it
        get_smooth.t = [x, x, x]
    # manage the rolling previous values
    get_smooth.t[2] = get_smooth.t[1]
    get_smooth.t[1] = get_smooth.t[0]
    get_smooth.t[0] = x
    # average the three last temperatures
    xs = (get_smooth.t[0] + get_smooth.t[1] + get_smooth.t[2]) / 3
    return xs


def get_temp():

    # First, get temp readings from both sensors
    t1 = sense.get_temperature_from_humidity()
    t2 = sense.get_temperature_from_pressure()
    # t becomes the average of the temperatures from both sensors
    t = (t1 + t2) / 2
    # Now, grab the CPU temperature
    t_cpu = get_cpu_temp()
    # Calculate the 'real' temperature compensating for CPU heating
    t_corr = t - ((t_cpu - t) / 1.5)
    # Finally, average out that value across the last three readings
    t_corr = get_smooth(t_corr)
    # convoluted, right?
    # Return the calculated temperature
    return t_corr


def processing_loop():
    global sense, wu_station_id, wu_station_key, last_temp

    # Initialize the initial arrow direction
    arrow_direction = None
    last_minute = None
    last_temp = get_temp()  # Take an initial temperature reading

    while 1:
        calc_temp = get_temp()
        temp_f = round(c_to_f(calc_temp), 1)
        logging.info("Current Temp: %sF, Last Temp: %sF" % (temp_f, c_to_f(last_temp)))

        current_minute = datetime.datetime.now().minute

        if current_minute != last_minute:
            last_minute = current_minute
            if (current_minute == 0) or ((current_minute % MEASUREMENT_INTERVAL) == 0):
                # [Your existing code...]

                if last_temp < temp_f:
                    arrow_direction = arrow_up
                    logging.info("Temperature Increased")
                elif last_temp > temp_f:
                    arrow_direction = arrow_down
                    logging.info("Temperature Decreased")
                else:
                    arrow_direction = bars
                    logging.info("Temperature Unchanged")

                sense.set_pixels(arrow_direction)
                last_temp = temp_f

                logging.debug('ID: {}'.format(wu_station_id))
                logging.debug('PASSWORD: {}'.format(wu_station_key))
                logging.debug('tempf: {}'.format(str(temp_f)))
                logging.debug('humidity: {}'.format(str(humidity)))
                logging.debug('baromin: {}'.format(str(pressure)))

                    # ========================================================
                    # Upload the weather data to Weather Underground
                    # ========================================================
                    # is weather upload enabled (True)?
                if WEATHER_UPLOAD:
                # From http://wiki.wunderground.com/index.php/PWS_-_Upload_Protocol
                    logging.info('Uploading data to Weather Underground')
                    # build a weather data object
                    weather_data = {
                        'action': 'updateraw',
                        'ID': wu_station_id,
                        'PASSWORD': wu_station_key,
                        'dateutc': "now",
                        'tempf': str(temp_f),
                        'humidity': str(humidity),
                        'baromin': str(pressure),
                    }
                    try:
                        upload_url = WU_URL + "?" + urlencode(weather_data)
                        response = urllib.request.urlopen(upload_url)
                        html = response.read()
                        logging.info('Server response: {}'.format(html))
                        # best practice to close the file
                        response.close()
                    except:
                        logging.error('Exception type: {}'.format(type(e)))
                        logging.error('Error: {}'.format(sys.exc_info()[0]))
                        traceback.print_exc(file=sys.stdout)
                else:
                    logging.info('Skipping Weather Underground upload')

        # wait a second then check again
        # You can always increase the sleep value below to check less often
    time.sleep(1)  # this should never happen since the above is an infinite loop


def main():
    global sense, wu_station_id, wu_station_key

    # Setup the basic console logger
    format_str = '%(asctime)s %(levelname)s %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(format=format_str, level=logging.INFO, datefmt=date_format)
    # When debugging, uncomment the following two lines
    # logger = logging.getLogger()
    # logger.setLevel(logging.DEBUG)

    print('\n' + HASHES)
    print(SINGLE_HASH, 'Pi Weather Station (Sense HAT)          ', SINGLE_HASH)
    print(SINGLE_HASH, 'By Zuhair Khan', SINGLE_HASH)
    print(HASHES)

    # make sure we don't have a MEASUREMENT_INTERVAL > 60
    if (MEASUREMENT_INTERVAL is None) or (MEASUREMENT_INTERVAL > 60):
        logging.info("The application's 'MEASUREMENT_INTERVAL' cannot be empty or greater than 60")
        sys.exit(1)

    # ============================================================================
    #  Read Weather Underground Configuration
    # ============================================================================
    logging.info('Initializing Weather Underground configuration')
    wu_station_id = Config.STATION_ID
    wu_station_key = Config.STATION_KEY
    if (wu_station_id is None) or (wu_station_key is None):
        logging.info('Missing values from the Weather Underground configuration file')
        sys.exit(1)

    # we made it this far, so it must have worked...
    logging.info('Successfully read Weather Underground configuration')
    logging.info('Station ID: {}'.format(wu_station_id))
    logging.debug('Station key: {}'.format(wu_station_key))

    try:
        logging.info('Initializing the Sense HAT client')
        sense = SenseHat()
        # sense.set_rotation(180)
        # then write some text to the Sense HAT
        sense.show_message('Init', text_colour=[255, 255, 0], back_colour=[0, 0, 255])
        # clear the screen
        sense.clear()
    except:
        logging.info('Unable to initialize the Sense HAT library')
        logging.error('Exception type: {}'.format(type(e)))
        logging.error('Error: {}'.format(sys.exc_info()[0]))
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    logging.info('Initialization complete!')
    processing_loop()



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application\n")
        sys.exit(0)
