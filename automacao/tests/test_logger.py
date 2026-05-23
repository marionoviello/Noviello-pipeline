import json

from src.logger import get_logger, log_stage, logfile_do_mes, setup_logging


def test_logfile_do_mes_formato(tmp_path):
    arquivo = logfile_do_mes(tmp_path)
    assert arquivo.name.endswith("-publicacoes.jsonl")
    # padrao AAAA-MM-publicacoes.jsonl
    partes = arquivo.stem.split("-")
    assert len(partes[0]) == 4 and len(partes[1]) == 2


def test_log_stage_escreve_jsonl_parseavel(tmp_path):
    arquivo = setup_logging(tmp_path)
    logger = get_logger("teste")
    log_stage(logger, "2026-S20-teste", "stage.03", "ok", duracao_ms=42)

    linhas = arquivo.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) >= 1
    evento = json.loads(linhas[-1])
    assert evento["peca_id"] == "2026-S20-teste"
    assert evento["stage"] == "stage.03"
    assert evento["status"] == "ok"
    assert evento["duracao_ms"] == 42
    assert "timestamp" in evento
