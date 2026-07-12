# Thin wrapper around the maintained self-registering runner image.
# Adds the `gh` CLI (used directly by gymboost-PWA-betaa's claude-assistant.yml).
# Node itself is NOT installed here on purpose — every workflow uses
# actions/setup-node@v5, which fetches its own pinned Node version at job
# time regardless of what the host runner has.
FROM myoung34/github-runner:latest

RUN (type -p wget curl) \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*
