#!/bin/python3
import datetime, logging, os, time
from dateutil.parser import parse

os.environ['TZ'] = 'America/Chicago'
time.tzset()

def current_datetime():
    return time.strftime('%Y-%m-%d %H:%M:%S')

def current_jde_date():
    return dt2Julian(current_datetime())

def current_jde_time():
    """return current jde time"""
    return int(time.strftime('%H%M%S'))

def dt2Julian(dt):
    """
    convert '%Y-%m-%d %H:%M:%S' to 'Cyj' where C = century or 0=19, 1=20, 2=21,...
    """
    try:
        date_obj = parse(dt)
        # replace leading number with correct jde century
        century = int(date_obj.strftime( '%C')) - 19
        return int(str(century) + date_obj.strftime('%y%j'))
    except Exception as e:
        logging.error(str(e))
        return 0

def dt2jde_time(dt):
    """return jde time for datetime string"""
    try:
        date_obj = parse(dt)
        return int(date_obj.strftime('%H%M%S'))
    except Exception as e:
        logging.error(str(e))
        return 0

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
        # default Jan 1, 1970
        return '1970-01-01T00:00:00+00:00'

def strtodatetime(dt):
    """returns datetime.datetime for date string"""
    try:
        return parse(dt)
    except Exception as e:
        logging.error(str(e))
        # default Jan 1, 1970
        return strtodatetime('1970/01/01')

def strtotime(dt):
    """returns time object for datetime string"""
    try:
        return parse(dt).timetuple()
    except Exception as e:
        logging.error(str(e))
        # default Jan 1, 1970
        return strtotime('1970/01/01')
