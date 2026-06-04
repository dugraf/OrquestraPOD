"""Definição dos PODs e dos perfis de aplicação.

Cada POD representa uma carga de trabalho com requisitos computacionais
distintos. Os perfis dão variedade realista (web, api, cache, batch, db),
cada um com faixas próprias de CPU, memória, disco, sensibilidade à latência
e tempo de vida (TTL).
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field, asdict

# Estados possíveis de um POD durante o ciclo de vida.
PENDENTE = "Pendente"        # criado, ainda na fila do Master
EXECUTANDO = "Executando"    # alocado em um Worker
CONCLUIDO = "Concluido"      # TTL expirou, recursos liberados
NAO_ALOCAVEL = "NaoAlocavel"  # nenhum Worker comporta os requisitos


# Perfis de aplicação: (cpu, mem em MB, disco em GB) são faixas (min, max).
# latency_sensitivity (0..1): o quanto a aplicação se beneficia de baixa latência.
# ttl: faixa de tempo de vida em segundos (quanto tempo ocupa o Worker).
POD_PROFILES = {
    "web":   {"cpu": (1, 2),  "mem": (256, 512),   "disk": (1, 3),   "lat": 0.9, "ttl": (12, 20), "cor": "#3b82f6"},
    "api":   {"cpu": (2, 4),  "mem": (512, 1024),  "disk": (2, 5),   "lat": 0.7, "ttl": (14, 24), "cor": "#22c55e"},
    "cache": {"cpu": (1, 2),  "mem": (1024, 2048), "disk": (1, 2),   "lat": 1.0, "ttl": (16, 28), "cor": "#a855f7"},
    "batch": {"cpu": (3, 6),  "mem": (512, 1536),  "disk": (8, 20),  "lat": 0.1, "ttl": (18, 30), "cor": "#f59e0b"},
    "db":    {"cpu": (2, 4),  "mem": (1024, 3072), "disk": (10, 25), "lat": 0.5, "ttl": (20, 34), "cor": "#ef4444"},
}

_contador = itertools.count(1)


@dataclass
class Pod:
    """Uma unidade de trabalho a ser escalonada em um Worker."""

    id: int
    nome: str
    perfil: str
    cpu_req: int          # núcleos de CPU
    mem_req: int          # memória em MB
    disk_req: int         # disco em GB
    latency_sensitivity: float  # 0..1
    ttl: int              # tempo de vida em segundos
    cor: str
    estado: str = PENDENTE
    worker: str | None = None     # nome do Worker onde foi alocado
    criado_em: float = 0.0
    alocado_em: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def gerar_pod(agora: float, perfil: str | None = None) -> Pod:
    """Cria um POD novo, sorteando os requisitos dentro das faixas do perfil."""
    if perfil is None:
        perfil = random.choice(list(POD_PROFILES))
    p = POD_PROFILES[perfil]
    pid = next(_contador)
    return Pod(
        id=pid,
        nome=f"{perfil}-{pid}",
        perfil=perfil,
        cpu_req=random.randint(*p["cpu"]),
        mem_req=random.randint(*p["mem"]),
        disk_req=random.randint(*p["disk"]),
        latency_sensitivity=p["lat"],
        ttl=random.randint(*p["ttl"]),
        cor=p["cor"],
        criado_em=agora,
    )
