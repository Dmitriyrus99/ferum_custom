Deployment and CI/CD

The deployment architecture for Ferum Customizations is containerized and automated to ensure reliable releases and easy maintenance across development, staging, and production environments. This section describes the environment setup, continuous integration and delivery process, database migrations, and testing strategy.

Environment Setup (Docker Compose): The application is deployed using Docker Compose, which defines all the necessary services:

A Frappe/ERPNext service (Docker container) that runs ERPNext v15 and the custom app. This container includes gunicorn workers for the ERPNext web server and possibly background workers (celery or RQ for scheduled tasks) as part of the bench setup.

A Database service: ERPNext can use MariaDB or PostgreSQL. Given “as they plan (PostgreSQL)”, we assume PostgreSQL is used. So, a Postgres container is defined, with a persistent volume for data.

A Redis service: ERPNext typically uses Redis for caching and queue. Likely one Redis instance for both cache and queue (unless they split into two).

The custom backend service (FastAPI): Possibly this runs within the same container as ERPNext or separately. There's an architectural choice: since the custom app is tightly integrated, they might have implemented the API within the ERPNext python environment (as a set of whitelisted methods or via frappe framework). However, because they mention FastAPI, it's likely a separate container that can interact with ERPNext via REST or direct DB.

If separate, the Docker Compose includes a service for the FastAPI app, based on a Python image, running Uvicorn or Gunicorn with the FastAPI. This container links to the DB and possibly to the ERPNext (if it calls via REST).


