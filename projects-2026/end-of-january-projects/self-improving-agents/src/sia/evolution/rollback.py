"""
Rollback Manager.

Manages code versions and provides rollback capabilities.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


@dataclass
class CodeSnapshot:
    """A snapshot of code at a point in time."""

    id: UUID = field(default_factory=uuid4)
    code: str = ""
    code_hash: str = ""
    version: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    # Metadata
    description: str = ""
    source: str = ""  # 'baseline', 'mutation', 'crossover', 'manual'
    parent_id: UUID | None = None

    # Status
    is_baseline: bool = False
    is_current: bool = False
    is_deprecated: bool = False

    # Performance metrics at snapshot time
    metrics: dict[str, Any] = field(default_factory=dict)

    # Evolution metadata
    mutation_ids: list[UUID] = field(default_factory=list)
    strategy_used: str = ""

    def __post_init__(self):
        """Calculate code hash if not provided."""
        if not self.code_hash and self.code:
            self.code_hash = hashlib.sha256(self.code.encode()).hexdigest()[:16]


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    previous_version: str
    rolled_back_to: str
    snapshot_id: UUID
    message: str
    changes_lost: int = 0  # Number of versions rolled back over


class RollbackManager:
    """
    Manages code versions and rollback operations.

    Features:
    - Version snapshots with metadata
    - Quick rollback to previous version
    - Rollback to specific version
    - Rollback to baseline
    - Version comparison
    - Cleanup old versions
    """

    def __init__(
        self,
        max_snapshots: int = 50,
        storage_path: Path | None = None,
        agent_id: str | None = None,
    ):
        """
        Initialize rollback manager.

        Args:
            max_snapshots: Maximum snapshots to keep
            storage_path: Path to persist snapshots (optional)
            agent_id: Agent identifier for namespacing
        """
        self.max_snapshots = max_snapshots
        self.storage_path = storage_path
        self.agent_id = agent_id or "default"

        self.snapshots: list[CodeSnapshot] = []
        self.current_index: int = -1
        self._version_counter: int = 0

        # Load existing snapshots if storage path provided
        if storage_path:
            self._load_snapshots()

    def create_snapshot(
        self,
        code: str,
        description: str = "",
        source: str = "manual",
        metrics: dict[str, Any] | None = None,
        is_baseline: bool = False,
        strategy_used: str = "",
        mutation_ids: list[UUID] | None = None,
    ) -> CodeSnapshot:
        """
        Create a new code snapshot.

        Args:
            code: Code to snapshot
            description: Description of this version
            source: How this version was created
            metrics: Performance metrics at this point
            is_baseline: Mark as baseline version
            strategy_used: Evolution strategy used
            mutation_ids: Mutations applied

        Returns:
            Created snapshot
        """
        # Increment version
        self._version_counter += 1
        version = f"v{self._version_counter}"

        # Get parent
        parent_id = None
        if self.snapshots and self.current_index >= 0:
            parent_id = self.snapshots[self.current_index].id

        # Create snapshot
        snapshot = CodeSnapshot(
            code=code,
            version=version,
            description=description,
            source=source,
            parent_id=parent_id,
            is_baseline=is_baseline,
            metrics=metrics or {},
            strategy_used=strategy_used,
            mutation_ids=mutation_ids or [],
        )

        # Mark previous as not current
        if self.snapshots and self.current_index >= 0:
            self.snapshots[self.current_index].is_current = False

        # Add to history
        # If we're not at the end, truncate forward history
        if self.current_index < len(self.snapshots) - 1:
            self.snapshots = self.snapshots[:self.current_index + 1]

        self.snapshots.append(snapshot)
        self.current_index = len(self.snapshots) - 1
        snapshot.is_current = True

        # Cleanup old snapshots if needed
        self._cleanup_old_snapshots()

        # Persist if storage configured
        if self.storage_path:
            self._save_snapshots()

        return snapshot

    def set_baseline(self, code: str, description: str = "Initial baseline") -> CodeSnapshot:
        """
        Set the baseline version.

        This is the original, human-written code that serves as
        the fallback for safety rollbacks.
        """
        # Clear baseline flag from other snapshots
        for s in self.snapshots:
            s.is_baseline = False

        return self.create_snapshot(
            code=code,
            description=description,
            source="baseline",
            is_baseline=True,
        )

    def rollback(self, steps: int = 1) -> RollbackResult:
        """
        Rollback by a number of steps.

        Args:
            steps: Number of versions to go back

        Returns:
            RollbackResult
        """
        if not self.snapshots:
            return RollbackResult(
                success=False,
                previous_version="",
                rolled_back_to="",
                snapshot_id=uuid4(),
                message="No snapshots available",
            )

        target_index = max(0, self.current_index - steps)

        if target_index == self.current_index:
            return RollbackResult(
                success=False,
                previous_version=self.current.version if self.current else "",
                rolled_back_to=self.current.version if self.current else "",
                snapshot_id=self.current.id if self.current else uuid4(),
                message="Already at earliest version",
            )

        return self._rollback_to_index(target_index)

    def rollback_to_version(self, version: str) -> RollbackResult:
        """
        Rollback to a specific version.

        Args:
            version: Version string (e.g., 'v5')

        Returns:
            RollbackResult
        """
        for i, snapshot in enumerate(self.snapshots):
            if snapshot.version == version:
                return self._rollback_to_index(i)

        return RollbackResult(
            success=False,
            previous_version=self.current.version if self.current else "",
            rolled_back_to="",
            snapshot_id=uuid4(),
            message=f"Version '{version}' not found",
        )

    def rollback_to_baseline(self) -> RollbackResult:
        """Rollback to the baseline version."""
        for i, snapshot in enumerate(self.snapshots):
            if snapshot.is_baseline:
                return self._rollback_to_index(i)

        return RollbackResult(
            success=False,
            previous_version=self.current.version if self.current else "",
            rolled_back_to="",
            snapshot_id=uuid4(),
            message="No baseline version found",
        )

    def rollback_to_snapshot(self, snapshot_id: UUID) -> RollbackResult:
        """
        Rollback to a specific snapshot by ID.

        Args:
            snapshot_id: Snapshot UUID

        Returns:
            RollbackResult
        """
        for i, snapshot in enumerate(self.snapshots):
            if snapshot.id == snapshot_id:
                return self._rollback_to_index(i)

        return RollbackResult(
            success=False,
            previous_version=self.current.version if self.current else "",
            rolled_back_to="",
            snapshot_id=uuid4(),
            message=f"Snapshot {snapshot_id} not found",
        )

    def _rollback_to_index(self, target_index: int) -> RollbackResult:
        """Internal rollback to a specific index."""
        previous_version = self.current.version if self.current else ""
        changes_lost = self.current_index - target_index

        # Update current flags
        if self.current:
            self.current.is_current = False

        target = self.snapshots[target_index]
        target.is_current = True
        self.current_index = target_index

        # Persist
        if self.storage_path:
            self._save_snapshots()

        return RollbackResult(
            success=True,
            previous_version=previous_version,
            rolled_back_to=target.version,
            snapshot_id=target.id,
            message=f"Rolled back from {previous_version} to {target.version}",
            changes_lost=changes_lost,
        )

    def redo(self, steps: int = 1) -> RollbackResult:
        """
        Redo (move forward in history) by a number of steps.

        Only works if we haven't created new snapshots after rollback.

        Args:
            steps: Number of versions to go forward

        Returns:
            RollbackResult
        """
        if not self.snapshots:
            return RollbackResult(
                success=False,
                previous_version="",
                rolled_back_to="",
                snapshot_id=uuid4(),
                message="No snapshots available",
            )

        target_index = min(len(self.snapshots) - 1, self.current_index + steps)

        if target_index == self.current_index:
            return RollbackResult(
                success=False,
                previous_version=self.current.version if self.current else "",
                rolled_back_to=self.current.version if self.current else "",
                snapshot_id=self.current.id if self.current else uuid4(),
                message="Already at latest version",
            )

        return self._rollback_to_index(target_index)

    @property
    def current(self) -> CodeSnapshot | None:
        """Get current snapshot."""
        if self.snapshots and 0 <= self.current_index < len(self.snapshots):
            return self.snapshots[self.current_index]
        return None

    @property
    def baseline(self) -> CodeSnapshot | None:
        """Get baseline snapshot."""
        for snapshot in self.snapshots:
            if snapshot.is_baseline:
                return snapshot
        return None

    def get_snapshot(self, snapshot_id: UUID) -> CodeSnapshot | None:
        """Get a snapshot by ID."""
        for snapshot in self.snapshots:
            if snapshot.id == snapshot_id:
                return snapshot
        return None

    def get_version(self, version: str) -> CodeSnapshot | None:
        """Get a snapshot by version string."""
        for snapshot in self.snapshots:
            if snapshot.version == version:
                return snapshot
        return None

    def list_versions(self) -> list[dict[str, Any]]:
        """List all versions with summary info."""
        return [
            {
                "id": str(s.id),
                "version": s.version,
                "description": s.description,
                "source": s.source,
                "created_at": s.created_at.isoformat(),
                "is_baseline": s.is_baseline,
                "is_current": s.is_current,
                "code_hash": s.code_hash,
            }
            for s in self.snapshots
        ]

    def compare_versions(
        self,
        version1: str,
        version2: str,
    ) -> dict[str, Any]:
        """
        Compare two versions.

        Args:
            version1: First version
            version2: Second version

        Returns:
            Comparison details
        """
        snap1 = self.get_version(version1)
        snap2 = self.get_version(version2)

        if not snap1 or not snap2:
            return {"error": "Version not found"}

        # Simple line-by-line diff
        lines1 = snap1.code.split("\n")
        lines2 = snap2.code.split("\n")

        added = 0
        removed = 0
        changed = 0

        # Very simple comparison
        max_lines = max(len(lines1), len(lines2))
        for i in range(max_lines):
            line1 = lines1[i] if i < len(lines1) else None
            line2 = lines2[i] if i < len(lines2) else None

            if line1 is None:
                added += 1
            elif line2 is None:
                removed += 1
            elif line1 != line2:
                changed += 1

        return {
            "version1": version1,
            "version2": version2,
            "lines_added": added,
            "lines_removed": removed,
            "lines_changed": changed,
            "total_change": added + removed + changed,
            "metrics_change": self._compare_metrics(
                snap1.metrics, snap2.metrics
            ),
        }

    def _compare_metrics(
        self,
        metrics1: dict[str, Any],
        metrics2: dict[str, Any],
    ) -> dict[str, Any]:
        """Compare metrics between two versions."""
        changes = {}
        all_keys = set(metrics1.keys()) | set(metrics2.keys())

        for key in all_keys:
            v1 = metrics1.get(key)
            v2 = metrics2.get(key)

            if v1 is None:
                changes[key] = {"change": "added", "new_value": v2}
            elif v2 is None:
                changes[key] = {"change": "removed", "old_value": v1}
            elif isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                diff = v2 - v1
                pct = (diff / v1 * 100) if v1 != 0 else 0
                changes[key] = {
                    "change": "modified",
                    "old_value": v1,
                    "new_value": v2,
                    "diff": diff,
                    "diff_pct": round(pct, 2),
                }
            elif v1 != v2:
                changes[key] = {
                    "change": "modified",
                    "old_value": v1,
                    "new_value": v2,
                }

        return changes

    def _cleanup_old_snapshots(self) -> None:
        """Remove old snapshots to stay within limit."""
        while len(self.snapshots) > self.max_snapshots:
            # Never remove baseline or current
            for i, snapshot in enumerate(self.snapshots):
                if not snapshot.is_baseline and not snapshot.is_current:
                    self.snapshots.pop(i)
                    # Adjust current_index if needed
                    if i <= self.current_index:
                        self.current_index -= 1
                    break
            else:
                # All snapshots are protected, can't remove any
                break

    def _save_snapshots(self) -> None:
        """Persist snapshots to storage."""
        if not self.storage_path:
            return

        storage_dir = Path(self.storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)

        file_path = storage_dir / f"{self.agent_id}_snapshots.json"

        data = {
            "agent_id": self.agent_id,
            "version_counter": self._version_counter,
            "current_index": self.current_index,
            "snapshots": [
                {
                    "id": str(s.id),
                    "code": s.code,
                    "code_hash": s.code_hash,
                    "version": s.version,
                    "created_at": s.created_at.isoformat(),
                    "description": s.description,
                    "source": s.source,
                    "parent_id": str(s.parent_id) if s.parent_id else None,
                    "is_baseline": s.is_baseline,
                    "is_current": s.is_current,
                    "is_deprecated": s.is_deprecated,
                    "metrics": s.metrics,
                    "mutation_ids": [str(m) for m in s.mutation_ids],
                    "strategy_used": s.strategy_used,
                }
                for s in self.snapshots
            ],
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_snapshots(self) -> None:
        """Load snapshots from storage."""
        if not self.storage_path:
            return

        file_path = Path(self.storage_path) / f"{self.agent_id}_snapshots.json"

        if not file_path.exists():
            return

        with open(file_path) as f:
            data = json.load(f)

        self._version_counter = data.get("version_counter", 0)
        self.current_index = data.get("current_index", -1)

        self.snapshots = []
        for s in data.get("snapshots", []):
            snapshot = CodeSnapshot(
                id=UUID(s["id"]),
                code=s["code"],
                code_hash=s["code_hash"],
                version=s["version"],
                created_at=datetime.fromisoformat(s["created_at"]),
                description=s["description"],
                source=s["source"],
                parent_id=UUID(s["parent_id"]) if s["parent_id"] else None,
                is_baseline=s["is_baseline"],
                is_current=s["is_current"],
                is_deprecated=s.get("is_deprecated", False),
                metrics=s.get("metrics", {}),
                mutation_ids=[UUID(m) for m in s.get("mutation_ids", [])],
                strategy_used=s.get("strategy_used", ""),
            )
            self.snapshots.append(snapshot)

    def clear(self) -> None:
        """Clear all snapshots (use with caution)."""
        self.snapshots = []
        self.current_index = -1
        self._version_counter = 0

        if self.storage_path:
            file_path = Path(self.storage_path) / f"{self.agent_id}_snapshots.json"
            if file_path.exists():
                file_path.unlink()
