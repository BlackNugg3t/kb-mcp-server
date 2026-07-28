# Thin wrapper around the maintained self-registering runner image.
# Adds the `gh` CLI (used directly by gymboost-PWA-betaa's claude-assistant.yml),
# the `docker` client (client only — the host's socket is mounted in via
# docker-compose.runner.yml, no nested daemon here — needed by db-smoke.yml's
# `supabase db start` and by watch-queue.sh's burst-runner `docker run`), and
# the `psql` client (postgresql-client — ubuntu-latest ships this by default,
# our base image doesn't; needed by db-smoke.yml's direct psql steps against
# the supabase-started Postgres).
# Node itself is NOT installed here on purpose — every workflow uses
# actions/setup-node, which fetches its own pinned Node version at job
# time regardless of what the host runner has.
FROM myoung34/github-runner:latest

RUN (type -p wget curl) \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh docker.io jq postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY watch-queue.sh /watch-queue.sh
RUN chmod +x /watch-queue.sh
