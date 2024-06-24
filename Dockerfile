ARG VERSION=alpine

FROM python:$VERSION

LABEL maintainer="joey@nekos.site"

COPY . /app

RUN cd /app && pip install -r requirements.txt

WORKDIR /app

ENTRYPOINT ["python", "-u", "/app/main.py"]