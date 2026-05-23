"""Testa o lock por peca: previne dois processos manipulando o mesmo estado.

O cenario real (observado em 20/05 00:04:02) foi: dois Noviello-Poller dispararam
ao mesmo segundo, ambos leram a mesma decisao=aprovar, ambos iam publicar. So
nao houve duplo post porque um dos processos foi morto a tempo.

O lock OS-level (msvcrt.locking no Windows, fcntl.flock no Unix) garante que
apenas um processo consiga manipular a peca por vez. O outro pega LockBusy e
pula essa tick.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.producer_state import ProducaoState, ProducaoStore
from src.state import LockBusy, PecaState, StateStore

PROJECT = Path(__file__).resolve().parents[1]


def _script_lock_peca(state_dir, peca_id, hold_secs=0):
    """Gera script Python standalone que tenta pegar o lock e imprime o resultado."""
    return (
        f"import sys, time\n"
        f"sys.path.insert(0, r'{PROJECT}')\n"
        f"from src.state import StateStore, LockBusy\n"
        f"store = StateStore(r'{state_dir}')\n"
        f"try:\n"
        f"  with store.lock({peca_id!r}):\n"
        f"    time.sleep({hold_secs})\n"
        f"    print('GOT_LOCK')\n"
        f"except LockBusy:\n"
        f"  print('BUSY')\n"
    )


def _script_lock_producao(state_dir, post_id):
    return (
        f"import sys\n"
        f"sys.path.insert(0, r'{PROJECT}')\n"
        f"from src.producer_state import ProducaoStore\n"
        f"from src.state import LockBusy\n"
        f"store = ProducaoStore(r'{state_dir}')\n"
        f"try:\n"
        f"  with store.lock({post_id!r}):\n"
        f"    print('GOT_LOCK')\n"
        f"except LockBusy:\n"
        f"  print('BUSY')\n"
    )


def test_lock_bloqueia_outro_processo(tmp_path):
    """Enquanto um processo segura o lock, outro processo pega LockBusy."""
    state_dir = tmp_path / "state"
    store = StateStore(state_dir)
    store.save(PecaState(peca_id="x"))

    with store.lock("x"):
        r = subprocess.run(
            [sys.executable, "-c", _script_lock_peca(state_dir, "x")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "BUSY" in r.stdout, f"esperava BUSY, stdout={r.stdout!r} stderr={r.stderr!r}"
        assert "GOT_LOCK" not in r.stdout


def test_lock_libera_apos_saida_do_bloco(tmp_path):
    """Apos sair do `with`, o lock e liberado: outro processo consegue."""
    state_dir = tmp_path / "state"
    store = StateStore(state_dir)
    store.save(PecaState(peca_id="x"))

    with store.lock("x"):
        pass  # solta imediatamente

    r = subprocess.run(
        [sys.executable, "-c", _script_lock_peca(state_dir, "x")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "GOT_LOCK" in r.stdout, f"stdout={r.stdout!r} stderr={r.stderr!r}"


def test_locks_de_pecas_diferentes_nao_interferem(tmp_path):
    """Lock de 'x' nao bloqueia processamento de 'y' — granularidade por peca."""
    state_dir = tmp_path / "state"
    store = StateStore(state_dir)
    store.save(PecaState(peca_id="x"))
    store.save(PecaState(peca_id="y"))

    with store.lock("x"):
        r = subprocess.run(
            [sys.executable, "-c", _script_lock_peca(state_dir, "y")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "GOT_LOCK" in r.stdout


def test_producao_store_tambem_tem_lock(tmp_path):
    """O lock funciona em ProducaoStore com a mesma semantica."""
    state_dir = tmp_path / "state"
    store = ProducaoStore(state_dir)
    store.save(ProducaoState(post_id="11748"))

    with store.lock("11748"):
        r = subprocess.run(
            [sys.executable, "-c", _script_lock_producao(state_dir, "11748")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "BUSY" in r.stdout, f"stdout={r.stdout!r} stderr={r.stderr!r}"


def test_dois_processos_competindo_pelo_lock(tmp_path):
    """Reproduz a race do 20/05 00:04:02: dois pollers ao mesmo segundo.

    Sem o lock, ambos processariam a peca (duplo publish). Com o lock,
    apenas um pega; o outro PULA com LockBusy.
    """
    import threading

    state_dir = tmp_path / "state"
    store = StateStore(state_dir)
    store.save(PecaState(peca_id="x"))

    # Cada "poller" simula o trabalho de handle_approve segurando o lock por 0.5s
    worker = _script_lock_peca(state_dir, "x", hold_secs=0.5)

    resultados = []

    def run():
        r = subprocess.run(
            [sys.executable, "-c", worker],
            capture_output=True,
            text=True,
            timeout=15,
        )
        resultados.append(r.stdout.strip())

    # Threads disparam os 2 subprocessos quase simultaneamente
    t1 = threading.Thread(target=run)
    t2 = threading.Thread(target=run)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    ordenados = sorted(resultados)
    assert ordenados == ["BUSY", "GOT_LOCK"], (
        f"esperado um BUSY e um GOT_LOCK, obtido {ordenados}"
    )


def test_lock_busy_e_silencioso_apos_falha(tmp_path):
    """Quando LockBusy e levantado, o arquivo .lock nao fica orfao."""
    state_dir = tmp_path / "state"
    store = StateStore(state_dir)
    store.save(PecaState(peca_id="x"))

    with store.lock("x"):
        r = subprocess.run(
            [sys.executable, "-c", _script_lock_peca(state_dir, "x")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "BUSY" in r.stdout

    # depois que solto, outro consegue normalmente
    r2 = subprocess.run(
        [sys.executable, "-c", _script_lock_peca(state_dir, "x")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "GOT_LOCK" in r2.stdout
