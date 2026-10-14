"""Modular release-gate checks."""

from release_gate.checks.approvals import check_approvals
from release_gate.checks.branch import check_branch_naming
from release_gate.checks.catalog_consistency import check_catalog_consistency
from release_gate.checks.required_fields import check_required_fields
from release_gate.checks.sast_deps import check_sast_dependencies
from release_gate.checks.service_kae import check_service_kae_binding
from release_gate.checks.sonar_exclusions import check_sonar_exclusions
from release_gate.checks.version_bump import check_version_bump

CHECK_RUNNERS = {
    "branch_naming": check_branch_naming,
    "required_fields": check_required_fields,
    "service_kae_binding": check_service_kae_binding,
    "catalog_consistency": check_catalog_consistency,
    "sonar_exclusions": check_sonar_exclusions,
    "sast_dependencies": check_sast_dependencies,
    "version_bump": check_version_bump,
    "approvals": check_approvals,
}

__all__ = ["CHECK_RUNNERS"]
