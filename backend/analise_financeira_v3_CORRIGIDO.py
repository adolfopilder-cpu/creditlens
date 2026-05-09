"""
P.I.L.D.E.R™ – Motor de Análise Financeira e Comportamental v3.0
Análise de Balanço (modelo Disdal) + CISP/Credinfar (modelo Okajima)
"""
from __future__ import annotations
import re
import datetime as dt
import os
import json
import urllib.request
from typing import Optional, Dict, List, Any

ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# =============================================================================
# UTILITÁRIOS DE EXTRAÇÃO
# =============================================================================
def extrair_float(texto: str, *padroes) -> Optional[float]:
    """Extrai valor numérico próximo a qualquer dos padrões.
    Suporta: R$ 36.7898 mi, R$ 36.789.800, 36789800, 36,78
    """
    for padrao in padroes:
        # 1. Tenta formato em MILHÕES: R$ X.XXXX mi ou X,X mi
        matches_mi = re.findall(
            rf"{padrao}[^\d\n]{{0,80}}R?\$?\s*([\d][\d\.\,]{{0,10}})\s*mi\b",
            texto, re.IGNORECASE
        )
        for m in matches_mi:
            try:
                v = str(m).strip().replace(",", ".")
                return float(v) * 1_000_000
            except:
                continue

        # 2. Tenta formato normal (com ou sem R$)
        matches = re.findall(
            rf"{padrao}[^\d\n]{{0,60}}R?\$?\s*([\d][\d\.\,]{{1,15}})",
            texto, re.IGNORECASE
        )
        for m in matches:
            try:
                v = str(m).strip()
                # Detecta se é decimal brasileiro (1.234,56) ou americano (1,234.56)
                if re.search(r"\d\.\d{{3}}", v) and "," in v:
                    # Formato BR: 1.234,56
                    v = v.replace(".", "").replace(",", ".")
                elif re.search(r"\d,\d{{3}}", v) and "." in v:
                    # Formato US: 1,234.56
                    v = v.replace(",", "")
                else:
                    v = v.replace(".", "").replace(",", ".")
                val = float(v)
                if val > 0:
                    return val
            except:
                continue
    return None


def extrair_percentual(texto: str, *padroes) -> Optional[float]:
    """Extrai percentual (0-100) próximo ao padrão."""
    for padrao in padroes:
        matches = re.findall(
            rf"{padrao}[^\d\n]{{0,40}}([\d\.,]+)\s*%",
            texto, re.IGNORECASE
        )
        for m in matches:
            try:
                v = str(m).replace(",", ".")
                return float(v)
            except:
                continue
    return None


def tem(texto: str, *termos) -> bool:
    t = texto.lower()
    return any(term.lower() in t for term in termos)


def classificar(valor, bom, atencao, label_bom="BOM", label_atencao="ATENÇÃO", label_ruim="RUIM"):
    if valor is None:
        return "N/D"
    if valor >= bom:
        return label_bom
    if valor >= atencao:
        return label_atencao
    return label_ruim


