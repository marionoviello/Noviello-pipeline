#!/usr/bin/env python3
"""
Calculadora de Acréscimos Legais sobre ITCMD — SP (Lei 10.705/2000)
Módulo da Skill noviello-orcamentista-sucessorio

Uso:
    from calculadora_acrescimos import calcular_acrescimos_itcmd
    resultado = calcular_acrescimos_itcmd(
        data_obito="2024-03-15",
        itcmd_base=23937.28,
        data_pagamento="2026-07-15",
        estrategia="conservadora"
    )
    print(resultado['itcmd_total'])
"""

from datetime import date, datetime
from typing import Union, Dict


# Tabela histórica de UFESPs (mantida atualizada na skill)
UFESP = {
    2020: 28.48,
    2021: 29.09,
    2022: 31.97,
    2023: 33.35,
    2024: 35.36,
    2025: 37.02,
    2026: 38.42,
}


def _parse_data(d: Union[str, date, datetime]) -> date:
    """Aceita string ISO (YYYY-MM-DD), date ou datetime."""
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        return datetime.strptime(d, "%Y-%m-%d").date()
    raise ValueError(f"Data em formato inválido: {d!r}")


def calcular_acrescimos_itcmd(
    data_obito: Union[str, date],
    itcmd_base: float,
    data_pagamento: Union[str, date, None] = None,
    estrategia: str = "conservadora",
) -> Dict:
    """
    Calcula os acréscimos legais sobre o ITCMD conforme Lei 10.705/2000 (SP).

    Parâmetros
    ----------
    data_obito : str (YYYY-MM-DD) ou date
        Data do falecimento (abertura da sucessão).
    itcmd_base : float
        ITCMD calculado sobre a base (VVR ou VV) na data do óbito, em R$.
    data_pagamento : str (YYYY-MM-DD) ou date, opcional
        Data projetada de recolhimento do imposto. Default: hoje + 90 dias.
    estrategia : str
        "rigorosa" (escala legal 0/10/20%) ou "conservadora" (20% a partir de 60 dias).

    Retorna
    -------
    dict com:
        dias_desde_obito : int
        faixa_multa : str — descrição da faixa aplicada
        percentual_multa : float — 0.0, 0.10 ou 0.20
        itcmd_base : float
        itcmd_atualizado : float — após correção UFESP
        multa : float
        correcao_monetaria : float
        juros_mora : float
        acrescimos_total : float — multa + correção + juros
        itcmd_total : float — base atualizada + multa + juros
        nota_explicativa : str — texto pronto para incluir no orçamento
    """
    d_obito = _parse_data(data_obito)
    d_pag = _parse_data(data_pagamento) if data_pagamento else date.today()

    dias = (d_pag - d_obito).days
    meses = dias / 30.0  # aproximação para juros

    # --- Correção monetária pela variação da UFESP ---
    ufesp_obito = UFESP.get(d_obito.year)
    ufesp_pag = UFESP.get(d_pag.year)
    if ufesp_obito is None or ufesp_pag is None:
        # Fallback: sem correção se ano não estiver na tabela
        fator_correcao = 1.0
        correcao_monetaria = 0.0
        itcmd_atualizado = itcmd_base
    else:
        fator_correcao = ufesp_pag / ufesp_obito
        itcmd_atualizado = itcmd_base * fator_correcao
        correcao_monetaria = itcmd_atualizado - itcmd_base

    # --- Multa (art. 21, I) ---
    if estrategia == "rigorosa":
        if dias <= 60:
            pct_multa = 0.0
            faixa = "Dentro do prazo (até 60 dias do óbito) — sem multa"
        elif dias <= 180:
            pct_multa = 0.10
            faixa = "Atraso entre 61 e 180 dias — multa legal de 10% (art. 21, I, Lei 10.705/00)"
        else:
            pct_multa = 0.20
            faixa = "Atraso superior a 180 dias — multa legal de 20% (art. 21, I, Lei 10.705/00)"
    elif estrategia == "conservadora":
        if dias <= 60:
            pct_multa = 0.0
            faixa = "Dentro do prazo (até 60 dias do óbito) — sem multa"
        else:
            pct_multa = 0.20
            faixa = (
                "Estratégia conservadora — multa de 20% aplicada quando óbito supera 60 dias, "
                "protegendo o cliente do risco de enquadramento futuro no art. 21, I, Lei 10.705/00"
            )
    else:
        raise ValueError(f"estrategia inválida: {estrategia!r}")

    multa = itcmd_atualizado * pct_multa

    # --- Juros de mora (1% ao mês a partir do 181º dia) ---
    if dias > 180:
        meses_atraso = (dias - 180) / 30.0
        juros_mora = itcmd_atualizado * 0.01 * meses_atraso
    else:
        juros_mora = 0.0

    acrescimos_total = multa + correcao_monetaria + juros_mora
    itcmd_total = itcmd_atualizado + multa + juros_mora

    # --- Nota explicativa pronta para o documento ---
    partes = []
    partes.append(
        f"ITCMD base calculado sobre o valor da transmissão: R$ {itcmd_base:,.2f}."
    )
    if correcao_monetaria > 0:
        partes.append(
            f"Correção monetária pela UFESP ({d_obito.year} → {d_pag.year}, "
            f"fator {fator_correcao:.4f}): +R$ {correcao_monetaria:,.2f}."
        )
    if multa > 0:
        partes.append(f"Multa por atraso ({pct_multa*100:.0f}%): +R$ {multa:,.2f}.")
    if juros_mora > 0:
        partes.append(
            f"Juros de mora (1%/mês × {(dias-180)/30.0:.1f} meses após o 181º dia): "
            f"+R$ {juros_mora:,.2f}."
        )
    partes.append(f"ITCMD total projetado: R$ {itcmd_total:,.2f}.")
    nota = " ".join(partes).replace(",", "§§").replace(".", ",").replace("§§", ".")
    # (troca formatação pt-BR: 1,234.56 → 1.234,56)

    return {
        "dias_desde_obito": dias,
        "meses_desde_obito": round(meses, 1),
        "faixa_multa": faixa,
        "percentual_multa": pct_multa,
        "itcmd_base": round(itcmd_base, 2),
        "itcmd_atualizado": round(itcmd_atualizado, 2),
        "multa": round(multa, 2),
        "correcao_monetaria": round(correcao_monetaria, 2),
        "juros_mora": round(juros_mora, 2),
        "acrescimos_total": round(acrescimos_total, 2),
        "itcmd_total": round(itcmd_total, 2),
        "ufesp_obito": ufesp_obito,
        "ufesp_pagamento": ufesp_pag,
        "fator_correcao": round(fator_correcao, 4),
        "nota_explicativa": nota,
        "estrategia_usada": estrategia,
    }


