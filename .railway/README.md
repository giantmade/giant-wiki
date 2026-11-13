# Railway configuration

The Railway `giant-wiki` project is defined in `railway.py`: web, worker (Celery with beat),
tailscale-proxy, MySQL, Redis and their volumes, for both `develop` and `production`.
Everything that differs between the two lives in `ENVIRONMENTS` at the top of the file.
Secrets (`SECRET_KEY`, `TS_AUTHKEY`) are marked `preserve()` and set with
`railway variable set`. The content-repo settings, `SITE_URL` and the Teams webhook are
shared variables set per environment in Railway; the file only references them.

```bash
python -m venv .railway/.venv && .railway/.venv/bin/pip install -r .railway/requirements.txt
export PATH="$PWD/.railway/.venv/bin:$PATH"   # the CLI runs railway.py with this python
railway link                                   # project giant-wiki
railway config plan --environment develop      # review first
railway config apply --environment develop
```

Anything removed from `railway.py` is deleted from the environment on apply, so always
read the plan before applying.
