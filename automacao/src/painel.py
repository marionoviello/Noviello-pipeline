"""Painel de aprovacao local — servidor Flask em 127.0.0.1:8765.

Lista as pecas pendentes (revisao de copy + aprovacao final), mostra arte e copy,
e grava a decisao do Mario (Aprovar / Ajustar) de volta no arquivo de estado.
Os scripts agendados (poller, producer) leem essa decisao na proxima rodada.

Rodar:  .venv\\Scripts\\python.exe -m src.painel
"""

from __future__ import annotations

from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from src.cadencia_state import CadenciaState
from src.config import load_config
from src.health import status_geral
from src.manifest import carregar_manifest
from src.producer_state import EstadoProd, ProducaoStore
from src.state import Estado, StateStore

PORTA = 8765
PAINEL_URL = f"http://localhost:{PORTA}"


def listar_pendencias(cfg) -> dict:
    """Devolve {'copy': [...], 'final': [...]} com as pecas aguardando decisao."""
    copy_items = []
    for est in ProducaoStore(cfg.state_dir).list_all():
        if est.status == EstadoProd.AGUARDANDO_REVISAO_COPY and not est.decisao:
            cc = est.copy_carrossel or {}
            copy_items.append(
                {
                    "id": est.post_id,
                    "titulo": est.titulo,
                    "slides": cc.get("slides", []),
                    "legenda": cc.get("legenda", ""),
                    "hashtags": cc.get("hashtags", []),
                    "linkedin": est.texto_linkedin,
                    "ai_tells": est.ai_tells_resumo or {},
                }
            )

    final_items = []
    for est in StateStore(cfg.state_dir).list_all():
        if est.status == Estado.AGUARDANDO_APROVACAO and not est.decisao:
            item = {"id": est.peca_id, "titulo": est.peca_id, "slides_arts": [],
                    "legenda": "", "linkedin": ""}
            try:
                peca = carregar_manifest(Path(est.manifest_path))
                item["titulo"] = peca.titulo_curto
                ig = peca.ativos("instagram") or {}
                item["slides_arts"] = [Path(p).name for p in ig.get("imagens", [])]
                if ig.get("legenda") and Path(ig["legenda"]).exists():
                    item["legenda"] = Path(ig["legenda"]).read_text(encoding="utf-8")
                li = peca.ativos("linkedin") or {}
                if li.get("texto") and Path(li["texto"]).exists():
                    item["linkedin"] = Path(li["texto"]).read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
            final_items.append(item)

    return {"copy": copy_items, "final": final_items}


def registrar_decisao(cfg, tipo: str, peca_id: str, decisao: str, ajuste_texto: str = "") -> None:
    """Grava a decisao no arquivo de estado da peca (producer-state ou watcher-state)."""
    if tipo == "copy":
        store = ProducaoStore(cfg.state_dir)
    elif tipo == "final":
        store = StateStore(cfg.state_dir)
    else:
        raise ValueError(f"tipo invalido: {tipo}")
    est = store.load(peca_id)
    est.decisao = decisao
    est.ajuste_texto = ajuste_texto
    store.save(est)


def status_cadencia(cfg) -> dict:
    """Resumo do estado da cadencia para o painel."""
    state = CadenciaState.carregar(cfg.state_dir)
    # ordena as ultimas 5 promocoes por promovido_em (mais recente primeiro)
    historico = sorted(
        (
            {"event_id": eid, **dados}
            for eid, dados in (state.eventos_promovidos or {}).items()
        ),
        key=lambda x: x.get("promovido_em_iso", ""),
        reverse=True,
    )[:5]
    return {
        "ativa_painel": state.ativa,
        "ativa_env": cfg.cadencia_ativa,
        "ultimo_run": state.ultimo_run_iso or "(nunca)",
        "calendario": cfg.cadencia_calendario,
        "janela_horas": cfg.cadencia_janela_horas,
        "filtro_titulo": cfg.cadencia_filtro_titulo,
        "categoria_backlog": cfg.wp_categoria_backlog,
        "total_promovidos": len(state.eventos_promovidos or {}),
        "historico": historico,
    }


def alternar_cadencia(cfg, ativa: bool) -> None:
    state = CadenciaState.carregar(cfg.state_dir)
    state.ativa = bool(ativa)
    state.salvar(cfg.state_dir)


def _pasta_da_peca(cfg, peca_id: str) -> Path | None:
    """Pasta onde estao os JPGs de uma peca em aprovacao final."""
    store = StateStore(cfg.state_dir)
    if not store.exists(peca_id):
        return None
    return Path(store.load(peca_id).manifest_path).parent


def criar_app(cfg) -> Flask:
    app = Flask(__name__, template_folder=str(cfg.templates_dir))

    @app.get("/")
    def index():
        return render_template(
            "painel.html",
            painel_url=PAINEL_URL,
            cadencia=status_cadencia(cfg),
            **listar_pendencias(cfg),
        )

    @app.post("/cadencia/toggle")
    def cadencia_toggle():
        nova = request.form.get("ativa", "false").lower() in {"1", "true", "yes", "on"}
        alternar_cadencia(cfg, nova)
        return redirect(url_for("index"))

    @app.get("/health")
    @app.get("/health.json")
    def health_json():
        snapshot = status_geral(cfg)
        # HTTP 200 se ok, 503 se nao (compativel com Uptime Kuma)
        return jsonify(snapshot), 200 if snapshot["ok"] else 503

    @app.get("/health.html")
    def health_html():
        snapshot = status_geral(cfg)
        return render_template("health.html", snapshot=snapshot)

    @app.get("/arte/<peca_id>/<arquivo>")
    def arte(peca_id: str, arquivo: str):
        pasta = _pasta_da_peca(cfg, peca_id)
        if pasta is None or not pasta.is_dir():
            abort(404)
        return send_from_directory(str(pasta), arquivo)

    @app.post("/decidir")
    def decidir():
        registrar_decisao(
            cfg,
            request.form["tipo"],
            request.form["peca_id"],
            request.form["decisao"],
            request.form.get("ajuste_texto", "").strip(),
        )
        return redirect(url_for("index"))

    return app


def main() -> int:
    cfg = load_config()
    from src.heartbeat import bater
    bater(cfg.state_dir, "painel")
    app = criar_app(cfg)
    app.run(host="127.0.0.1", port=PORTA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