NGINX reverse proxy: Usually, the official ERPNext images bundle Nginx inside, but in a container setup, one might have an Nginx container that routes requests to ERPNext or the custom backend as needed. The deployment steps mention bench setup production which generates Nginx configs on host or container. So possibly, they run Nginx on the host or in a container to serve both ERPNext and the FastAPI under different routes (for example, https://domain/api/* goes to FastAPI, everything else to ERPNext).

Possibly other utility services: e.g., a Sentry sidecar if self-hosting Sentry (likely not, probably using Sentry cloud), or a Prometheus Node Exporter container to feed server metrics to Prometheus (if using host, perhaps not containerized).

Certbot or similar for SSL might either be run outside or as a one-time container to fetch certs and then volumes are used by Nginx.


The process to set up:

1. Copy .env and set environment variables (as in DEPLOY.md) for DB passwords, admin credentials, bot token, etc..


2. Run docker compose up -d --build to build images and start all containers. They have a custom Dockerfile for the app likely, which fetches the ERPNext base image and installs ferum_customs app onto it.


3. Once up, create a new ERPNext site if not already (the compose might orchestrate this, or manual step as shown). They run bench new-site and then bench install-app ferum_customs inside the container. In dev/test environment, the site could be pre-baked.


4. The fix-missing-db.sh script indicates sometimes site creation fails and they handle DB user creation separately if needed.


5. Verify application via tests inside container (they included a command to run pytest) and pre-commit checks. This is likely done in CI too, but deployment guide suggests doing it on server too as sanity check.


6. For production config, they run bench setup production frappe which sets up supervisor and Nginx config inside container or host. In Docker context, possibly not needed if using a container for those. But in their steps, it sounds like they might be mixing host and container. However, since they use docker compose, I suspect they either run the bench commands within the container with appropriate flags and then copy out the config to host.



Given they mention GitHub Actions and CI/CD:

Continuous Integration (CI): A GitHub Actions workflow likely triggers on each push or PR. It probably does:

Run tests (execute pytest in a container or environment to verify none fail).

Possibly run linting (they have Ruff, Black, ESLint, etc. configured). The pre-commit config ensures code style, and the Action might enforce those (like run pre-commit run --all-files).

Build the Docker image and possibly run it (maybe using docker-compose in CI to bring up services and run a quick integration test).

If tests and lint pass, coverage is uploaded (they have a Codecov badge), meaning coverage reports are generated and sent to Codecov for tracking test coverage.

Optionally, if on main branch and tests pass, the CI might push the Docker image to a registry (like GitHub Container Registry or Docker Hub) with a new tag (maybe the commit hash or a version).


Continuous Deployment (CD):

They might not have fully automated deployment to production (since it’s an internal system, they could deploy manually). But could use actions to deploy to a server (maybe via SSH or using a Kubernetes if they had one, but likely they use the single VM with compose).

Possibly a CD pipeline triggers on pushing a Git tag (for a new release) and it logs into the server and pulls the updated image and restarts containers. This could be implemented with something like a GitHub Action SSH into host to perform git pull && docker compose up -d.

Or they might use a simpler approach: manual deployment by pulling changes on server. Since the code is in a Git repo, one could update container by re-building from new commit. The presence of CHANGELOG.md suggests they cut releases and inform team of changes.

There's mention: "CI process should publish or package documentation if available (like developer docs) and maintain a CHANGELOG for releases". So maybe CI also generates docs (maybe from docstrings or something, or just ensure technical spec up to date).


Database Migration Patterns:

Whenever the custom app updates (new DocType, changed field), ERPNext's migration system (bench migrate) needs to be run. The deployment likely calls bench migrate after pulling new code. In container context, if they build a new image, they might run migrations in an init step. If using bench update inside container, that auto migrates.

Since the app evolves, they must create patches for any on-the-fly data migrations. E.g., if they rename a DocType or change a field type, they write a patch script in ferum_customs/patches.txt and corresponding .py, and bench migrate will run it. They emphasize "idempotent patches" in the business doc (common practice), meaning patches should check if already applied to avoid errors on re-run.

The repo indeed has patches.txt and likely patch files. Each patch ensures it can run multiple times without harm. That way, if someone runs migrate again, it doesn't break data consistency.


Testing Strategy:

Unit tests: They have Pytest configured. Tests probably cover critical business logic functions (like the validate hooks, or API endpoints returning correct responses). They could have tests for each DocType’s constraints, and maybe simulate a full workflow scenario.

Possibly integration tests using API calls to ensure endpoints enforce rules (like trying to close a request without report yields error).

They run these tests in CI (the deployment doc shows a step to run tests in container as verification).

Also, they might do manual acceptance testing in a staging environment, especially for UI flows (since Playwright is listed for UI testing). They could have Playwright automated tests to simulate a user clicking through forms. If those exist, CI might run them in headless mode.

Test coverage is tracked via Codecov badge, meaning they aim for good coverage of the custom code.


Staging Environment: They likely have at least a staging site for final testing before production. Possibly on a different server or on the same server with a different site name (ERPNext bench supports multiple sites). They might spin up another Docker Compose instance for staging. Data could be anonymized or a subset of production for testing new releases with the team.

Release Process:

The team might use Git flow or similar, merging features into main, then tagging a release (like v1.0.0). The CHANGELOG is updated with changes for that release. CI would then build images and they deploy to staging. After user acceptance, they deploy to production by pulling the new image/compose.

Because it’s an internal small team, some steps might be semi-manual with checklists rather than fully automated, but the groundwork for automation is present.


Container Orchestration:

Right now, Docker Compose is sufficient. If scaling or high availability was needed, they might consider Kubernetes or Docker Swarm. But given the scope, one instance can handle all, and downtime for updates (a minute or two to reboot containers) is acceptable, as presumably they schedule maintenance windows if needed (preferably after hours).


Backup and Recovery in Deployment:

As part of CI/CD, they ensure backups are taken before deploying major changes. Possibly a step in the deployment playbook: "Take backup, then update containers".

Migrations are run immediately after code update; if a migration fails, they have backup to rollback. A rollback might mean restoring DB and using previous image if needed.


Dev Environment Parity:

Developers can run the same Docker Compose on their machines (maybe a slightly different config). They might use bench start in dev (frappe’s dev mode) as well. But using Docker ensures consistency (e.g., using same DB version, etc.).

They likely use a separate site_config.json for dev (with developer mode on for migrations, etc.). CI might also spin up environment similarly to ensure no "it works on my machine" issues.


Continuous Monitoring in Deployment:

They use Prometheus as said, which could be part of the cluster. If using Docker, maybe a separate docker-compose file for monitoring stack (Prometheus, Grafana).

They also have Sentry, which is not a part of deployment but a service they send data to.



GitHub Actions specifics:

Possibly a workflow YAML exists (the badge implies at least one named CI). It might do docker build or bench ci pipeline.

After CI passes, maybe an Action uses ssh to run docker compose pull && docker compose up -d on the production server. Or they might refrain from that due to security and do manual deploy.


DevOps Culture:

They maintain a single source of truth in Git for both code and configuration (the .env is the only part not in Git for security).

Code changes go through code review (maybe via PRs, using code owners etc.). The repository possibly has a CONTRIBUTING.md mentioned, meaning they welcome contributions (if open or internal collab).

Each commit or PR is tested by CI to catch issues early.

They maintain a CHANGELOG so stakeholders know what changed in each version.

They also might keep documentation in the repo (the technical spec might eventually be distilled into an official doc for future devs, possibly in markdown like the one we produce).

For CI secrets (like Codecov token, etc.), they use GitHub Actions secret storage. For deployment keys, they'd use an SSH key or secure runner.


Migrating Data/Legacy: If they had legacy data (like from spreadsheets or older DB), initial migration scripts might be used one-time to import those into ERPNext. This isn't covered, so presumably initial data entry was manual or minimal.

Testing and QA: They emphasize test coverage and thorough testing of all logic (as the business doc says, covering CRUD, scripts, roles, etc.). That means:

Unit tests for all custom server scripts (like test that you cannot close a request without report, etc. perhaps by simulating that scenario) – possibly implemented in test_service_request.py etc..

Role permission tests: e.g., ensure a Client user cannot access another client’s data (could be tested via API calls or by invoking permission logic directly).

Migration tests: if a patch is added, test that applying it twice has no adverse effect, etc.


By having these processes, they aim for zero-downtime or minimal-downtime deployments and the ability to iterate quickly without breaking existing functionality. The development team can be confident that if CI passes, the build is good to deploy, and if something does go wrong, backups and logs are there to recover and diagnose quickly.