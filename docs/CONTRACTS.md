# Release Gate — contracts and rule matrix

## Sources

| Source | Role | Notes |
|--------|------|-------|
| Jira DC | Release issue id = branch name; required fields; release composition | Contour label + business requirements are mandatory |
| Bitbucket DC | PR, diff, reviewers, build status, comments | Release branches are not protected (except master/dev) |
| Confluence DC | Clusters / owners / PIO / impact table | Imported into catalog; not read on every pipeline run |
| Project Config | repository → service / KAE mapping | Cross-checked against catalog; mismatches must be explicit |
| DPM | Auto-fill missing KAEs; block distribution registration if missing | Gate mirrors this: missing KAE → BLOCK |
| SonarQube | Exclusion list for traffic-light | Red = exclusion bypass; Yellow = legal (tests/mocks) |
| SAST / deps | Findings attached to PR/release | Observe in shadow; WARN in enforce for MVP |

## Catalog schema

Versioned JSON/YAML at `catalog/catalog.yaml` (see `schemas/catalog.schema.json`).

Canonical path: `repository → service → KAE → owners (PIO + Delivery)`.

Silent auto-correction of KAE names is **forbidden**. Mismatches surface as `catalog_consistency` WARN/BLOCK evidence.

## Gate input

```json
{
  "release_id": "REL-1234",
  "repository": "PROJ/myservice",
  "commit": "abc123",
  "pr_id": 42,
  "phase": "pr|release",
  "mode": "shadow|enforce"
}
```

## Check result

Statuses: `PASS` | `WARN` | `BLOCK` | `UNKNOWN`

Every result carries evidence (`label`, `value`, `url`) and a policy (`block` | `warn` | `observe`).

`UNKNOWN` is reserved for API/timeouts/missing data — never treated as PASS.

## Rule matrix

| check_id | Enforce | Shadow | Phase |
|----------|---------|--------|-------|
| branch_naming | BLOCK | WARN | pr, release |
| required_fields | BLOCK | WARN | pr, release |
| service_kae_binding | BLOCK | BLOCK* | pr, release |
| catalog_consistency | WARN | WARN | pr, release |
| sonar_exclusions | WARN | OBSERVE | pr |
| sast_dependencies | WARN | OBSERVE | pr, release |
| version_bump | WARN | OBSERVE | release |
| approvals | WARN | OBSERVE | pr, release |

\* In shadow mode the overall exit code stays `0`, but `service_kae_binding` still reports BLOCK in the artifact so pilots see real severity.

## Overrides

Manual override requires `check_id`, `reason`, `approver`. Stored immutably in the report; never deletes the original check evidence.

## Reporting

- One idempotent Bitbucket PR comment (marker: `<!-- release-gate:report -->`)
- Bitbucket build status key: `release-gate`
- JSON + HTML artifact attached to the Jira release issue
