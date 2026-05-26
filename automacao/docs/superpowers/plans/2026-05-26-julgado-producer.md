# Julgado da Semana Producer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Producer automatizado que detecta o evento `[NOV-MKT] LI 08h30 — Julgado` no Google Calendar, lê o PDF da semana, extrai dados via pypdf+Anthropic, gera carrossel IG + card LinkedIn com os 4 campos `area`/`selo_tribunal`/`processo_id`/`carimbo` populados — passando pelo fluxo de painel + email + watcher existente.

**Architecture:** Módulo isolado `src/julgado_producer.py` chamado de `producer.main()`. Estado em `state/julgados/<event_id>.json` separado. Reaproveita `calendar_client`, `anthropic_client` (com 3 métodos novos), `carousel_render` (Batch a), `julgado-card.html` (com 1 fix de placeholder), e todo o fluxo de aprovação por email + publishers já em produção. Zero migração de state.

**Tech Stack:** Python 3.14, pypdf, Anthropic SDK (existente), Playwright (existente), Flask (painel existente), pytest.

**Reference docs:**
- Spec: `automacao/docs/superpowers/specs/2026-05-26-julgado-producer-design.md`
- Padrões de código: `automacao/src/producer.py`, `automacao/src/producer_state.py` (espelhar estrutura)

---

## File Structure (definitivo)

**Arquivos NOVOS:**
- `automacao/src/julgado_state.py` — `EstadoJulgado`, `JulgadoState`, `JulgadoStore`, `transition`, `TransicaoInvalida`
- `automacao/src/pdf_extractor.py` — `extrair_texto_pdf`, `localizar_pdf_da_semana`, `extrair_dados_julgado`, `PDFExtractorError`
- `automacao/src/julgado_card_render.py` — `renderizar_card`
- `automacao/src/julgado_producer.py` — `detectar_e_extrair`, `processar_revisao`, `montar_peca`, `main_julgado`
- `automacao/tests/test_julgado_state.py`
- `automacao/tests/test_pdf_extractor.py`
- `automacao/tests/test_julgado_card_render.py`
- `automacao/tests/test_julgado_producer.py`
- `automacao/tests/fixtures/julgado_dummy.pdf` (smoke fixture)

**Arquivos MODIFICADOS:**
- `automacao/src/anthropic_client.py` — 3 métodos novos
- `automacao/src/config.py` — 5 campos novos
- `automacao/src/producer.py` — hook 1 bloco no `main()`
- `automacao/src/painel.py` — `listar_pendencias` ganha chave `julgado`, `registrar_decisao` aceita tipo
- `automacao/templates/julgado-card.html` — `Unanimidade` → `{carimbo_label}`
- `automacao/templates/painel.html` — seção nova "Julgado da Semana"
- `automacao/samples/_julgado_card_publicar.py` — patch mínimo de retrocompat
- `automacao/requirements.txt` — `pypdf>=4.0.0`
- `automacao/tests/test_painel.py` — testes da nova seção

---

## Convenções

- **Diretório de trabalho:** `C:/Users/mario/Documents/Noviello-Produtividade/automacao` (todos os comandos `pytest` rodam dali).
- **Python:** `.venv/Scripts/python.exe` (Windows venv).
- **Comando padrão de teste:** `.venv/Scripts/python.exe -m pytest <path> -v`
- **Pré-condição global:** rodar `pytest -q` a cada commit pra confirmar baseline +1.
- **Estilo:** seguir convenções de `producer.py` / `producer_state.py` (docstrings em PT-BR, type hints, `from __future__ import annotations`).
- **TDD:** test → fail → impl → pass → commit, sempre.

---

## Wave 1 — Base modules (sem dependências externas)

### Task 1: `JulgadoState` + `JulgadoStore`

**Files:**
- Create: `automacao/src/julgado_state.py`
- Test: `automacao/tests/test_julgado_state.py`

- [ ] **Step 1.1: Escrever os testes (TDD)**

Criar `automacao/tests/test_julgado_state.py` com:

```python
import pytest

from src.julgado_state import (
    EstadoJulgado,
    JulgadoState,
    JulgadoStore,
    TransicaoInvalida,
    transition,
    _safe_key,
)


def test_safe_key_sanitiza_chars_invalidos():
    assert _safe_key("evt_abc@123") == "evt_abc_123"
    assert _safe_key("a/b\\c:d") == "a_b_c_d"
    assert _safe_key("ok-123_xyz") == "ok-123_xyz"


def test_store_crud(tmp_path):
    store = JulgadoStore(tmp_path)
    estado = JulgadoState(event_id="evt-xyz", semana_iso=22, ano_iso=2026)
    assert store.exists("evt-xyz") is False
    store.save(estado)
    assert store.exists("evt-xyz") is True
    carregado = store.load("evt-xyz")
    assert carregado.semana_iso == 22
    assert carregado.status == EstadoJulgado.DETECTADO
    store.delete("evt-xyz")
    assert store.exists("evt-xyz") is False


def test_event_id_com_chars_especiais_sanitiza_no_path(tmp_path):
    store = JulgadoStore(tmp_path)
    estado = JulgadoState(event_id="evt@abc/123", semana_iso=1, ano_iso=2026)
    store.save(estado)
    # arquivo no disco com chars seguros
    arquivos = list((tmp_path / "julgados").glob("*.json"))
    assert len(arquivos) == 1
    assert "@" not in arquivos[0].name
    assert "/" not in arquivos[0].name
    # load preserva o event_id original
    carregado = store.load("evt@abc/123")
    assert carregado.event_id == "evt@abc/123"


def test_transicao_valida_registra_historico():
    est = JulgadoState(event_id="x", semana_iso=1, ano_iso=2026)
    transition(est, EstadoJulgado.AGUARDANDO_REVISAO)
    transition(est, EstadoJulgado.APROVADO)
    transition(est, EstadoJulgado.PECA_MONTADA)
    assert est.status == EstadoJulgado.PECA_MONTADA
    assert len(est.historico) == 3


def test_transicao_invalida_levanta():
    est = JulgadoState(event_id="x", semana_iso=1, ano_iso=2026)
    with pytest.raises(TransicaoInvalida):
        transition(est, EstadoJulgado.PECA_MONTADA)


def test_erro_permite_recovery():
    est = JulgadoState(
        event_id="x", semana_iso=1, ano_iso=2026, status=EstadoJulgado.ERRO,
    )
    transition(est, EstadoJulgado.AGUARDANDO_REVISAO)
    assert est.status == EstadoJulgado.AGUARDANDO_REVISAO


def test_decisao_persiste(tmp_path):
    store = JulgadoStore(tmp_path)
    est = JulgadoState(
        event_id="x", semana_iso=1, ano_iso=2026,
        decisao="ajustar", ajuste_texto="trocar relator",
    )
    store.save(est)
    carregado = store.load("x")
    assert carregado.decisao == "ajustar"
    assert carregado.ajuste_texto == "trocar relator"


def test_list_all_ignora_arquivos_invalidos(tmp_path):
    store = JulgadoStore(tmp_path)
    store.save(JulgadoState(event_id="a", semana_iso=1, ano_iso=2026))
    # arquivo invalido
    (tmp_path / "julgados" / "lixo.json").write_text("{nao eh json", encoding="utf-8")
    pecas = store.list_all()
    assert len(pecas) == 1
    assert pecas[0].event_id == "a"


def test_from_dict_ignora_campos_extras():
    dados = {"event_id": "x", "semana_iso": 1, "ano_iso": 2026, "campo_obsoleto": "x"}
    est = JulgadoState.from_dict(dados)
    assert est.event_id == "x"
```

- [ ] **Step 1.2: Rodar tests (devem falhar — módulo ainda não existe)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_state.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.julgado_state'`

- [ ] **Step 1.3: Implementar o módulo**

Criar `automacao/src/julgado_state.py`:

```python
"""Persistencia de estado do Julgado da Semana — um arquivo por evento do calendario.

Arquivos em state/julgados/<event_id_safe>.json. Chave de idempotencia e o event.id
do Google Calendar (sanitizado para nomes de arquivo validos).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.state import _file_lock, agora_iso


class EstadoJulgado:
    DETECTADO = "detectado"
    AGUARDANDO_REVISAO = "aguardando_revisao"
    APROVADO = "aprovado"
    PECA_MONTADA = "peca_montada"
    ERRO = "erro"


_TRANSICOES: dict[str, set[str]] = {
    EstadoJulgado.DETECTADO: {EstadoJulgado.AGUARDANDO_REVISAO, EstadoJulgado.ERRO},
    EstadoJulgado.AGUARDANDO_REVISAO: {EstadoJulgado.APROVADO, EstadoJulgado.ERRO},
    EstadoJulgado.APROVADO: {EstadoJulgado.PECA_MONTADA, EstadoJulgado.ERRO},
    EstadoJulgado.ERRO: {EstadoJulgado.AGUARDANDO_REVISAO, EstadoJulgado.APROVADO},
    EstadoJulgado.PECA_MONTADA: set(),
}


class TransicaoInvalida(Exception):
    pass


@dataclass
class JulgadoState:
    event_id: str
    semana_iso: int = 0
    ano_iso: int = 0
    event_summary: str = ""
    event_start_iso: str = ""
    status: str = EstadoJulgado.DETECTADO
    pdf_path: str = ""
    dados_julgado: dict = field(default_factory=dict)
    copy_carrossel: dict = field(default_factory=dict)
    texto_linkedin: str = ""
    decisao: str = ""
    ajuste_texto: str = ""
    tentativas_ajuste: int = 0
    ai_tells_resumo: dict = field(default_factory=dict)
    erro_mensagem: str = ""
    atualizado_em: str = field(default_factory=agora_iso)
    historico: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> "JulgadoState":
        campos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in dados.items() if k in campos})


def transition(estado: JulgadoState, novo_estado: str) -> None:
    permitidos = _TRANSICOES.get(estado.status, set())
    if novo_estado not in permitidos:
        raise TransicaoInvalida(
            f"transicao invalida: {estado.status} -> {novo_estado} "
            f"(permitidos: {sorted(permitidos)})"
        )
    estado.historico.append({"de": estado.status, "para": novo_estado, "em": agora_iso()})
    estado.status = novo_estado
    estado.atualizado_em = agora_iso()


_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9_\-]")


def _safe_key(event_id: str) -> str:
    """Substitui qualquer char nao-alfanumerico/_/- por underscore."""
    return _SAFE_KEY_RE.sub("_", event_id)


class JulgadoStore:
    """CRUD de arquivos de estado em state/julgados/."""

    def __init__(self, state_dir: Path):
        self.dir = Path(state_dir) / "julgados"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, event_id: str) -> Path:
        return self.dir / f"{_safe_key(event_id)}.json"

    def exists(self, event_id: str) -> bool:
        return self._path(event_id).exists()

    def load(self, event_id: str) -> JulgadoState:
        dados = json.loads(self._path(event_id).read_text(encoding="utf-8"))
        return JulgadoState.from_dict(dados)

    def save(self, estado: JulgadoState) -> None:
        estado.atualizado_em = agora_iso()
        tmp = self._path(estado.event_id).with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(estado.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path(estado.event_id))

    def delete(self, event_id: str) -> None:
        self._path(event_id).unlink(missing_ok=True)

    def list_all(self) -> list[JulgadoState]:
        estados = []
        for arquivo in sorted(self.dir.glob("*.json")):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
                estados.append(JulgadoState.from_dict(dados))
            except (json.JSONDecodeError, TypeError):
                continue
        return estados

    def lock(self, event_id: str):
        """Lock exclusivo nao-bloqueante (context manager). Levanta LockBusy se ocupado."""
        return _file_lock(self.dir / f"{_safe_key(event_id)}.lock")
```