# =============================================================================
# ANÁLISE DE BALANÇO — Modelo Disdal
# =============================================================================
def analisar_balanco_completo(texto: str, nome_arquivo: str = "") -> dict:
    """
    Análise completa de Balanço Patrimonial + DRE.
    Extrai indicadores reais e gera flags como analista sênior.
    """
    if not texto or len(texto.strip()) < 100:
        return _balanco_vazio(nome_arquivo)

    t = texto
    tl = texto.lower()
    red_flags = []
    yellow_flags = []
    green_flags = []
    indicadores = {}
    pontos = 0

    # ── DRE ──────────────────────────────────────────────────────────────
    receita_bruta = extrair_float(t,
        r"receita operacional bruta", r"receita bruta", r"faturamento bruto")
    receita_liq = extrair_float(t,
        r"receita operacional l[íi]quida", r"receita l[íi]quida", r"rol\b")
    lucro_bruto = extrair_float(t, r"lucro bruto")
    lucro_liq = extrair_float(t,
        r"lucro l[íi]quido", r"resultado l[íi]quido", r"lucro do exerc[íi]cio")
    prejuizo = extrair_float(t,
        r"preju[íi]zo l[íi]quido", r"preju[íi]zo do exerc[íi]cio", r"resultado negativo")
    ebitda = extrair_float(t, r"ebitda", r"lajida")
    lair = extrair_float(t, r"lair\b", r"lucro antes do ir")
    res_financeiro = extrair_float(t,
        r"resultado financeiro l[íi]quido", r"receitas financeiras")
    deducoes = extrair_float(t, r"dedu[çc][õo]es", r"devolu[çc][õo]es")
    cmv = extrair_float(t, r"cmv\b", r"custo das mercadorias", r"custo dos produtos")
    desp_vendas = extrair_float(t, r"despesas com vendas", r"despesas comerciais")
    desp_admin = extrair_float(t, r"despesas administrativas", r"despesas gerais")
    desp_logistica = extrair_float(t, r"log[íi]stica", r"frete", r"distribui[çc][aã]o")
    irpj_csll = extrair_float(t, r"irpj", r"csll", r"imposto de renda")

    # Margens
    margem_bruta = None
    margem_liq = None
    if lucro_bruto and receita_liq and receita_liq > 0:
        margem_bruta = round(lucro_bruto / receita_liq * 100, 1)
        indicadores["margem_bruta"] = margem_bruta
    if lucro_liq and receita_liq and receita_liq > 0:
        margem_liq = round(lucro_liq / receita_liq * 100, 1)
        indicadores["margem_liquida"] = margem_liq
    # Tenta extrair diretamente do texto
    if not margem_bruta:
        margem_bruta = extrair_percentual(t, r"margem bruta")
        if margem_bruta:
            indicadores["margem_bruta"] = margem_bruta
    if not margem_liq:
        margem_liq = extrair_percentual(t, r"margem l[íi]quida")
        if margem_liq:
            indicadores["margem_liquida"] = margem_liq

    if receita_bruta:
        indicadores["receita_bruta"] = receita_bruta
    if receita_liq:
        indicadores["receita_liquida"] = receita_liq
    if lucro_bruto:
        indicadores["lucro_bruto"] = lucro_bruto
    if lucro_liq:
        indicadores["lucro_liquido"] = lucro_liq
    if ebitda:
        indicadores["ebitda"] = ebitda
    if res_financeiro:
        indicadores["resultado_financeiro"] = res_financeiro

    # ── BALANÇO PATRIMONIAL ───────────────────────────────────────────────
    ativo_total = extrair_float(t, r"ativo total", r"total do ativo", r"total ativo")
    ativo_circ = extrair_float(t, r"ativo circulante\b", r"total ativo circulante")
    passivo_circ = extrair_float(t, r"passivo circulante\b", r"total passivo circulante")
    passivo_total = extrair_float(t, r"passivo total", r"total do passivo")
    pl = extrair_float(t, r"patrim[oô]nio l[íi]quido", r"\bpl\b")
    capital_social = extrair_float(t, r"capital social")
    reservas = extrair_float(t, r"reservas de lucros", r"reserva legal", r"reserva de lucros")
    caixa = extrair_float(t, r"dispon[íi]vel", r"caixa e bancos", r"caixa\b")
    titulos_rec = extrair_float(t, r"t[íi]tulos a receber", r"contas a receber", r"clientes")
    estoques = extrair_float(t, r"estoques?\b")
    emprestimos = extrair_float(t, r"empr[eé]stimos", r"financiamentos")
    afac = extrair_float(t, r"afac\b", r"adiantamento.*capital", r"adiantamento futuro")
    mutuo = extrair_float(t, r"m[úu]tuo", r"intercompany")

    if ativo_total: indicadores["ativo_total"] = ativo_total
    if pl: indicadores["patrimonio_liquido"] = pl
    if capital_social: indicadores["capital_social"] = capital_social
    if reservas: indicadores["reservas_lucros"] = reservas
    if caixa: indicadores["caixa_disponivel"] = caixa
    if titulos_rec: indicadores["titulos_receber"] = titulos_rec
    if estoques: indicadores["estoques"] = estoques

    # ── INDICADORES CALCULADOS ────────────────────────────────────────────
    # Liquidez corrente
    liq_corrente = extrair_float(t, r"liquidez corrente", r"lc\b", r"ac/pc")
    if not liq_corrente and ativo_circ and passivo_circ and passivo_circ > 0:
        liq_corrente = round(ativo_circ / passivo_circ, 2)
    if liq_corrente:
        indicadores["liquidez_corrente"] = liq_corrente

    # Liquidez imediata
    liq_imediata = extrair_float(t, r"liquidez imediata", r"li\b")
    if not liq_imediata and caixa and passivo_circ and passivo_circ > 0:
        liq_imediata = round(caixa / passivo_circ, 3)
    if liq_imediata:
        indicadores["liquidez_imediata"] = liq_imediata

    # PL/Ativo
    pl_ativo = extrair_percentual(t, r"pl\s*/\s*ativo", r"patrim[oô]nio.*ativo")
    if not pl_ativo and pl and ativo_total and ativo_total > 0:
        pl_ativo = round(pl / ativo_total * 100, 1)
    if pl_ativo:
        indicadores["pl_sobre_ativo"] = pl_ativo

    # Capital de giro
    cgl = None
    if ativo_circ and passivo_circ:
        cgl = ativo_circ - passivo_circ
        indicadores["capital_giro_liquido"] = cgl

    # Dívida financeira / PL
    div_pl = None
    if emprestimos and pl and pl > 0:
        div_pl = round(emprestimos / pl, 2)
        indicadores["divida_fin_sobre_pl"] = div_pl

    # ── FLAGS DE BALANÇO ─────────────────────────────────────────────────
    # Resultado
    if tem(t, "prejuízo do exercício", "prejuízo líquido", "resultado negativo"):
        val = extrair_float(t, r"preju[íi]zo") or 0
        red_flags.append(f"🔴 Resultado NEGATIVO identificado{f' — R$ {val:,.0f}' if val else ''} — empresa operando com prejuízo")
        pontos -= 15
    elif lucro_liq:
        green_flags.append(f"🟢 Lucro líquido: R$ {lucro_liq:,.0f} | Margem: {margem_liq:.1f}%" if margem_liq else f"🟢 Lucro líquido: R$ {lucro_liq:,.0f}")
        pontos += 8
    elif tem(t, "lucro", "resultado positivo"):
        green_flags.append("🟢 Resultado positivo (lucro) identificado no exercício")
        pontos += 5

    # Receita
    if receita_liq:
        green_flags.append(f"🟢 Receita líquida: R$ {receita_liq:,.0f}")
        pontos += 3
    if tem(t, "queda de receita", "redução de receita", "retração", "receita caiu"):
        red_flags.append("🔴 Queda/redução de receita identificada — risco de continuidade operacional")
        pontos -= 8
    if tem(t, "crescimento de receita", "aumento de receita", "crescimento do faturamento"):
        green_flags.append("🟢 Crescimento de receita registrado")
        pontos += 4

    # Margem bruta
    if margem_bruta:
        if margem_bruta >= 25:
            green_flags.append(f"🟢 Margem bruta saudável: {margem_bruta:.1f}%")
            pontos += 4
        elif margem_bruta >= 15:
            yellow_flags.append(f"🟡 Margem bruta moderada: {margem_bruta:.1f}%")
        else:
            red_flags.append(f"🔴 Margem bruta comprimida: {margem_bruta:.1f}% — pressão sobre resultado")
            pontos -= 6

    # Margem líquida
    if margem_liq is not None:
        if margem_liq < 0:
            red_flags.append(f"🔴 Margem líquida NEGATIVA: {margem_liq:.1f}% — resultado operacional comprometido")
            pontos -= 12
        elif margem_liq < 2:
            yellow_flags.append(f"🟡 Margem líquida apertada: {margem_liq:.1f}% — pouca folga")
            pontos -= 4
        elif margem_liq >= 5:
            green_flags.append(f"🟢 Margem líquida saudável: {margem_liq:.1f}%")
            pontos += 4

    # PL
    if tem(t, "patrimônio líquido negativo", "pl negativo", "passivo a descoberto"):
        red_flags.append("🔴 PATRIMÔNIO LÍQUIDO NEGATIVO — passivo a descoberto / insolvência técnica")
        pontos -= 20
    elif pl:
        green_flags.append(f"🟢 Patrimônio líquido: R$ {pl:,.0f}" + (f" ({pl_ativo:.1f}% do ativo)" if pl_ativo else ""))
        pontos += 5
        if pl_ativo and pl_ativo >= 40:
            green_flags.append(f"🟢 Empresa capitalizada: PL/Ativo = {pl_ativo:.1f}%")
            pontos += 3

    # Reservas
    if reservas:
        green_flags.append(f"🟢 Reservas de lucros acumuladas: R$ {reservas:,.0f}")
        pontos += 3

    # Liquidez corrente
    if liq_corrente:
        if liq_corrente >= 1.5:
            green_flags.append(f"🟢 Liquidez corrente saudável: {liq_corrente:.2f}×")
            pontos += 8
        elif liq_corrente >= 1.0:
            yellow_flags.append(f"🟡 Liquidez corrente aceitável, próxima do limite: {liq_corrente:.2f}×")
            pontos += 2
        else:
            red_flags.append(f"🔴 Liquidez corrente pressionada: {liq_corrente:.2f}× — risco de inadimplência com fornecedores")
            pontos -= 12

    # Liquidez imediata
    if liq_imediata and liq_imediata < 0.05:
        yellow_flags.append(f"🟡 Liquidez imediata baixa: {liq_imediata:.3f}× — caixa imediato restrito")
        pontos -= 3

    # Capital de giro
    if cgl and cgl > 0:
        green_flags.append(f"🟢 Capital de giro líquido positivo: R$ {cgl:,.0f}")
        pontos += 3
    elif cgl and cgl < 0:
        red_flags.append(f"🔴 Capital de giro líquido NEGATIVO: R$ {cgl:,.0f}")
        pontos -= 8

    # Dívida financeira
    if div_pl is not None and div_pl < 0.1:
        green_flags.append(f"🟢 Dívida financeira mínima: {div_pl:.2f}× PL — empresa praticamente sem alavancagem")
        pontos += 5
    elif div_pl and div_pl > 1.0:
        red_flags.append(f"🔴 Alta alavancagem financeira: dívida = {div_pl:.2f}× PL")
        pontos -= 10

    # Resultado financeiro
    if res_financeiro and res_financeiro > 0:
        green_flags.append(f"🟢 Resultado financeiro líquido positivo: R$ {res_financeiro:,.0f} — empresa possui aplicações relevantes")
        pontos += 4

    # AFAC
    if afac:
        yellow_flags.append(f"🟡 AFAC de R$ {afac:,.0f} no ativo — verificar beneficiário, prazo e risco de não conversão em equity")
        pontos -= 3

    # Mútuo intragrupo
    if mutuo:
        yellow_flags.append(f"🟡 Operações intragrupo (mútuo) identificadas — solicitar prazo e condições")
        pontos -= 2

    # Demonstrativos sem auditoria
    if tem(t, "sem auditoria", "internos", "não auditado", "contabilidade interna"):
        red_flags.append("🔴 Demonstrativos internos SEM auditoria externa — solicitar DFs auditadas para operações relevantes")
        pontos -= 5
    elif tem(t, "auditoria independente", "auditor independente", "sem ressalva", "opinião não modificada"):
        green_flags.append("🟢 Demonstrações financeiras auditadas por auditor independente")
        pontos += 5

    # Ressalva de auditoria
    if tem(t, "ressalva", "opinião com ressalva", "exceto por"):
        red_flags.append("🔴 RESSALVA DE AUDITORIA identificada — verificar natureza e materialidade")
        pontos -= 8

    # Contas de compensação
    contas_comp = extrair_float(t, r"contas de compensa[çc][aã]o", r"compensação")
    if contas_comp and contas_comp > 1000000:
        yellow_flags.append(f"🟡 Contas de compensação expressivas: R$ {contas_comp:,.0f} — solicitar detalhamento, podem mascarar obrigações contingentes")
        pontos -= 2

    # Perdas não operacionais
    if tem(t, "perdas não operacionais", "resultado não operacional negativo"):
        val = extrair_float(t, r"perdas n[aã]o operacionais", r"n[aã]o operacional")
        yellow_flags.append(f"🟡 Perdas não operacionais identificadas{f' — R$ {val:,.0f}' if val else ''} — investigar natureza")

    # RJ / Stress crítico
    if tem(t, "recuperação judicial"):
        red_flags.append("🔴🚨 RECUPERAÇÃO JUDICIAL mencionada — RISCO CRÍTICO")
        pontos -= 45
    if tem(t, "passivo a descoberto", "capital negativo"):
        red_flags.append("🔴 Passivo a descoberto / capital negativo identificado")
        pontos -= 20

    # Fluxo de caixa
    if tem(t, "fluxo de caixa negativo", "queima de caixa", "cash burn"):
        red_flags.append("🔴 Fluxo de caixa negativo identificado — risco operacional")
        pontos -= 10
    if tem(t, "geração de caixa", "fluxo positivo", "geração operacional"):
        green_flags.append("🟢 Geração de caixa operacional positiva")
        pontos += 4

    # Score e parecer
    pontos = int(max(-50, min(25, pontos)))
    status = "confirmacao" if not red_flags and green_flags else \
             "indicio" if len(red_flags) <= 1 else "erro"

    resumo_partes = []
    if red_flags:
        resumo_partes.append(f"⚠ {len(red_flags)} RED FLAG(S)")
    if yellow_flags:
        resumo_partes.append(f"{len(yellow_flags)} atenção")
    if green_flags:
        resumo_partes.append(f"✓ {len(green_flags)} positivo(s)")
    resumo = " | ".join(resumo_partes) if resumo_partes else "Balanço analisado"

    parecer = _gerar_parecer_balanco(
        red_flags, yellow_flags, green_flags, indicadores,
        pontos, nome_arquivo, texto
    )

    return {
        "disponivel": True,
        "arquivo": nome_arquivo,
        "status": status,
        "resumo": resumo,
        "pontos": pontos,
        "red_flags": red_flags,
        "yellow_flags": yellow_flags,
        "green_flags": green_flags,
        "indicadores": indicadores,
        "parecer_gestor": parecer,
    }


