from __future__ import annotations

from pathlib import Path
import shutil


def preserve_crystallography(manifest: dict, source_root: Path, target_root: Path) -> None:
    """Copy each CIF bundle as a unit so JSON-relative figure paths stay valid."""
    for index, entry in enumerate(manifest.get("compounds", {}).values(), 1):
        artifacts = entry.setdefault("artifacts", {})
        relative = entry.setdefault("relative_artifacts", {})
        raw = artifacts.get("crystallography_data")
        if not raw:
            continue
        candidates = [source_root / relative["crystallography_data"]] if relative.get("crystallography_data") else []
        candidates.append(Path(raw))
        data = next((p for p in candidates if p.is_file()), None)
        if data is None:
            raise FileNotFoundError(f"Crystallography data for {entry.get('number')}: {raw}")
        destination = target_root / "reports" / "crystallography" / f"preserved_{index}"
        if data.parent.resolve() != destination.resolve():
            shutil.copytree(data.parent, destination, dirs_exist_ok=True)
        for key, path in list(artifacts.items()):
            if key not in {"crystallography_data", "crystallography_report"} and not key.startswith(("cif_", "crystal_file_")):
                continue
            old = Path(path)
            try:
                suffix = old.relative_to(Path(raw).parent)
            except ValueError:
                suffix = Path(old.name)
            new = destination / suffix
            artifacts[key] = str(new)
            relative[key] = str(new.relative_to(target_root))
        for structure in (entry.get("structure", {}), entry.get("domain_snapshot", {}).get("structure", {})):
            structure["cif_folder"] = str(destination)
            structure["cif_files"] = [v for k, v in artifacts.items() if k.startswith("cif_")]
            structure["crystallography_data_path"] = artifacts["crystallography_data"]
            structure["crystallography_report_path"] = artifacts.get("crystallography_report", "")
