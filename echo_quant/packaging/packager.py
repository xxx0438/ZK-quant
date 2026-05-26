"""Model → artifact + reproducibility kit.

Strategy v0.4.3:
- Only ONNX is supported as the runtime artifact format.
  * Why: ONNX is sandboxable. Pickle is an arbitrary-code-execution vector.
  * sklearn / xgboost / pytorch all export to ONNX.
- The model's Python source goes into the reproducibility kit (kit.tar.gz),
  but is NOT executed at runtime. Echo's runtime only loads the ONNX.
- Kit contents:
    model.py             — quant's Python source
    requirements.txt     — pinned deps
    README.md            — auto-generated
    dataset_hash.txt     — which dataset was used for the backtest
    backtest_result.json — output of `echo-cli backtest`
    metadata.json        — model_id, asset, version, schemas
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from echo_quant.exceptions import PackagingError
from echo_quant.model import Inputs, Model

class PackagedModel:
    def __init__(
        self,
        artifact_path: Path,
        artifact_sha256: str,
        kit_path: Path,
        kit_sha256: str,
        metadata: dict,
    ):
        self.artifact_path = artifact_path
        self.artifact_sha256 = artifact_sha256
        self.kit_path = kit_path
        self.kit_sha256 = kit_sha256
        self.metadata = metadata

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def export_to_onnx(model: Model, sample_inputs: Inputs) -> bytes:
    """Detect the model's underlying framework and convert to ONNX.

    Quants attach a `.onnx_model` attribute OR a `.to_onnx()` method
    on their Model class. We try both, then fall back to wrapping as a
    Python-callable ONNX op (last resort, slow).
    """
    # Path 1: explicit ONNX bytes attribute
    if hasattr(model, "onnx_bytes") and isinstance(model.onnx_bytes, bytes):
        return model.onnx_bytes

    # Path 2: model.to_onnx(sample_inputs) -> bytes
    if hasattr(model, "to_onnx") and callable(model.to_onnx):
        result = model.to_onnx(sample_inputs)
        if isinstance(result, bytes):
            return result
        if hasattr(result, "SerializeToString"):
            return result.SerializeToString()
        raise PackagingError(f"to_onnx() returned unsupported type {type(result)}")

    # Path 3: sklearn model attribute
    if hasattr(model, "sklearn_model"):
        try:
            from skl2onnx import to_onnx
            import numpy as np

            # Need to know the input shape: ask the quant to provide feature_vector()
            if not hasattr(model, "feature_vector"):
                raise PackagingError(
                    "Models with sklearn_model must also implement feature_vector(inputs)"
                )
            sample_vec = model.feature_vector(sample_inputs)
            sample_arr = np.array([sample_vec], dtype=np.float32)
            onx = to_onnx(model.sklearn_model, sample_arr)
            return onx.SerializeToString()
        except ImportError as e:
            raise PackagingError("Install with `pip install echo-quant[sklearn]`") from e

    raise PackagingError(
        "Could not export model to ONNX. Attach one of:\n"
        "  - self.onnx_bytes: bytes\n"
        "  - self.to_onnx(inputs) -> bytes\n"
        "  - self.sklearn_model + self.feature_vector(inputs) (with sklearn extra)\n"
        "Or override `to_onnx` directly on your Model subclass."
    )

def package_model(
    model: Model,
    source_path: Path,
    sample_inputs: Inputs,
    output_dir: Path,
    *,
    backtest_result: Optional[dict] = None,
    requirements: Optional[list[str]] = None,
) -> PackagedModel:
    """Produce artifact.onnx + kit.tar.gz under output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. ONNX export
    artifact_path = output_dir / f"{model.model_id}.onnx"
    try:
        onnx_bytes = export_to_onnx(model, sample_inputs)
    except Exception as e:
        raise PackagingError(f"ONNX export failed: {e}") from e
    artifact_path.write_bytes(onnx_bytes)
    artifact_sha = _sha256_file(artifact_path)

    # 2. Metadata
    metadata = {
        "model_id": model.model_id,
        "asset": model.asset,
        "version": model.version,
        "category": model.category,
        "description": model.description,
        "required_data": model.required_data(),
        "artifact_sha256": artifact_sha,
        "sdk_version": _sdk_version(),
        "packaged_at": datetime.now(timezone.utc).isoformat(),
    }

    # 3. Build kit
    kit_path = output_dir / f"{model.model_id}.kit.tar.gz"
    _build_kit(
        kit_path=kit_path,
        source_path=source_path,
        metadata=metadata,
        backtest_result=backtest_result,
        requirements=requirements or _infer_requirements(),
    )
    kit_sha = _sha256_file(kit_path)

    metadata["kit_sha256"] = kit_sha

    return PackagedModel(
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha,
        kit_path=kit_path,
        kit_sha256=kit_sha,
        metadata=metadata,
    )

