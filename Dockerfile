FROM python:3.9-slim

ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY poetry.lock pyproject.toml /app/

RUN set -ex \
  && apt-get update && apt-get -y --no-install-recommends install curl \
  && curl -sSL https://install.python-poetry.org | python3 -

ENV PATH=/root/.local/bin:${PATH}

RUN set -ex \
  && poetry config virtualenvs.create false \
  && poetry install --no-dev --no-root --no-interaction --no-ansi

COPY . /app/
EXPOSE 80
CMD gunicorn core.wsgi -b 0.0.0.0:80 --log-file -