def _gerar_parecer_balanco(red, yellow, green, ind, pts, arquivo, texto_raw):
    linhas = [
        f"{ASSINATURA}",
        "━" * 65,
        "ANÁLISE DE BALANÇO PATRIMONIAL E DRE — ANALISTA SÊNIOR",
        f"Arquivo: {arquivo} | Pontuação financeira: {'+' if pts > 0 else ''}{pts}",
        "━" * 65,
    ]

    # DRE
    dre_items = {
        "Receita Bruta": ind.get("receita_bruta"),
        "Receita Líquida (ROL)": ind.get("receita_liquida"),
        "Lucro Bruto": ind.get("lucro_bruto"),
        "Lucro Líquido": ind.get("lucro_liquido"),
        "EBITDA": ind.get("ebitda"),
        "Resultado Financeiro Líq.": ind.get("resultado_financeiro"),
    }
    dre_tem = {k: v for k, v in dre_items.items() if v}
    if dre_tem:
        linhas.append("\n📊 DRE — DEMONSTRAÇÃO DO RESULTADO")
        linhas.append(f"{'Item':<35} {'Valor (R$)':>20}")
        linhas.append("-" * 57)
        for k, v in dre_tem.items():
            linhas.append(f"{k:<35} {v:>20,.0f}")
        if ind.get("margem_bruta"):
            linhas.append(f"  → Margem Bruta: {ind['margem_bruta']:.1f}%")
        if ind.get("margem_liquida"):
            linhas.append(f"  → Margem Líquida: {ind['margem_liquida']:.1f}%")

    # BP
    bp_items = {
        "Ativo Total": ind.get("ativo_total"),
        "Caixa e Disponível": ind.get("caixa_disponivel"),
        "Títulos a Receber": ind.get("titulos_receber"),
        "Estoques": ind.get("estoques"),
        "Patrimônio Líquido": ind.get("patrimonio_liquido"),
        "Capital Social": ind.get("capital_social"),
        "Reservas de Lucros": ind.get("reservas_lucros"),
    }
    bp_tem = {k: v for k, v in bp_items.items() if v}
    if bp_tem:
        linhas.append("\n🏦 BALANÇO PATRIMONIAL")
        linhas.append(f"{'Item':<35} {'Valor (R$)':>20}")
        linhas.append("-" * 57)
        for k, v in bp_tem.items():
            linhas.append(f"{k:<35} {v:>20,.0f}")

    # Indicadores
    ind_calc = {
        "Liquidez Corrente": (ind.get("liquidez_corrente"), "×", "≥1,5 BOM | ≥1,0 OK | <1,0 ATENÇÃO"),
        "Liquidez Imediata": (ind.get("liquidez_imediata"), "×", "<0,05 BAIXO"),
        "PL / Ativo Total": (ind.get("pl_sobre_ativo"), "%", "≥40% EXCELENTE"),
        "Margem Bruta": (ind.get("margem_bruta"), "%", "≥25% BOA"),
        "Margem Líquida": (ind.get("margem_liquida"), "%", "≥5% SAUDÁVEL"),
        "Capital de Giro Líq.": (ind.get("capital_giro_liquido"), "R$", ">0 SÓLIDO"),
        "Dívida Fin. / PL": (ind.get("divida_fin_sobre_pl"), "×", "<0,5 OK"),
    }
    ind_tem = [(k, v, u, ref) for k, (v, u, ref) in ind_calc.items() if v is not None]
    if ind_tem:
        linhas.append("\n📈 INDICADORES-CHAVE")
        linhas.append(f"{'Indicador':<30} {'Valor':>12} {'Referência'}")
        linhas.append("-" * 65)
        for k, v, u, ref in ind_tem:
            if u == "R$":
                linhas.append(f"{k:<30} {f'R$ {v:,.0f}':>12}  {ref}")
            elif u == "%":
                linhas.append(f"{k:<30} {f'{v:.1f}%':>12}  {ref}")
            else:
                linhas.append(f"{k:<30} {f'{v:.2f}×':>12}  {ref}")

    # Flags
    if red:
        linhas.append("\n🔴 RED FLAGS — ALERTAS CRÍTICOS")
        for f in red:
            linhas.append(f"  {f}")
    if yellow:
        linhas.append("\n🟡 YELLOW FLAGS — PONTOS DE ATENÇÃO")
        for f in yellow:
            linhas.append(f"  {f}")
    if green:
        linhas.append("\n🟢 GREEN FLAGS — ASPECTOS POSITIVOS")
        for f in green:
            linhas.append(f"  {f}")

    # Conclusão
    linhas.append("\n📋 CONCLUSÃO DO ANALISTA SÊNIOR")
    if any("recuperação judicial" in f.lower() or "passivo a descoberto" in f.lower() for f in red):
        linhas.append("  ⛔ SITUAÇÃO CRÍTICA — Sinais severos de insolvência. NEGAR crédito.")
        linhas.append("     Acionar jurídico imediatamente. Revisar toda a carteira.")
    elif len(red) >= 3:
        linhas.append("  🚨 Perfil financeiro DETERIORADO. Múltiplos alertas críticos.")
        linhas.append("     NEGAR ou limitar ao mínimo com garantia real e aval pessoal.")
    elif len(red) >= 1:
        linhas.append("  ⚠️  Perfil financeiro PRESSIONADO. Alertas presentes.")
        linhas.append("     Aprovar com cautela: limite reduzido, prazo curto, monitoramento mensal.")
    elif len(yellow) >= 2:
        linhas.append("  🟡 Perfil MODERADO. Pontos de atenção que merecem acompanhamento.")
        linhas.append("     Aprovar com monitoramento trimestral e condições de upgrade.")
    elif green:
        linhas.append("  ✅ Perfil financeiro SAUDÁVEL. Indicadores positivos predominam.")
        linhas.append("     Aprovar conforme política interna. Monitoramento semestral.")
    else:
        linhas.append("  ❓ Análise inconclusiva — poucos indicadores extraídos.")
        linhas.append("     Solicitar balanço auditado em formato estruturado.")

    linhas.append("\n" + "━" * 65)
    linhas.append(ASSINATURA)
    return "\n".join(linhas)


