"""Cliente da API Anthropic — gera copy de carrossel e texto de LinkedIn.

Usa o SDK oficial `anthropic` (retry e erros tipados embutidos). Suporta
enriquecimento opcional via:
- `system_extra`: skills `noviello-*` carregadas dinamicamente (juntadas ao brief).
- `contexto_blog`: corpus de artigos recentes do blog (cross-link, anti-repeticao).

Todos os blocos usam `cache_control: ephemeral` da Anthropic. O sistema (brief +
skills) e cacheado, o corpus e cacheado, o artigo e cacheado — entre a chamada
de carrossel e a de LinkedIn ha cache hit alto, e entre pecas seguidas o sistema
+ corpus ficam cacheados.

Ordem dos blocos (importa para cache):
1. system: brief + skills extras (cache_control)
2. user[0]: corpus do blog, se houver (cache_control)
3. user[1]: artigo de referencia (cache_control)
4. user[2]: instrucao (sem cache — varia a cada chamada)
"""

from __future__ import annotations

import json
from pathlib import Path

import anthropic

from src import ai_tells_detector
from src.voice_rules import VOICE_RULES_INSTAGRAM, VOICE_RULES_LINKEDIN

BRIEF = "brief-marca.txt"

# structured output: garante JSON valido para o carrossel
CAROUSEL_SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "corpo": {"type": "string"},
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