def _build_kit(
    *,
    kit_path: Path,
    source_path: Path,
    metadata: dict,
    backtest_result: Optional[dict],
    requirements: list[str],
):
    """Assemble the reproducibility tarball."""
    if not source_path.exists():
        raise PackagingError(f"Source file not found: {source_path}")

    with tarfile.open(kit_path, "w:gz") as tar:
        # model.py
        tar.add(source_path, arcname="model.py")

        # metadata.json
        meta_data = json.dumps(metadata, indent=2).encode()
        _add_bytes(tar, "metadata.json", meta_data)

        # requirements.txt
        reqs = "\n".join(requirements).encode()
        _add_bytes(tar, "requirements.txt", reqs)

        # backtest_result.json (optional)
        if backtest_result:
            br = json.dumps(backtest_result, indent=2, default=str).encode()
            _add_bytes(tar, "backtest_result.json", br)

        # README.md (auto-generated)
        readme = _generate_readme(metadata, backtest_result).encode()
        _add_bytes(tar, "README.md", readme)

def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes):
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mtime = 0  # deterministic for hashing
    tar.addfile(info, io.BytesIO(data))

def _generate_readme(metadata: dict, backtest: Optional[dict]) -> str:
    lines = [
        f"# {metadata['model_id']}",
        "",
        f"- **Asset**: {metadata['asset']}",
        f"- **Version**: {metadata['version']}",
        f"- **Category**: {metadata['category']}",
        f"- **Artifact SHA256**: `{metadata['artifact_sha256']}`",
        f"- **Packaged**: {metadata['packaged_at']}",
        "",
        "## Description",
        metadata.get("description") or "_(no description)_",
        "",
    ]
    if backtest:
        m = backtest.get("metrics", {})
        lines += [
            "## Backtest",
            f"- Period: {backtest.get('period_start')} → {backtest.get('period_end')}",
            f"- Trades: {m.get('n_trades')}",
            f"- Sharpe: {m.get('sharpe')}",
            f"- Max DD: {m.get('max_drawdown_pct')}",
            f"- Win rate: {m.get('win_rate')}",
            "",
        ]
    lines += [
        "## Required canonical data fields",
        *[f"- `{f}`" for f in metadata.get("required_data", [])],
    ]
    return "\n".join(lines)

def _infer_requirements() -> list[str]:
    """Best-effort: capture installed versions of key libs."""
    out = []
    for pkg in ("echo-quant", "numpy", "pandas", "onnx", "onnxruntime"):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", pkg],
                capture_output=True, text=True, check=False,
            )
            for line in result.stdout.splitlines():
                if line.startswith("Version:"):
                    out.append(f"{pkg}=={line.split(':', 1)[1].strip()}")
                    break
        except Exception:
            continue
    return out

def _sdk_version() -> str:
    try:
        from importlib.metadata import version
        return version("echo-quant")
    except Exception:
        return "unknown"