def _balanco_vazio(nome):
    return {
        "disponivel": False, "arquivo": nome,
        "status": "nao_consultado",
        "resumo": "Balanço não anexado ou sem texto extraível",
        "pontos": -8,
        "red_flags": [], "yellow_flags": [], "green_flags": [],
        "indicadores": {},
        "parecer_gestor": (
            f"{ASSINATURA}\n"
            "ANÁLISE DE BALANÇO — SEM DOCUMENTO\n\n"
            "Nenhuma demonstração financeira foi anexada.\n"
            "Avaliação financeira aplicada de forma conservadora (–8 pts).\n"
            "Para análise completa, solicitar: Balanço Patrimonial + DRE dos últimos 2 exercícios,\n"
            "de preferência auditados por auditor independente."
        ),
    }


# =============================================================================
# ANÁLISE CISP / CREDINFAR — Modelo Okajima
# =============================================================================
def analisar_cisp_completo(texto: str, nome_arquivo: str = "") -> dict:
    """
    Análise completa de ficha CISP/Credinfar.
    Extrai: débito, aging, PMV, concentração setorial, painel de risco.
    """
    if not texto or len(texto.strip()) < 50:
        return _cisp_vazio(nome_arquivo)

    t = texto
    tl = texto.lower()
    red_flags = []
    yellow_flags = []
    green_flags = []
    indicadores = {}
    pontos = 0

    # ── DÉBITO E AGING ────────────────────────────────────────────────────
    debito_atual = extrair_float(t,
        r"d[eé]bito atual", r"d[eé]bito total", r"exposi[çc][aã]o total",
        r"volume em aberto", r"saldo devedor")
    if debito_atual:
        indicadores["debito_atual"] = debito_atual

    # Vencidos por faixa
    venc_5d = extrair_float(t, r"vencido\s*\+?\s*5\s*d", r"venc\.\s*\+5", r"\+5\s*dias")
    venc_15d = extrair_float(t, r"vencido\s*\+?\s*15\s*d", r"venc\.\s*\+15", r"\+15\s*dias")
    venc_30d = extrair_float(t, r"vencido\s*\+?\s*30\s*d", r"venc\.\s*\+30", r"\+30\s*dias")
    venc_60d = extrair_float(t, r"vencido\s*\+?\s*60\s*d", r"venc\.\s*\+60", r"\+60\s*dias")
    venc_90d = extrair_float(t, r"vencido\s*\+?\s*90\s*d", r"venc\.\s*\+90", r"\+90\s*dias")

    if venc_5d: indicadores["vencido_5d"] = venc_5d
    if venc_15d: indicadores["vencido_15d"] = venc_15d
    if venc_30d: indicadores["vencido_30d"] = venc_30d
    if venc_60d: indicadores["vencido_60d"] = venc_60d
    if venc_90d: indicadores["vencido_90d"] = venc_90d

    # Percentuais de vencimento
    pct_5d = extrair_percentual(t, r"vencido\s*\+?\s*5", r"\+5\s*d")
    pct_15d = extrair_percentual(t, r"vencido\s*\+?\s*15", r"\+15\s*d")
    pct_30d = extrair_percentual(t, r"vencido\s*\+?\s*30", r"\+30\s*d")
    if pct_5d: indicadores["pct_vencido_5d"] = pct_5d
    if pct_15d: indicadores["pct_vencido_15d"] = pct_15d
    if pct_30d: indicadores["pct_vencido_30d"] = pct_30d

    # ── PMV (PRAZO MÉDIO DE VENCIMENTO) ───────────────────────────────────
    pmv = extrair_float(t, r"pmv\b", r"prazo m[eé]dio", r"prazo m[eé]dio de vencimento")
    if pmv:
        indicadores["pmv_dias"] = pmv
        if pmv > 45:
            yellow_flags.append(f"🟡 PMV elevado: {pmv:.0f} dias — acima do padrão setorial")
            pontos -= 3
        elif pmv <= 30:
            green_flags.append(f"🟢 PMV dentro do padrão: {pmv:.0f} dias")

    # ── CLASSE DE RISCO ───────────────────────────────────────────────────
    classe_match = re.search(r"classe\s+(?:de\s+risco\s+)?([A-E])\b", t, re.IGNORECASE)
    classe_risco = classe_match.group(1).upper() if classe_match else None
    if classe_risco:
        indicadores["classe_risco"] = classe_risco
        if classe_risco in ("A", "B"):
            green_flags.append(f"🟢 Classe de risco {classe_risco} — perfil aceitável")
            pontos += 3
        elif classe_risco == "C":
            yellow_flags.append(f"🟡 Classe de risco {classe_risco} — atenção")
            pontos -= 3
        else:
            red_flags.append(f"🔴 Classe de risco {classe_risco} — risco elevado")
            pontos -= 8

    # ── ANÁLISE DO AGING ─────────────────────────────────────────────────
    if debito_atual and venc_30d:
        pct_30d_calc = round(venc_30d / debito_atual * 100, 1)
        if pct_30d_calc >= 25:
            red_flags.append(
                f"🔴 Parcela madura crítica: {pct_30d_calc:.1f}% do débito vencida há +30 dias "
                f"(R$ {venc_30d:,.0f}) — sinaliza problema real de recomposição de caixa"
            )
            pontos -= 12
        elif pct_30d_calc >= 10:
            yellow_flags.append(f"🟡 {pct_30d_calc:.1f}% do débito vencido há +30 dias — monitorar evolução")
            pontos -= 5

    if debito_atual and venc_15d:
        pct_15d_calc = round(venc_15d / debito_atual * 100, 1)
        if pct_15d_calc >= 30:
            red_flags.append(
                f"🔴 Sinal forte de estresse: {pct_15d_calc:.1f}% do débito vencido há +15 dias "
                f"(R$ {venc_15d:,.0f}) — antecede endurecimento do mercado"
            )
            pontos -= 10
        elif pct_15d_calc >= 15:
            yellow_flags.append(f"🟡 {pct_15d_calc:.1f}% do débito vencido há +15 dias")
            pontos -= 4

    if debito_atual and venc_5d:
        pct_5d_calc = round(venc_5d / debito_atual * 100, 1)
        if pct_5d_calc >= 40:
            red_flags.append(
                f"🔴 Nível alto de atraso: {pct_5d_calc:.1f}% do débito vencido há +5 dias "
                f"(R$ {venc_5d:,.0f})"
            )
            pontos -= 8
        elif pct_5d_calc >= 20:
            yellow_flags.append(f"🟡 {pct_5d_calc:.1f}% do débito vencido há +5 dias")
            pontos -= 3

    # ── CONCENTRAÇÃO SETORIAL ─────────────────────────────────────────────
    setores_risco = []
    for setor in ["hpc", "higiene", "cosméticos", "varejo", "alimentação",
                  "farma", "construção", "têxtil", "moda"]:
        if setor in tl:
            val = extrair_float(t, setor)
            setores_risco.append(setor.upper())
    if setores_risco:
        indicadores["setores_expostos"] = setores_risco

    # Concentração HPC/Higiene (como no caso Okajima)
    if "hpc" in tl or "higiene pessoal" in tl:
        hpc_val = extrair_float(t, r"hpc", r"higiene pessoal")
        if hpc_val and debito_atual and hpc_val / debito_atual > 0.5:
            red_flags.append(
                f"🔴 Alta concentração em HPC/Higiene: R$ {hpc_val:,.0f} "
                f"({hpc_val/debito_atual*100:.0f}% do débito) com atraso expressivo"
            )
            pontos -= 8

    # ── ALERTA DA PRÓPRIA FICHA ───────────────────────────────────────────
    if tem(t, "alerta", "excesso de vencido", "excesso de atraso"):
        red_flags.append("🔴 ALERTA REGISTRADO NA PRÓPRIA FICHA CISP — sinal de deterioração reconhecida pelo mercado")
        pontos -= 10

    # ── GARANTIAS ────────────────────────────────────────────────────────
    garantia = extrair_float(t, r"seguro de cr[eé]dito", r"garantia", r"aval")
    if garantia:
        indicadores["garantia_valor"] = garantia
        cobertura = round(garantia / debito_atual * 100, 1) if debito_atual else None
        if cobertura and cobertura < 15:
            yellow_flags.append(
                f"🟡 Garantia/seguro de R$ {garantia:,.0f} — cobertura parcial "
                f"({cobertura:.1f}% da exposição total)"
            )
        elif garantia:
            green_flags.append(f"🟢 Garantia/seguro registrado: R$ {garantia:,.0f}")
            pontos += 3

    # ── CHEQUE SEM FUNDOS ────────────────────────────────────────────────
    if tem(t, "cheque sem fundos", "ccf", "cheques devolvidos"):
        red_flags.append("🔴 Cheque(s) sem fundos registrado(s) — sinaliza quebra de disciplina financeira")
        pontos -= 15
    elif tem(t, "sem cheque", "quesito 5", "não há cheque", "ausência de cheque"):
        green_flags.append("🟢 Sem ocorrências de cheque sem fundos na ficha")
        pontos += 2

    # ── HISTÓRICO E RELACIONAMENTO ────────────────────────────────────────
    assoc_debito = extrair_float(t, r"associadas com d[eé]bito", r"fornecedores com d[eé]bito")
    if assoc_debito:
        indicadores["associadas_debito"] = int(assoc_debito)
        if assoc_debito >= 8:
            yellow_flags.append(f"🟡 {int(assoc_debito)} fornecedores com débito — dispersão relevante de inadimplência")
            pontos -= 4

    vendas_recentes = extrair_float(t, r"vendas nos\s*\d+\s*[úu]ltimos", r"transa[çc][õo]es recentes")
    if vendas_recentes:
        indicadores["vendas_recentes"] = int(vendas_recentes)
        if vendas_recentes >= 3:
            green_flags.append(f"🟢 {int(vendas_recentes)} vendas recentes — relação comercial ainda ativa")
            pontos += 2

    # ── ESTABILIDADE ─────────────────────────────────────────────────────
    meses_match = re.search(r"(\d+)\s*mes(?:es)?\s*(?:na\s*classe|est[aá]vel)", t, re.IGNORECASE)
    if meses_match:
        meses = int(meses_match.group(1))
        indicadores["meses_estabilidade"] = meses
        if meses >= 12:
            green_flags.append(f"🟢 {meses} meses na mesma classe de risco — estabilidade relativa")
            pontos += 2

    # ── BLOQUEIO / NEGATIVAÇÃO ────────────────────────────────────────────
    if tem(t, "bloqueado", "negativado", "suspenso", "restrito"):
        red_flags.append("🔴 Cadastro com restrição/bloqueio ativo")
        pontos -= 15

    # Adimplência positiva
    if tem(t, "adimplente", "bom pagador", "pontual", "em dia") and not red_flags:
        green_flags.append("🟢 Histórico de pontualidade comercial registrado")
        pontos += 6

    # Protestos
    if tem(t, "protesto", "cartório", "ieptb"):
        red_flags.append("🔴 Protestos cartorários identificados")
        pontos -= 10

    pontos = int(max(-30, min(15, pontos)))
    status = "confirmacao" if not red_flags and green_flags else \
             "indicio" if len(red_flags) <= 1 else "erro"

    parecer = _gerar_parecer_cisp(
        red_flags, yellow_flags, green_flags, indicadores,
        pontos, nome_arquivo, debito_atual
    )

    resumo_partes = []
    if red_flags: resumo_partes.append(f"⚠ {len(red_flags)} RED FLAG(S)")
    if yellow_flags: resumo_partes.append(f"{len(yellow_flags)} atenção")
    if green_flags: resumo_partes.append(f"✓ {len(green_flags)} positivo(s)")
    if debito_atual: resumo_partes.append(f"Débito: R$ {debito_atual:,.0f}")

    return {
        "disponivel": True,
        "arquivo": nome_arquivo,
        "status": status,
        "resumo": " | ".join(resumo_partes) if resumo_partes else "CISP analisada",
        "pontos": pontos,
        "red_flags": red_flags,
        "yellow_flags": yellow_flags,
        "green_flags": green_flags,
        "indicadores": indicadores,
        "parecer_gestor": parecer,
    }


