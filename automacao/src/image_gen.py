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


# ---- Helpers de prompt 5-part por contexto juridico ----------------------

_SUJEITO_POR_AREA = {
    "sucessório": "objetos simbolicos de sucessao familiar — caneta tinteiro sobre papel timbrado, alianca de casamento e foto de familia em moldura antiga, escrivaninha de madeira escura com luminaria de banqueiro",
    "sucessorio": "objetos simbolicos de sucessao familiar — caneta tinteiro sobre papel timbrado, alianca de casamento e foto de familia em moldura antiga, escrivaninha de madeira escura com luminaria de banqueiro",
    "imobiliário": "elementos arquitetonicos de um imovel residencial premium — fachada de predio antigo com escada de granito, vista de janela classica para skyline de Sao Paulo, chave de bronze sobre escritura em pergaminho",
    "imobiliario": "elementos arquitetonicos de um imovel residencial premium — fachada de predio antigo com escada de granito, vista de janela classica para skyline de Sao Paulo, chave de bronze sobre escritura em pergaminho",
    "urbanístico": "vista aerea de bairro paulistano (Jabaquara, Vila Mariana), arvores antigas e arquitetura residencial dos anos 1960-70",
    "urbanistico": "vista aerea de bairro paulistano (Jabaquara, Vila Mariana), arvores antigas e arquitetura residencial dos anos 1960-70",
    "saude": "ambiente clinico sereno — corredor de clinica privada, mao segurando carteira de plano de saude, prontuario sobre mesa de madeira",
    "saude suplementar": "ambiente clinico sereno — corredor de clinica privada, mao segurando carteira de plano de saude, prontuario sobre mesa de madeira",
    "senior": "ambiente domestico aconchegante de pessoa Senior — xicaras de cafe sobre mesa de centro com livros, retrato em moldura, jardim interno visto da janela",
    "sênior": "ambiente domestico aconchegante de pessoa Senior — xicaras de cafe sobre mesa de centro com livros, retrato em moldura, jardim interno visto da janela",
    "previdenciário": "documentos previdenciarios sobre escrivaninha — carteira de trabalho antiga, oculos sobre extrato, calculadora classica",
    "previdenciario": "documentos previdenciarios sobre escrivaninha — carteira de trabalho antiga, oculos sobre extrato, calculadora classica",
}

_AMBIENTE_FALLBACK = (
    "em um escritorio de advocacia premium, parede de tijolinhos a vista ao "
    "fundo, estantes com livros juridicos em couro, luz de janela alta caindo "
    "diagonalmente"
)


def _sujeito_por_categoria(categorias: list[str], titulo: str) -> str:
    """Escolhe sujeito visual baseado nas categorias (case-insensitive)."""
    for cat in categorias or []:
        chave = (cat or "").strip().lower()
        for area, sujeito in _SUJEITO_POR_AREA.items():
            if area in chave:
                return sujeito
    # fallback: derivar do titulo
    titulo_lower = (titulo or "").lower()
    for area, sujeito in _SUJEITO_POR_AREA.items():
        if area in titulo_lower:
            return sujeito
    return "um escritorio de advocacia tradicional — caneta tinteiro sobre documento, livros antigos em couro"


def _ambiente_por_tema(lead: str, titulo: str) -> str:
    """Ambiente derivado do lead/titulo (pega palavras-chave de contexto)."""
    texto = f"{titulo} {lead}".lower()
    # normaliza acentos basicos para casar "imovel" tanto com/sem acento
    texto_n = (texto.replace("á", "a").replace("é", "e").replace("í", "i")
                    .replace("ó", "o").replace("ú", "u").replace("ã", "a")
                    .replace("õ", "o").replace("ç", "c").replace("â", "a")
                    .replace("ê", "e").replace("ô", "o"))
    if any(t in texto_n for t in ("familia", "filhos", "patrimonio", "heranca", "sucessao")):
        return "em ambiente domestico-juridico de transicao geracional, com luz de fim de tarde"
    if any(t in texto_n for t in ("imovel", "predio", "casa", "loteamento", "registro")):
        return "com elementos arquitetonicos brasileiros classicos no fundo desfocado"
    if any(t in texto_n for t in ("contrato", "clausula", "escritura", "minuta")):
        return "sobre mesa de madeira escura com luminaria de banqueiro acesa"
    return _AMBIENTE_FALLBACK


# Estilo visual fixo para garantir consistencia entre slides da mesma peca.
# Aplicado a TODOS os prompts (postfix) — Mario revisa quando quiser refinar.
ESTILO_NOVIELLO = (
    "Fotografia editorial profissional, paleta de cores discreta em tons neutros "
    "(sepia, dourado suave, cinza claro), iluminacao natural, composicao limpa, "
    "alta resolucao. SEM TEXTO, sem logos, sem marcas dagua, sem pessoas em primeiro "
    "plano. Formato vertical 4:5, foco em ambiente/objeto. Estetica sobria e "
    "institucional, adequada a comunicacao juridica."
)

# Estilo especifico pro hero de artigo (formato 16:9, mais ambiente)
ESTILO_HERO_ARTIGO = (
    "Fotografia editorial profissional, formato landscape 16:9 (1200x630px), "
    "paleta sobria em tons quentes (claret escuro, dourado suave, creme), "
    "iluminacao natural cinematografica, composicao com profundidade. Adequado "
    "a hero image de blog juridico. SEM TEXTO, SEM logos, SEM marcas dagua, "
    "SEM pessoas com rostos identificaveis (silhuetas/maos OK). Foco em "
    "ambiente, objeto simbolico ou cena conceitual. Estetica institucional "
    "premium, adequada a Noviello Advocacia (publico Senior, classe A/AA/B)."
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

    def gerar_hero_artigo(
        self,
        titulo: str,
        lead: str,
        categorias: list[str],
        pasta_destino: Path,
        nome_arquivo: str = "hero.png",
    ) -> Path:
        """Gera hero de artigo do blog (16:9, ~1200x630).

        Constroi prompt 5-part (image type / subject / environment / specs /
        constraints) baseado no titulo + lead + categorias. Sem texto, sem
        rostos, sem logos.
        """
        # 1. Image type
        tipo = "Uma fotografia editorial premium, formato landscape (paisagem 16:9)"

        # 2. Subject — derivado das categorias e do titulo
        sujeito = _sujeito_por_categoria(categorias, titulo)

        # 3. Environment — derivado do lead
        ambiente = _ambiente_por_tema(lead, titulo)

        # 4. Technical specs
        specs = (
            "Lente 35mm f/2.8, luz natural de janela lateral (golden hour), "
            "profundidade de campo media, composicao centralizada com "
            "espaco negativo a direita para overlay de titulo"
        )

        # 5. Constraints
        constraints = (
            "SEM TEXTO, sem palavras visiveis, sem letras, sem numeros, "
            "sem logos, sem marcas dagua, sem rostos identificaveis "
            "(silhuetas e maos OK). Tons quentes e sobrios."
        )

        prompt = (
            f"{tipo} de {sujeito}, {ambiente}. {specs}. {constraints}."
        )

        spec = ImagemSpec(
            nome_arquivo=nome_arquivo,
            prompt=prompt,
            estilo=ESTILO_HERO_ARTIGO,
        )
        return self.gerar(spec, pasta_destino)

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
