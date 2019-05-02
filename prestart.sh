#! /usr/bin/env sh
set -e

if [ -n "$FIRST_START" ]; then
    export FLASK_APP="app:create_app('config')"
    flask fab create-db
    flask fab create-admin < admin.sh
fi
