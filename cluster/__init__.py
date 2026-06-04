"""Pacote do orquestrador de PODs (mini-Kubernetes).

Contém o Master (escalonador), os Workers, os PODs, os algoritmos de
escalonamento e o cálculo de estatísticas/comparação.
"""

from .pod import Pod, POD_PROFILES, gerar_pod
from .worker import Worker
from .scheduler import MultiMetricScheduler, DefaultScheduler
from .master import Master
from . import stats

__all__ = [
    "Pod",
    "POD_PROFILES",
    "gerar_pod",
    "Worker",
    "MultiMetricScheduler",
    "DefaultScheduler",
    "Master",
    "stats",
]