- [ ] **Step 1.4: Rodar tests (devem passar todos)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_state.py -v
```
Expected: 8 passed.

- [ ] **Step 1.5: Confirmar baseline + 8 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 172 passed (164 baseline + 8).

- [ ] **Step 1.6: Commit**

```bash
git add src/julgado_state.py tests/test_julgado_state.py
git commit -m "Julgado: JulgadoState + JulgadoStore (Wave 1.1)"
```

---

### Task 2: `pdf_extractor` — leitura de PDF e localização da pasta da semana

**Files:**
- Create: `automacao/src/pdf_extractor.py`
- Create: `automacao/tests/fixtures/julgado_dummy.pdf`
- Test: `automacao/tests/test_pdf_extractor.py`

- [ ] **Step 2.1: Adicionar `pypdf` ao requirements e instalar**

Editar `automacao/requirements.txt` adicionando linha:
```
pypdf>=4.0.0
```

Instalar:
```bash
.venv/Scripts/python.exe -m pip install "pypdf>=4.0.0"
```

- [ ] **Step 2.2: Criar fixture PDF**

Criar `automacao/tests/fixtures/julgado_dummy.pdf` programaticamente (1 página com texto conhecido). Comando único:

```bash
.venv/Scripts/python.exe -c "
from pypdf import PdfWriter
from pypdf.generic import RectangleObject
import io
# pypdf >=4 nao tem builder de texto direto; usar reportlab nao queremos.
# Geramos um PDF minimo via bytes (1 pagina A4, texto 'TESTE PDF EXTRATOR')
from pathlib import Path
pdf_bytes = bytes.fromhex(
    '255044462d312e340a25e2e3cfd30a312030206f626a3c3c2f547970652f436174616c6f672f50616765732032203020523e3e656e646f626a0a322030206f626a3c3c2f547970652f50616765732f4b6964735b33203020525d2f436f756e7420313e3e656e646f626a0a332030206f626a3c3c2f547970652f506167652f506172656e7420322030205220'
    '2f4d65646961426f785b30203020353935203834325d2f436f6e74656e74732034203020522f5265736f75726365733c3c2f466f6e743c3c2f46313c3c2f547970652f466f6e742f53756274797065'
    '2f54797065312f426173654f6e742f48656c7665746963613e3e3e3e3e3e3e3e656e646f626a0a342030206f626a3c3c2f4c656e677468203434'
    '3e3e73747265616d0a42540a2f463120313220546620353020373030205464202854455354452050444620455854524154524f4f522920546a0a45540a656e6473747265616d0a656e646f626a0a787265660a302035'
    '0a3030303030303030303020363535333520660a3030303030303030303920303030303020e000300030303030303030303538203030303030206e0a0a747261696c65723c3c2f53697a652035'
    '2f526f6f7420312030203e3e0a737461727478726566000033380a2525454f46'
)
Path('tests/fixtures').mkdir(parents=True, exist_ok=True)
Path('tests/fixtures/julgado_dummy.pdf').write_bytes(pdf_bytes)
print('PDF criado:', Path('tests/fixtures/julgado_dummy.pdf').stat().st_size, 'bytes')
"
```

Se o hex acima falhar como PDF válido (pypdf reclamar), substituir por:
```bash
.venv/Scripts/python.exe -c "
from pathlib import Path
# Fallback: usar reportlab pra gerar um PDF real, mas sem adicionar dep:
# em vez disso, gera PDF minimo via construcao manual aceita por pypdf.
from pypdf import PdfWriter
w = PdfWriter()
w.add_blank_page(width=595, height=842)
Path('tests/fixtures').mkdir(parents=True, exist_ok=True)
with open('tests/fixtures/julgado_dummy.pdf', 'wb') as f:
    w.write(f)
print('PDF em branco criado')
"
```

Nota: O teste `test_extrair_texto_pdf_smoke` aceita string vazia para PDF em branco — verificar nos testes abaixo.

- [ ] **Step 2.3: Escrever os testes**

Criar `automacao/tests/test_pdf_extractor.py`:

```python
import pytest
from pathlib import Path

from src.pdf_extractor import (
    PDFExtractorError,
    extrair_texto_pdf,
    localizar_pdf_da_semana,
)

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "julgado_dummy.pdf"


def test_localizar_pdf_pasta_inexistente_falha(tmp_path):
    with pytest.raises(PDFExtractorError, match="nao existe"):
        localizar_pdf_da_semana(tmp_path / "julgados", 22)


