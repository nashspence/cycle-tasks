FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl tini \
  && rm -rf /var/lib/apt/lists/*

ARG TEMPORAL_CLI_VERSION=1.5.0
RUN arch="$(dpkg --print-architecture)" && \
    case "$arch" in amd64) a="amd64" ;; arm64) a="arm64" ;; *) echo "unsupported arch" >&2; exit 1 ;; esac && \
    curl -fsSL -o /tmp/temporal.tgz \
      "https://temporal.download/cli/archive/v${TEMPORAL_CLI_VERSION}?platform=linux&arch=${a}" && \
    tar -C /usr/local/bin -xzf /tmp/temporal.tgz temporal && rm /tmp/temporal.tgz

ARG PGRST_VERSION=12.2.3
RUN arch="$(dpkg --print-architecture)" && \
    case "$arch" in amd64) a="x86_64-linux" ;; arm64) a="aarch64-linux" ;; *) echo "unsupported arch" >&2; exit 1 ;; esac && \
    curl -fsSL -o /tmp/pgrst.tar.xz \
      "https://github.com/PostgREST/postgrest/releases/download/v${PGRST_VERSION}/postgrest-v${PGRST_VERSION}-${a}.tar.xz" && \
    tar -C /usr/local/bin -xJf /tmp/pgrst.tar.xz postgrest && rm /tmp/pgrst.tar.xz

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py reminder_worker.py entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/app/entrypoint.sh"]
