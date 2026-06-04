"""Testes unitários do escalonamento (critério de qualidade técnica).

Rode com:  python -m pytest -v   (ou  python test_scheduler.py)
"""

from cluster.pod import Pod, EXECUTANDO
from cluster.worker import Worker, criar_workers
from cluster.scheduler import MultiMetricScheduler, DefaultScheduler


def _pod(cpu=2, mem=512, disk=2, lat=1.0):
    return Pod(id=1, nome="t", perfil="web", cpu_req=cpu, mem_req=mem,
               disk_req=disk, latency_sensitivity=lat, ttl=10, cor="#fff")


def test_comporta_respeita_disco():
    w = Worker("w", cpu_total=8, mem_total=4096, disk_total=5, latency=10)
    assert w.comporta(_pod(disk=5))
    assert not w.comporta(_pod(disk=6))  # disco insuficiente


def test_alocar_e_liberar_recursos():
    w = Worker("w", cpu_total=8, mem_total=4096, disk_total=20, latency=10)
    p = _pod(cpu=3, mem=1024, disk=5)
    w.alocar(p, agora=0.0)
    assert (w.cpu_uso, w.mem_uso, w.disk_uso) == (3, 1024, 5)
    assert p.estado == EXECUTANDO and p.worker == "w"
    w.liberar(p)
    assert (w.cpu_uso, w.mem_uso, w.disk_uso) == (0, 0, 0)


def test_proposto_prefere_baixa_latencia_para_pod_sensivel():
    # Dois workers equivalentes em recursos, diferentes só na latência.
    rapido = Worker("edge", cpu_total=8, mem_total=4096, disk_total=20, latency=5)
    lento = Worker("far",  cpu_total=8, mem_total=4096, disk_total=20, latency=80)
    sched = MultiMetricScheduler()
    escolhido = sched.escolher([lento, rapido], _pod(lat=1.0))
    assert escolhido is rapido  # POD sensível -> nó de menor latência


def test_padrao_ignora_latencia():
    # O escalonador padrão (CPU+mem) não deve diferenciar por latência:
    # com recursos iguais, o score empata e a latência é irrelevante.
    rapido = Worker("edge", cpu_total=8, mem_total=4096, disk_total=20, latency=5)
    lento = Worker("far",  cpu_total=8, mem_total=4096, disk_total=20, latency=80)
    sched = DefaultScheduler()
    assert sched.pontuar(rapido, _pod()) == sched.pontuar(lento, _pod())


def test_retorna_none_quando_nao_cabe():
    w = Worker("w", cpu_total=1, mem_total=128, disk_total=1, latency=10)
    sched = MultiMetricScheduler()
    assert sched.escolher([w], _pod(cpu=4, mem=2048, disk=10)) is None


if __name__ == "__main__":
    # Execução simples sem pytest.
    import traceback
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for t in testes:
        try:
            t(); ok += 1; print(f"PASS {t.__name__}")
        except Exception:
            print(f"FAIL {t.__name__}"); traceback.print_exc()
    print(f"\n{ok}/{len(testes)} testes passaram.")
