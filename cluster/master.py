"""Nó Master: orquestra o cluster usando o paradigma produtor/consumidor.

Conceitos de SO demonstrados:
  * Threads (threading.Thread) para produtor, consumidor e reaper.
  * Fila thread-safe (queue.Queue) como buffer entre produtor e consumidor.
  * Exclusão mútua (threading.Lock) protegendo o estado compartilhado do cluster.

Fluxo:
  Produtor  -> cria PODs e os coloca na fila
  Consumidor (escalonador) -> retira PODs da fila e os aloca nos Workers
  Reaper    -> remove PODs cujo TTL expirou, liberando recursos
"""

from __future__ import annotations

import queue
import threading
import time

from .pod import Pod, gerar_pod, PENDENTE, EXECUTANDO, CONCLUIDO, NAO_ALOCAVEL
from .worker import criar_workers
from .scheduler import MultiMetricScheduler


class Master:
    def __init__(self, total_pods: int = 18, intervalo_producao: float = 1.2):
        self.workers = criar_workers()
        self.scheduler = MultiMetricScheduler()
        self.fila: "queue.Queue[Pod]" = queue.Queue()
        self.lock = threading.Lock()

        self.total_pods = total_pods
        self.intervalo_producao = intervalo_producao

        # Estado/histórico compartilhado (sempre acessado sob self.lock).
        self.pods_criados: list[Pod] = []
        self.pods_concluidos: list[Pod] = []
        self.pods_nao_alocaveis: list[Pod] = []
        self.eventos: list[str] = []   # log textual para o dashboard

        self._rodando = False
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------------ ciclo
    def iniciar(self) -> None:
        if self._rodando:
            return
        self._rodando = True
        self._registrar("Cluster iniciado: Master + %d Workers." % len(self.workers))
        self._threads = [
            threading.Thread(target=self._produtor, name="produtor", daemon=True),
            threading.Thread(target=self._consumidor, name="consumidor", daemon=True),
            threading.Thread(target=self._reaper, name="reaper", daemon=True),
        ]
        for t in self._threads:
            t.start()

    # --------------------------------------------------------------- produtor
    def _produtor(self) -> None:
        """Gera PODs variados e os enfileira (papel de produtor).

        Produz um lote inicial (`total_pods`) rapidamente e, em seguida,
        continua gerando PODs indefinidamente em ritmo mais lento. Como o
        reaper libera recursos, o cluster atinge um regime permanente — ideal
        para uma demonstração contínua no vídeo.
        """
        i = 0
        while self._rodando:
            agora = time.time()
            pod = gerar_pod(agora)
            with self.lock:
                self.pods_criados.append(pod)
                self._registrar(
                    f"Produtor criou {pod.nome} "
                    f"(cpu={pod.cpu_req}, mem={pod.mem_req}MB, disco={pod.disk_req}GB, "
                    f"lat_sens={pod.latency_sensitivity})"
                )
            self.fila.put(pod)
            i += 1
            # lote inicial rápido; depois, ritmo mais espaçado para manter equilíbrio
            time.sleep(self.intervalo_producao if i < self.total_pods else self.intervalo_producao * 2)

    # ------------------------------------------------------------- consumidor
    def _consumidor(self) -> None:
        """Retira PODs da fila e os escalona nos Workers (papel de consumidor)."""
        while self._rodando:
            try:
                pod = self.fila.get(timeout=0.5)
            except queue.Empty:
                continue
            with self.lock:
                worker = self.scheduler.escolher(self.workers, pod)
                if worker is None:
                    pod.estado = NAO_ALOCAVEL
                    self.pods_nao_alocaveis.append(pod)
                    self._registrar(f"Escalonador NÃO encontrou Worker para {pod.nome}.")
                else:
                    worker.alocar(pod, time.time())
                    self._registrar(
                        f"Escalonador alocou {pod.nome} em {worker.nome} "
                        f"(lat={worker.latency}ms)."
                    )
            self.fila.task_done()
            time.sleep(0.4)  # tempo de "deploy" do POD, deixa a animação visível

    # ------------------------------------------------------------------ reaper
    def _reaper(self) -> None:
        """Finaliza PODs cujo TTL expirou, liberando recursos no Worker."""
        while self._rodando:
            agora = time.time()
            with self.lock:
                for worker in self.workers:
                    expirados = [
                        p for p in worker.pods
                        if p.alocado_em and (agora - p.alocado_em) >= p.ttl
                    ]
                    for p in expirados:
                        worker.liberar(p)
                        p.estado = CONCLUIDO
                        self.pods_concluidos.append(p)
                        self._registrar(f"{p.nome} concluiu (TTL) e liberou {worker.nome}.")
            time.sleep(1.0)

    # ------------------------------------------------------------------- util
    def _registrar(self, msg: str) -> None:
        """Adiciona um evento ao log (deve ser chamado sob self.lock)."""
        t = time.strftime("%H:%M:%S")
        self.eventos.append(f"[{t}] {msg}")
        if len(self.eventos) > 200:
            self.eventos = self.eventos[-200:]

    def snapshot(self) -> dict:
        """Estado completo e serializável do cluster (para o /api/state)."""
        with self.lock:
            executando = sum(len(w.pods) for w in self.workers)
            return {
                "workers": [w.to_dict() for w in self.workers],
                "fila": [p.nome for p in list(self.fila.queue)],
                "eventos": self.eventos[-25:][::-1],
                "resumo": {
                    "criados": len(self.pods_criados),
                    "executando": executando,
                    "concluidos": len(self.pods_concluidos),
                    "nao_alocaveis": len(self.pods_nao_alocaveis),
                    "na_fila": self.fila.qsize(),
                    "total_planejado": self.total_pods,
                },
                "scheduler": self.scheduler.nome,
            }