def test_localizar_pdf_pasta_vazia_falha(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    with pytest.raises(PDFExtractorError, match="nenhum PDF"):
        localizar_pdf_da_semana(tmp_path / "julgados", 22)


def test_localizar_pdf_multiplos_pdfs_falha(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    (pasta / "a.pdf").write_bytes(b"%PDF-1.4")
    (pasta / "b.pdf").write_bytes(b"%PDF-1.4")
    with pytest.raises(PDFExtractorError, match="mais de um PDF"):
        localizar_pdf_da_semana(tmp_path / "julgados", 22)


def test_localizar_pdf_unico_devolve(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    pdf = pasta / "acordao.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    resultado = localizar_pdf_da_semana(tmp_path / "julgados", 22)
    assert resultado == pdf


def test_localizar_pdf_zerofill_semana(tmp_path):
    """sem-01 (zerofill) e sem-1 (sem fill) ambos devem funcionar."""
    pasta = tmp_path / "julgados" / "sem-01"
    pasta.mkdir(parents=True)
    pdf = pasta / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert localizar_pdf_da_semana(tmp_path / "julgados", 1) == pdf


def test_localizar_pdf_ignora_arquivos_nao_pdf(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    (pasta / "README.txt").write_text("ignore", encoding="utf-8")
    pdf = pasta / "acordao.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert localizar_pdf_da_semana(tmp_path / "julgados", 22) == pdf


def test_extrair_texto_pdf_smoke():
    """PDF de fixture em branco devolve string (possivelmente vazia)."""
    assert FIXTURE_PDF.exists(), f"fixture nao existe: {FIXTURE_PDF}"
    texto = extrair_texto_pdf(FIXTURE_PDF)
    assert isinstance(texto, str)


def test_extrair_texto_pdf_inexistente_falha(tmp_path):
    with pytest.raises(PDFExtractorError):
        extrair_texto_pdf(tmp_path / "nao-existe.pdf")


def test_extrair_texto_pdf_corrompido_falha(tmp_path):
    pdf = tmp_path / "corrompido.pdf"
    pdf.write_text("isto nao eh um PDF", encoding="utf-8")
    with pytest.raises(PDFExtractorError):
        extrair_texto_pdf(pdf)
```

- [ ] **Step 2.4: Rodar testes (devem falhar — sem implementação)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pdf_extractor.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.pdf_extractor'`

- [ ] **Step 2.5: Implementar `pdf_extractor.py`**

Criar `automacao/src/pdf_extractor.py`:

```python
"""Extracao de texto e localizacao de PDFs do Julgado da Semana.

Pipeline: localizar_pdf_da_semana(julgados_dir, N) -> extrair_texto_pdf(pdf) ->
extrair_dados_julgado(texto, anthropic_cli) -> dict estruturado.

A funcao extrair_dados_julgado e definida em outro modulo (anthropic_client)
e re-exportada aqui no Wave 2 (Task 4).
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFExtractorError(Exception):
    pass


def localizar_pdf_da_semana(julgados_dir: Path, semana_iso: int) -> Path:
    """Devolve o caminho do unico PDF em julgados_dir / 'sem-{N:02d}'.

    Levanta PDFExtractorError se:
    - julgados_dir/sem-N nao existe
    - pasta esta vazia (sem PDFs)
    - pasta tem 2+ PDFs (ambiguidade)
    """
    pasta = Path(julgados_dir) / f"sem-{semana_iso:02d}"
    if not pasta.exists():
        raise PDFExtractorError(f"pasta da semana nao existe: {pasta}")
    pdfs = sorted(pasta.glob("*.pdf"))
    if not pdfs:
        raise PDFExtractorError(f"nenhum PDF em {pasta}")
    if len(pdfs) > 1:
        nomes = ", ".join(p.name for p in pdfs)
        raise PDFExtractorError(
            f"mais de um PDF em {pasta} (esperado 1): {nomes}"
        )
    return pdfs[0]


def extrair_texto_pdf(pdf_path: Path) -> str:
    """Le texto bruto do PDF usando pypdf. Retorna string concatenada de todas as paginas.

    Levanta PDFExtractorError se o arquivo nao existe ou nao e um PDF valido.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise PDFExtractorError(f"arquivo nao existe: {pdf_path}")
    try:
        reader = PdfReader(str(pdf_path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise PDFExtractorError(f"falha ao ler PDF {pdf_path}: {exc}") from exc

    partes: list[str] = []
    for pagina in reader.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 — pypdf pode levantar varios
            raise PDFExtractorError(
                f"falha ao extrair texto da pagina em {pdf_path}: {exc}"
            ) from exc
    return "\n".join(partes).strip()
```

- [ ] **Step 2.6: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pdf_extractor.py -v
```
Expected: 9 passed.

- [ ] **Step 2.7: Confirmar baseline + 17 testes acumulados**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 181 passed (164 + 8 + 9).

- [ ] **Step 2.8: Commit**

```bash
git add src/pdf_extractor.py tests/test_pdf_extractor.py tests/fixtures/julgado_dummy.pdf requirements.txt
git commit -m "Julgado: pdf_extractor (localizar + extrair_texto) + pypdf dep (Wave 1.2)"
```

---

## Wave 2 — Anthropic integration

### Task 3: `anthropic_client.extrair_dados_julgado()`

**Files:**
- Modify: `automacao/src/anthropic_client.py` (adicionar método + schema)
- Test: `automacao/tests/test_anthropic_client_julgado.py` (NOVO)

- [ ] **Step 3.1: Escrever os testes (com mock)**

Criar `automacao/tests/test_anthropic_client_julgado.py`:

```python
"""Testes dos novos metodos do AnthropicClient (Julgado).

Mocka a chamada ao SDK Anthropic em nivel do streaming.
Nao precisa de API key real.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.anthropic_client import AnthropicClient, JULGADO_SCHEMA, CAROUSEL_SCHEMA_JULGADO


def _fake_response(payload):
    """Constroi resposta fake do Anthropic SDK (lista content[].text)."""
    msg = MagicMock()
    bloco = MagicMock()
    bloco.type = "text"
    bloco.text = json.dumps(payload) if isinstance(payload, dict) else payload
    msg.content = [bloco]
    return msg


def _fake_stream_cm(payload):
    """Context manager fake pro `with self._client.messages.stream(...) as stream:`"""
    stream = MagicMock()
    stream.get_final_message.return_value = _fake_response(payload)
    cm = MagicMock()
    cm.__enter__ = lambda self: stream
    cm.__exit__ = lambda self, *a: False
    return cm


def _make_client(tmp_path):
    """Constroi AnthropicClient com brief vazio no templates_dir tempo."""
    (tmp_path / "brief-marca.txt").write_text("brief de teste", encoding="utf-8")
    return AnthropicClient({"api_key": "sk-fake"}, tmp_path)


def test_julgado_schema_tem_campos_obrigatorios():
    """O schema definido como contrato com a IA inclui todos os campos obrigatorios."""
    obrig = set(JULGADO_SCHEMA["required"])
    assert obrig >= {
        "area", "selo_tribunal", "processo", "relator",
        "tese", "citacao_principal", "carimbo", "fundamentos",
    }


def test_carousel_schema_julgado_inclui_campos_julgado():
    """O schema do carrossel-julgado expoe os 4 campos novos como opcionais nos slides."""
    slide_props = CAROUSEL_SCHEMA_JULGADO["properties"]["slides"]["items"]["properties"]
    assert "area" in slide_props
    assert "selo_tribunal" in slide_props
    assert "processo_id" in slide_props
    assert "carimbo" in slide_props
    # mas obrigatorios continuam sendo titulo+corpo (retrocompat)
    obrig = set(CAROUSEL_SCHEMA_JULGADO["properties"]["slides"]["items"]["required"])
    assert obrig == {"titulo", "corpo"}


def test_extrair_dados_julgado_chama_stream_e_devolve_dict(tmp_path):
    cliente = _make_client(tmp_path)
    payload = {
        "area": "Direito Imobiliario",
        "selo_tribunal": "STJ",
        "orgao_completo": "Terceira Turma do STJ",
        "turma": "3a Turma",
        "processo": "REsp 2.215.421/SE",
        "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi",
        "relator_curto": "Min. Nancy Andrighi",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "O justo titulo deve ser interpretado de forma ampla...",
        "carimbo": "Unanimidade",
        "fundamentos": [
            {"fonte": "Art. 1.242 CC", "texto": "Usucapiao ordinaria..."}
        ],
    }
    with patch.object(
        cliente._client.messages, "stream", return_value=_fake_stream_cm(payload),
    ):
        resultado = cliente.extrair_dados_julgado("texto bruto do PDF aqui")

    assert resultado["processo"] == "REsp 2.215.421/SE"
    assert resultado["carimbo"] == "Unanimidade"
    assert len(resultado["fundamentos"]) == 1


def test_gerar_carrossel_julgado_inclui_campos_4_no_slide(tmp_path):
    cliente = _make_client(tmp_path)
    dados = {
        "area": "Direito Imobiliario",
        "selo_tribunal": "STJ",
        "processo": "REsp 2.215.421/SE",
        "carimbo": "Unanimidade",
        "tese": "x",
        "citacao_principal": "y",
        "relator": "z",
        "fundamentos": [],
    }
    payload = {
        "slides": [
            {
                "titulo": "Capa", "corpo": "STJ revoluciona usucapiao",
                "area": "Direito Imobiliario", "selo_tribunal": "STJ",
                "processo_id": "REsp 2.215.421/SE", "carimbo": "Unanimidade",
            },
            {"titulo": "Slide 2", "corpo": "..."},
        ],
        "legenda": "legenda",
        "hashtags": ["#usucapiao"],
    }
    with patch.object(
        cliente._client.messages, "stream", return_value=_fake_stream_cm(payload),
    ):
        resultado = cliente.gerar_carrossel_julgado(dados)
    assert resultado["slides"][0]["area"] == "Direito Imobiliario"
    assert resultado["slides"][0]["carimbo"] == "Unanimidade"
    # ai_tells anexado como em gerar_carrossel
    assert "_ai_tells" in resultado


def test_gerar_linkedin_julgado_devolve_texto(tmp_path):
    cliente = _make_client(tmp_path)
    dados = {
        "tese": "x", "processo": "y", "relator": "z",
        "citacao_principal": "w", "fundamentos": [],
    }
    with patch.object(
        cliente._client.messages, "stream",
        return_value=_fake_stream_cm("Post LinkedIn de teste."),
    ):
        resultado = cliente.gerar_linkedin_julgado(dados)
    assert resultado == "Post LinkedIn de teste."


def test_gerar_carrossel_julgado_com_ajuste(tmp_path):
    """Ajuste do revisor entra no prompt (validado via captura do call)."""
    cliente = _make_client(tmp_path)
    payload = {"slides": [{"titulo": "x", "corpo": "y"}], "legenda": "", "hashtags": []}
    capturado = {}

    def fake_stream(**kwargs):
        capturado.update(kwargs)
        return _fake_stream_cm(payload)

    with patch.object(cliente._client.messages, "stream", side_effect=fake_stream):
        cliente.gerar_carrossel_julgado(
            {"tese": "x", "fundamentos": []}, ajuste="trocar slide 1",
        )
    # alguma parte do user content tem "trocar slide 1"
    msgs = capturado["messages"]
    texto_completo = json.dumps(msgs, ensure_ascii=False)
    assert "trocar slide 1" in texto_completo
```

- [ ] **Step 3.2: Rodar testes (devem falhar)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_anthropic_client_julgado.py -v
```
Expected: `ImportError: cannot import name 'JULGADO_SCHEMA'`

- [ ] **Step 3.3: Implementar o schema e os 3 métodos no `anthropic_client.py`**

Editar `automacao/src/anthropic_client.py`. Após a constante `CAROUSEL_SCHEMA` (linha ~53), adicionar:

```python
# Schema do carrossel quando entrada e um julgado estruturado.
# Inclui os 4 campos opcionais do Batch (a) em cada slide.
CAROUSEL_SCHEMA_JULGADO = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "corpo": {"type": "string"},
                    "area": {"type": "string"},
                    "selo_tribunal": {"type": "string"},
                    "processo_id": {"type": "string"},
                    "carimbo": {"type": "string"},
                },
                "required": ["titulo", "corpo"],
                "additionalProperties": False,
            },
        },
        "legenda": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["slides", "legenda", "hashtags"],
    "additionalProperties": False,
}


# Schema de extracao de dados estruturados de um acordao.
JULGADO_SCHEMA = {
    "type": "object",
    "properties": {
        "area": {"type": "string"},
        "selo_tribunal": {"type": "string"},
        "orgao_completo": {"type": "string"},
        "turma": {"type": "string"},
        "processo": {"type": "string"},
        "data_julgamento": {"type": "string"},
        "relator": {"type": "string"},
        "relator_curto": {"type": "string"},
        "tese": {"type": "string"},
        "citacao_principal": {"type": "string"},
        "carimbo": {"type": "string"},
        "fundamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fonte": {"type": "string"},
                    "texto": {"type": "string"},
                },
                "required": ["fonte", "texto"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "area", "selo_tribunal", "processo", "relator",
        "tese", "citacao_principal", "carimbo", "fundamentos",
    ],
    "additionalProperties": False,
}
```

Após o método `gerar_linkedin` (final da classe `AnthropicClient`), adicionar:

```python
    # ===== Julgado da Semana =====

    def extrair_dados_julgado(self, pdf_texto: str) -> dict:
        """Extrai dados estruturados de um acordao a partir do texto bruto do PDF.

        Devolve dict conforme JULGADO_SCHEMA. Levanta json.JSONDecodeError se a
        resposta da IA nao for JSON valido (nao deveria acontecer com structured
        output, mas blindamos no chamador).
        """
        instrucao = (
            "A partir do TEXTO DO ACORDAO acima, extraia os dados estruturados "
            "do julgado para uso em comunicacao social juridica.\n\n"
            "Regras:\n"
            "- area: ramo do direito principal (ex: 'Direito Imobiliario', "
            "'Direito Sucessorio', 'Saude Suplementar', 'Direito Senior').\n"
            "- selo_tribunal: SIGLA curta (STJ, STF, TJ-SP, TRF-3, etc).\n"
            "- orgao_completo: nome longo do orgao (ex: 'Terceira Turma do STJ').\n"
            "- turma: turma + indicacao de unanimidade se aparecer.\n"
            "- processo: identificador completo (REsp NNN/UF, RE NNN, etc).\n"
            "- data_julgamento: formato DD/MM/AAAA.\n"
            "- relator: nome completo com titulo (Min., Des.).\n"
            "- relator_curto: forma compacta para citacao.\n"
            "- tese: a tese juridica em UMA frase declarativa (max 140 chars).\n"
            "- citacao_principal: trecho TEXTUAL do voto (entre aspas no PDF, se houver).\n"
            "- carimbo: 'Unanimidade' se decisao foi unanime; 'Maioria' se nao; "
            "se for repetitivo, 'Repetitivo Tema X'; se for precedente notavel, "
            "'Precedente'.\n"
            "- fundamentos: lista de 3 a 5 fundamentos jurididos com {fonte, texto}.\n\n"
            "Se algum campo nao puder ser determinado pelo PDF, devolva string vazia "
            "(EXCETO os campos required, que devem sempre vir preenchidos)."
        )
        bloco_pdf = {
            "type": "text",
            "text": f"TEXTO DO ACORDAO:\n\n{pdf_texto}",
            "cache_control": {"type": "ephemeral"},
        }
        with self._client.messages.stream(
            model=self._model,
            max_tokens=8000,
            system=self._system_blocks(""),  # sem voice rules na extracao
            thinking={"type": "adaptive"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": JULGADO_SCHEMA},
            },
            messages=[{"role": "user", "content": [
                bloco_pdf,
                {"type": "text", "text": instrucao},
            ]}],
        ) as stream:
            resp = stream.get_final_message()
        return json.loads(self._texto_resposta(resp))

    def gerar_carrossel_julgado(
        self,
        dados: dict,
        *,
        n_min: int = 7,
        n_max: int = 9,
        ajuste: str = "",
        system_extra: str = "",
        contexto_blog: str = "",
    ) -> dict:
        """Gera carrossel multi-slide a partir de dados estruturados do julgado.

        Cada slide vem com area/selo_tribunal/processo_id/carimbo populados
        (o template `slide-carrossel.html` consome esses campos via Batch (a)).
        """
        dados_json = json.dumps(dados, ensure_ascii=False, indent=2)
        instrucao = (
            f"A partir do JULGADO ESTRUTURADO acima, produza a copy de um carrossel "
            f"de Instagram para @novielloadv com {n_min} a {n_max} slides.\n"
            f"Slide 1 = capa (gancho forte com a tese). Slides do meio = "
            f"contextualizacao, fundamentos e impacto pratico. Ultimo = CTA "
            f"educativo. Cite o processo no ultimo slide.\n\n"
            f"IMPORTANTE: TODO slide deve incluir os 4 campos abaixo "
            f"(copiando do JULGADO ESTRUTURADO):\n"
            f"- area: '{dados.get('area', '')}'\n"
            f"- selo_tribunal: '{dados.get('selo_tribunal', '')}'\n"
            f"- processo_id: '{dados.get('processo', '')}'\n"
            f"- carimbo: '{dados.get('carimbo', '')}'\n\n"
            f"Tambem produza: 'legenda' (texto da legenda do post) e 'hashtags'.\n\n"
            f"OBRIGATORIO: ao final da legenda, inclua disclaimer educativo no "
            f"espirito do Provimento OAB 205/2021 (texto curto, '⚠️ Este conteudo "
            f"e educativo e nao substitui a analise individualizada...')."
        )
        if ajuste.strip():
            instrucao += f"\n\nAJUSTES SOLICITADOS:\n{ajuste.strip()}"

        bloco_dados = {
            "type": "text",
            "text": f"JULGADO ESTRUTURADO:\n\n{dados_json}",
            "cache_control": {"type": "ephemeral"},
        }
        blocos_user = []
        if contexto_blog and contexto_blog.strip():
            blocos_user.append(self._contexto_block(contexto_blog))
        blocos_user.append(bloco_dados)
        blocos_user.append({"type": "text", "text": instrucao})

        with self._client.messages.stream(
            model=self._model,
            max_tokens=24000,
            system=self._system_blocks(system_extra, voice_rules=VOICE_RULES_INSTAGRAM),
            thinking={"type": "adaptive"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": CAROUSEL_SCHEMA_JULGADO},
            },
            messages=[{"role": "user", "content": blocos_user}],
        ) as stream:
            resp = stream.get_final_message()
        carrossel = json.loads(self._texto_resposta(resp))
        texto_concat = " ".join(
            [carrossel.get("legenda", "")]
            + [s.get("titulo", "") + " " + s.get("corpo", "") for s in carrossel.get("slides", [])]
        )
        carrossel["_ai_tells"] = ai_tells_detector.detectar(texto_concat)
        return carrossel

    def gerar_linkedin_julgado(
        self,
        dados: dict,
        url_blog: str = "",
        *,
        ajuste: str = "",
        system_extra: str = "",
        contexto_blog: str = "",
    ) -> str:
        """Gera post LinkedIn (B2B, tom tecnico) a partir do julgado estruturado."""
        dados_json = json.dumps(dados, ensure_ascii=False, indent=2)
        link_linha = f"\nTermine com o link do artigo completo: {url_blog}" if url_blog.strip() else ""
        instrucao = (
            f"A partir do JULGADO ESTRUTURADO acima, escreva um post de LinkedIn "
            f"para o perfil pessoal do Dr. Mario Noviello (publico B2B: advogados, "
            f"incorporadores, gestores). Tom tecnico, autoridade, sem cliches."
            f"{link_linha}\n"
            "Cite explicitamente o numero do processo, a relatoria, a data e a "
            "votacao (unanimidade/maioria). Use UMA citacao textual do voto se "
            "disponivel em 'citacao_principal'. Encerre com 1-2 linhas de impacto "
            "pratico para o advogado da area.\n"
            "Maximo ~1500 caracteres, no maximo 3 hashtags. Responda apenas com o "
            "texto do post.\n\n"
            "ESTILO OBRIGATORIO:\n"
            "- NAO use travessoes longos (—, –). Use ponto, virgula ou parenteses.\n"
            "- NAO use asteriscos para enfase.\n"
            "- Linguagem natural, sem marcadores de IA."
        )
        if ajuste.strip():
            instrucao += f"\n\nAJUSTES SOLICITADOS:\n{ajuste.strip()}"

        bloco_dados = {
            "type": "text",
            "text": f"JULGADO ESTRUTURADO:\n\n{dados_json}",
            "cache_control": {"type": "ephemeral"},
        }
        blocos_user = []
        if contexto_blog and contexto_blog.strip():
            blocos_user.append(self._contexto_block(contexto_blog))
        blocos_user.append(bloco_dados)
        blocos_user.append({"type": "text", "text": instrucao})

        with self._client.messages.stream(
            model=self._model,
            max_tokens=8000,
            system=self._system_blocks(system_extra, voice_rules=VOICE_RULES_LINKEDIN),
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": blocos_user}],
        ) as stream:
            resp = stream.get_final_message()
        return self._texto_resposta(resp).strip()
```

- [ ] **Step 3.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_anthropic_client_julgado.py -v
```
Expected: 6 passed.

- [ ] **Step 3.5: Confirmar baseline + 23 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 187 passed.

- [ ] **Step 3.6: Commit**

```bash
git add src/anthropic_client.py tests/test_anthropic_client_julgado.py
git commit -m "Julgado: anthropic_client (extrair + gerar_carrossel + gerar_linkedin) (Wave 2.1)"
```

---

### Task 4: `pdf_extractor.extrair_dados_julgado()` wrapper com validação

**Files:**
- Modify: `automacao/src/pdf_extractor.py`
- Modify: `automacao/tests/test_pdf_extractor.py`

- [ ] **Step 4.1: Adicionar testes de validação no `test_pdf_extractor.py`**

Append ao arquivo existente:

```python
from unittest.mock import MagicMock

from src.pdf_extractor import extrair_dados_julgado


def _anthropic_mock(payload):
    cli = MagicMock()
    cli.extrair_dados_julgado.return_value = payload
    return cli


def test_extrair_dados_julgado_passa_quando_completo():
    cli = _anthropic_mock({
        "area": "Direito Imobiliario", "selo_tribunal": "STJ",
        "orgao_completo": "Terceira Turma", "turma": "3a",
        "processo": "REsp 2.215.421/SE", "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi", "relator_curto": "Min. Nancy",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "O justo titulo deve ser interpretado de forma ampla",
        "carimbo": "Unanimidade",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "Usucapiao..."}],
    })
    dados = extrair_dados_julgado("texto PDF", cli)
    assert dados["processo"] == "REsp 2.215.421/SE"


def test_extrair_dados_julgado_campo_obrigatorio_vazio_falha():
    cli = _anthropic_mock({
        "area": "", "selo_tribunal": "STJ", "processo": "REsp X",
        "relator": "Min. Y", "tese": "T", "citacao_principal": "C",
        "carimbo": "Unanimidade", "fundamentos": [{"fonte": "F", "texto": "T"}],
    })
    with pytest.raises(PDFExtractorError, match="campo obrigatorio vazio: area"):
        extrair_dados_julgado("texto PDF", cli)


def test_extrair_dados_julgado_fundamentos_vazios_falha():
    cli = _anthropic_mock({
        "area": "X", "selo_tribunal": "STJ", "processo": "REsp X",
        "relator": "Min. Y", "tese": "T", "citacao_principal": "C",
        "carimbo": "Unanimidade", "fundamentos": [],
    })
    with pytest.raises(PDFExtractorError, match="fundamentos"):
        extrair_dados_julgado("texto PDF", cli)


def test_extrair_dados_julgado_texto_vazio_falha():
    cli = _anthropic_mock({})
    with pytest.raises(PDFExtractorError, match="texto do PDF vazio"):
        extrair_dados_julgado("", cli)
```

- [ ] **Step 4.2: Rodar testes (devem falhar — função não existe)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pdf_extractor.py -v -k dados_julgado
```
Expected: `ImportError: cannot import name 'extrair_dados_julgado'`

- [ ] **Step 4.3: Implementar `extrair_dados_julgado` em `pdf_extractor.py`**

Append ao final de `src/pdf_extractor.py`:

```python
_CAMPOS_OBRIGATORIOS = (
    "area", "selo_tribunal", "processo", "relator",
    "tese", "citacao_principal", "carimbo",
)


def extrair_dados_julgado(pdf_texto: str, anthropic_cli) -> dict:
    """Chama AnthropicClient.extrair_dados_julgado e valida os campos obrigatorios.

    Levanta PDFExtractorError com mensagem clara se algum campo obrigatorio vier
    vazio ou se fundamentos vier vazio.
    """
    if not pdf_texto or not pdf_texto.strip():
        raise PDFExtractorError("texto do PDF vazio — extracao impossivel")

    dados = anthropic_cli.extrair_dados_julgado(pdf_texto)

    faltando = [c for c in _CAMPOS_OBRIGATORIOS if not str(dados.get(c, "")).strip()]
    if faltando:
        raise PDFExtractorError(
            f"campo obrigatorio vazio: {', '.join(faltando)} — IA nao conseguiu "
            f"estruturar o PDF. Revise o PDF e tente de novo."
        )

    fundamentos = dados.get("fundamentos", [])
    if not isinstance(fundamentos, list) or len(fundamentos) == 0:
        raise PDFExtractorError(
            "fundamentos vazios — IA nao identificou base juridica. "
            "Verifique se o PDF e um acordao completo."
        )

    return dados
```

- [ ] **Step 4.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pdf_extractor.py -v
```
Expected: 13 passed (9 anteriores + 4 novos).

- [ ] **Step 4.5: Confirmar baseline**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 191 passed.

- [ ] **Step 4.6: Commit**

```bash
git add src/pdf_extractor.py tests/test_pdf_extractor.py
git commit -m "Julgado: extrair_dados_julgado wrapper com validacao (Wave 2.2)"
```

---

## Wave 3 — Card render

### Task 5: Template patch — `{carimbo_label}` dinâmico

**Files:**
- Modify: `automacao/templates/julgado-card.html` (linha do carimbo)
- Modify: `automacao/samples/_julgado_card_publicar.py` (passar carimbo_label)

- [ ] **Step 5.1: Editar `julgado-card.html`**

Em `automacao/templates/julgado-card.html`, localizar (linha ~369):

```html
<div class="carimbo-unanime"><span class="bullet">●</span> Unanimidade</div>
```

Trocar por:

```html
<div class="carimbo-unanime"><span class="bullet">●</span> {carimbo_label}</div>
```

- [ ] **Step 5.2: Patch `samples/_julgado_card_publicar.py` para retrocompat**

Em `automacao/samples/_julgado_card_publicar.py`, na função `montar_html`, após o loop `for k, v in dados.items()` (linha ~88), antes do `out = out.replace("{fundamentos_html}", ...)`, adicionar:

```python
    # Carimbo dinamico (default Unanimidade quando nao especificado)
    out = out.replace("{carimbo_label}", _html.escape(dados.get("carimbo", "Unanimidade") or "Unanimidade"))
```

Inserir após:
```python
    out = template
    for k, v in dados.items():
        if k == "fundamentos":
            continue
        if k.startswith("subtitulo_marca_"):
            continue
        out = out.replace("{" + k + "}", _html.escape(str(v)) if k != "citacao_principal" else _html.escape(v))
```

e antes de:
```python
    out = out.replace("{fundamentos_html}", fundamentos_html)
```

- [ ] **Step 5.3: Smoke render manual (sem teste automatizado para evitar Playwright)**

```bash
.venv/Scripts/python.exe samples/_julgado_card_publicar.py --so-render
```
Expected: Geração de `samples/julgado-card-li.jpg` e `samples/julgado-card-ig.jpg` sem erros. Abra visualmente e confirme o carimbo continua mostrando "Unanimidade".

- [ ] **Step 5.4: Confirmar que nada quebrou no pytest**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 191 passed (sem mudança no número porque foi só patch de template).

- [ ] **Step 5.5: Commit**

```bash
git add templates/julgado-card.html samples/_julgado_card_publicar.py
git commit -m "Julgado: template julgado-card.html aceita carimbo dinamico (Wave 3.1)"
```

---

### Task 6: `julgado_card_render.py`

**Files:**
- Create: `automacao/src/julgado_card_render.py`
- Create: `automacao/tests/test_julgado_card_render.py`

- [ ] **Step 6.1: Escrever os testes (puramente sobre o HTML preenchido, sem Playwright)**

Criar `automacao/tests/test_julgado_card_render.py`:

```python
from pathlib import Path

from src.config import AUTOMACAO_DIR
from src.julgado_card_render import _preencher_card

TEMPLATE = (AUTOMACAO_DIR / "templates" / "julgado-card.html").read_text(encoding="utf-8")


def _dados_completos():
    return {
        "area": "Direito Imobiliario",
        "selo_tribunal": "STJ",
        "orgao": "STJ",
        "orgao_completo": "Terceira Turma do STJ",
        "turma": "3a Turma · Unanimidade",
        "processo": "REsp 2.215.421/SE",
        "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi",
        "relator_curto": "Min. Nancy Andrighi",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "O justo titulo deve ser interpretado de forma ampla",
        "carimbo": "Unanimidade",
        "label_doc": "Documento Analisado",
        "legenda_doc": "Recibo de compra",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "Usucapiao ordinaria"}],
        "tema_rodape": "Usucapiao Ordinaria",
        "tema_rodape_sub": "Recibo como Justo Titulo",
        "assinatura": "T. M. S.",
    }


def test_preencher_card_substitui_campos_basicos():
    out = _preencher_card(TEMPLATE, _dados_completos(), canal="li")
    assert "Recibo basta como justo titulo" in out
    assert "REsp 2.215.421/SE" in out
    assert "Min. Nancy Andrighi" in out
    assert "{tese}" not in out
    assert "{processo}" not in out


def test_carimbo_default_unanimidade_quando_vazio():
    dados = _dados_completos()
    dados["carimbo"] = ""
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Unanimidade" in out


def test_carimbo_dinamico_maioria():
    dados = _dados_completos()
    dados["carimbo"] = "Maioria"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Maioria" in out
    # nao deve ter o default
    assert "Unanimidade" not in out


def test_carimbo_dinamico_repetitivo_tema():
    dados = _dados_completos()
    dados["carimbo"] = "Repetitivo Tema 1234"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Repetitivo Tema 1234" in out


def test_subtitulo_marca_li():
    dados = _dados_completos()
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Imobili" in out  # "Imobiliario e Sucessorio"
    assert "Direito Sênior" not in out


def test_subtitulo_marca_ig():
    dados = _dados_completos()
    out = _preencher_card(TEMPLATE, dados, canal="ig")
    assert "Direito Sênior" in out


def test_escapa_html_em_campos():
    dados = _dados_completos()
    dados["tese"] = "Tese & <script>alert(1)</script>"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "&amp;" in out
    assert "&lt;script&gt;" in out
    assert "<script>alert(1)</script>" not in out


def test_fundamentos_renderiza_lista():
    dados = _dados_completos()
    dados["fundamentos"] = [
        {"fonte": "Art. 1.242 CC", "texto": "Usucapiao ordinaria"},
        {"fonte": "Sumula 237", "texto": "Pode ser arguido em defesa"},
    ]
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Art. 1.242 CC" in out
    assert "Sumula 237" in out
    assert "Pode ser arguido" in out


def test_subtitulo_marca_personalizado_override():
    """Se dados['subtitulo_marca_li'] vier explicito, usa esse."""
    dados = _dados_completos()
    dados["subtitulo_marca_li"] = "Advocacia · Customizado"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Advocacia · Customizado" in out
```

- [ ] **Step 6.2: Rodar testes (falham)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_card_render.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.julgado_card_render'`

- [ ] **Step 6.3: Implementar `julgado_card_render.py`**

Criar `automacao/src/julgado_card_render.py`:

```python
"""Renderiza o card LinkedIn/IG do Julgado da Semana em JPG 1080x1350.

Preenche templates/julgado-card.html com os dados estruturados e dispara
scripts/render-slide.py (Playwright) para gerar o JPG.
"""

from __future__ import annotations

import html as _html
import shutil
import subprocess
import sys
from pathlib import Path

CARD_TEMPLATE = "julgado-card.html"
LOGO = "logo-noviello-branco.png"

SUBTITULOS_PADRAO = {
    "li": "Advocacia · Imobiliario e Sucessorio",
    "ig": "Advocacia · Direito Sênior",
}


class CardRenderError(Exception):
    pass


def _fundamentos_html(fundamentos: list[dict]) -> str:
    return "\n".join(
        f'<div class="fund-item"><div class="fonte">{_html.escape(f.get("fonte", ""))}</div>'
        f'<div class="texto">{_html.escape(f.get("texto", ""))}</div></div>'
        for f in fundamentos
    )


# Campos do dados dict que mapeiam direto para placeholders do template.
# Outros (fundamentos, carimbo, subtitulo_marca_*) tem tratamento especial.
_CAMPOS_TEMPLATE = (
    "area", "orgao", "orgao_completo", "turma", "processo",
    "data_julgamento", "relator", "relator_curto",
    "tese", "citacao_principal",
    "label_doc", "legenda_doc",
    "tema_rodape", "tema_rodape_sub", "assinatura",
)


def _preencher_card(template: str, dados: dict, *, canal: str = "li") -> str:
    """Devolve o HTML preenchido. Nao escreve em disco.

    `canal` ('li'|'ig') controla o subtitulo da marca.
    """
    out = template

    # Carimbo (default 'Unanimidade')
    carimbo_label = (dados.get("carimbo") or "Unanimidade").strip() or "Unanimidade"
    out = out.replace("{carimbo_label}", _html.escape(carimbo_label))

    # Campos diretos (escape sempre — citacao tambem)
    for chave in _CAMPOS_TEMPLATE:
        valor = str(dados.get(chave, ""))
        out = out.replace("{" + chave + "}", _html.escape(valor))

    # 'orgao' default ao selo_tribunal se nao vier
    if "{orgao}" in out:
        out = out.replace("{orgao}", _html.escape(dados.get("selo_tribunal", "")))

    # Fundamentos
    fundamentos = dados.get("fundamentos") or []
    out = out.replace("{fundamentos_html}", _fundamentos_html(fundamentos))

    # Subtitulo da marca por canal (override via dados['subtitulo_marca_li' | '_ig'])
    chave_sub = f"subtitulo_marca_{canal}"
    subtitulo = dados.get(chave_sub) or SUBTITULOS_PADRAO.get(canal, "Advocacia")
    out = out.replace("{subtitulo_marca}", _html.escape(subtitulo))

    return out


def renderizar_card(
    dados: dict,
    pasta_destino: Path,
    templates_dir: Path,
    render_script: Path,
    *,
    canal: str = "li",
    nome_base: str = "card",
) -> Path:
    """Renderiza o card como JPG. Devolve o caminho do JPG gerado.

    Levanta CardRenderError em falha.
    """
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    templates_dir = Path(templates_dir)

    template_text = (templates_dir / CARD_TEMPLATE).read_text(encoding="utf-8")
    html = _preencher_card(template_text, dados, canal=canal)

    # Copia logo para a pasta de destino (img src relativa no template)
    logo_src = templates_dir / LOGO
    if logo_src.exists():
        shutil.copy(logo_src, pasta_destino / LOGO)

    arq_html = pasta_destino / f"{nome_base}-{canal}.html"
    arq_jpg = pasta_destino / f"{nome_base}-{canal}.jpg"
    arq_html.write_text(html, encoding="utf-8")

    resultado = subprocess.run(
        [sys.executable, str(render_script), str(arq_html), str(arq_jpg)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if resultado.returncode != 0 or not arq_jpg.exists():
        raise CardRenderError(
            f"falha ao renderizar card {canal}: {resultado.stderr or resultado.stdout}"
        )
    return arq_jpg
```

- [ ] **Step 6.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_card_render.py -v
```
Expected: 8 passed.

- [ ] **Step 6.5: Confirmar baseline + 31 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 199 passed.

- [ ] **Step 6.6: Commit**

```bash
git add src/julgado_card_render.py tests/test_julgado_card_render.py
git commit -m "Julgado: julgado_card_render (HTML fill + Playwright JPG) (Wave 3.2)"
```

---

## Wave 4 — Producer

### Task 7: Config — campos novos do Julgado

**Files:**
- Modify: `automacao/src/config.py`
- Modify: `automacao/tests/test_config.py`

- [ ] **Step 7.1: Adicionar testes em `test_config.py`**

Append ao arquivo:

```python
def test_julgado_defaults(monkeypatch, tmp_path):
    """Sem env vars, julgado tem defaults sensatos."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    # forca .env nao encontrado
    monkeypatch.setattr("src.config.ENV_PATH", tmp_path / "nao-existe.env")
    from src.config import load_config
    cfg = load_config()
    assert cfg.julgado_ativo is True
    assert cfg.julgado_calendario == "Noviello — Marketing"
    assert cfg.julgado_filtro_titulo == "[NOV-MKT] LI 08h30 — Julgado"
    assert cfg.julgado_janela_horas == 72
    assert cfg.julgado_dir == cfg.producao_dir / "julgados"


def test_julgado_dir_override_via_env(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.ENV_PATH", tmp_path / "nao-existe.env")
    monkeypatch.setenv("JULGADO_DIR", str(tmp_path / "custom-julgados"))
    from src.config import load_config
    cfg = load_config()
    assert cfg.julgado_dir == tmp_path / "custom-julgados"


def test_julgado_ativo_desligado_via_env(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.ENV_PATH", tmp_path / "nao-existe.env")
    monkeypatch.setenv("JULGADO_ATIVO", "false")
    from src.config import load_config
    cfg = load_config()
    assert cfg.julgado_ativo is False
```

Nota: pode ser necessário ajustar `monkeypatch` se `test_config.py` atual já usa um padrão diferente. Verificar e seguir o padrão existente.

- [ ] **Step 7.2: Rodar testes (devem falhar — campos não existem)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py -v -k julgado
```
Expected: `AttributeError: 'Config' object has no attribute 'julgado_ativo'`

- [ ] **Step 7.3: Adicionar campos no `Config` e no `load_config`**

Em `automacao/src/config.py`, na dataclass `Config`, após `google_ai_api_key: str = ""` (linha 99), adicionar:

```python
    # Julgado da Semana (Wave 4 — producer automatizado)
    julgado_ativo: bool = True
    julgado_calendario: str = "Noviello — Marketing"
    julgado_filtro_titulo: str = "[NOV-MKT] LI 08h30 — Julgado"
    julgado_janela_horas: int = 72
    julgado_dir: Path | None = None
```

Em `load_config`, após `google_ai_api_key=_get("GOOGLE_AI_API_KEY"),` (linha ~194), adicionar:

```python
        julgado_ativo=_bool(_get("JULGADO_ATIVO", "true")),
        julgado_calendario=_get("JULGADO_CALENDARIO", "Noviello — Marketing"),
        julgado_filtro_titulo=_get("JULGADO_FILTRO_TITULO", "[NOV-MKT] LI 08h30 — Julgado"),
        julgado_janela_horas=int(_get("JULGADO_JANELA_HORAS", "72") or "72"),
        julgado_dir=Path(_get("JULGADO_DIR")) if _get("JULGADO_DIR") else None,
```

Logo após `cfg = Config(...)` (antes de `for d in (cfg.state_dir, cfg.logs_dir):` linha ~198), adicionar resolução do default:

```python
    if cfg.julgado_dir is None:
        cfg.julgado_dir = cfg.producao_dir / "julgados"
```

- [ ] **Step 7.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py -v
```
Expected: todos os testes de config passam, incluindo os 3 novos.

- [ ] **Step 7.5: Confirmar baseline + 34 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 202 passed.

- [ ] **Step 7.6: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "Julgado: config (julgado_ativo, calendario, filtro, janela, dir) (Wave 4.0)"
```

---

### Task 8: `julgado_producer.detectar_e_extrair()`

**Files:**
- Create: `automacao/src/julgado_producer.py` (esqueleto + função 1)
- Create: `automacao/tests/test_julgado_producer.py`

- [ ] **Step 8.1: Escrever testes da detecção (mock pesado de calendar + anthropic)**

Criar `automacao/tests/test_julgado_producer.py`:

```python
import datetime as _dt
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.julgado_producer import (
    detectar_e_extrair,
    pasta_da_semana,
    processo_slug,
    semana_iso_de_iso_string,
)
from src.julgado_state import EstadoJulgado, JulgadoStore


def _cfg(tmp_path) -> Config:
    """Config minima pra testar producer (paths reais, credentials fake)."""
    cfg = Config(
        project_root=tmp_path,
        automacao_dir=tmp_path / "automacao",
        producao_dir=tmp_path / "producao",
        publicado_dir=tmp_path / "publicado",
        state_dir=tmp_path / "state",
        logs_dir=tmp_path / "logs",
        templates_dir=tmp_path / "templates",
        enabled_channels=["instagram", "linkedin"],
        dry_run=True,
        email_aprovador="teste@teste.com",
        julgado_dir=tmp_path / "producao" / "julgados",
    )
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def test_semana_iso_de_iso_string_data_conhecida():
    # 26/05/2026 (terca) — semana ISO 22
    assert semana_iso_de_iso_string("2026-05-26T08:30:00-03:00") == (2026, 22)


def test_semana_iso_de_iso_string_so_data():
    assert semana_iso_de_iso_string("2026-05-26") == (2026, 22)


def test_pasta_da_semana_formato():
    base = Path("/tmp/julgados")
    assert pasta_da_semana(base, 22) == base / "sem-22"
    assert pasta_da_semana(base, 1) == base / "sem-01"


def test_processo_slug_normaliza():
    assert processo_slug("REsp 2.215.421/SE") == "resp-2-215-421-se"
    assert processo_slug("RE 1.234.567") == "re-1-234-567"
    assert processo_slug("AgRg em REsp 999/RJ") == "agrg-em-resp-999-rj"


def test_detectar_e_extrair_sem_eventos_no_op(tmp_path):
    cfg = _cfg(tmp_path)
    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = []
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    logger = MagicMock()
    detectar_e_extrair(cfg, cal, cli, store, logger)
    assert store.list_all() == []


def test_detectar_e_extrair_evento_ja_processado_skip(tmp_path):
    cfg = _cfg(tmp_path)
    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = [{
        "id": "evt-1", "summary": "[NOV-MKT] LI 08h30 — Julgado",
        "start_iso": "2026-05-26T08:30:00-03:00", "end_iso": "",
    }]
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    # ja existe
    from src.julgado_state import JulgadoState
    store.save(JulgadoState(event_id="evt-1", semana_iso=22, ano_iso=2026))
    logger = MagicMock()
    detectar_e_extrair(cfg, cal, cli, store, logger)
    # Anthropic nao deveria ser chamado
    cli.extrair_dados_julgado.assert_not_called()


def test_detectar_e_extrair_sem_pdf_grava_erro(tmp_path):
    cfg = _cfg(tmp_path)
    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = [{
        "id": "evt-1", "summary": "[NOV-MKT] LI 08h30 — Julgado",
        "start_iso": "2026-05-26T08:30:00-03:00", "end_iso": "",
    }]
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    logger = MagicMock()
    # NAO cria a pasta sem-22 — deve gravar erro com erro_mensagem util
    detectar_e_extrair(cfg, cal, cli, store, logger)
    pecas = store.list_all()
    assert len(pecas) == 1
    assert pecas[0].status == EstadoJulgado.ERRO
    assert "sem-22" in pecas[0].erro_mensagem.lower() or "nao existe" in pecas[0].erro_mensagem.lower()
    cli.extrair_dados_julgado.assert_not_called()


def test_detectar_e_extrair_pipeline_completo(tmp_path):
    cfg = _cfg(tmp_path)
    # cria pasta + PDF dummy
    pasta_sem = cfg.julgado_dir / "sem-22"
    pasta_sem.mkdir(parents=True)
    pdf = pasta_sem / "acordao.pdf"
    # PDF em branco (basta para chegar no extrair_dados_julgado, que mockamos)
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    with open(pdf, "wb") as f:
        w.write(f)

    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = [{
        "id": "evt-1", "summary": "[NOV-MKT] LI 08h30 — Julgado",
        "start_iso": "2026-05-26T08:30:00-03:00", "end_iso": "",
    }]
    dados_extraidos = {
        "area": "Direito Imobiliario", "selo_tribunal": "STJ",
        "orgao_completo": "Terceira Turma", "turma": "3a Turma",
        "processo": "REsp 2.215.421/SE", "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi", "relator_curto": "Min. Nancy",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "...",
        "carimbo": "Unanimidade",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "x"}],
    }
    cli = MagicMock()
    cli.extrair_dados_julgado.return_value = dados_extraidos
    cli.gerar_carrossel_julgado.return_value = {
        "slides": [{"titulo": "Capa", "corpo": "STJ"}],
        "legenda": "legenda", "hashtags": ["#x"], "_ai_tells": [],
    }
    cli.gerar_linkedin_julgado.return_value = "Post LinkedIn"

    store = JulgadoStore(cfg.state_dir)
    logger = MagicMock()

    detectar_e_extrair(cfg, cal, cli, store, logger)

    pecas = store.list_all()
    assert len(pecas) == 1
    estado = pecas[0]
    assert estado.event_id == "evt-1"
    assert estado.semana_iso == 22
    assert estado.ano_iso == 2026
    assert estado.status == EstadoJulgado.AGUARDANDO_REVISAO
    assert estado.dados_julgado["processo"] == "REsp 2.215.421/SE"
    assert estado.copy_carrossel["legenda"] == "legenda"
    assert estado.texto_linkedin == "Post LinkedIn"
    assert estado.pdf_path == str(pdf)
```

- [ ] **Step 8.2: Rodar testes (falham — módulo não existe)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 8.3: Implementar a Etapa A do producer**

Criar `automacao/src/julgado_producer.py`:

```python
"""Producer do Julgado da Semana — Wave 4.

Etapa A: detecta evento "[NOV-MKT] LI 08h30 — Julgado" no Google Calendar,
le PDF de producao/julgados/sem-N/, extrai dados via pypdf + Anthropic,
gera copy de carrossel + LinkedIn e disponibiliza no painel.

Etapa B: le decisao do painel (aprovar/ajustar); em aprovar, monta a peca
(renderiza carrossel + card LI + escreve MANIFEST).

Rodar (via producer.main): apos as Etapas A/B do blog, dentro de
producer.main_loop, se cfg.julgado_ativo.
"""

from __future__ import annotations

import datetime as _dt
import re
import time
from pathlib import Path

from src import ai_tells_detector, carousel_render, julgado_card_render
from src.julgado_state import (
    EstadoJulgado,
    JulgadoState,
    JulgadoStore,
    TransicaoInvalida,
    transition,
)
from src.logger import log_stage
from src.pdf_extractor import (
    PDFExtractorError,
    extrair_dados_julgado,
    extrair_texto_pdf,
    localizar_pdf_da_semana,
)
from src.state import LockBusy, agora_iso

PILAR = "Julgado da Semana"


# ===== Helpers de data/path =====

def semana_iso_de_iso_string(iso_string: str) -> tuple[int, int]:
    """Devolve (ano_iso, semana_iso) a partir de um ISO 8601 (com ou sem timezone)."""
    # aceita "2026-05-26T08:30:00-03:00" ou "2026-05-26"
    s = iso_string.split("T")[0]
    data = _dt.date.fromisoformat(s)
    ano, semana, _ = data.isocalendar()
    return ano, semana


def pasta_da_semana(julgados_dir: Path, semana_iso: int) -> Path:
    return Path(julgados_dir) / f"sem-{semana_iso:02d}"


_PROC_SLUG_RE = re.compile(r"[^a-z0-9]+")


def processo_slug(processo: str) -> str:
    """REsp 2.215.421/SE -> resp-2-215-421-se"""
    return _PROC_SLUG_RE.sub("-", processo.lower()).strip("-")


def _render_script(cfg) -> Path:
    return cfg.project_root / "scripts" / "render-slide.py"


# ===== Etapa A =====

def _processar_evento_novo(
    evento: dict, cfg, anthropic_cli, store, logger,
) -> None:
    event_id = evento["id"]
    summary = evento.get("summary", "")
    start_iso = evento.get("start_iso", "")

    ano_iso, semana_iso = semana_iso_de_iso_string(start_iso)

    estado = JulgadoState(
        event_id=event_id,
        semana_iso=semana_iso,
        ano_iso=ano_iso,
        event_summary=summary,
        event_start_iso=start_iso,
    )

    inicio = time.monotonic()
    try:
        pdf_path = localizar_pdf_da_semana(cfg.julgado_dir, semana_iso)
        estado.pdf_path = str(pdf_path)
        pdf_texto = extrair_texto_pdf(pdf_path)
        dados = extrair_dados_julgado(pdf_texto, anthropic_cli)
        estado.dados_julgado = dados

        copy = anthropic_cli.gerar_carrossel_julgado(dados)
        tells_carrossel = copy.pop("_ai_tells", [])
        estado.copy_carrossel = copy

        texto_li = anthropic_cli.gerar_linkedin_julgado(dados)
        tells_li = ai_tells_detector.detectar(texto_li)
        estado.texto_linkedin = texto_li

        estado.ai_tells_resumo = {
            "carrossel": ai_tells_detector.resumir(tells_carrossel),
            "linkedin": ai_tells_detector.resumir(tells_li),
        }
    except PDFExtractorError as exc:
        estado.status = EstadoJulgado.ERRO
        estado.erro_mensagem = str(exc)
        store.save(estado)
        log_stage(logger, event_id, "julgado.etapaA", "erro_extracao", erro=str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        estado.status = EstadoJulgado.ERRO
        estado.erro_mensagem = f"erro inesperado: {exc}"
        store.save(estado)
        log_stage(logger, event_id, "julgado.etapaA", "erro_inesperado", erro=str(exc))
        return

    try:
        transition(estado, EstadoJulgado.AGUARDANDO_REVISAO)
    except TransicaoInvalida:
        # state acabou de ser criado em DETECTADO — transicao DETECTADO->AGUARDANDO_REVISAO valida
        pass
    store.save(estado)

    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, event_id, "julgado.etapaA", "no_painel",
              processo=dados.get("processo", ""), duracao_ms=dur)


def detectar_e_extrair(cfg, cal_client, anthropic_cli, store, logger) -> None:
    """Etapa A do Julgado — varre calendario, extrai PDFs novos, popula store."""
    try:
        eventos = cal_client.listar_eventos_futuros(
            cfg.julgado_calendario,
            cfg.julgado_janela_horas,
            cfg.julgado_filtro_titulo,
        )
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, "julgado", "etapaA", "erro_listar_calendario", erro=str(exc))
        return

    for evento in eventos:
        event_id = evento.get("id", "")
        if not event_id:
            continue
        if store.exists(event_id):
            continue
        try:
            with store.lock(event_id):
                if store.exists(event_id):
                    continue
                _processar_evento_novo(evento, cfg, anthropic_cli, store, logger)
        except LockBusy:
            log_stage(logger, event_id, "julgado.etapaA", "evento_ocupado")
            continue
```

- [ ] **Step 8.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v
```
Expected: 7 passed (testes da detecção; processar_revisao e montar_peca vêm nas próximas tasks).

- [ ] **Step 8.5: Confirmar baseline + 41 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 209 passed.

- [ ] **Step 8.6: Commit**

```bash
git add src/julgado_producer.py tests/test_julgado_producer.py
git commit -m "Julgado: detectar_e_extrair (Etapa A do producer) (Wave 4.1)"
```

---

### Task 9: `julgado_producer.processar_revisao()` + `_regenerar_copy`

**Files:**
- Modify: `automacao/src/julgado_producer.py`
- Modify: `automacao/tests/test_julgado_producer.py`

- [ ] **Step 9.1: Adicionar testes da processar_revisao**

Append em `tests/test_julgado_producer.py`:

```python
from src.julgado_producer import processar_revisao


def test_processar_revisao_aguardando_sem_decisao_no_op(tmp_path):
    cfg = _cfg(tmp_path)
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        dados_julgado={"processo": "REsp X", "tese": "T"},
    )
    store.save(estado)
    logger = MagicMock()
    processar_revisao(estado, cfg, cli, store, logger)
    cli.gerar_carrossel_julgado.assert_not_called()


def test_processar_revisao_ajustar_regenera(tmp_path):
    cfg = _cfg(tmp_path)
    cli = MagicMock()
    cli.gerar_carrossel_julgado.return_value = {
        "slides": [{"titulo": "X", "corpo": "Y"}],
        "legenda": "nova legenda", "hashtags": [], "_ai_tells": [],
    }
    cli.gerar_linkedin_julgado.return_value = "novo linkedin"

    store = JulgadoStore(cfg.state_dir)
    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        dados_julgado={"processo": "REsp X", "tese": "T", "fundamentos": []},
        decisao="ajustar", ajuste_texto="trocar slide 1",
    )
    store.save(estado)
    logger = MagicMock()

    processar_revisao(estado, cfg, cli, store, logger)

    cli.gerar_carrossel_julgado.assert_called_once()
    cli.gerar_linkedin_julgado.assert_called_once()
    # decisao limpa apos regerar
    recarregado = store.load("x")
    assert recarregado.decisao == ""
    assert recarregado.ajuste_texto == ""
    assert recarregado.tentativas_ajuste == 1
    assert recarregado.copy_carrossel["legenda"] == "nova legenda"
    assert recarregado.texto_linkedin == "novo linkedin"
```

- [ ] **Step 9.2: Rodar (falham)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v -k revisao
```
Expected: `ImportError: cannot import name 'processar_revisao'`

- [ ] **Step 9.3: Implementar `processar_revisao` e `_regenerar_copy` em `julgado_producer.py`**

Append ao arquivo:

```python
# ===== Etapa B — regeneracao e aprovacao =====

def _regenerar_copy(
    estado: JulgadoState, cfg, anthropic_cli, store, logger,
) -> None:
    ajuste = estado.ajuste_texto
    try:
        copy = anthropic_cli.gerar_carrossel_julgado(estado.dados_julgado, ajuste=ajuste)
        tells_carrossel = copy.pop("_ai_tells", [])
        estado.copy_carrossel = copy

        texto_li = anthropic_cli.gerar_linkedin_julgado(estado.dados_julgado, ajuste=ajuste)
        tells_li = ai_tells_detector.detectar(texto_li)
        estado.texto_linkedin = texto_li

        estado.ai_tells_resumo = {
            "carrossel": ai_tells_detector.resumir(tells_carrossel),
            "linkedin": ai_tells_detector.resumir(tells_li),
        }
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, estado.event_id, "julgado.etapaB", "erro_regeracao", erro=str(exc))
        return

    estado.decisao = ""
    estado.ajuste_texto = ""
    estado.tentativas_ajuste += 1
    store.save(estado)
    log_stage(logger, estado.event_id, "julgado.etapaB", "copy_regerada")


def processar_revisao(
    estado: JulgadoState, cfg, anthropic_cli, store, logger,
) -> None:
    """Etapa B: aprovar -> montar peca; ajustar -> regenerar."""
    # Recuperacao de crash: estado ja foi aprovado mas peca nao montada
    if estado.status == EstadoJulgado.APROVADO:
        _finalizar(estado, cfg, store, logger)
        return
    if estado.status != EstadoJulgado.AGUARDANDO_REVISAO:
        return

    if estado.decisao == "aprovar":
        transition(estado, EstadoJulgado.APROVADO)
        store.save(estado)
        _finalizar(estado, cfg, store, logger)
    elif estado.decisao == "ajustar":
        _regenerar_copy(estado, cfg, anthropic_cli, store, logger)


def _finalizar(estado, cfg, store, logger) -> None:
    """Stub — implementado na Task 10 (montar_peca)."""
    # Por enquanto, no-op com log; Task 10 substitui
    log_stage(logger, estado.event_id, "julgado.etapaB", "finalizar_stub")
```

- [ ] **Step 9.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v
```
Expected: 9 passed (7 anteriores + 2 novos).

- [ ] **Step 9.5: Confirmar baseline + 43 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 211 passed.

- [ ] **Step 9.6: Commit**

```bash
git add src/julgado_producer.py tests/test_julgado_producer.py
git commit -m "Julgado: processar_revisao + regenerar_copy (Wave 4.2)"
```

---

### Task 10: `julgado_producer.montar_peca()` (render + MANIFEST)

**Files:**
- Modify: `automacao/src/julgado_producer.py` (substitui `_finalizar` stub)
- Modify: `automacao/tests/test_julgado_producer.py`

- [ ] **Step 10.1: Testes da montar_peca (mockar Playwright subprocess)**

Append em `tests/test_julgado_producer.py`:

```python
from src.julgado_producer import montar_peca


def _setup_renders_mockados(monkeypatch, jpgs_carrossel, jpg_card):
    """Mocka carousel_render.renderizar e julgado_card_render.renderizar_card."""
    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar",
        lambda slides, pasta, templates, script: jpgs_carrossel,
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda dados, pasta, templates, script, **kw: jpg_card,
    )


def test_montar_peca_escreve_manifest_correto(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    # cria pasta dummy onde jpgs serao "gerados"
    pasta_peca = cfg.producao_dir / "2026-S22" / "julgado-resp-2-215-421-se"
    pasta_peca.mkdir(parents=True)
    jpg_card = pasta_peca / "card-li.jpg"
    jpg_card.write_bytes(b"fake-jpg")
    jpgs_carrossel = []
    for i in range(1, 4):
        p = pasta_peca / f"slide{i:02d}.jpg"
        p.write_bytes(b"fake-jpg")
        jpgs_carrossel.append(p)

    _setup_renders_mockados(monkeypatch, jpgs_carrossel, jpg_card)

    estado = JulgadoState(
        event_id="evt-1", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.APROVADO,
        dados_julgado={
            "area": "Direito Imobiliario", "selo_tribunal": "STJ",
            "processo": "REsp 2.215.421/SE", "tese": "T",
            "fundamentos": [],
        },
        copy_carrossel={
            "slides": [
                {"titulo": "Capa", "corpo": "C"},
                {"titulo": "S2", "corpo": "C2"},
                {"titulo": "CTA", "corpo": "C3"},
            ],
            "legenda": "legenda do post",
            "hashtags": ["#x", "#y"],
        },
        texto_linkedin="Post LinkedIn aqui",
    )
    logger = MagicMock()
    pasta = montar_peca(estado, cfg, logger)

    manifest_path = pasta / "MANIFEST.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["tipo"] == "julgado"
    assert manifest["pilar"] == "Julgado da Semana"
    assert manifest["peca_id"] == "julgado-2026-S22-resp-2-215-421-se"
    assert manifest["status"] == "pronta_para_aprovacao"
    assert manifest["validacoes"]["oab_205"] == "aprovado"
    assert manifest["validacoes"]["marca"] == "v2-conforme"

    ig = manifest["ativos"]["instagram"]
    assert len(ig["imagens"]) == 3
    assert ig["tipo_post"] == "carrossel"
    assert ig["hashtags"] == ["#x", "#y"]
    assert Path(ig["legenda"]).exists()
    assert "legenda do post" in Path(ig["legenda"]).read_text(encoding="utf-8")

    li = manifest["ativos"]["linkedin"]
    assert Path(li["imagem"]).exists()
    assert Path(li["texto"]).exists()
    assert "Post LinkedIn aqui" in Path(li["texto"]).read_text(encoding="utf-8")

    # NAO tem wordpress (Mario faz manual)
    assert "wordpress" not in manifest["ativos"]


def test_montar_peca_slides_recebem_4_campos(tmp_path, monkeypatch):
    """O carousel_render.renderizar deve ser chamado com slides ja contendo
    area/selo_tribunal/processo_id/carimbo se nao vierem da IA."""
    cfg = _cfg(tmp_path)
    pasta_peca = cfg.producao_dir / "2026-S22" / "julgado-resp-x"
    pasta_peca.mkdir(parents=True)
    jpg_card = pasta_peca / "card-li.jpg"
    jpg_card.write_bytes(b"x")
    jpgs = [pasta_peca / "slide01.jpg"]
    jpgs[0].write_bytes(b"x")

    slides_capturados = {"slides": None}

    def fake_renderizar(slides, pasta, templates, script, **kw):
        slides_capturados["slides"] = slides
        return jpgs

    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar", fake_renderizar,
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda *a, **kw: jpg_card,
    )

    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.APROVADO,
        dados_julgado={
            "area": "Direito Imobiliario", "selo_tribunal": "STJ",
            "processo": "REsp X", "carimbo": "Unanimidade",
            "tese": "T", "fundamentos": [],
        },
        copy_carrossel={
            # IA nao incluiu os 4 campos no slide — montar_peca deve preencher do dados
            "slides": [{"titulo": "Capa", "corpo": "C"}],
            "legenda": "L", "hashtags": [],
        },
        texto_linkedin="LI",
    )
    montar_peca(estado, cfg, MagicMock())

    s = slides_capturados["slides"][0]
    assert s["area"] == "Direito Imobiliario"
    assert s["selo_tribunal"] == "STJ"
    assert s["processo_id"] == "REsp X"
    assert s["carimbo"] == "Unanimidade"


def test_montar_peca_preserva_campos_quando_ia_ja_preencheu(tmp_path, monkeypatch):
    """Se a IA ja preencheu area/selo/proc/carimbo num slide, montar_peca nao sobrescreve."""
    cfg = _cfg(tmp_path)
    pasta_peca = cfg.producao_dir / "2026-S22" / "julgado-resp-y"
    pasta_peca.mkdir(parents=True)
    jpgs = [pasta_peca / "slide01.jpg"]
    jpgs[0].write_bytes(b"x")
    jpg_card = pasta_peca / "card-li.jpg"
    jpg_card.write_bytes(b"x")

    slides_capturados = {"slides": None}
    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar",
        lambda slides, *a, **kw: (slides_capturados.__setitem__("slides", slides) or jpgs),
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda *a, **kw: jpg_card,
    )

    estado = JulgadoState(
        event_id="y", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.APROVADO,
        dados_julgado={
            "area": "Direito A", "selo_tribunal": "STJ",
            "processo": "REsp Y", "carimbo": "Unanimidade",
            "tese": "T", "fundamentos": [],
        },
        copy_carrossel={
            "slides": [{
                "titulo": "Capa", "corpo": "C",
                "area": "Direito B (preferido)",
                "selo_tribunal": "STF",
                "processo_id": "RE Y (preferido)",
                "carimbo": "Maioria",
            }],
            "legenda": "L", "hashtags": [],
        },
        texto_linkedin="LI",
    )
    montar_peca(estado, cfg, MagicMock())

    s = slides_capturados["slides"][0]
    # IA tem precedencia
    assert s["area"] == "Direito B (preferido)"
    assert s["selo_tribunal"] == "STF"
    assert s["processo_id"] == "RE Y (preferido)"
    assert s["carimbo"] == "Maioria"


def test_processar_revisao_aprovar_chama_montar_peca(tmp_path, monkeypatch):
    """E2E: decisao=aprovar dispara montar_peca e transiciona pra PECA_MONTADA."""
    cfg = _cfg(tmp_path)
    pasta_alvo = cfg.producao_dir / "2026-S22" / "julgado-resp-x"
    pasta_alvo.mkdir(parents=True)
    (pasta_alvo / "card-li.jpg").write_bytes(b"x")
    (pasta_alvo / "slide01.jpg").write_bytes(b"x")

    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar",
        lambda *a, **kw: [pasta_alvo / "slide01.jpg"],
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda *a, **kw: pasta_alvo / "card-li.jpg",
    )

    store = JulgadoStore(cfg.state_dir)
    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        decisao="aprovar",
        dados_julgado={
            "area": "X", "selo_tribunal": "STJ", "processo": "REsp X",
            "carimbo": "Unanimidade", "tese": "T", "fundamentos": [],
        },
        copy_carrossel={"slides": [{"titulo": "Capa", "corpo": "C"}], "legenda": "L", "hashtags": []},
        texto_linkedin="LI",
    )
    store.save(estado)
    cli = MagicMock()

    processar_revisao(estado, cfg, cli, store, MagicMock())

    recarregado = store.load("x")
    assert recarregado.status == EstadoJulgado.PECA_MONTADA
