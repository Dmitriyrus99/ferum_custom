FROM frappe/bench:version-15

USER root

# wkhtmltopdf from Ubuntu/Debian repos is built without the required Qt patches.
# Install wkhtmltox (patched Qt build) from upstream packaging releases.
ARG WKHTMLTOX_VERSION=0.12.6.1-3
ARG WKHTMLTOX_DIST=

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fontconfig \
        git \
        xfonts-75dpi \
        xfonts-base; \
    apt-get purge -y wkhtmltopdf || true; \
    dist="${WKHTMLTOX_DIST:-}"; \
    if [ -z "$dist" ]; then \
        . /etc/os-release; \
        case "${ID:-}:${VERSION_CODENAME:-}" in \
            debian:bookworm|debian:bullseye|ubuntu:jammy|ubuntu:focal|ubuntu:bionic) dist="$VERSION_CODENAME" ;; \
            ubuntu:noble) dist="jammy" ;; \
            *) dist="bookworm" ;; \
        esac; \
    fi; \
    arch="$(dpkg --print-architecture)"; \
    [ "$arch" = "amd64" ] || (echo >&2 "Unsupported arch for wkhtmltox: $arch"; exit 1); \
    url="https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOX_VERSION}/wkhtmltox_${WKHTMLTOX_VERSION}.${dist}_${arch}.deb"; \
    curl -fsSL -o /tmp/wkhtmltox.deb "$url"; \
    dpkg -i /tmp/wkhtmltox.deb || apt-get -f install -y --no-install-recommends; \
    rm -f /tmp/wkhtmltox.deb; \
    wkhtmltopdf --version | grep -qi 'patched qt'; \
    rm -rf /var/lib/apt/lists/*

USER frappe

WORKDIR /home/frappe/frappe-bench

# Build arguments for apps.json
ARG APPS_JSON_BASE64

# Install apps from APPS_JSON_BASE64
# This step will clone and install apps defined in apps.json
# The apps.json is passed as a base64 encoded string
RUN if [ -n "$APPS_JSON_BASE64" ]; then \
    echo "$APPS_JSON_BASE64" | base64 -d > apps.json; \
    bench get-apps-from-json apps.json; \
    bench install-apps-from-json apps.json; \
    rm apps.json; \
fi

# Build assets for all installed apps
RUN bench build

# Set default command to keep container running (bench start will be run via docker exec)
CMD ["sleep", "infinity"]