class AnthropicClient:
    def __init__(self, anthropic_cfg: dict, templates_dir: Path):
        self._client = anthropic.Anthropic(api_key=anthropic_cfg["api_key"])
        self._model = anthropic_cfg.get("model") or "claude-opus-4-7"
        self._brief = (Path(templates_dir) / BRIEF).read_text(encoding="utf-8")

    def _artigo_block(self, artigo_texto: str) -> dict:
        """Bloco do artigo, marcado para cache (prefixo reaproveitavel entre chamadas)."""
        return {
            "type": "text",
            "text": f"ARTIGO DE REFERENCIA:\n\n{artigo_texto}",
            "cache_control": {"type": "ephemeral"},
        }

    def _contexto_block(self, contexto: str) -> dict:
        return {
            "type": "text",
            "text": contexto,
            "cache_control": {"type": "ephemeral"},
        }

    def _system_blocks(self, system_extra: str, voice_rules: str = "") -> list[dict]:
        """Brief base + skills extras + voice rules, num bloco unico cacheado.

        voice_rules vai ANTES do brief para dar prioridade (modelo le primeiro).
        """
        partes = []
        if voice_rules and voice_rules.strip():
            partes.append(voice_rules.strip())
        partes.append(self._brief)
        if system_extra and system_extra.strip():
            partes.append(system_extra.strip())
        sistema = "\n\n---\n\n".join(partes)
        return [
            {
                "type": "text",
                "text": sistema,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _user_content(self, artigo_texto: str, instrucao_texto: str, contexto_blog: str) -> list[dict]:
        """Constroi a lista de blocos da mensagem do usuario.

        Ordem: corpus (se houver) -> artigo -> instrucao. Cache fica no corpus
        e no artigo; instrucao sempre re-processada (varia por chamada).
        """
        blocos: list[dict] = []
        if contexto_blog and contexto_blog.strip():
            blocos.append(self._contexto_block(contexto_blog))
        blocos.append(self._artigo_block(artigo_texto))
        blocos.append({"type": "text", "text": instrucao_texto})
        return blocos

    def _texto_resposta(self, resp) -> str:
        return next(b.text for b in resp.content if b.type == "text")

    def gerar_carrossel(
        self,
        artigo_texto: str,
        titulo: str,
        n_min: int = 8,
        n_max: int = 10,
        ajuste: str = "",
        *,
        system_extra: str = "",
        contexto_blog: str = "",
    ) -> dict:
        """Devolve {slides: [{titulo, corpo}], legenda: str, hashtags: [str]}.

        `ajuste`: instrucoes de revisao do Mario, incorporadas na regeneracao.
        `system_extra`: texto extra anexado ao brief (ex.: skills da area).
        `contexto_blog`: bloco de contexto (ex.: corpus de artigos do blog).
        """
        texto = (
            f"A partir do ARTIGO acima, produza a copy de um carrossel de Instagram "
            f"para @novielloadv, com {n_min} a {n_max} slides.\n"
            f"Titulo da peca: {titulo}\n"
            "Slide 1 = capa/gancho. Slides do meio = desenvolvimento (um conceito "
            "por slide). Ultimo slide = chamada para acao com um CTA aprovado.\n"
            "Tambem produza: 'legenda' (texto da legenda do post no Instagram) e "
            "'hashtags' (lista de hashtags relevantes).\n\n"
            "OBRIGATORIO: ao final da legenda do Instagram, inclua um disclaimer "
            "educativo no espirito do Provimento OAB 205/2021 — texto curto, "
            "preferencialmente com o emoji aviso, algo no estilo: "
            "'⚠️ Este conteudo e educativo e nao substitui a analise individualizada "
            "do seu caso por um advogado especializado.' Pode reescrever com palavras "
            "proprias, mas a mensagem precisa estar presente."
        )
        if ajuste.strip():
            texto += f"\n\nAJUSTES SOLICITADOS PELO REVISOR (incorpore-os):\n{ajuste.strip()}"
        # 24K cobre thinking (adaptive) + 10 slides + legenda + hashtags.
        # SDK exige streaming acima do limite de ~10min — usamos messages.stream.
        with self._client.messages.stream(
            model=self._model,
            max_tokens=24000,
            system=self._system_blocks(system_extra, voice_rules=VOICE_RULES_INSTAGRAM),
            thinking={"type": "adaptive"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": CAROUSEL_SCHEMA},
            },
            messages=[{"role": "user", "content": self._user_content(artigo_texto, texto, contexto_blog)}],
        ) as stream:
            resp = stream.get_final_message()
        carrossel = json.loads(self._texto_resposta(resp))
        # auditoria pos-geracao (anexa como metadado pro painel)
        texto_concat = " ".join(
            [carrossel.get("legenda", "")]
            + [s.get("titulo", "") + " " + s.get("corpo", "") for s in carrossel.get("slides", [])]
        )
        carrossel["_ai_tells"] = ai_tells_detector.detectar(texto_concat)
        return carrossel

    def gerar_linkedin(
        self,
        artigo_texto: str,
        titulo: str,
        url_artigo: str,
        ajuste: str = "",
        *,
        system_extra: str = "",
        contexto_blog: str = "",
    ) -> str:
        """Devolve o texto de um post curto de LinkedIn."""
        texto = (
            f"A partir do ARTIGO acima, escreva um post curto de LinkedIn para o "
            f"perfil pessoal do Dr. Mario Noviello (publico B2B, tom tecnico e de "
            f"autoridade). Titulo da peca: {titulo}\n"
            f"Termine com o link para o artigo completo: {url_artigo}\n"
            "Maximo ~1300 caracteres, no maximo 3 hashtags. Responda apenas com o "
            "texto do post, sem comentarios.\n\n"
            "ESTILO OBRIGATORIO — texto natural, sem marcadores de IA:\n"
            "- NAO use travessoes longos (—, –) para separar ideias. Use ponto, "
            "virgula, dois-pontos ou parenteses.\n"
            "- NAO use asteriscos para enfase (*texto*, **texto**). A enfase vem "
            "da escolha das palavras.\n"
            "- Releia mentalmente o texto antes de devolver e remova qualquer "
            "travessao ou asterisco que tenha aparecido."
        )
        if ajuste.strip():
            texto += f"\n\nAJUSTES SOLICITADOS PELO REVISOR (incorpore-os):\n{ajuste.strip()}"
        with self._client.messages.stream(
            model=self._model,
            max_tokens=8000,
            system=self._system_blocks(system_extra, voice_rules=VOICE_RULES_LINKEDIN),
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": self._user_content(artigo_texto, texto, contexto_blog)}],
        ) as stream:
            resp = stream.get_final_message()
        return self._texto_resposta(resp).strip()