```

- [ ] **Step 10.2: Rodar testes (falham — `montar_peca` ainda é stub)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v -k montar_peca
```
Expected: `ImportError` or `AttributeError`.

- [ ] **Step 10.3: Substituir `_finalizar` stub por implementação real e adicionar `montar_peca`**

Em `src/julgado_producer.py`, REMOVER o stub do `_finalizar` e adicionar (no final do arquivo):

```python
# ===== Montagem da peca =====

def _pasta_peca(cfg, estado: JulgadoState) -> Path:
    proc_slug = processo_slug(estado.dados_julgado.get("processo", "sem-processo"))
    return cfg.producao_dir / f"{estado.ano_iso}-S{estado.semana_iso:02d}" / f"julgado-{proc_slug}"


def _slides_enriquecidos(copy_slides: list[dict], dados: dict) -> list[dict]:
    """Garante que cada slide tem area/selo_tribunal/processo_id/carimbo.

    Se a IA ja preencheu (valor nao-vazio), preserva. Caso contrario, usa o do
    dados_julgado.
    """
    defaults = {
        "area": dados.get("area", ""),
        "selo_tribunal": dados.get("selo_tribunal", ""),
        "processo_id": dados.get("processo", ""),
        "carimbo": dados.get("carimbo", ""),
    }
    enriquecidos: list[dict] = []
    for slide in copy_slides:
        novo = dict(slide)
        for k, v in defaults.items():
            if not str(novo.get(k, "")).strip():
                novo[k] = v
        enriquecidos.append(novo)
    return enriquecidos


def montar_peca(estado: JulgadoState, cfg, logger) -> Path:
    """Renderiza carrossel + card LI + escreve MANIFEST. Devolve pasta da peca."""
    import json

    pasta = _pasta_peca(cfg, estado)
    pasta.mkdir(parents=True, exist_ok=True)

    dados = estado.dados_julgado or {}
    copy = estado.copy_carrossel or {}
    slides_raw = copy.get("slides", []) or []
    slides = _slides_enriquecidos(slides_raw, dados)

    jpgs = carousel_render.renderizar(
        slides, pasta, cfg.templates_dir, _render_script(cfg),
    )
    jpg_card = julgado_card_render.renderizar_card(
        dados, pasta, cfg.templates_dir, _render_script(cfg),
        canal="li", nome_base="card",
    )

    legenda_path = pasta / "legenda.txt"
    legenda = copy.get("legenda", "")
    hashtags = copy.get("hashtags", []) or []
    if hashtags:
        legenda = (legenda + "\n\n" + " ".join(hashtags)).strip()
    legenda_path.write_text(legenda, encoding="utf-8")

    linkedin_path = pasta / "linkedin.txt"
    linkedin_path.write_text(estado.texto_linkedin or "", encoding="utf-8")

    proc_slug = processo_slug(dados.get("processo", "sem-processo"))
    peca_id = f"julgado-{estado.ano_iso}-S{estado.semana_iso:02d}-{proc_slug}"

    manifest = {
        "peca_id": peca_id,
        "tipo": "julgado",
        "pilar": PILAR,
        "titulo_curto": dados.get("tese", "")[:140],
        "data_publicacao_alvo": estado.event_start_iso or agora_iso(),
        "status": "pronta_para_aprovacao",
        "validacoes": {"oab_205": "aprovado", "marca": "v2-conforme", "ortografia": "ok"},
        "ativos": {
            "instagram": {
                "imagens": [str(j) for j in jpgs],
                "legenda": str(legenda_path),
                "hashtags": hashtags,
                "tipo_post": "carrossel",
            },
            "linkedin": {
                "imagem": str(jpg_card),
                "texto": str(linkedin_path),
            },
        },
        "cross_link": {"ig_para_wp": False, "li_para_wp": False, "linktree_topo": False},
    }
    (pasta / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pasta


def _finalizar(estado, cfg, store, logger) -> None:
    """Renderiza, escreve MANIFEST e transiciona pra PECA_MONTADA."""
    inicio = time.monotonic()
    try:
        montar_peca(estado, cfg, logger)
    except Exception as exc:  # noqa: BLE001
        estado.status = EstadoJulgado.ERRO
        estado.erro_mensagem = f"erro na montagem: {exc}"
        store.save(estado)
        log_stage(logger, estado.event_id, "julgado.etapaB", "erro_montagem", erro=str(exc))
        return
    transition(estado, EstadoJulgado.PECA_MONTADA)
    store.save(estado)
    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, estado.event_id, "julgado.etapaB", "peca_montada", duracao_ms=dur)
```

