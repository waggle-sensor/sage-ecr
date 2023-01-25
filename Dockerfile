FROM python:3.8-alpine

WORKDIR /usr/src/app

# required for python library mysqlclient
RUN apk add linux-headers mariadb-connector-c-dev gcc musl-dev git

COPY requirements.txt /usr/src/app/
RUN /usr/local/bin/python -m pip install --upgrade pip && pip install -r requirements.txt

COPY *.py /usr/src/app/

CMD gunicorn ecr_api:app --log-level=info --bind=0.0.0.0:5000 --reload --graceful-timeout 630 --timeout 700
