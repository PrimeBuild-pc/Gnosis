from __future__ import annotations

import json
import re
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
        key, _, value = line.partition("=")
        if value.startswith('"') and value.endswith('"'):
            value = json.loads(value).replace("$$", "$")
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _compose_value(value: str) -> str:
    # Compose parses .env twice (project interpolation and env_file); escape both.
    return json.dumps(value.replace("$", "$$"), ensure_ascii=False)


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Aggiorna (o aggiunge in coda) le righe KEY=value indicate, preservando il resto del file."""
    if any(
        not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or any(char in value for char in "\r\n\0")
        for key, value in updates.items()
    ):
        raise ValueError("Chiavi non valide o valori multilinea non consentiti")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                if key in remaining:
                    output.append(f"{key}={_compose_value(remaining.pop(key))}")
                continue
        output.append(line)
    for key, value in remaining.items():
        output.append(f"{key}={_compose_value(value)}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def mask(value: str) -> str:
    """Mostra solo la presenza del segreto, non lunghezza o suffisso."""
    return "********" if value else ""
