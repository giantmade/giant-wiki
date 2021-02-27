web: gunicorn core.wsgi -b 0.0.0.0:80 --log-file -
release: python /app/manage.py migrate && python /app/manage.py search_index --rebuild -f
