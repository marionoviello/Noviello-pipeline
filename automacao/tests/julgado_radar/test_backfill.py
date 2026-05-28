"""Testes do backfill — orquestrador STJ + TJ-SP com mocks completos."""

import datetime as _dt
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.julgado_radar import backfill, db, feeds_stj
from src.julgado_radar.config import AREAS_ALVO


# ===== FakePage minimal pra mockar Playwright nos testes do backfill =====

class _FakePage:
    """Mock minimo de playwright.Page — vide tests/julgado_radar/test_feeds_stj.py
    para a versao canonica. Replica aqui pra evitar acoplamento entre arquivos."""

    def __init__(self, *, selects, blocos):
        self.selects = selects
        self.blocos = blocos
        self._sel = ""

    def goto(self, url, **kwargs): pass
    def wait_for_load_state(self, *a, **k): pass
    def wait_for_timeout(self, ms): pass

    def evaluate(self, script, *args):
        if args and isinstance(args[0], str) and args[0].startswith("#"):
            return self.selects.get(args[0][1:], [])
        return []

    def eval_on_selector(self, selector, script):
        return self.blocos.get(self._sel, "")

    def select_option(self, selector, *, value):
        self._sel = value


def _pw_factory(page):
    @contextmanager
    def factory():
        yield page
    return factory


def _cfg(tmp_path) -> Config:
    cfg = Config(
        project_root=tmp_path,
        automacao_dir=tmp_path / "automacao",
        producao_dir=tmp_path / "producao",
        publicado_dir=tmp_path / "publicado",
        state_dir=tmp_path / "state",
        logs_dir=tmp_path / "logs",
        templates_dir=tmp_path / "templates",
        enabled_channels=["instagram"],
        dry_run=True,
        email_aprovador="t@t.com",
    )
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    return cfg


# ===== Stats =====

def test_stats_como_dict_inclui_categorias():
    s = backfill.Stats(stj_inseridos=10, tjsp_inseridos=20, inicio=0, fim=5)
    d = s.como_dict()
    assert d["stj"]["inseridos"] == 10
    assert d["tjsp"]["inseridos"] == 20
    assert d["duracao_seg"] == 5.0


def test_stats_duracao_zerada_se_invalido():
    s = backfill.Stats(inicio=10, fim=5)  # fim antes do inicio
    assert s.duracao_seg == 0.0


# ===== Helpers de periodo =====

def test_meses_da_janela():
    meses = backfill._meses_da_janela([2023, 2024])
    assert len(meses) == 24
    assert (2023, 1) in meses
    assert (2024, 12) in meses


def test_periodo_do_mes_fevereiro_bissexto():
    inicio, fim = backfill._periodo_do_mes(2024, 2)
    assert inicio == _dt.date(2024, 2, 1)
    assert fim == _dt.date(2024, 2, 29)


def test_periodo_do_mes_fevereiro_nao_bissexto():
    inicio, fim = backfill._periodo_do_mes(2023, 2)
    assert fim == _dt.date(2023, 2, 28)


# ===== executar_backfill (smoke completo com mocks) =====

def test_executar_backfill_sem_fontes_no_op(tmp_path):
    cfg = _cfg(tmp_path)
    stats = backfill.executar_backfill(
        cfg, janela=1, fontes=(), areas=("imobiliario",),
        anthropic_cli=MagicMock(), sleep_fn=lambda s: None,
    )
    assert stats.stj_inseridos == 0
    assert stats.tjsp_inseridos == 0


def test_executar_backfill_sem_anthropic_pula_stj(tmp_path):
    """Sem anthropic_cli, STJ e silenciosamente pulado, TJ-SP segue."""
    cfg = _cfg(tmp_path)
    stats = backfill.executar_backfill(
        cfg, janela=1, fontes=("stj",), anthropic_cli=None,
        sleep_fn=lambda s: None,
    )
    assert stats.stj_inseridos == 0
    assert stats.stj_erros == 0  # nao e erro, foi pulado


def test_executar_backfill_stj_completo_com_mocks(tmp_path, monkeypatch):
    """Fluxo end-to-end com Playwright mock: 1 informativo, 1 item aceito."""
    cfg = _cfg(tmp_path)

    # ano atual sera detectado por executar_backfill — usamos um ano dentro
    # de ANOS_SUPORTADOS (2026) e povoamos o combo correspondente.
    ano = _dt.date.today().year
    if ano not in (2021, 2022, 2023, 2024, 2025, 2026):
        ano = 2026
    page = _FakePage(
        selects={f"idInformativoEdicoesCombo{ano}": [
            {"value": "0855", "text": "Informativo 855"},
        ]},
        blocos={"0855": "<ul><li>PROCESSO REsp 999/SP. Texto longo o suficiente "
                        "pra passar do limiar de 200 chars. " + ("x " * 80) + "</li></ul>"},
    )

    cli = MagicMock()
    cli.extrair_item_stj.return_value = {
        "relevante": True, "area": "imobiliario",
        "processo_id": "REsp 999/SP", "tese": "Tese teste",
        "relator": "Min. X", "fundamentos": [],
    }

    stats = backfill.executar_backfill(
        cfg, janela=1, fontes=("stj",),
        anthropic_cli=cli,
        playwright_factory=_pw_factory(page),
        sleep_fn=lambda s: None,
    )
    assert stats.stj_inseridos == 1
    assert stats.por_area[("STJ", "imobiliario")] == 1


