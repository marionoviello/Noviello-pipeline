"""Testes do backup (F3)."""

from __future__ import annotations

import tarfile
import time
from pathlib import Path

from src import backup
from src.config import load_config


def _cfg(tmp_path):
    cfg = load_config()
    cfg.project_root = tmp_path / "proj"
    cfg.automacao_dir = tmp_path / "proj" / "automacao"
    cfg.state_dir = tmp_path / "proj" / "automacao" / "state"
    cfg.logs_dir = tmp_path / "proj" / "automacao" / "logs"
    # cria estrutura minima
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    (cfg.project_root / "producao").mkdir(parents=True, exist_ok=True)
    return cfg


def test_fazer_backup_inclui_state_e_producao(tmp_path):
    cfg = _cfg(tmp_path)
    # popular conteudo
    (cfg.state_dir / "cadencia.json").write_text('{"ativa": true}', encoding="utf-8")
    (cfg.project_root / "producao" / "peca-x.txt").write_text("conteudo", encoding="utf-8")

    destino = tmp_path / "backups"
    arq = backup.fazer_backup(cfg, destino=destino)
    assert arq is not None
    assert arq.exists()
    assert arq.suffix == ".gz"

    # confere conteudo do tar
    with tarfile.open(arq, "r:gz") as tar:
        nomes = [m.name.replace("\\", "/") for m in tar.getmembers()]
        assert any("automacao/state/cadencia.json" in n for n in nomes)
        assert any("producao/peca-x.txt" in n for n in nomes)


def test_fazer_backup_exclui_locks_e_pycache(tmp_path):
    cfg = _cfg(tmp_path)
    (cfg.state_dir / "ok.json").write_text("{}", encoding="utf-8")
    (cfg.state_dir / "transient.lock").write_text("", encoding="utf-8")
    (cfg.state_dir / "fail.tmp").write_text("", encoding="utf-8")
    pycache = cfg.state_dir / "__pycache__"
    pycache.mkdir()
    (pycache / "x.pyc").write_text("", encoding="utf-8")

    destino = tmp_path / "backups"
    arq = backup.fazer_backup(cfg, destino=destino)
    with tarfile.open(arq, "r:gz") as tar:
        nomes = [m.name.replace("\\", "/") for m in tar.getmembers()]
    assert any("ok.json" in n for n in nomes)
    assert not any(n.endswith(".lock") for n in nomes)
    assert not any(n.endswith(".tmp") for n in nomes)
    assert not any("__pycache__" in n for n in nomes)


def test_fazer_backup_nada_para_empacotar(tmp_path):
    cfg = _cfg(tmp_path)
    # state_dir vazio, producao vazia
    # tarball cria arquivo "vazio" — mas a funcao filtra...
    # Na verdade, mesmo dir vazio adiciona entry no tar. So devolve None se
    # nem state_dir nem producao_dir existem.
    # Vou apagar os diretorios e testar caso edge:
    import shutil
    shutil.rmtree(cfg.state_dir)
    shutil.rmtree(cfg.project_root / "producao")
    destino = tmp_path / "backups"
    arq = backup.fazer_backup(cfg, destino=destino)
    assert arq is None


def test_rotacionar_mantem_n_mais_recentes(tmp_path):
    destino = tmp_path / "backups"
    destino.mkdir()
    # cria 5 arquivos fake
    for i in range(5):
        f = destino / f"noviello-pipeline-2026-05-2{i}T00-00-00.tar.gz"
        f.write_text("x")
        # mtime crescente
        mtime = time.time() - (5 - i) * 3600
        import os
        os.utime(f, (mtime, mtime))

    apagados = backup.rotacionar(destino=destino, manter=3)
    assert apagados == 2
    restantes = list(destino.glob("*.tar.gz"))
    assert len(restantes) == 3


def test_rotacionar_destino_inexistente(tmp_path):
    apagados = backup.rotacionar(destino=tmp_path / "nope", manter=3)
    assert apagados == 0


def test_listar_backups_ordenado_mais_recente_primeiro(tmp_path):
    destino = tmp_path / "backups"
    destino.mkdir()
    f1 = destino / "noviello-pipeline-2026-05-20T00-00-00.tar.gz"
    f2 = destino / "noviello-pipeline-2026-05-22T00-00-00.tar.gz"
    f1.write_text("a")
    time.sleep(0.01)
    f2.write_text("b")
    backups = backup.listar_backups(destino)
    assert len(backups) == 2
    assert backups[0]["nome"] == f2.name  # mais recente primeiro
