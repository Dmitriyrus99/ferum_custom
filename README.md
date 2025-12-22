### Ferum

Custom

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench install-app ferum_custom
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/ferum_custom
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Runs tests on every push to `main`/`develop` and on pull requests (includes `pip-audit`).
- Linters: Runs `pre-commit` and [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) on pushes and pull requests.
- Deploy: Runs on push to `main` only when secrets are set (`SSH_HOST`, `SSH_USERNAME`, `SSH_KEY`, `DEPLOY_PATH`).


### License

mit
