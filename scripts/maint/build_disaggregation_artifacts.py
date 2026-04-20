"""
Build disaggregation packet artifacts from repo-local lineage and panel data.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "backend"))

from app.services.disaggregation_artifacts import (
    DEFAULT_ARTIFACT_DIR,
    build_disaggregation_artifacts,
    write_disaggregation_artifacts,
)


def main() -> None:
    artifacts = build_disaggregation_artifacts()
    write_disaggregation_artifacts(artifacts, Path(DEFAULT_ARTIFACT_DIR))
    print(
        "Generated disaggregation artifacts:",
        len(artifacts["packets"]),
        "packets,",
        len(artifacts["weights"]),
        "weights,",
        len(artifacts["qa"]),
        "qa rows",
    )


if __name__ == "__main__":
    main()
