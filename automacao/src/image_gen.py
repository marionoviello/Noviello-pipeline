"""Geracao de imagens para slides via Google Gemini (gemini-2.5-flash-image).

Wrapper minimo em volta do SDK `google-genai`. Foco: gerar imagens editoriais
PNG para usar como fundo/elemento em slides do carrossel.

Custos: free tier do Gemini cobre uso modesto (~50 imgs/dia). Latencia ~6-10s
por imagem.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


class ImagemGenError(Exception):
    pass


# Estilo visual fixo para garantir consistencia entre slides da mesma peca.
# Aplicado a TODOS os prompts (postfix) — Mario revisa quando quiser refinar.
ESTILO_NOVIELLO = (
    "Fotografia editorial profissional, paleta de cores discreta em tons neutros "
    "(sepia, dourado suave, cinza claro), iluminacao natural, composicao limpa, "
    "alta resolucao. SEM TEXTO, sem logos, sem marcas dagua, sem pessoas em primeiro "
    "plano. Formato vertical 4:5, foco em ambiente/objeto. Estetica sobria e "
    "institucional, adequada a comunicacao juridica."
)


@dataclass
class ImagemSpec:
    """Especificacao de uma imagem a gerar."""
    nome_arquivo: str           # ex.: "skyline-sp.png"
    prompt: str                 # tema/cena especifica
    estilo: str = ESTILO_NOVIELLO


class GeradorImagens:
    """Cliente de geracao de imagens. Mantem instancia para reuso e cache."""

    def __init__(self, api_key: str, modelo: str = "gemini-2.5-flash-image"):
        # Import tardio: nao queremos forcar dependencia se nao for usado
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._modelo = modelo

    def gerar(self, spec: ImagemSpec, pasta_destino: Path) -> Path:
        """Gera UMA imagem e salva em `pasta_destino/spec.nome_arquivo`.

        Devolve o Path da imagem gerada. Levanta ImagemGenError se falhar.
        """
        pasta_destino = Path(pasta_destino)
        pasta_destino.mkdir(parents=True, exist_ok=True)
        destino = pasta_destino / spec.nome_arquivo

        prompt_completo = f"{spec.prompt}\n\n{spec.estilo}"

        try:
            resp = self._client.models.generate_content(
                model=self._modelo,
                contents=prompt_completo,
            )
        except Exception as exc:  # noqa: BLE001
            raise ImagemGenError(f"falha na chamada Gemini: {exc}") from exc

        for cand in resp.candidates or []:
            for part in cand.content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    destino.write_bytes(inline.data)
                    return destino

        raise ImagemGenError(
            f"Gemini nao retornou imagem para '{spec.nome_arquivo}'. Resposta: "
            f"{getattr(resp, 'text', '(sem texto)')[:200] if hasattr(resp, 'text') else 'N/A'}"
        )

    def gerar_lote(
        self,
        specs: list[ImagemSpec],
        pasta_destino: Path,
        sleep_entre_chamadas: float = 0.5,
    ) -> list[Path]:
        """Gera varias imagens em sequencia. Pula falhas, devolve so as OK.

        Pequena pausa entre chamadas para nao estourar quota.
        """
        resultados: list[Path] = []
        for i, spec in enumerate(specs):
            t0 = time.monotonic()
            try:
                p = self.gerar(spec, pasta_destino)
                dur = time.monotonic() - t0
                print(f"  [{i+1}/{len(specs)}] {spec.nome_arquivo} ({dur:.1f}s, {p.stat().st_size} bytes)")
                resultados.append(p)
            except ImagemGenError as exc:
                print(f"  [{i+1}/{len(specs)}] FALHOU {spec.nome_arquivo}: {exc}")
            if i < len(specs) - 1 and sleep_entre_chamadas:
                time.sleep(sleep_entre_chamadas)
        return resultados
