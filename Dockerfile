FROM frappe/bench:version-15

USER root

# Install git and other necessary tools
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

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