# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

RUN apt-get update && \
    apt-get install -y libaio1 && \
    apt-get clean

ENV PYTHON_USERNAME="grp7"
ENV PYTHON_PASSWORD="grp7"
ENV PYTHON_CONNECTSTRING="172.22.134.87/XE"
ENV LD_LIBRARY_PATH="instantclient_19_23"

WORKDIR /python-docker

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "app.py" ]

