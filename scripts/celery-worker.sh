#!/bin/bash
set -e

cd /app/src

exec celery -A core worker \
    --loglevel=INFO \
    --concurrency=2
