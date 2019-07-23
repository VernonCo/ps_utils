FROM python:3.7-slim

LABEL maintainer="Stuart Zurcher <stuartz@vernoncompany.com>"

COPY ./requirements.txt /
RUN DEBIAN_FRONTEND="noninteractive" \
    && apt update && apt upgrade -y \
    && apt install -y nginx python3-dev  build-essential mysql-client default-libmysqlclient-dev \
    nano wget locate \
    # openssl ca-certificates ntpdate \
    && pip install --upgrade pip \
    && pip install -r /requirements.txt \
    && pip install --upgrade certifi \
    && apt autoremove && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
    # remove python certs to use openssl
    # && rm /usr/local/lib/python3.7/site-packages/pip/_vendor/certifi/cacert.pem \
    # && rm /usr/local/lib/python3.7/site-packages/certifi/cacert.pem

COPY ./entrypoint.sh /entrypoint.sh

COPY ./start.sh  ./prestart.sh /

#suds-py fix for ref in wsdls
COPY ./venv/lib/python3.6/site-packages/suds/xsd/sxbase.py /usr/local/lib/python3.7/site-packages/suds/xsd/sxbase.py

# allow execute
RUN chmod +x /entrypoint.sh && chmod +x /start.sh

# USER www-data

# COPY ./gunicorn_conf.py /gunicorn_conf.py
COPY ./nginx.conf /etc/nginx

COPY ./ps_utils /app

WORKDIR /app

ENV PYTHONPATH=/app

EXPOSE 80

# ENTRYPOINT ["/entrypoint.sh"]

# Run the start script, it will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Nginx w/ uwsgi (prod) or werkzeug (dev)
CMD ["/start.sh"]
