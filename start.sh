#! /usr/bin/env sh
set -e


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
    python run.py
else
    /etc/init.d/nginx restart
    uwsgi --ini uwsgi.ini
    # Start Gunicorn  --- had issues with creating the views for each worker
    # exec gunicorn -k egg:meinheld#gunicorn_worker -c "$GUNICORN_CONF" "$APP_MODULE"
fi
