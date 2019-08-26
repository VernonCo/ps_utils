#! /usr/bin/env sh
set -e

cd /app
# If there's a prestart.sh script in the /app directory, run it before starting
PRE_START_PATH=/prestart.sh
echo "Checking for script in $PRE_START_PATH"
if [ -f $PRE_START_PATH ] ; then
    echo "Running script $PRE_START_PATH"
    . "$PRE_START_PATH"
else
    echo "There is no script $PRE_START_PATH"
fi


if test "$FLASK_ENV" = "development" ; then
    pypy3 run.py
else
    nginx -t && /etc/init.d/nginx restart
    # uwsgi is having issues with pypy3 must change nginx.conf to work with uwsgi socket
    # uwsgi --ini uwsgi.ini

    # gunicorn
    gunicorn --name 'Gunicorn App Gevent' --chdir ./app --bind 0.0.0.0:9000 app:app --worker-connections 1001 --workers 4
fi
