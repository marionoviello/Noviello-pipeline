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


# Schema do carrossel quando entrada e um julgado estruturado.
# Cada slide aceita os 4 campos opcionais do Batch (a): area, selo_tribunal,
# processo_id, carimbo (todos string vazia por default).
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


# Schema de extracao estruturada de um acordao a partir do texto bruto do PDF.
JULGADO_SCHEMA = {
    "type": "object",
    "properties": {
        "area": {"type": "string"},
        "orgao": {"type": "string"},
        "orgao_completo": {"type": "string"},
        "turma": {"type": "string"},
        "processo_id": {"type": "string"},
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
        "area", "orgao", "processo_id", "relator",
        "tese", "citacao_principal", "carimbo", "fundamentos",
    ],
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

    # ===== Julgado da Semana =====

    def extrair_dados_julgado(self, pdf_texto: str) -> dict:
        """Extrai dados estruturados de um acordao a partir do texto bruto do PDF.

        Devolve dict conforme JULGADO_SCHEMA: {area, orgao, orgao_completo,
        turma, processo_id, data_julgamento, relator, relator_curto, tese,
        citacao_principal, carimbo, fundamentos}.

        Os campos required do schema sao sempre devolvidos pelo Anthropic
        (structured output). Validacao adicional (campos vazios) fica no
        chamador (julgado_parser.parse_julgado).
        """
        instrucao = (
            "A partir do TEXTO DO ACORDAO acima, extraia os dados estruturados "
            "do julgado para uso em comunicacao social juridica.\n\n"
            "Regras de extracao:\n"
            "- area: ramo do direito principal (ex: 'Direito Imobiliario', "
            "'Direito Sucessorio', 'Saude Suplementar').\n"
            "- orgao: SIGLA curta do tribunal (STJ, STF, TJ-SP, TRF-3, etc).\n"
            "- orgao_completo: nome longo (ex: 'Terceira Turma do STJ').\n"
            "- turma: turma/secao + indicacao de unanimidade se aparecer.\n"
            "- processo_id: identificador completo (REsp 2.215.421/SE, RE 123, etc).\n"
            "- data_julgamento: formato DD/MM/AAAA.\n"
            "- relator: nome completo com titulo (Min., Des.).\n"
            "- relator_curto: forma compacta para citacao no slide.\n"
            "- tese: tese juridica em UMA frase declarativa (max 140 chars).\n"
            "- citacao_principal: trecho TEXTUAL do voto (entre aspas no PDF se houver).\n"
            "- carimbo: 'Unanimidade' se decisao unanime; 'Maioria' caso contrario; "
            "'Repetitivo Tema X' se for tese repetitiva; 'Precedente' se notavel.\n"
            "- fundamentos: lista de 3 a 5 fundamentos juridicos com {fonte, texto}.\n\n"
            "Se algum campo opcional (orgao_completo, turma, data_julgamento, "
            "relator_curto) nao puder ser determinado, devolva string vazia."
        )
        bloco_pdf = {
            "type": "text",
            "text": f"TEXTO DO ACORDAO:\n\n{pdf_texto}",
            "cache_control": {"type": "ephemeral"},
        }
        with self._client.messages.stream(
            model=self._model,
            max_tokens=8000,
            system=self._system_blocks(""),
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
        (mapeados do dict de entrada). Anexa `_ai_tells` como metadado.
        """
        dados_json = json.dumps(dados, ensure_ascii=False, indent=2)
        # No slide, selo_tribunal = orgao (sigla curta). processo_id = processo_id.
        instrucao = (
            f"A partir do JULGADO ESTRUTURADO acima, produza a copy de um carrossel "
            f"de Instagram para @novielloadv com {n_min} a {n_max} slides.\n"
            f"Slide 1 = capa com gancho forte na tese. Slides do meio = "
            f"contextualizacao, fundamentos e impacto pratico. Ultimo = CTA "
            f"educativo. Cite o processo no ultimo slide.\n\n"
            f"IMPORTANTE — todo slide deve incluir os 4 campos abaixo (copie do "
            f"JULGADO ESTRUTURADO, sem alterar):\n"
            f"- area: '{dados.get('area', '')}'\n"
            f"- selo_tribunal: '{dados.get('orgao', '')}'\n"
            f"- processo_id: '{dados.get('processo_id', '')}'\n"
            f"- carimbo: '{dados.get('carimbo', '')}'\n\n"
            f"Tambem produza: 'legenda' (texto do post no IG) e 'hashtags'.\n\n"
            "OBRIGATORIO: ao final da legenda, inclua disclaimer educativo no "
            "espirito do Provimento OAB 205/2021 (texto curto, '⚠️ Este conteudo "
            "e educativo e nao substitui a analise individualizada...')."
        )
        if ajuste.strip():
            instrucao += f"\n\nAJUSTES SOLICITADOS:\n{ajuste.strip()}"

        bloco_dados = {
            "type": "text",
            "text": f"JULGADO ESTRUTURADO:\n\n{dados_json}",
            "cache_control": {"type": "ephemeral"},
        }
        blocos_user: list[dict] = []
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
        """Gera post LinkedIn (B2B, tom tecnico) a partir do julgado estruturado.

        `url_blog` opcional: se vier preenchido, instrui o modelo a encerrar
        com o link. Caso contrario, omite a instrucao (Mario publica o blog
        manual depois).
        """
        dados_json = json.dumps(dados, ensure_ascii=False, indent=2)
        link_linha = (
            f"\nTermine com o link do artigo completo: {url_blog}"
            if url_blog.strip() else ""
        )
        instrucao = (
            "A partir do JULGADO ESTRUTURADO acima, escreva um post de LinkedIn "
            "para o perfil pessoal do Dr. Mario Noviello (publico B2B: advogados, "
            "incorporadores, gestores). Tom tecnico, autoridade, sem cliches."
            + link_linha + "\n"
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
        blocos_user: list[dict] = []
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

    # ===== Radar de Julgados =====

    def extrair_item_stj(self, bloco_texto: str, schema: dict) -> dict:
        """Classifica + extrai campos de UM item de informativo STJ.

        bloco_texto: trecho do PDF correspondente a 1 julgado destacado.
        schema: JSON schema (STJ_ITEM_SCHEMA do parser do radar).

        Devolve dict conforme schema. Cache no system block via brief padrao.
        """
        instrucao = (
            "A partir do TEXTO DO ITEM acima (1 julgado de informativo STJ), "
            "preencha o JSON estruturado:\n"
            "- relevante: true se area entra em (urbanistico/imobiliario/sucessorio), false caso contrario.\n"
            "- area: 'urbanistico' | 'imobiliario' | 'sucessorio' | 'fora'.\n"
            "  * urbanistico: REURB, parcelamento solo, OODC, CEPAC, operacao urbana, EIV.\n"
            "  * imobiliario: usucapiao, ITBI, incorporacao, alienacao fiduciaria de imovel, condominio edilicio.\n"
            "  * sucessorio: inventario, heranca, testamento, holding familiar, partilha.\n"
            "  * fora: qualquer outra area.\n"
            "- processo_id: ex 'REsp 2.215.421/SE'.\n"
            "- relator: nome do Ministro relator (com titulo).\n"
            "- orgao: turma/secao (ex '3a Turma', '2a Secao').\n"
            "- data_julgamento: DD/MM/AAAA.\n"
            "- classe: 'Recurso Especial' | 'Habeas Corpus' | 'Mandado de Seguranca' etc.\n"
            "- tese: nucleo da decisao em UMA frase declarativa (max 280 chars).\n"
            "- ementa: texto integral da ementa quando aparece no bloco.\n"
            "- citacao_voto: 1 trecho marcante do voto, com aspas, se houver.\n"
            "- fundamentos: lista de 1 a 4 itens {fonte, texto} (artigos, sumulas, precedentes citados)."
        )
        bloco = {
            "type": "text",
            "text": f"TEXTO DO ITEM:\n\n{bloco_texto}",
            "cache_control": {"type": "ephemeral"},
        }
        with self._client.messages.stream(
            model=self._model,
            max_tokens=6000,
            system=self._system_blocks(""),
            thinking={"type": "adaptive"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=[{"role": "user", "content": [
                bloco,
                {"type": "text", "text": instrucao},
            ]}],
        ) as stream:
            resp = stream.get_final_message()
        return json.loads(self._texto_resposta(resp))

    def classificar_area(self, ementa: str, areas_validas: list[str]) -> str:
        """Pede pro modelo classificar a area do julgado (1 string curta).

        Usado pelo TJ-SP parser, onde temos so a ementa.
        """
        schema = {
            "type": "object",
            "properties": {"area": {"type": "string", "enum": areas_validas}},
            "required": ["area"],
            "additionalProperties": False,
        }
        instrucao = (
            "Classifique o TEMA do julgado na area mais especifica dentre as opcoes "
            f"validas: {', '.join(areas_validas)}.\n"
            "Use 'fora' se nao for nenhuma das areas-alvo (urbanistico, imobiliario, sucessorio)."
        )
        bloco = {
            "type": "text",
            "text": f"EMENTA:\n\n{ementa}",
            "cache_control": {"type": "ephemeral"},
        }
        with self._client.messages.stream(
            model=self._model,
            max_tokens=512,
            system=self._system_blocks(""),
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=[{"role": "user", "content": [
                bloco,
                {"type": "text", "text": instrucao},
            ]}],
        ) as stream:
            resp = stream.get_final_message()
        return json.loads(self._texto_resposta(resp))["area"]
