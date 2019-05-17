#! /usr/bin/env sh
set -e

# wait for db to be available
while ! mysqladmin ping -h"$DB_HOST" --silent; do
    sleep 1
done
