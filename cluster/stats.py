"""Estatísticas do cluster e comparação entre os dois escalonadores.

`comparar()` roda EXATAMENTE o mesmo conjunto de PODs pelos dois
escalonadores (proposto x padrão K8s), partindo de Workers idênticos,
e devolve métricas lado a lado para o dashboard:

  * alocados x não-alocados
  * desvio-padrão da utilização entre Workers (quanto menor, mais balanceado)
  * latência média ponderada dos PODs (peso = sensibilidade à latência)
"""

from __future__ import annotations

import random
import statistics

from .pod import gerar_pod
from .worker import criar_workers
from .scheduler import MultiMetricScheduler, DefaultScheduler


def _desvio_utilizacao(workers) -> float:
    """Desvio-padrão da utilização média (CPU/mem/disco) entre os Workers."""
    medias = []
    for w in workers:
        u = w.utilizacao()
        medias.append((u["cpu"] + u["mem"] + u["disk"]) / 3)
    return round(statistics.pstdev(medias), 2) if len(medias) > 1 else 0.0


def _latencia_media_ponderada(workers) -> float:
    """Latência média sentida pelos PODs, ponderada pela sensibilidade.

    PODs sensíveis a latência pesam mais; mede a qualidade das decisões de
    rede do escalonador (menor é melhor).
    """
    soma_peso = 0.0
    soma = 0.0
    for w in workers:
        for p in w.pods:
            peso = p.latency_sensitivity
            soma += w.latency * peso
            soma_peso += peso
    return round(soma / soma_peso, 1) if soma_peso else 0.0


def _executar(workers, scheduler, pods) -> dict:
    """Aloca a lista de PODs nos Workers usando o escalonador dado."""
    alocados = 0
    nao_alocaveis = 0
    for pod in pods:
        w = scheduler.escolher(workers, pod)
        if w is None:
            nao_alocaveis += 1
        else:
            w.alocar(pod, agora=0.0)
            alocados += 1
    return {
        "scheduler": scheduler.nome,
        "alocados": alocados,
        "nao_alocaveis": nao_alocaveis,
        "balanceamento_stddev": _desvio_utilizacao(workers),
        "latencia_media_ponderada": _latencia_media_ponderada(workers),
        "workers": [
            {"nome": w.nome, "utilizacao": w.utilizacao(), "pods": len(w.pods)}
            for w in workers
        ],
    }


def comparar(n_pods: int = 24, seed: int = 42) -> dict:
    """Compara o escalonador proposto com o padrão sob a MESMA carga."""
    # Workload determinístico para que a comparação seja justa e reprodutível.
    random.seed(seed)
    pods_base = [gerar_pod(agora=0.0) for _ in range(n_pods)]

    # Cada escalonador recebe sua própria cópia limpa dos Workers e dos PODs.
    import copy

    res_prop = _executar(criar_workers(), MultiMetricScheduler(), copy.deepcopy(pods_base))
    res_padrao = _executar(criar_workers(), DefaultScheduler(), copy.deepcopy(pods_base))
    random.seed()  # restaura aleatoriedade para o resto do sistema

    return {
        "n_pods": n_pods,
        "proposto": res_prop,
        "padrao": res_padrao,
    }
