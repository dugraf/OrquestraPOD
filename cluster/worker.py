"""Nó Worker: possui capacidades computacionais e hospeda PODs.

Cada Worker tem capacidade total e recursos atualmente em uso de CPU,
memória e disco, além de uma latência de rede (ms) até o gateway/Master.
Os Workers são deliberadamente heterogêneos para tornar as decisões do
escalonador visíveis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .pod import Pod, EXECUTANDO


@dataclass
class Worker:
    nome: str
    cpu_total: int
    mem_total: int        # MB
    disk_total: int       # GB
    latency: int          # ms até o gateway (métrica de rede)
    cpu_uso: int = 0
    mem_uso: int = 0
    disk_uso: int = 0
    pods: list = field(default_factory=list)

    # --- capacidade livre ---------------------------------------------------
    @property
    def cpu_livre(self) -> int:
        return self.cpu_total - self.cpu_uso

    @property
    def mem_livre(self) -> int:
        return self.mem_total - self.mem_uso

    @property
    def disk_livre(self) -> int:
        return self.disk_total - self.disk_uso

    # --- operações ----------------------------------------------------------
    def comporta(self, pod: Pod) -> bool:
        """True se o Worker tem recursos livres suficientes para o POD."""
        return (
            pod.cpu_req <= self.cpu_livre
            and pod.mem_req <= self.mem_livre
            and pod.disk_req <= self.disk_livre
        )

    def alocar(self, pod: Pod, agora: float) -> None:
        self.cpu_uso += pod.cpu_req
        self.mem_uso += pod.mem_req
        self.disk_uso += pod.disk_req
        pod.estado = EXECUTANDO
        pod.worker = self.nome
        pod.alocado_em = agora
        self.pods.append(pod)

    def liberar(self, pod: Pod) -> None:
        self.cpu_uso = max(0, self.cpu_uso - pod.cpu_req)
        self.mem_uso = max(0, self.mem_uso - pod.mem_req)
        self.disk_uso = max(0, self.disk_uso - pod.disk_req)
        if pod in self.pods:
            self.pods.remove(pod)

    # --- métricas -----------------------------------------------------------
    def utilizacao(self) -> dict:
        """Percentuais de utilização (0..100) por recurso."""
        return {
            "cpu": round(100 * self.cpu_uso / self.cpu_total, 1),
            "mem": round(100 * self.mem_uso / self.mem_total, 1),
            "disk": round(100 * self.disk_uso / self.disk_total, 1),
        }

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "cpu_total": self.cpu_total,
            "mem_total": self.mem_total,
            "disk_total": self.disk_total,
            "latency": self.latency,
            "cpu_uso": self.cpu_uso,
            "mem_uso": self.mem_uso,
            "disk_uso": self.disk_uso,
            "utilizacao": self.utilizacao(),
            "pods": [p.to_dict() for p in self.pods],
        }


def criar_workers() -> list[Worker]:
    """Cria 3 Workers com perfis de hardware bem distintos.

    - worker-cpu : muita CPU/RAM, latência média (bom para api/cache/web)
    - worker-disk: muito disco, latência alta (bom para batch/db)
    - worker-edge: hardware menor, porém latência baixíssima (bom p/ sensíveis a latência)
    """
    return [
        Worker("worker-cpu",  cpu_total=16, mem_total=8192,  disk_total=40,  latency=25),
        Worker("worker-disk", cpu_total=12, mem_total=6144,  disk_total=120, latency=40),
        Worker("worker-edge", cpu_total=8,  mem_total=4096,  disk_total=30,  latency=5),
    ]
