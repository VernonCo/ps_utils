#!/bin/python3
import datetime, logging, os, time
from dateutil.parser import parse

os.environ['TZ'] = 'America/Chicago'
time.tzset()

def current_datetime():
    return time.strftime('%Y-%m-%d %H:%M:%S')

def current_jde_time():
    """return current jde time"""
    return int(time.strftime('%H%M%S'))

def dt2Julian(dt):
    """
    convert '%Y-%m-%d %H:%M:%S' to 'Cyj' where C = century or 1=19, 2=20
    """

    date = strtotime(dt)
    century =  time.strftime( '%C', date )[:1]
    return int(century + time.strftime('%y%j',date))

def dt2jde_time(dt):
    """return jde time for datetime string"""
    try:
        dt = strtodatetime(dt)
        return int(dt.strftime('%H%M%S'))
    except Exception as e:
        logging.error(str(e))
        return ''

def julianDate2ISO8601(d, offset='+00:00'):
    """
    return ISO8601 formated datetime from julian date
    optional offset  [+|-]hh:mm
    """
    try:
        d = str(d)  # make sure it is a string
        # replace leading number with correct century
        centuryArray = ['19','20','21']
        d = centuryArray[int(d[:1])] + d[1:]
        # format to iso8601 datetime
        return datetime.datetime.strptime(d, '%Y%j').date().strftime('%Y-%m-%dT00:00:00') + offset
    except Exception as e:
        logging.error(str(e))
        return 0

def strtodatetime(dt):
    try:
        return parse(dt)
    except Exception as e:
        logging.error(str(e))
        return 0

def strtotime(dt):
    """returns time object for datetime string"""
    # change to common format
    dt = parse(dt).strftime('%Y-%m-%d %H:%M:%S')
    return time.strptime(dt, '%Y-%m-%d %H:%M:%S')