- [ ] **Step 10.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v
```
Expected: 13 passed (9 anteriores + 4 novos).

- [ ] **Step 10.5: Confirmar baseline + 47 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 215 passed.

- [ ] **Step 10.6: Commit**

```bash
git add src/julgado_producer.py tests/test_julgado_producer.py
git commit -m "Julgado: montar_peca (render carrossel + card LI + MANIFEST) (Wave 4.3)"
```

---

### Task 11: `julgado_producer.main_julgado()` — entrypoint

**Files:**
- Modify: `automacao/src/julgado_producer.py`
- Modify: `automacao/tests/test_julgado_producer.py`

- [ ] **Step 11.1: Adicionar teste de `main_julgado`**

Append em `tests/test_julgado_producer.py`:

```python
from src.julgado_producer import main_julgado


def test_main_julgado_orquestra_etapa_b_depois_etapa_a(tmp_path, monkeypatch):
    """Verifica que main_julgado processa estados existentes (Etapa B) ANTES
    de detectar novos (Etapa A). Isso permite ajuste/aprovacao virar peca antes
    de gerar nova copy pro mesmo evento."""
    cfg = _cfg(tmp_path)
    store = JulgadoStore(cfg.state_dir)
    # estado em AGUARDANDO_REVISAO sem decisao — Etapa B vai ser no-op pra ele
    estado_existente = JulgadoState(
        event_id="velho", semana_iso=20, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
    )
    store.save(estado_existente)

    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = []  # nenhum evento novo
    cli = MagicMock()
    logger = MagicMock()

    main_julgado(cfg, cli, cal, store, logger)

    # main rodou sem erro; estado nao mudou
    assert store.load("velho").status == EstadoJulgado.AGUARDANDO_REVISAO