def formatar_brl(valor: float) -> str:
    """Formata valor em R$ padrão brasileiro: 1.234.567,89"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


if __name__ == "__main__":
    # Exemplo de uso — caso Ranniere
    print("=" * 70)
    print("EXEMPLO — Óbito do tio em 2023, mãe em 2024")
    print("=" * 70)

    # Óbito do tio: hipotético 10/05/2023 (VV: 299.216 × 4% = R$ 11.968,64)
    tio = calcular_acrescimos_itcmd(
        data_obito="2023-05-10",
        itcmd_base=11968.64,
        data_pagamento="2026-07-15",
        estrategia="conservadora",
    )
    print(f"\n[TIO] Óbito 2023-05-10 | ITCMD base c/MS: R$ 11.968,64")
    print(f"  Dias desde óbito: {tio['dias_desde_obito']} ({tio['meses_desde_obito']} meses)")
    print(f"  Faixa: {tio['faixa_multa']}")
    print(f"  ITCMD atualizado: {formatar_brl(tio['itcmd_atualizado'])}")
    print(f"  Correção monetária: {formatar_brl(tio['correcao_monetaria'])}")
    print(f"  Multa (20%): {formatar_brl(tio['multa'])}")
    print(f"  Juros: {formatar_brl(tio['juros_mora'])}")
    print(f"  TOTAL: {formatar_brl(tio['itcmd_total'])}")

    # Óbito da mãe: hipotético 20/08/2024 (VV: 598.432 × 4% = R$ 23.937,28)
    mae = calcular_acrescimos_itcmd(
        data_obito="2024-08-20",
        itcmd_base=23937.28,
        data_pagamento="2026-07-15",
        estrategia="conservadora",
    )
    print(f"\n[MÃE] Óbito 2024-08-20 | ITCMD base c/MS: R$ 23.937,28")
    print(f"  Dias desde óbito: {mae['dias_desde_obito']} ({mae['meses_desde_obito']} meses)")
    print(f"  Faixa: {mae['faixa_multa']}")
    print(f"  ITCMD atualizado: {formatar_brl(mae['itcmd_atualizado'])}")
    print(f"  Correção monetária: {formatar_brl(mae['correcao_monetaria'])}")
    print(f"  Multa (20%): {formatar_brl(mae['multa'])}")
    print(f"  Juros: {formatar_brl(mae['juros_mora'])}")
    print(f"  TOTAL: {formatar_brl(mae['itcmd_total'])}")

    print(f"\n{'='*70}")
    print(f"TOTAL ITCMD PROJETADO COM ACRÉSCIMOS:")
    print(f"  Base (s/acréscimos): {formatar_brl(tio['itcmd_base'] + mae['itcmd_base'])}")
    print(f"  Atualizado + acréscimos: {formatar_brl(tio['itcmd_total'] + mae['itcmd_total'])}")
    print(f"  Total de acréscimos: {formatar_brl(tio['acrescimos_total'] + mae['acrescimos_total'])}")