def _gerar_parecer_cisp(red, yellow, green, ind, pts, arquivo, debito):
    linhas = [
        f"{ASSINATURA}",
        "━" * 65,
        "ANÁLISE CISP / CREDINFAR — COMPORTAMENTO COMERCIAL",
        f"Arquivo: {arquivo} | Pontuação comportamental: {'+' if pts > 0 else ''}{pts}",
        "━" * 65,
    ]

    # Painel de indicadores
    if ind:
        linhas.append("\n📊 INDICADORES EXTRAÍDOS DA FICHA")
        linhas.append(f"{'Indicador':<35} {'Valor':>20}")
        linhas.append("-" * 57)
        for k, v in ind.items():
            label = k.replace("_", " ").title()
            if isinstance(v, float) and v > 1000:
                linhas.append(f"{label:<35} {'R$ {:,.0f}'.format(v):>20}")
            elif isinstance(v, float) and v < 100:
                linhas.append(f"{label:<35} {f'{v:.2f}':>20}")
            elif isinstance(v, list):
                linhas.append(f"{label:<35} {', '.join(v):>20}")
            else:
                linhas.append(f"{label:<35} {str(v):>20}")

    # Aging detalhado
    if debito and any(k in ind for k in ("vencido_5d","vencido_15d","vencido_30d")):
        linhas.append("\n📅 ANÁLISE DE AGING")
        linhas.append(f"{'Faixa':<25} {'Valor (R$)':>15} {'% do Débito':>12} {'Leitura'}")
        linhas.append("-" * 70)
        linhas.append(f"{'Débito atual total':<25} {'R$ {:,.0f}'.format(debito):>15} {'100,0%':>12} {'—'}")
        for faixa, key, ref in [
            ("+5 dias", "vencido_5d", 20),
            ("+15 dias", "vencido_15d", 15),
            ("+30 dias", "vencido_30d", 10),
            ("+60 dias", "vencido_60d", 5),
            ("+90 dias", "vencido_90d", 3),
        ]:
            val = ind.get(key)
            if val:
                pct = val / debito * 100
                sinal = "🔴 CRÍTICO" if pct >= ref*2 else "🟡 ATENÇÃO" if pct >= ref else "🟢 OK"
                linhas.append(f"{'Vencido ' + faixa:<25} {'R$ {:,.0f}'.format(val):>15} {f'{pct:.1f}%':>12} {sinal}")

    # Painel sintético de risco (estilo Okajima)
    linhas.append("\n🎯 PAINEL SINTÉTICO DE RISCO (0=baixo | 10=alto)")
    linhas.append("-" * 50)
    painel = []
    if red: painel.append(("Pontualidade comercial", min(10, len(red) * 2.5)))
    if ind.get("vencido_30d") and debito:
        painel.append(("Volume vencido maduro (+30d)", min(10, (ind["vencido_30d"]/debito)*40)))
    if ind.get("vencido_15d") and debito:
        painel.append(("Sinais de estresse (+15d)", min(10, (ind["vencido_15d"]/debito)*30)))
    if ind.get("garantia_valor") and debito:
        cobertura = ind["garantia_valor"]/debito
        painel.append(("Mitigadores / garantias", max(0, 5 - cobertura*10)))
    for nome, score in sorted(painel, key=lambda x: x[1], reverse=True):
        barra = "█" * int(score) + "░" * (10 - int(score))
        linhas.append(f"  {nome:<30} {barra} {score:.1f}")

    # Flags
    if red:
        linhas.append("\n🔴 RED FLAGS")
        for f in red: linhas.append(f"  {f}")
    if yellow:
        linhas.append("\n🟡 YELLOW FLAGS")
        for f in yellow: linhas.append(f"  {f}")
    if green:
        linhas.append("\n🟢 GREEN FLAGS")
        for f in green: linhas.append(f"  {f}")

    # Conclusão
    linhas.append("\n📋 DECISÃO RECOMENDADA")
    n_red = len(red)
    if n_red >= 3:
        linhas.append("  ⛔ RISCO ALTO — Reduzir ou congelar limite.")
        linhas.append("  Exigir: balanço + DRE + DFC + aval + cessão de recebíveis.")
        linhas.append("  Monitoramento: semanal. Gatilho: piora de +30d → suspensão imediata.")
    elif n_red >= 1:
        linhas.append("  ⚠️  OPERAR COM TRAVA DE LIMITE.")
        linhas.append("  Prazo curto e revisável. Reforço de garantias além do seguro.")
        linhas.append("  Monitoramento: semanal da ficha CISP, especialmente +15d e +30d.")
    elif yellow:
        linhas.append("  🟡 APROVAÇÃO CAUTELOSA. Monitoramento mensal.")
        linhas.append("  Manter limite atual. Solicitar documentação fiscal e financeira.")
    else:
        linhas.append("  ✅ Comportamento comercial POSITIVO. Aprovação conforme política.")
        linhas.append("  Monitoramento: trimestral.")

    linhas.append("\n" + "━" * 65)
    linhas.append(ASSINATURA)
    return "\n".join(linhas)