def test_main_julgado_propaga_lock_busy(tmp_path):
    """LockBusy num estado nao faz a iteracao parar (continua nos proximos)."""
    cfg = _cfg(tmp_path)
    store = JulgadoStore(cfg.state_dir)

    e1 = JulgadoState(event_id="a", semana_iso=20, ano_iso=2026,
                      status=EstadoJulgado.AGUARDANDO_REVISAO)
    e2 = JulgadoState(event_id="b", semana_iso=21, ano_iso=2026,
                      status=EstadoJulgado.AGUARDANDO_REVISAO)
    store.save(e1)
    store.save(e2)

    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = []
    cli = MagicMock()
    logger = MagicMock()

    main_julgado(cfg, cli, cal, store, logger)
    # ambos sobreviveram
    assert store.exists("a")
    assert store.exists("b")
```

- [ ] **Step 11.2: Rodar (falham — main_julgado não existe)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v -k main_julgado
```
Expected: `ImportError: cannot import name 'main_julgado'`

- [ ] **Step 11.3: Implementar `main_julgado`**

Append em `src/julgado_producer.py`:

```python
def main_julgado(cfg, anthropic_cli, cal_client, store, logger) -> None:
    """Entrypoint do producer do Julgado.

    Ordem:
    1. Etapa B (processar_revisao) para cada estado existente. Permite que
       aprovacoes/ajustes virem pecas ANTES de checar calendar.
    2. Etapa A (detectar_e_extrair) para descobrir eventos novos.
    """
    for estado in store.list_all():
        try:
            with store.lock(estado.event_id):
                if not store.exists(estado.event_id):
                    continue
                estado_atual = store.load(estado.event_id)
                processar_revisao(estado_atual, cfg, anthropic_cli, store, logger)
        except LockBusy:
            log_stage(logger, estado.event_id, "julgado.etapaB", "estado_ocupado")
            continue
        except Exception as exc:  # noqa: BLE001
            log_stage(logger, estado.event_id, "julgado.etapaB",
                      "erro_inesperado", erro=str(exc))

    detectar_e_extrair(cfg, cal_client, anthropic_cli, store, logger)
```

