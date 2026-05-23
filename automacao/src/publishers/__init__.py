"""Registro de publishers e orquestracao de publicacao por canal.

publicar_canal aplica, em ordem: ativos no MANIFEST -> canal habilitado -> credencial
-> circuit breaker -> DRY_RUN -> publicacao real.
"""

from __future__ import annotations

from src.circuit import canal_pausado, registrar_falha, registrar_sucesso
from src.publish_result import OK, PublishResult
from src.publishers import instagram, linkedin, wordpress

PUBLISHERS = {
    "instagram": instagram,
    "linkedin": linkedin,
    "wordpress": wordpress,
}


def publicar_canal(canal: str, peca, cfg, logger) -> PublishResult:
    modulo = PUBLISHERS.get(canal)
    if modulo is None:
        return PublishResult.falha(canal, f"canal desconhecido: {canal}")

    if not peca.ativos(canal):
        return PublishResult.pulado(canal, "sem ativos no MANIFEST")

    if not cfg.channel_enabled(canal):
        return PublishResult.pulado(canal, "canal fora de ENABLED_CHANNELS")

    if not modulo.pronto(cfg):
        return PublishResult.pulado(canal, modulo.motivo_indisponivel(cfg))

    if canal_pausado(cfg.state_dir, canal):
        # falha real (nao 'pulado'): a peca nao pode ser dada como publicada sem
        # este canal. Vai para ERRO e aguarda manual_retry apos a pausa de 1h.
        return PublishResult.falha(canal, "circuit breaker aberto — canal pausado 1h")

    if cfg.dry_run:
        logger.info("publish", canal=canal, peca_id=peca.peca_id, modo="dry_run")
        return PublishResult.simulado(canal, peca.peca_id)

    try:
        resultado = modulo.publish(peca, cfg, logger)
        if resultado.ok and resultado.status == OK:
            registrar_sucesso(cfg.state_dir, canal)
        return resultado
    except Exception as exc:  # noqa: BLE001
        info = registrar_falha(cfg.state_dir, canal)
        logger.info(
            "publish",
            canal=canal,
            peca_id=peca.peca_id,
            status="erro",
            falhas_consecutivas=info["falhas_consecutivas"],
            erro=str(exc),
        )
        return PublishResult.falha(canal, str(exc))


def publicar_todos(peca, cfg, logger) -> dict[str, PublishResult]:
    """Publica em todos os canais presentes no MANIFEST. Devolve {canal: PublishResult}."""
    return {
        canal: publicar_canal(canal, peca, cfg, logger)
        for canal in peca.canais_no_manifest()
    }
