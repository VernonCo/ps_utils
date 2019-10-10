# pypy3 v7.1.1
FROM pypy:3.6-slim
LABEL maintainer="Stuart Zurcher <stuartz@vernoncompany.com>"

COPY ./requirements.txt /
RUN DEBIAN_FRONTEND="noninteractive" \
    && apt update && apt upgrade -y \
    && apt install -y nginx python3-dev  build-essential mysql-client default-libmysqlclient-dev \
    nano wget locate dnsutils \
    # openssl ca-certificates ntpdate \
    && pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r /requirements.txt \
    && pip install --upgrade certifi \
    && apt autoremove && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
    # remove python certs to use openssl
    # && rm /usr/local/lib/python3.7/site-packages/pip/_vendor/certifi/cacert.pem \
    # && rm /usr/local/lib/python3.7/site-packages/certifi/cacert.pem


#suds-py fix for ref in wsdls
COPY ./sxbase.py /usr/local/site-packages/suds/xsd/sxbase.py

# COPY ./entrypoint.sh /entrypoint.sh

COPY ./start.sh  ./prestart.sh /
# allow execute
RUN chmod +x /start.sh # chmod +x /entrypoint.sh

# for gunicorn server
COPY ./nginx.conf /etc/nginx
# for uswgi server (change start.sh and uncomment FROM line 1)
# COPY ./nginx-uwsgi.conf /etc/nginx

COPY ./ps_utils /app

WORKDIR /app

ENV PYTHONPATH=/app

#nginx 80, gunicorn 9000
EXPOSE 80 9000

# ENTRYPOINT ["/entrypoint.sh"]

# Run the start script, it will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Nginx w/ uwsgi (prod) or werkzeug (dev)
CMD ["/start.sh"]