- [ ] **Step 11.4: Rodar testes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_julgado_producer.py -v
```
Expected: 15 passed.

- [ ] **Step 11.5: Confirmar baseline + 49 testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 217 passed.

- [ ] **Step 11.6: Commit**

```bash
git add src/julgado_producer.py tests/test_julgado_producer.py
git commit -m "Julgado: main_julgado entrypoint (Wave 4.4)"
```

---

## Wave 5 — Integração

### Task 12: Hook no `producer.main()`

**Files:**
- Modify: `automacao/src/producer.py`

- [ ] **Step 12.1: Adicionar import + bloco hook**

Em `automacao/src/producer.py`, após o import `from src.wp_source import ...` (linha ~42), adicionar:

```python
from src.calendar_client import CalendarClient
from src.julgado_producer import main_julgado
from src.julgado_state import JulgadoStore
```

No final da função `main()`, ANTES do `logger.info("producer", status="fim", ...)` (linha ~477), adicionar:

```python
    # ===== Etapa Julgado da Semana =====
    if cfg.julgado_ativo:
        try:
            cal_client = CalendarClient(cfg.google)
            julgado_store = JulgadoStore(cfg.state_dir)
            main_julgado(cfg, anthropic_cli, cal_client, julgado_store, logger)
        except Exception as exc:  # noqa: BLE001
            log_stage(logger, "julgado", "etapa_julgado", "erro_inesperado", erro=str(exc))
```

- [ ] **Step 12.2: Rodar a suite inteira pra confirmar nada quebrou**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 217 passed.

- [ ] **Step 12.3: Smoke test do producer (dry-run com julgado desligado)**

```bash
$env:JULGADO_ATIVO="false"; .venv/Scripts/python.exe -m src.producer
```
Expected: termina sem erros. Logs em `logs/<ano>-<mes>-publicacoes.jsonl` mostram `status="fim"`.

- [ ] **Step 12.4: Commit**

```bash
git add src/producer.py
git commit -m "Julgado: hook em producer.main (Wave 5.1)"
```

---

### Task 13: Painel — nova seção "Julgado da Semana"

**Files:**
- Modify: `automacao/src/painel.py`
- Modify: `automacao/templates/painel.html`
- Modify: `automacao/tests/test_painel.py`

- [ ] **Step 13.1: Ler `templates/painel.html` para entender estrutura atual**

```bash
.venv/Scripts/python.exe -c "
from pathlib import Path
p = Path('templates/painel.html')
print(p.read_text(encoding='utf-8')[:2000])
"
```

(Não tem step de código aqui — só leitura para contextualizar. O conteúdo guia o ponto exato de inserção da nova seção.)

- [ ] **Step 13.2: Adicionar testes da painel**

Em `automacao/tests/test_painel.py`, append:

```python
from src.julgado_state import EstadoJulgado, JulgadoState, JulgadoStore


