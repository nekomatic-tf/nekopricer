ARG VERSION=alpine

FROM python:$VERSION

LABEL maintainer="joey@nekos.site"

WORKDIR /app

COPY pyproject.toml .
COPY poetry.lock .
COPY README.md .
COPY nekopricer/ ./nekopricer

RUN pip install -e .

ENTRYPOINT [ "python", "-m", "nekopricer" ]