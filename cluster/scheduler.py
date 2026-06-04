"""Algoritmos de escalonamento.

- MultiMetricScheduler: solução proposta, com 4 métricas (CPU, memória,
  disco e latência de rede). Uma a mais que o padrão do Kubernetes.
- DefaultScheduler: imita o escalonador padrão do K8s, que pontua os nós
  apenas por CPU e memória. Usado para fins de comparação.

Ambos retornam o Worker escolhido (ou None se nenhum comporta o POD) e
expõem `pontuar()` para inspeção/explicação da decisão.
"""

from __future__ import annotations

from .pod import Pod
from .worker import Worker

# Latência máxima de referência usada para normalizar a métrica de rede.
LATENCIA_MAX = 100.0


class MultiMetricScheduler:
    """Escalonador proposto: pondera CPU, memória, disco e latência.

    Estratégia: dentre os Workers que comportam o POD, escolhe o de maior
    score. O score favorece nós que ficarão mais folgados após a alocação
    (balanceamento de carga / least-loaded) e, para PODs sensíveis a
    latência, favorece nós de menor latência de rede.
    """

    nome = "Proposto (multi-métrica)"

    def __init__(self, w_cpu=0.3, w_mem=0.3, w_disk=0.25, w_lat=0.15):
        self.w_cpu = w_cpu
        self.w_mem = w_mem
        self.w_disk = w_disk
        self.w_lat = w_lat

    def pontuar(self, worker: Worker, pod: Pod) -> float:
        # Folga relativa de cada recurso APÓS alocar o POD (0..1).
        folga_cpu = (worker.cpu_livre - pod.cpu_req) / worker.cpu_total
        folga_mem = (worker.mem_livre - pod.mem_req) / worker.mem_total
        folga_disk = (worker.disk_livre - pod.disk_req) / worker.disk_total
        # Qualidade de latência (1 = ótima), ponderada pela sensibilidade do POD.
        qual_lat = (1 - worker.latency / LATENCIA_MAX) * pod.latency_sensitivity
        return (
            self.w_cpu * folga_cpu
            + self.w_mem * folga_mem
            + self.w_disk * folga_disk
            + self.w_lat * qual_lat
        )

    def escolher(self, workers: list[Worker], pod: Pod) -> Worker | None:
        candidatos = [w for w in workers if w.comporta(pod)]
        if not candidatos:
            return None
        return max(candidatos, key=lambda w: self.pontuar(w, pod))


class DefaultScheduler:
    """Baseline estilo Kubernetes: considera apenas CPU e memória.

    Ignora disco e latência. Pode escolher um nó que não tem disco
    suficiente quando avaliado por todos cabe — aqui ainda respeitamos o
    encaixe real, mas a DECISÃO (score) só leva CPU e memória em conta,
    podendo alocar PODs sensíveis a latência em nós lentos.
    """

    nome = "Padrão K8s (CPU+memória)"

    def __init__(self, w_cpu=0.5, w_mem=0.5):
        self.w_cpu = w_cpu
        self.w_mem = w_mem

    def pontuar(self, worker: Worker, pod: Pod) -> float:
        folga_cpu = (worker.cpu_livre - pod.cpu_req) / worker.cpu_total
        folga_mem = (worker.mem_livre - pod.mem_req) / worker.mem_total
        return self.w_cpu * folga_cpu + self.w_mem * folga_mem

    def escolher(self, workers: list[Worker], pod: Pod) -> Worker | None:
        candidatos = [w for w in workers if w.comporta(pod)]
        if not candidatos:
            return None
        return max(candidatos, key=lambda w: self.pontuar(w, pod))