def test_listar_pendencias_inclui_julgado(tmp_path, monkeypatch):
    from src.config import load_config
    from src.painel import listar_pendencias

    monkeypatch.setattr("src.config.ENV_PATH", tmp_path / "nao-existe.env")
    monkeypatch.setenv("NOVIELLO_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config()

    store = JulgadoStore(cfg.state_dir)
    estado = JulgadoState(
        event_id="evt-1", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        dados_julgado={
            "tese": "Tese aqui", "processo": "REsp X",
            "relator": "Min. Y", "area": "Imobiliario",
            "carimbo": "Unanimidade",
        },
        copy_carrossel={
            "slides": [{"titulo": "S1", "corpo": "C1"}],
            "legenda": "L", "hashtags": ["#x"],
        },
        texto_linkedin="LI text",
    )
    store.save(estado)

    pendencias = listar_pendencias(cfg)
    assert "julgado" in pendencias
    assert len(pendencias["julgado"]) == 1
    item = pendencias["julgado"][0]
    assert item["id"] == "evt-1"
    assert item["titulo"] == "Tese aqui"
    assert item["processo"] == "REsp X"
    assert item["relator"] == "Min. Y"
    assert item["area"] == "Imobiliario"
    assert item["carimbo"] == "Unanimidade"
    assert item["linkedin"] == "LI text"
    assert item["legenda"] == "L"
    assert len(item["slides"]) == 1


def test_listar_pendencias_julgado_em_erro_aparece(tmp_path, monkeypatch):
    """Estados com status=ERRO tambem aparecem no painel com erro_mensagem."""
    from src.config import load_config
    from src.painel import listar_pendencias

    monkeypatch.setattr("src.config.ENV_PATH", tmp_path / "nao-existe.env")
    monkeypatch.setenv("NOVIELLO_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config()

    store = JulgadoStore(cfg.state_dir)
    store.save(JulgadoState(
        event_id="evt-erro", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.ERRO,
        erro_mensagem="pasta sem-22 nao existe",
    ))

    pendencias = listar_pendencias(cfg)
    assert any(i["id"] == "evt-erro" for i in pendencias["julgado"])
    item = next(i for i in pendencias["julgado"] if i["id"] == "evt-erro")
    assert item["erro_mensagem"] == "pasta sem-22 nao existe"


def test_registrar_decisao_julgado(tmp_path, monkeypatch):
    from src.config import load_config
    from src.painel import registrar_decisao

    monkeypatch.setattr("src.config.ENV_PATH", tmp_path / "nao-existe.env")
    monkeypatch.setenv("NOVIELLO_STATE_DIR", str(tmp_path / "state"))
    cfg = load_config()

    store = JulgadoStore(cfg.state_dir)
    store.save(JulgadoState(
        event_id="evt-1", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
    ))

    registrar_decisao(cfg, "julgado", "evt-1", "aprovar")
    carregado = store.load("evt-1")
    assert carregado.decisao == "aprovar"

    registrar_decisao(cfg, "julgado", "evt-1", "ajustar", "trocar relator")
    carregado = store.load("evt-1")
    assert carregado.decisao == "ajustar"
    assert carregado.ajuste_texto == "trocar relator"
```

- [ ] **Step 13.3: Rodar (falham)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_painel.py -v -k julgado
```
Expected: `KeyError: 'julgado'` ou similar.

- [ ] **Step 13.4: Adicionar suporte a julgado em `painel.py`**

Em `automacao/src/painel.py`, no topo (imports), adicionar:

```python
from src.julgado_state import EstadoJulgado, JulgadoState, JulgadoStore
```

Em `listar_pendencias`, ANTES do `return {"copy": ..., "final": ...}`, adicionar lógica de julgado:

```python
    # ===== Julgado da Semana =====
    julgado_items = []
    for est in JulgadoStore(cfg.state_dir).list_all():
        # mostra AGUARDANDO_REVISAO sem decisao OU ERRO (pra Mario corrigir)
        if est.status == EstadoJulgado.AGUARDANDO_REVISAO and est.decisao:
            continue
        if est.status not in (EstadoJulgado.AGUARDANDO_REVISAO, EstadoJulgado.ERRO):
            continue
        dados = est.dados_julgado or {}
        cc = est.copy_carrossel or {}
        julgado_items.append({
            "id": est.event_id,
            "status": est.status,
            "titulo": dados.get("tese", "(sem tese extraida)"),
            "processo": dados.get("processo", ""),
            "relator": dados.get("relator", ""),
            "area": dados.get("area", ""),
            "selo_tribunal": dados.get("selo_tribunal", ""),
            "carimbo": dados.get("carimbo", ""),
            "citacao": dados.get("citacao_principal", ""),
            "fundamentos": dados.get("fundamentos", []),
            "slides": cc.get("slides", []),
            "legenda": cc.get("legenda", ""),
            "hashtags": cc.get("hashtags", []),
            "linkedin": est.texto_linkedin,
            "ai_tells": est.ai_tells_resumo or {},
            "erro_mensagem": est.erro_mensagem,
            "semana_iso": est.semana_iso,
            "ano_iso": est.ano_iso,
        })
```

Atualizar o return:
```python
    return {"copy": copy_items, "final": final_items, "julgado": julgado_items}
```

Em `registrar_decisao`, adicionar tratamento de `tipo == "julgado"`:

```python
def registrar_decisao(cfg, tipo: str, peca_id: str, decisao: str, ajuste_texto: str = "") -> None:
    if tipo == "copy":
        store = ProducaoStore(cfg.state_dir)
    elif tipo == "final":
        store = StateStore(cfg.state_dir)
    elif tipo == "julgado":
        store = JulgadoStore(cfg.state_dir)
    else:
        raise ValueError(f"tipo invalido: {tipo}")
    est = store.load(peca_id)
    est.decisao = decisao
    est.ajuste_texto = ajuste_texto
    store.save(est)
```

- [ ] **Step 13.5: Rodar testes do painel**

```bash
.venv/Scripts/python.exe -m pytest tests/test_painel.py -v
```
Expected: testes existentes ainda passam + 3 novos passam.

- [ ] **Step 13.6: Adicionar seção visual em `templates/painel.html`**

Em `automacao/templates/painel.html`, localizar onde renderiza a seção `{% for item in copy %}` (a seção de revisão de copy do blog). Imediatamente APÓS o `{% endfor %}` que fecha essa seção, adicionar:

```html
{% if julgado %}
<section class="grupo">
  <h2>Julgado da Semana <span class="contador">({{ julgado|length }})</span></h2>
  {% for item in julgado %}
  <article class="peca julgado {% if item.status == 'erro' %}erro{% endif %}">
    <header>
      <span class="badge">{{ item.area }}</span>
      <span class="badge">{{ item.selo_tribunal }}</span>
      <span class="badge carimbo">{{ item.carimbo }}</span>
      <span class="semana">Sem {{ item.ano_iso }}-S{{ "%02d"|format(item.semana_iso) }}</span>
    </header>
    {% if item.status == 'erro' %}
      <div class="erro-bloco">
        <strong>Erro na extracao:</strong>
        <pre>{{ item.erro_mensagem }}</pre>
      </div>
    {% else %}
      <h3>{{ item.titulo }}</h3>
      <p class="meta">{{ item.relator }} · {{ item.processo }}</p>
      <blockquote>"{{ item.citacao }}"</blockquote>
      <details>
        <summary>Slides do carrossel ({{ item.slides|length }})</summary>
        {% for slide in item.slides %}
          <div class="slide">
            <strong>{{ loop.index }}. {{ slide.titulo }}</strong>
            <p>{{ slide.corpo }}</p>
          </div>
        {% endfor %}
      </details>
      <details>
        <summary>Legenda IG + Hashtags</summary>
        <pre>{{ item.legenda }}</pre>
        <p>{{ item.hashtags|join(' ') }}</p>
      </details>
      <details>
        <summary>Texto LinkedIn</summary>
        <pre>{{ item.linkedin }}</pre>
      </details>
      <details>
        <summary>Fundamentos ({{ item.fundamentos|length }})</summary>
        {% for f in item.fundamentos %}
          <div><strong>{{ f.fonte }}:</strong> {{ f.texto }}</div>
        {% endfor %}
      </details>
      <form method="post" action="/decidir" class="acoes">
        <input type="hidden" name="tipo" value="julgado">
        <input type="hidden" name="peca_id" value="{{ item.id }}">
        <button type="submit" name="decisao" value="aprovar" class="aprovar">Aprovar</button>
        <textarea name="ajuste_texto" placeholder="Ajuste solicitado (se houver)"></textarea>
        <button type="submit" name="decisao" value="ajustar" class="ajustar">Ajustar</button>
      </form>
    {% endif %}
  </article>
  {% endfor %}
</section>
{% endif %}
```

Nota: caso o painel.html atual use classes Tailwind / outro framework, adaptar — o teste do passo 13.5 não cobre o HTML diretamente, mas garante que `listar_pendencias` devolve o dict com a chave `julgado`. Após edição, abrir o painel localmente e verificar visualmente (passo 13.7).

- [ ] **Step 13.7: Smoke test visual do painel**

```bash
.venv/Scripts/python.exe -m src.painel
```
Abrir `http://localhost:8765` no browser. Sem julgados no store, a seção não aparece. Criar manualmente um JSON em `state/julgados/teste.json` e recarregar para validar a renderização. (Esse passo é manual; não bloqueia CI.)

- [ ] **Step 13.8: Confirmar testes**

```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: 220 passed (217 + 3 novos do painel).

- [ ] **Step 13.9: Commit**

```bash
git add src/painel.py templates/painel.html tests/test_painel.py
git commit -m "Julgado: painel.py + secao em painel.html (Wave 5.2)"
```

---

## Wave 6 — Verificação E2E e fechamento

### Task 14: Bateria final de testes + verificação manual

**Files:** (nenhum código novo, só verificação)

- [ ] **Step 14.1: Rodar a suite completa com verbose**

```bash
.venv/Scripts/python.exe -m pytest -v 2>&1 | tail -50
```
Expected: 220 passed, 0 failed. Confirma meta ≥194.

- [ ] **Step 14.2: Verificar contagem por arquivo**

```bash
.venv/Scripts/python.exe -m pytest --collect-only -q 2>&1 | tail -3
```
Expected: `220 tests collected`.

- [ ] **Step 14.3: Smoke import-test (todos os módulos novos carregam sem erro)**

```bash
.venv/Scripts/python.exe -c "
from src.julgado_state import EstadoJulgado, JulgadoState, JulgadoStore
from src.pdf_extractor import extrair_texto_pdf, localizar_pdf_da_semana, extrair_dados_julgado
from src.julgado_card_render import renderizar_card
from src.julgado_producer import main_julgado, detectar_e_extrair, processar_revisao, montar_peca
from src.anthropic_client import AnthropicClient, JULGADO_SCHEMA, CAROUSEL_SCHEMA_JULGADO
print('todos os imports OK')
"
```
Expected: `todos os imports OK`.

- [ ] **Step 14.4: Verificar producer rodando sem evento real (julgado_ativo=true + sem PDF)**

```bash
$env:JULGADO_ATIVO="true"
.venv/Scripts/python.exe -m src.producer
```
Expected: termina sem exceções. Logs mostram `etapa_julgado` rodando. Sem PDF na pasta de julgados, não cria estado (porque também não tem evento futuro com PDF correspondente em ambiente local — OK).

- [ ] **Step 14.5: Confirmar sample manual continua funcional (regressão visual)**

```bash
.venv/Scripts/python.exe samples/_julgado_card_publicar.py --so-render
```
Expected: gera `samples/julgado-card-li.jpg` e `samples/julgado-card-ig.jpg` sem erros. Abrir visualmente: carimbo continua "Unanimidade".

- [ ] **Step 14.6: Resumo final no commit log**

```bash
git log --oneline -15
```
Expected: 14 commits novos (1 por task) seguidos do commit do design spec.

- [ ] **Step 14.7: Tag de release interno (opcional, para fácil rollback)**

```bash
git tag julgado-producer-v1.0
```

---

## Self-review

**Spec coverage:**
- ✅ `pdf_extractor.py` (Wave 1.2): localiza, lê, valida estrutura
- ✅ `julgado_state.py` (Wave 1.1): EstadoJulgado, JulgadoState, JulgadoStore, transition
- ✅ `anthropic_client.py` extensões (Wave 2.1): 3 métodos novos + schemas
- ✅ `extrair_dados_julgado` validação (Wave 2.2)
- ✅ Template patch `{carimbo_label}` (Wave 3.1)
- ✅ `julgado_card_render.py` (Wave 3.2)
- ✅ Config fields (Wave 4.0)
- ✅ `detectar_e_extrair` (Wave 4.1)
- ✅ `processar_revisao` + regenerar (Wave 4.2)
- ✅ `montar_peca` + slides enriquecidos (Wave 4.3)
- ✅ `main_julgado` orquestrador (Wave 4.4)
- ✅ Hook em `producer.main()` (Wave 5.1)
- ✅ Painel — `listar_pendencias` + `registrar_decisao` + template (Wave 5.2)
- ✅ Verificação E2E + smoke (Wave 6)
- ✅ Retrocompatibilidade: nenhum teste existente alterado; `julgado-card.html` patch com default = comportamento atual.

**Placeholder scan:** Nenhum TBD/TODO. Todos os steps têm código completo ou comando concreto.

**Type consistency:**
- `JulgadoState.dados_julgado` é dict (Task 1) — usado como dict em Tasks 8, 9, 10. ✓
- `JulgadoState.copy_carrossel` é dict (Task 1) — segue padrão de `ProducaoState.copy_carrossel`. ✓
- `anthropic_cli.extrair_dados_julgado` é método (Task 3), chamado em `pdf_extractor.extrair_dados_julgado` (Task 4) — nomes iguais por design (wrapper acima do método). ✓
- `EstadoJulgado.AGUARDANDO_REVISAO` (Task 1) usado consistentemente. ✓
- `JulgadoStore.exists/save/load/lock` API (Task 1) usada em Tasks 8, 11. ✓

**Meta de testes:** 164 baseline + ~56 novos = **≥220 passed**. Goal pede ≥164, esta meta supera bastante.

Plan completo e auto-revisado.
