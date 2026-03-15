from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


def _prompt_candidates() -> List[Path]:
    env_path = os.getenv("PROMPTS_FILE")
    candidates: List[Path] = []

    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path("prompts.yaml"),
            Path("app/modules/prompts.yaml"),
            Path("medicina_com_ia/prompts.yaml"),
            Path("medicina_com_ia/app/modules/prompts.yaml"),
        ]
    )
    return candidates


def resolve_prompts_path() -> Path:
    for candidate in _prompt_candidates():
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Arquivo de prompts não encontrado. Tentados: "
        + ", ".join(str(c) for c in _prompt_candidates())
    )


def carregar_prompts() -> Tuple[Dict[str, Dict[str, str]], str]:
    prompts_path = resolve_prompts_path()
    with prompts_path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    if not isinstance(payload, dict):
        raise ValueError("Formato inválido de prompts.yaml: esperado objeto no topo.")
    return payload, str(prompts_path)


def catalogo_profissoes_necessidades() -> Dict[str, List[str]]:
    prompts, _ = carregar_prompts()
    catalogo: Dict[str, List[str]] = {}
    for profissao, necessidades in prompts.items():
        if isinstance(necessidades, dict):
            catalogo[profissao] = list(necessidades.keys())
    return catalogo
