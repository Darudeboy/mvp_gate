# Shadow pilot checklist

## Goal

Connect `release-gate` to **one** CI pipeline, collect false positives, then enable agreed blockers.

## Steps

1. Publish Docker image `release-gate:0.1.0` (or install the package in the pipeline image).
2. Copy `ci/bitbucket-pipelines.example.yml` step into the pilot repository.
3. Configure secrets: `JIRA_*`, `BITBUCKET_*`, optionally `SONAR_*`, `DPM_*`, `SAST_*`.
4. Point `RELEASE_GATE_CATALOG` at the shared catalog (or vendor a copy in the repo).
5. Run for 1–2 sprints with `--mode shadow`:
   - CI always green (`exit 0`)
   - PR gets one updated `<!-- release-gate:report -->` comment
   - `artifacts/latest.html` attached to the release Jira issue
6. Triage weekly:
   - Count `BLOCK` / `WARN` / `UNKNOWN` by `check_id`
   - Fix catalog mismatches explicitly (no silent renames)
   - Shrink Sonar exclusion red-zone files
7. Enable enforce gradually:
   - First: `service_kae_binding`, `required_fields`
   - Then: `branch_naming`
   - Keep Sonar/SAST as WARN/OBSERVE until abuse metrics drop
8. Manual override path: commit `overrides.json` referenced by `--overrides` with `check_id`, `reason`, `approver`.

## Success criteria

- Release id shows services, KAEs, PRs, versions, check results
- Re-runs update the same PR comment (no duplicates)
- Catalog mismatches are explicit
- Every WARN/BLOCK/override has evidence
- API outages surface as `UNKNOWN`, never as `PASS`