def test_executar_backfill_stj_idempotente(tmp_path, monkeypatch):
    """Rodar 2x = 0 novos na segunda (fetch_log pula)."""
    cfg = _cfg(tmp_path)
    ano = _dt.date.today().year
    if ano not in (2021, 2022, 2023, 2024, 2025, 2026):
        ano = 2026

    page = _FakePage(
        selects={f"idInformativoEdicoesCombo{ano}": [
            {"value": "0855", "text": "Informativo 855"},
        ]},
        blocos={"0855": "<li>PROCESSO " + ("X " * 200) + "</li>"},
    )

    cli = MagicMock()
    cli.extrair_item_stj.return_value = {
        "relevante": True, "area": "imobiliario",
        "processo_id": "REsp 999", "tese": "T", "fundamentos": [],
    }

    backfill.executar_backfill(
        cfg, janela=1, fontes=("stj",), anthropic_cli=cli,
        playwright_factory=_pw_factory(page), sleep_fn=lambda s: None,
    )
    stats2 = backfill.executar_backfill(
        cfg, janela=1, fontes=("stj",), anthropic_cli=cli,
        playwright_factory=_pw_factory(page), sleep_fn=lambda s: None,
    )
    assert stats2.stj_inseridos == 0  # idempotente


def test_executar_backfill_tjsp_completo_com_mocks(tmp_path):
    cfg = _cfg(tmp_path)

    html_resultado = """
    <html><body>
    <p>1111111-11.2024.8.26.0100</p>
    <p>Classe/Assunto: <span>Apelacao Civel</span></p>
    <p>Relator: <span>Des. X</span></p>
    <p>Data do Julgamento: <span>15/04/2024</span></p>
    <p>Ementa: <span>USUCAPIAO ORDINARIA. Recibo de compra. Justo titulo configurado conforme art. 1242 CC.</span></p>
    </body></html>
    """

    def fake_post(url, params):
        return 200, html_resultado.encode("utf-8")

    stats = backfill.executar_backfill(
        cfg, janela=1, fontes=("tjsp",), areas=("imobiliario",),
        anthropic_cli=MagicMock(),
        http_post=fake_post, sleep_fn=lambda s: None,
    )
    # 12 meses x 1 area = 12 fontes. Cada uma encontra 1 acordao.
    # dedup por (TJ-SP, "1111111-11..."): so 1 sobrevive no DB
    assert stats.tjsp_inseridos == 1
    assert stats.tjsp_atualizados >= 11  # restantes sao re-upserts


def test_executar_backfill_tjsp_ementa_curta_descarta(tmp_path):
    cfg = _cfg(tmp_path)
    html_curto = """
    <html><body>
    <p>1111111-11.2024.8.26.0100</p>
    <p>Classe: <span>Apelacao</span></p>
    <p>Relator: <span>X</span></p>
    <p>Ementa: <span>curto</span></p>
    </body></html>
    """

    def fake_post(url, params):
        return 200, html_curto.encode("utf-8")

    stats = backfill.executar_backfill(
        cfg, janela=1, fontes=("tjsp",), areas=("imobiliario",),
        anthropic_cli=MagicMock(),
        http_post=fake_post, sleep_fn=lambda s: None,
    )
    assert stats.tjsp_inseridos == 0
    assert stats.tjsp_descartados >= 1


# ===== CLI =====

def test_argparser_defaults():
    p = backfill._construir_argparser()
    args = p.parse_args([])
    assert args.janela == 5
    assert args.fontes == "stj,tjsp"
    assert args.dry_run is False


def test_argparser_janela_override():
    p = backfill._construir_argparser()
    args = p.parse_args(["--janela", "2"])
    assert args.janela == 2


def test_argparser_dry_run():
    p = backfill._construir_argparser()
    args = p.parse_args(["--dry-run"])
    assert args.dry_run is True


def test_main_dry_run_devolve_0(capsys):
    rc = backfill.main(["--dry-run", "--janela", "1"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "DRY-RUN" in captured.out
    assert "janela=1" in captured.out
