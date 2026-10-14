# release-gate

MVP unified release control CLI for Atlassian Data Center.

Runs modular checks (branch/KAE/Sonar/SAST/approvals), writes JSON+HTML artifacts, and publishes an **idempotent** Bitbucket PR comment + build status.

## Quick start

```bash
cd release-gate
pip install -e ".[dev]"

release-gate run \
  --release-id REL-100 \
  --repository PAY/payments-api \
  --commit abc123def456 \
  --phase pr \
  --mode shadow \
  --no-publish \
  --changed-file src/main/java/App.java \
  --extra project_config=@examples/project_config.example.json \
  --extra sast_findings=@examples/sast_findings.example.json
```

Artifacts land in `artifacts/` (`latest.json`, `latest.html`, `latest.md`).

## Modes

| Mode | CI exit | Purpose |
|------|---------|---------|
| `shadow` | always `0` | Pilot / observe; report still shows real severities |
| `enforce` | `2` on unresolved `BLOCK` | After shadow false-positive review |

## Environment

| Variable | Purpose |
|----------|---------|
| `RELEASE_GATE_MODE` | `shadow` / `enforce` |
| `RELEASE_GATE_CATALOG` | Path to catalog YAML |
| `RELEASE_GATE_OUTPUT` | Artifact directory |
| `RELEASE_GATE_DRY_RUN` | Skip mutating API calls |
| `JIRA_*` / `BITBUCKET_*` / `CONFLUENCE_*` / `SONAR_*` / `DPM_*` / `SAST_*` | `BASE_URL`, `TOKEN` or `USERNAME`/`PASSWORD`, `TIMEOUT`, `RETRIES` |

## Catalog

Versioned source of truth: `catalog/catalog.yaml` (`repository → service → KAE → owners`).

Import a Confluence owners table fragment:

```bash
release-gate import-confluence --page-id 123456 --out catalog/from-confluence.yaml
```

Silent auto-fix of KAE names is intentionally **not** supported.

## Docker

```bash
docker build -t release-gate:0.1.0 .
docker run --rm -v ${PWD}/artifacts:/artifacts release-gate:0.1.0 run \
  --release-id REL-100 \
  --repository PAY/payments-api \
  --commit abc123 \
  --mode shadow \
  --no-publish
```

## CI pilot

See `ci/bitbucket-pipelines.example.yml` and `ci/Jenkinsfile.example`. Start in shadow on one repository, then flip `RELEASE_GATE_MODE=enforce` for agreed BLOCK rules (`service_kae_binding`, `required_fields`, `branch_naming`).

Contracts and rule matrix: [`docs/CONTRACTS.md`](docs/CONTRACTS.md). Pilot checklist: [`docs/PILOT.md`](docs/PILOT.md).

## Tests

```bash
pytest -q
```
