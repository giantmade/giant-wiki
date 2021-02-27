FROM python:3.9-slim

ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY poetry.lock pyproject.toml /app/

RUN set -ex \
  && apt-get update && apt-get -y --no-install-recommends install curl \
  && curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python \
  && . $HOME/.poetry/env \
  && poetry config virtualenvs.create false \
  && poetry install --no-dev --no-root --no-interaction --no-ansi

ENV PATH=/root/.poetry/bin:${PATH}

COPY . /app/
EXPOSE 80
CMD gunicorn core.wsgi -b 0.0.0.0:80 --log-file -