from railway_sdk import define_railway, github, mysql, preserve, project, redis, service, volume

# `railway config plan|apply` targets the linked environment, or `--environment <name>`.
# Everything that differs between environments lives in ENVIRONMENTS; the rest is shared.
# The wiki has no public domain: people reach it over the Giant tailnet through
# tailscale-proxy, at http://<ts_hostname>/.
REGION = "europe-west4-drams3a"

ENVIRONMENTS = {
    "develop": {
        "branch": "develop",
        "ts_hostname": "giant-wiki-develop",
        # Develop's web sleeps when idle; every app service runs capped.
        "web_deploy": {
            "sleepApplication": True,
            "limitOverride": {"containers": {"cpu": 1, "memoryBytes": 2_000_000_000}},
        },
        "deploy": {"limitOverride": {"containers": {"cpu": 1, "memoryBytes": 2_000_000_000}}},
    },
    "production": {
        "branch": "main",
        "ts_hostname": "giant-wiki",
        # Production never sleeps and has no cap today (Railway's defaults, so not spelled out).
        "web_deploy": {},
        "deploy": {},
    },
}

# Set per environment as shared variables, not here: WIKI_REPO_BRANCH (production
# `wiki-reorganise`, develop `develop` in giantmade/giant-wiki-data), SITE_URL, and
# TEAMS_NOTIFICATION_WEBHOOK (production only; develop has none so it never posts to Teams).
SHARED = ["GIT_SSH_KEY", "SITE_URL", "TEAMS_NOTIFICATION_WEBHOOK", "WIKI_REPO_BRANCH", "WIKI_REPO_PATH", "WIKI_REPO_URL"]


@define_railway
def main(ctx=None):
    name = getattr(ctx, "environment", None) or "develop"
    env = ENVIRONMENTS.get(name)
    if env is None:
        raise ValueError(f'No configuration for environment "{name}" in railway.py')

    # railway_sdk's redis()/mysql() only take a region, so the start command and the
    # public TCP proxy are set on the node with with_fields(). deploy is replaced whole,
    # so the region's replica count is repeated here.
    cache = redis("Redis", region=REGION).with_fields(
        deploy={
            "multiRegionConfig": {REGION: {"numReplicas": 1}},
            "startCommand": '/bin/sh -c "rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH"',
        },
    )
    database = mysql("MySQL", region=REGION).with_fields(
        deploy={
            "multiRegionConfig": {REGION: {"numReplicas": 1}},
            "requiredMountPath": "/var/lib/mysql",
            "startCommand": "docker-entrypoint.sh mysqld --innodb-use-native-aio=0 --disable-log-bin --performance_schema=0 --innodb-buffer-pool-size=1G",
        },
        networking={"tcpProxies": {"3306": {}}},
    )
    volume_config = {
        "alerts": {"usage": {"100": {}, "80": {}, "95": {}}},
        "allowOnlineResize": True,
        "region": REGION,
        "sizeMB": 50000,
    }
    redis_volume = volume("redis-volume", volume_config)
    mysql_volume = volume("mysql-volume", volume_config)
    tailscale_volume = volume("tailscale-proxy-volume", volume_config)

    source = github("giantmade/giant-wiki", branch=env["branch"], checkSuites=False)
    # Railpack also reads railpack.json (apt packages for mysqlclient and git).
    build = {"builder": "RAILPACK"}
    app_env = {
        "DEBUG": "False",
        "SITE_TITLE": "Giant Wiki",
        "GIT_AUTHOR_NAME": "Giant Wiki",
        "GIT_AUTHOR_EMAIL": "wiki@giantmade.com",
        "DATABASE_URL": database.env.MYSQL_URL,
        "REDIS_URL": cache.env.REDIS_URL,
        "CELERY_BROKER_URL": cache.env.REDIS_URL,
        "CELERY_RESULT_BACKEND": cache.env.REDIS_URL,
        **{key: f"${{{{shared.{key}}}}}" for key in SHARED},
        # Secrets: set with `railway variable set`, never written here. preserve() keeps a
        # value that exists and is a no-op where it does not.
        "SECRET_KEY": preserve(),
    }

    web = service(
        "web",
        source=source,
        build=build,
        # Clones or pulls the content repo, then runs gunicorn.
        start="scripts/railway-start.sh",
        preDeploy="cd src && python manage.py migrate --noinput && python manage.py collectstatic --noinput",
        healthcheck="/health/",
        healthcheckTimeout=300,
        replicas={REGION: 1},
        deploy={"restartPolicyType": "ON_FAILURE", **env["web_deploy"]},
        # Only reached through tailscale-proxy and Railway's private network.
        env={**app_env, "ALLOWED_HOSTS": "*"},
    )
    worker = service(
        "worker",
        source=source,
        build=build,
        # Celery worker with beat embedded (-B).
        start="scripts/railway-worker.sh",
        replicas={REGION: 1},
        deploy={"restartPolicyType": "ON_FAILURE", **env["deploy"]},
        env={**app_env, "ALLOWED_HOSTS": "*.railway.internal,localhost"},
    )
    tailscale_proxy = service(
        "tailscale-proxy",
        source=github("giantmade/tailscale-proxy", branch="main", checkSuites=False),
        build=build,
        replicas={REGION: 1},
        deploy=env["deploy"],
        volumeMounts={"/var/lib/tailscale": tailscale_volume},
        env={
            "PROXY_TARGET": "${{web.RAILWAY_PRIVATE_DOMAIN}}:8080",
            "TS_HOSTNAME": env["ts_hostname"],
            "TS_AUTHKEY": preserve(),
        },
    )

    return project(
        "giant-wiki",
        variables={"managed": True},
        resources=[redis_volume, mysql_volume, tailscale_volume, cache, database, web, worker, tailscale_proxy],
    )
