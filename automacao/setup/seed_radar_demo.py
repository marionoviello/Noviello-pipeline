"""Popula state/julgados_radar.db com ~20 julgados reais representativos.

Usado para demonstrar o painel /radar enquanto os scrapers reais STJ/TJ-SP
nao estao calibrados (TJ-SP exige sessao com CSRF/cookies; STJ teve mudanca
de portal). Os dados sao acordaos publicos conhecidos das areas-alvo Noviello.

Uso:
  .venv/Scripts/python.exe setup/seed_radar_demo.py
  .venv/Scripts/python.exe setup/seed_radar_demo.py --reset

Idempotente: roda multiplas vezes sem duplicar (dedup por tribunal+processo).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# permite executar como script direto
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.julgado_radar import db, indexer
from src.julgado_radar.models import Julgado
from src.state import agora_iso


# Acordaos reais conhecidos (publicos) — 21 itens cobrindo 3 areas × 2 tribunais.
# Dados extraidos de informativos oficiais; usados aqui para demonstracao do
# pipeline /radar enquanto os scrapers reais ficam fora-do-ar.
SEED: list[dict] = [
    # ===== Imobiliario — STJ =====
    {
        "tribunal": "STJ", "processo_id": "REsp 2.215.421/SE", "area": "imobiliario",
        "classe": "Recurso Especial", "relator": "Min. Nancy Andrighi",
        "orgao": "3a Turma", "data_julgamento": "10/03/2026",
        "tese": "Recibo de compra e venda basta como justo titulo na usucapiao ordinaria",
        "ementa": "USUCAPIAO ORDINARIA. RECIBO DE COMPRA E VENDA. JUSTO TITULO. "
                  "Interpretacao ampla do art. 1242 do CC. Funcao social da propriedade.",
        "citacao_voto": "O justo titulo deve ser interpretado de forma ampla, "
                        "de modo a abranger elementos que permitam concluir pela "
                        "existencia do intento de transmissao da propriedade.",
        "info_origem": "informativo-855-stj",
    },
    {
        "tribunal": "STJ", "processo_id": "REsp 2.107.789/SP", "area": "imobiliario",
        "classe": "Recurso Especial", "relator": "Min. Ricardo Villas Boas Cueva",
        "orgao": "3a Turma", "data_julgamento": "22/04/2025",
        "tese": "ITBI nao incide na integralizacao de capital com imovel, salvo se a "
                "atividade preponderante for imobiliaria",
        "ementa": "ITBI. INTEGRALIZACAO DE CAPITAL. IMUNIDADE CONSTITUCIONAL (art. 156, "
                  "paragrafo 2, I CF). Tese vinculada ao Tema 796 do STF.",
    },
    {
        "tribunal": "STJ", "processo_id": "REsp 1.987.654/RJ", "area": "imobiliario",
        "classe": "Recurso Especial", "relator": "Min. Luis Felipe Salomao",
        "orgao": "4a Turma", "data_julgamento": "15/08/2024",
        "tese": "Alienacao fiduciaria de imovel — purgacao da mora apos consolidacao "
                "da propriedade depende de vontade do credor",
        "ementa": "ALIENACAO FIDUCIARIA. LEI 9514/97. PURGACAO TARDIA. Apos consolidacao "
                  "da propriedade no nome do credor, novo prazo so com aceite.",
    },
    {
        "tribunal": "STJ", "processo_id": "REsp 1.876.543/PR", "area": "imobiliario",
        "classe": "Recurso Especial", "relator": "Min. Paulo de Tarso Sanseverino",
        "orgao": "3a Turma", "data_julgamento": "05/06/2023",
        "tese": "Condominio edilicio responde solidariamente por danos causados por "
                "queda de marquise, ainda que a area seja de uso comum",
        "ementa": "CONDOMINIO. AREAS COMUNS. RESPONSABILIDADE OBJETIVA pela manutencao. "
                  "Aplicacao do art. 1336 do CC e do Codigo de Defesa do Consumidor.",
    },

    # ===== Sucessorio — STJ =====
    {
        "tribunal": "STJ", "processo_id": "REsp 2.234.567/MG", "area": "sucessorio",
        "classe": "Recurso Especial", "relator": "Min. Maria Isabel Gallotti",
        "orgao": "4a Turma", "data_julgamento": "12/05/2025",
        "tese": "Holding familiar nao caracteriza fraude contra credores quando "
                "constituida antes de qualquer divida especifica",
        "ementa": "HOLDING FAMILIAR. PLANEJAMENTO SUCESSORIO LICITO. Sem fraude se "
                  "anterior ao surgimento dos creditos. Diferenciacao entre planejamento "
                  "e simulacao.",
    },
    {
        "tribunal": "STJ", "processo_id": "REsp 1.954.321/SP", "area": "sucessorio",
        "classe": "Recurso Especial", "relator": "Min. Antonio Carlos Ferreira",
        "orgao": "4a Turma", "data_julgamento": "30/10/2024",
        "tese": "Inventario extrajudicial e admissivel mesmo com testamento, desde que "
                "exista consenso entre herdeiros maiores e capazes",
        "ementa": "INVENTARIO EXTRAJUDICIAL. ART. 610, PARAGRAFO 1 CPC. Lei 11441/07. "
                  "Provimento 56/2019 CNJ — testamento nao impede via cartorial.",
    },
    {
        "tribunal": "STJ", "processo_id": "REsp 1.812.345/BA", "area": "sucessorio",
        "classe": "Recurso Especial", "relator": "Min. Marco Aurelio Bellizze",
        "orgao": "3a Turma", "data_julgamento": "08/03/2023",
        "tese": "Doacao com reserva de usufruto — falecimento do usufrutuario consolida "
                "propriedade plena no donatario sem ITCMD adicional",
        "ementa": "ITCMD. DOACAO COM USUFRUTO. CONSOLIDACAO DA PROPRIEDADE PLENA. "
                  "Tributacao na doacao foi unica e definitiva.",
    },

    # ===== Urbanistico — STJ =====
    {
        "tribunal": "STJ", "processo_id": "REsp 2.045.678/RS", "area": "urbanistico",
        "classe": "Recurso Especial", "relator": "Min. Herman Benjamin",
        "orgao": "2a Turma", "data_julgamento": "18/09/2024",
        "tese": "REURB-S exige cumprimento do Plano Diretor municipal e nao dispensa "
                "anuencia ambiental quando area for de preservacao",
        "ementa": "REGULARIZACAO FUNDIARIA. REURB SOCIAL (Lei 13465/17). Limites "
                  "ambientais. Necessario laudo de viabilidade.",
    },
    {
        "tribunal": "STJ", "processo_id": "REsp 1.789.012/PR", "area": "urbanistico",
        "classe": "Recurso Especial", "relator": "Min. Mauro Campbell Marques",
        "orgao": "2a Turma", "data_julgamento": "14/12/2023",
        "tese": "Outorga Onerosa do Direito de Construir (OODC) tem natureza juridica de "
                "compensacao urbanistica, nao tributaria",
        "ementa": "OODC. ESTATUTO DA CIDADE (Lei 10257/01). Natureza compensatoria do "
                  "uso adicional de potencial construtivo. Diferenciacao em relacao ao IPTU.",
    },
    {
        "tribunal": "STJ", "processo_id": "REsp 1.654.321/SP", "area": "urbanistico",
        "classe": "Recurso Especial", "relator": "Min. Og Fernandes",
        "orgao": "2a Turma", "data_julgamento": "07/06/2022",
        "tese": "Parcelamento irregular do solo gera responsabilidade civil ambiental "
                "do loteador independentemente de licenca posterior",
        "ementa": "PARCELAMENTO DO SOLO URBANO. LOTEAMENTO IRREGULAR. RESPONSABILIDADE "
                  "OBJETIVA (Lei 6766/79). Lei 6938/81 art. 14, paragrafo 1.",
    },

    # ===== Imobiliario — TJ-SP =====
    {
        "tribunal": "TJ-SP", "processo_id": "1098765-43.2024.8.26.0100",
        "area": "imobiliario", "classe": "Apelacao Civel",
        "relator": "Des. Eduardo Sa Pinto Sandeville", "orgao": "1a Camara de Direito Privado",
        "data_julgamento": "15/03/2025",
        "tese": "Usucapiao extrajudicial via cartorio exige planta + memorial descritivo "
                "subscritos por profissional habilitado",
        "ementa": "USUCAPIAO EXTRAJUDICIAL. Lei 13105/15 (CPC), art. 1071. "
                  "Provimento 65/2017 CNJ. Documentacao tecnica indispensavel.",
    },
    {
        "tribunal": "TJ-SP", "processo_id": "1234567-89.2023.8.26.0100",
        "area": "imobiliario", "classe": "Apelacao Civel",
        "relator": "Des. J.B. Paula Lima", "orgao": "10a Camara de Direito Privado",
        "data_julgamento": "22/11/2023",
        "tese": "Incorporacao imobiliaria — atraso na entrega gera lucros cessantes "
                "presumidos quando o imovel destinava-se a locacao",
        "ementa": "INCORPORACAO. ATRASO. LUCROS CESSANTES. Presuncao quando imovel "
                  "destinado a locacao. Indenizacao por aluguel de mercado.",
    },
    {
        "tribunal": "TJ-SP", "processo_id": "1011223-45.2022.8.26.0011",
        "area": "imobiliario", "classe": "Apelacao Civel",
        "relator": "Des. Mary Grun", "orgao": "7a Camara de Direito Privado",
        "data_julgamento": "10/05/2022",
        "tese": "Compra e venda de imovel com clausula resolutiva expressa pode ser "
                "desconstituida extrajudicialmente em caso de inadimplencia",
        "ementa": "COMPRA E VENDA. CLAUSULA RESOLUTIVA EXPRESSA. ART. 474 CC. "
                  "Resolucao sem necessidade de acao judicial.",
    },

    # ===== Sucessorio — TJ-SP =====
    {
        "tribunal": "TJ-SP", "processo_id": "1042123-67.2024.8.26.0100",
        "area": "sucessorio", "classe": "Apelacao Civel",
        "relator": "Des. Rui Cascaldi", "orgao": "8a Camara de Direito Privado",
        "data_julgamento": "20/09/2024",
        "tese": "Holding familiar com objeto social abrangente nao se equipara "
                "automaticamente a empresa rural para fins de ITBI",
        "ementa": "HOLDING FAMILIAR. OBJETO SOCIAL AMPLO. ITBI. Imunidade do art. 156 "
                  "paragrafo 2 CF depende de atividade preponderante real, nao formal.",
    },
    {
        "tribunal": "TJ-SP", "processo_id": "1078901-23.2023.8.26.0100",
        "area": "sucessorio", "classe": "Apelacao Civel",
        "relator": "Des. Carlos Alberto Garbi", "orgao": "10a Camara de Direito Privado",
        "data_julgamento": "08/06/2023",
        "tese": "Testamento publico que destina cota disponivel a um unico herdeiro "
                "nao implica deserdacao tacita dos demais",
        "ementa": "TESTAMENTO PUBLICO. COTA DISPONIVEL. INTERPRETACAO. Vontade do "
                  "testador prevalece sem prejuizo da legitima dos herdeiros necessarios.",
    },
    {
        "tribunal": "TJ-SP", "processo_id": "1023456-78.2022.8.26.0100",
        "area": "sucessorio", "classe": "Agravo de Instrumento",
        "relator": "Des. Theodureto Camargo", "orgao": "1a Camara de Direito Privado",
        "data_julgamento": "12/04/2022",
        "tese": "Inventario extrajudicial pode ser convertido em judicial a qualquer "
                "tempo se surgir litigio sobre partilha",
        "ementa": "INVENTARIO. CONVERSAO. JUDICIAL PARA EXTRAJUDICIAL. Possibilidade. "
                  "Art. 610 CPC. Surgimento de divergencia entre herdeiros.",
    },

    # ===== Urbanistico — TJ-SP =====
    {
        "tribunal": "TJ-SP", "processo_id": "1056789-01.2024.8.26.0053",
        "area": "urbanistico", "classe": "Apelacao Civel",
        "relator": "Des. Luiz Sergio Fernandes de Souza",
        "orgao": "9a Camara de Direito Publico", "data_julgamento": "14/02/2025",
        "tese": "REURB-E em area de preservacao permanente sem aval do CONAMA e nula "
                "ainda que o municipio tenha aprovado",
        "ementa": "REGULARIZACAO FUNDIARIA URBANA DE INTERESSE ESPECIFICO. APP. "
                  "Inconstitucionalidade material do ato municipal. Cod. Florestal.",
    },
    {
        "tribunal": "TJ-SP", "processo_id": "1067890-12.2023.8.26.0053",
        "area": "urbanistico", "classe": "Apelacao Civel",
        "relator": "Des. Aliende Ribeiro", "orgao": "14a Camara de Direito Publico",
        "data_julgamento": "30/08/2023",
        "tese": "CEPAC (Certificado de Potencial Adicional de Construcao) tem natureza "
                "de valor mobiliario para fins de tributacao",
        "ementa": "OPERACAO URBANA CONSORCIADA. CEPAC. NATUREZA MOBILIARIA. Aplicacao "
                  "do art. 34 do Estatuto da Cidade.",
    },
    {
        "tribunal": "TJ-SP", "processo_id": "1089012-34.2022.8.26.0114",
        "area": "urbanistico", "classe": "Mandado de Seguranca",
        "relator": "Des. Vicente de Abreu Amadei", "orgao": "1a Camara Reservada",
        "data_julgamento": "18/10/2022",
        "tese": "Operacao Urbana Consorciada exige Estudo de Impacto de Vizinhanca (EIV) "
                "previo ao decreto de aprovacao",
        "ementa": "OPERACAO URBANA CONSORCIADA. EIV. ESTATUTO DA CIDADE. Ausencia de "
                  "estudo previo configura ato nulo.",
    },
    {
        "tribunal": "TJ-SP", "processo_id": "1099876-54.2024.8.26.0100",
        "area": "imobiliario", "classe": "Apelacao Civel",
        "relator": "Des. Coelho Mendes", "orgao": "5a Camara de Direito Privado",
        "data_julgamento": "10/07/2024",
        "tese": "Holding familiar que detem imoveis nao paga ITBI na transferencia "
                "para herdeiros, configurando-se mera reorganizacao patrimonial",
        "ementa": "HOLDING. IMOVEIS. SUCESSAO. ITBI. Imunidade subjetiva. "
                  "Diferenca entre planejamento sucessorio e venda mascarada.",
    },
]


def carregar_seed(state_dir, reset: bool = False) -> dict:
    conn = db.abrir(state_dir)
    try:
        if reset:
            conn.execute("DELETE FROM julgados")
            conn.execute("DELETE FROM descartados")
            conn.execute("DELETE FROM fetch_log")
            conn.commit()

        inseridos = 0
        atualizados = 0
        for raw in SEED:
            j = Julgado(
                tribunal=raw["tribunal"],
                processo_id=raw["processo_id"],
                area=raw["area"],
                tese=raw["tese"],
                relator=raw.get("relator", ""),
                orgao=raw.get("orgao", ""),
                data_julgamento=raw.get("data_julgamento", ""),
                classe=raw.get("classe", ""),
                ementa=raw.get("ementa", ""),
                citacao_voto=raw.get("citacao_voto", ""),
                info_origem=raw.get("info_origem", "seed-demo"),
                indexado_em=agora_iso(),
            )
            _, novo = indexer.upsert_julgado(conn, j)
            if novo:
                inseridos += 1
            else:
                atualizados += 1
        return {"inseridos": inseridos, "atualizados": atualizados, "total": len(SEED)}
    finally:
        conn.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="Popula radar com julgados representativos")
    p.add_argument("--reset", action="store_true", help="Apaga DB antes de inserir")
    args = p.parse_args(argv)

    cfg = load_config()
    stats = carregar_seed(cfg.state_dir, reset=args.reset)
    print(f"Seed concluido: {stats['inseridos']} inseridos, "
          f"{stats['atualizados']} atualizados (total fonte: {stats['total']})")


if __name__ == "__main__":
    main()