def _cisp_vazio(nome):
    return {
        "disponivel": False, "arquivo": nome,
        "status": "nao_consultado",
        "resumo": "Ficha CISP/Credinfar não anexada",
        "pontos": 0,
        "red_flags": [], "yellow_flags": [], "green_flags": [],
        "indicadores": {},
        "parecer_gestor": f"{ASSINATURA}\nFicha CISP não disponível para análise comportamental.",
    }


# =============================================================================
# CONSOLIDAÇÃO FINAL
# =============================================================================
def gerar_analise_completa(resultado: dict, balanco: dict,
                            cisp: dict, balanco_texto: str = "",
                            cisp_texto: str = "") -> dict:
    from analise_detalhada_v2 import (
        gerar_parecer_analista_senior,
        registrar_rastreabilidade,
        CATEGORIAS_EVIDENCIA,
    )
    cnpj = resultado.get("cnpj", "")
    fontes = resultado.get("fontes", [])
    dados_cadastrais = next(
        ({k: v for k, v in f.items()
          if k not in ("raw","evidence","status","resumo","detalhe","pontos","consultado_em","fonte")}
         for f in fontes if "receita" in f.get("fonte","").lower()),
        {}
    )
    parecer = gerar_parecer_analista_senior(
        cnpj, dados_cadastrais, fontes, balanco_texto, cisp_texto
    )
    rastreio = registrar_rastreabilidade(cnpj, parecer["fontes_classificadas"], parecer)
    return {
        **resultado,
        "balanco_detalhado": balanco,
        "cisp_detalhado": cisp,
        "parecer_senior": parecer,
        "rastreabilidade": rastreio,
        "framework_evidencia": CATEGORIAS_EVIDENCIA,
        "assinatura": ASSINATURA,
        "relatorio_gerado_em": dt.datetime.now().isoformat(),
    }
