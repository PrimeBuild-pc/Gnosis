from __future__ import annotations

from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    """Analizza un file KEY=value (righe vuote e commenti # ignorati)."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Aggiorna (o aggiunge in coda) le righe KEY=value indicate, preservando il resto del file."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    for key, value in remaining.items():
        output.append(f"{key}={value}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def mask(value: str) -> str:
    """Maschera un valore sensibile per la UI, mostrando solo le ultime 4 cifre."""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]
