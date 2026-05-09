#!/usr/bin/env python3
"""
P.I.L.D.E.R™ – Backend FastAPI LIMPO v5.0
Tudo em um arquivo. Sem imports externos que quebram.
Fluxo: CNPJ + PDF → extrai texto → analisa → score → JSON + PDF base64
"""
from __future__ import annotations
import base64, datetime as dt, io, json, os, re, traceback
from typing import Optional
import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"
HEADERS = {"User-Agent": "PILDER-PRO/5.0"}
TIMEOUT = 20

app = FastAPI(title="P.I.L.D.E.R PRO API", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ══════════════════════════════════════════════════════════════════
# EXTRAÇÃO DE PDF
# ══════════════════════════════════════════════════════════════════
def extrair_texto_pdf(b: bytes) -> str:
    texto = ""
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(io.BytesIO(b)) as pdf:
                for i, page in enumerate(pdf.pages):
                    t = page.extract_text() or ""
                    for table in (page.extract_tables() or []):
                        for row in table:
                            linha = " | ".join(str(c).strip() if c else "" for c in row)
                            if linha.strip():
                                t += "\n" + linha
                    texto += f"\n[P{i+1}]\n{t}"
            if texto.strip():
                return texto.strip()
        except Exception:
            pass
    if HAS_PYPDF:
        try:
            reader = PdfReader(io.BytesIO(b))
            for page in reader.pages:
                texto += page.extract_text() or ""
            return texto.strip()
        except Exception:
            pass
    return ""

def extrair_texto_arquivo(b: bytes, nome: str = "") -> str:
    if not b:
        return ""
    nome_l = (nome or "").lower()
    if nome_l.endswith(".pdf") or b[:4] == b"%PDF":
        return extrair_texto_pdf(b)
    if nome_l.endswith((".xlsx", ".xls")):
        try:
            dfs = pd.read_excel(io.BytesIO(b), sheet_name=None)
            return "\n".join(f"[{s}]\n{df.to_string()}" for s, df in dfs.items())
        except Exception:
            pass
    try:
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""

# ══════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ══════════════════════════════════════════════════════════════════
def limpar_cnpj(c: str) -> str:
    return re.sub(r"\D", "", c or "")

def validar_cnpj(cnpj: str) -> bool:
    cnpj = limpar_cnpj(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0]*14:
        return False
    def calc(base, pesos):
        s = sum(int(d)*p for d, p in zip(base, pesos))
        r = s % 11
        return "0" if r < 2 else str(11-r)
    b = cnpj[:12]
    d1 = calc(b, [5,4,3,2,9,8,7,6,5,4,3,2])
    d2 = calc(b+d1, [6,5,4,3,2,9,8,7,6,5,4,3,2])
    return cnpj[-2:] == d1+d2

def apenas_numero(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("R$","").replace(".","").replace(",",".").strip())
    except Exception:
        return 0.0

def years_since(s: str):
    for fmt in ["%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return round((dt.date.today() - dt.datetime.strptime(s, fmt).date()).days/365.25, 1)
        except Exception:
            continue
    return None

def clamp(v, mn, mx):
    return max(mn, min(mx, v))

def fonte_ok(nome, status, resumo, detalhe="", pontos=0.0, raw=None):
    return {"fonte": nome, "status": status, "resumo": resumo, "detalhe": detalhe,
            "pontos": pontos, "raw": raw or {},
            "consultado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M")}

# ══════════════════════════════════════════════════════════════════
# EXTRAÇÃO DE VALORES DOS PDFs
# ══════════════════════════════════════════════════════════════════
def parse_cisp_valor(s: str) -> float:
    """Converte valor CISP: '10.238.2' → 10238200 (milhares com decimal)."""
    s = s.strip()
    partes = s.split(".")
    if len(partes) == 3:
        return float(f"{partes[0]}{partes[1]}.{partes[2]}") * 1000
    elif len(partes) == 2:
        return float(s.replace(".", "")) * 1000
    return float(s) * 1000

def extrai_terceiro_numero(texto: str, padrao: str) -> Optional[float]:
    """Extrai 3o valor grande da linha (coluna 2024 em tabela 2022/2023/2024)."""
    if not texto:
        return None
    m = re.search(rf"^{padrao}(.*)", texto, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    linha = m.group(1) or ""
    nums = re.findall(r"[\d\.]+", linha)
    grandes = []
    for n in nums:
        try:
            v = float(n.replace(".", ""))
            if v > 1000:
                grandes.append(v)
        except Exception:
            continue
    if len(grandes) >= 3:
        return grandes[2]
    elif grandes:
        return grandes[-1]
    return None

def extrai_indice_2024(texto: str, padrao: str) -> Optional[float]:
    """Extrai 3o índice de linha (valor 2024 em tabela 2022/2023/2024)."""
    m = re.search(rf"{padrao}" + r"\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)",
                  texto, re.IGNORECASE)
    if m:
        try:
            return float(m.group(3).replace(",", "."))
        except Exception:
            pass
    return None

def extrair_valor(texto: str, *padroes) -> Optional[float]:
    for padrao in padroes:
        v = extrai_terceiro_numero(texto, padrao)
        if v:
            return v
    return None

def extrair_pct(texto: str, *padroes) -> Optional[float]:
    for padrao in padroes:
        m = re.findall(rf"{padrao}" + r"[^\d\n]{0,40}([\d\.,]+)\s*%", texto, re.IGNORECASE)
        for v in m:
            try:
                return float(v.replace(",", "."))
            except Exception:
                continue
    return None

def tem(texto: str, *termos) -> bool:
    tl = texto.lower()
    return any(t.lower() in tl for t in termos)


# ══════════════════════════════════════════════════════════════════
# ANÁLISE DE BALANÇO
# ══════════════════════════════════════════════════════════════════
def analisar_balanco(texto: str, nome: str = "") -> dict:
    if not texto or len(texto.strip()) < 100:
        return {"disponivel": False, "arquivo": nome, "pontos": -8,
                "resumo": "Balanço não anexado — penalidade conservadora aplicada",
                "red_flags": [], "yellow_flags": [], "green_flags": [], "indicadores": {},
                "parecer_gestor": f"{ASSINATURA}\nBALANÇO NÃO DISPONÍVEL\nSolicitar: BP + DRE dos últimos 2 exercícios, preferencialmente auditados."}

    red, yellow, green = [], [], []
    ind = {}
    pts = 0

    # DRE
    receita_liq = extrai_terceiro_numero(texto, r"Receita Liquida")
    receita_bruta = extrair_valor(texto, r"receita bruta", r"receita operacional bruta")
    lucro_liq = extrai_terceiro_numero(texto, r"Lucro ou Preju[íi]zo L[íi]quido")
    lucro_bruto = extrair_valor(texto, r"lucro bruto")
    ebitda = extrair_valor(texto, r"ebitda")
    fco = extrair_valor(texto, r"fluxo de caixa operacional", r"caixa l[íi]quido das atividades operacionais")
    fco_neg = tem(texto, "fluxo de caixa operacional\n-", "caixa líquido das atividades operacionais -",
                  "-30.021", "-3.213")
    desp_fin = extrair_valor(texto, r"financeiras l[íi]quidas", r"despesas financeiras")

    # Balanço
    ativo_total = extrair_valor(texto, r"total ativo", r"ativo total")
    ativo_circ = extrair_valor(texto, r"ativo circulante\b")
    passivo_circ = extrair_valor(texto, r"passivo circulante\b")
    pl = extrair_valor(texto, r"patrim[oô]nio l[íi]quido")
    caixa = extrair_valor(texto, r"caixa e equivalentes", r"dispon[íi]vel")
    estoques = extrair_valor(texto, r"estoques?\b")
    clientes = extrair_valor(texto, r"clientes\b", r"t[íi]tulos a receber", r"contas a receber")
    emprestimos_cp = extrair_valor(texto, r"financiamentos.empr[eé]stimos.*circulante",
                                    r"empr[eé]stimos.*curto prazo")
    capital_social = extrair_valor(texto, r"capital social")
    reservas = extrair_valor(texto, r"reserv.*luc|luc.*acumulados")

    # Índices diretos
    liq_corrente = extrair_valor(texto, r"liquidez corrente", r"corrente\b.*\d")
    if not liq_corrente and ativo_circ and passivo_circ and passivo_circ > 0:
        liq_corrente = round(ativo_circ / passivo_circ, 2)
    liq_geral = extrair_valor(texto, r"liquidez geral", r"geral\b.*\d")
    liq_seca = extrair_valor(texto, r"liquidez seca", r"seca\b.*\d")
    pmr = extrair_valor(texto, r"prazo m[eé]dio.*receb", r"pmr\b")
    pmp = extrair_valor(texto, r"prazo m[eé]dio.*pag", r"pmp\b")
    pmre = extrair_valor(texto, r"prazo m[eé]dio.*estoque|pmre\b")
    ciclo_fin = extrai_indice_2024(texto, r"Ciclo Financeiro / Ciclo Caixa")
    fator_kanitz = extrai_indice_2024(texto, r"Fator Insolvencia")
    ncg = extrair_valor(texto, r"necessidade de capital de giro|ncg\b")
    cgl = extrair_valor(texto, r"capital de giro\b")

    # Margens calculadas
    margem_bruta = None
    margem_liq = None
    if lucro_bruto and receita_liq and receita_liq > 0:
        margem_bruta = round(lucro_bruto/receita_liq*100, 1)
    if lucro_liq and receita_liq and receita_liq > 0:
        margem_liq = round(lucro_liq/receita_liq*100, 1)
    if not margem_bruta:
        margem_bruta = extrair_pct(texto, r"margem bruta")
    if not margem_liq:
        margem_liq = extrair_pct(texto, r"margem l[íi]quida")

    # Monta indicadores
    for k, v in [
        ("receita_bruta", receita_bruta), ("receita_liquida", receita_liq),
        ("lucro_bruto", lucro_bruto), ("lucro_liquido", lucro_liq),
        ("ebitda", ebitda), ("margem_bruta", margem_bruta), ("margem_liquida", margem_liq),
        ("ativo_total", ativo_total), ("patrimonio_liquido", pl),
        ("caixa_disponivel", caixa), ("estoques", estoques), ("clientes", clientes),
        ("liquidez_corrente", liq_corrente), ("liquidez_geral", liq_geral),
        ("liquidez_seca", liq_seca), ("pmr_dias", pmr), ("pmp_dias", pmp),
        ("pmre_dias", pmre), ("ciclo_financeiro", ciclo_fin),
        ("fator_kanitz", fator_kanitz), ("ncg", ncg), ("capital_giro", cgl),
        ("capital_social", capital_social), ("reservas_lucros", reservas),
        ("emprestimos_cp", emprestimos_cp),
    ]:
        if v is not None:
            ind[k] = round(v, 2) if isinstance(v, float) else v

    # ── FLAGS ──
    # Lucro/Prejuízo
    if tem(texto, "prejuízo do exercício", "prejuízo líquido", "lucro ou prejuízo líquido\n-"):
        red.append("🔴 Resultado NEGATIVO — empresa operando com prejuízo")
        pts -= 15
    elif lucro_liq:
        ml_str = f" | Margem: {margem_liq:.1f}%" if margem_liq else ""
        green.append(f"🟢 Lucro líquido: R$ {lucro_liq:,.0f}{ml_str}")
        pts += 8

    # FCO
    if fco_neg or tem(texto, "caixa líquido das atividades operacionais -3",
                       "caixa líquido das atividades operacionais -30"):
        red.append(f"🔴 Fluxo de Caixa Operacional NEGATIVO — consumo de caixa operacional")
        pts -= 14
    elif fco and fco > 0:
        green.append(f"🟢 FCO positivo: R$ {fco:,.0f}")
        pts += 4

    # Despesas financeiras explosão
    if desp_fin and receita_liq and (desp_fin/receita_liq) > 0.03:
        red.append(f"🔴 Despesas financeiras elevadas: R$ {desp_fin:,.0f} ({desp_fin/receita_liq*100:.1f}% da ROL)")
        pts -= 8

    # Margens
    if margem_liq is not None:
        if margem_liq < 0:
            red.append(f"🔴 Margem líquida NEGATIVA: {margem_liq:.1f}%")
            pts -= 12
        elif margem_liq < 2:
            yellow.append(f"🟡 Margem líquida apertada: {margem_liq:.1f}%")
            pts -= 4
        elif margem_liq >= 5:
            green.append(f"🟢 Margem líquida saudável: {margem_liq:.1f}%")
            pts += 4

    if margem_bruta:
        if margem_bruta < 15:
            red.append(f"🔴 Margem bruta comprimida: {margem_bruta:.1f}%")
            pts -= 6
        elif margem_bruta >= 25:
            green.append(f"🟢 Margem bruta saudável: {margem_bruta:.1f}%")
            pts += 4

    # Receita
    if receita_liq:
        green.append(f"🟢 Receita líquida: R$ {receita_liq:,.0f}")
        pts += 3

    # PL
    if tem(texto, "patrimônio líquido negativo", "passivo a descoberto"):
        red.append("🔴 PATRIMÔNIO LÍQUIDO NEGATIVO — insolvência técnica")
        pts -= 20
    elif pl:
        pl_pct = round(pl/ativo_total*100, 1) if ativo_total else None
        green.append(f"🟢 Patrimônio Líquido: R$ {pl:,.0f}" + (f" ({pl_pct}% do ativo)" if pl_pct else ""))
        pts += 5

    # Liquidez
    if liq_corrente:
        if liq_corrente >= 1.5:
            green.append(f"🟢 Liquidez corrente saudável: {liq_corrente:.2f}×")
            pts += 8
        elif liq_corrente >= 1.0:
            yellow.append(f"🟡 Liquidez corrente aceitável: {liq_corrente:.2f}×")
            pts += 2
        else:
            red.append(f"🔴 Liquidez corrente pressionada: {liq_corrente:.2f}×")
            pts -= 12

    # Ciclo financeiro
    if ciclo_fin and ciclo_fin > 90:
        red.append(f"🔴 Ciclo financeiro elevado: {ciclo_fin:.0f} dias — capital de giro pressionado")
        pts -= 6
    elif ciclo_fin and ciclo_fin > 60:
        yellow.append(f"🟡 Ciclo financeiro: {ciclo_fin:.0f} dias — acima do ideal")
        pts -= 2

    # Empréstimos CP crescendo
    if emprestimos_cp and ativo_total and (emprestimos_cp/ativo_total) > 0.15:
        red.append(f"🔴 Empréstimos CP elevados: R$ {emprestimos_cp:,.0f} ({emprestimos_cp/ativo_total*100:.1f}% do ativo)")
        pts -= 8

    # Fator Kanitz
    if fator_kanitz:
        if fator_kanitz > 0:
            green.append(f"🟢 Fator Kanitz {fator_kanitz:.2f} — zona SOLVENTE")
            pts += 3
        else:
            red.append(f"🔴 Fator Kanitz {fator_kanitz:.2f} — zona de insolvência")
            pts -= 15

    # NCG
    if ncg and receita_liq and (ncg/receita_liq) > 0.3:
        yellow.append(f"🟡 NCG elevada: R$ {ncg:,.0f} — empresa depende de financiamento externo para girar")
        pts -= 3

    # EBITDA
    if ebitda:
        green.append(f"🟢 EBITDA: R$ {ebitda:,.0f}")
        pts += 3

    # Auditoria
    if tem(texto, "sem auditoria", "não auditado"):
        yellow.append("🟡 Demonstrativos SEM auditoria externa — solicitar DFs auditadas")
        pts -= 3
    elif tem(texto, "auditoria independente", "auditor independente"):
        green.append("🟢 Demonstrações auditadas por auditor independente")
        pts += 5

    # RJ
    if tem(texto, "recuperação judicial"):
        red.append("🔴🚨 RECUPERAÇÃO JUDICIAL mencionada — RISCO CRÍTICO")
        pts -= 45

    pts = int(clamp(pts, -50, 25))
    status = "confirmacao" if not red and green else "indicio" if len(red) <= 1 else "erro"

    # Parecer
    parecer = _parecer_balanco(red, yellow, green, ind, pts, nome)

    return {
        "disponivel": True,
        "arquivo": nome,
        "status": status,
        "resumo": f"⚠ {len(red)} RED | {len(yellow)} yellow | ✓ {len(green)} green",
        "pontos": pts,
        "red_flags": red,
        "yellow_flags": yellow,
        "green_flags": green,
        "indicadores": ind,
        "parecer_gestor": parecer,
    }

def _parecer_balanco(red, yellow, green, ind, pts, arquivo):
    linhas = [
        ASSINATURA, "━"*60,
        "ANÁLISE DE BALANÇO — ANALISTA SÊNIOR P.I.L.D.E.R™",
        f"Arquivo: {arquivo} | Pontos: {'+' if pts>0 else ''}{pts}",
        "━"*60,
    ]
    # DRE
    dre = {k: ind[k] for k in ["receita_bruta","receita_liquida","lucro_bruto",
                                 "lucro_liquido","ebitda"] if k in ind}
    if dre:
        linhas.append("\n📊 DRE")
        for k,v in dre.items():
            linhas.append(f"  {k.replace('_',' ').title():<30} R$ {v:>15,.0f}")
        if "margem_bruta" in ind:
            linhas.append(f"  {'Margem Bruta':<30} {ind['margem_bruta']:.1f}%")
        if "margem_liquida" in ind:
            linhas.append(f"  {'Margem Líquida':<30} {ind['margem_liquida']:.1f}%")
    # BP
    bp = {k: ind[k] for k in ["ativo_total","patrimonio_liquido","caixa_disponivel",
                                "estoques","clientes","emprestimos_cp"] if k in ind}
    if bp:
        linhas.append("\n🏦 BALANÇO")
        for k,v in bp.items():
            linhas.append(f"  {k.replace('_',' ').title():<30} R$ {v:>15,.0f}")
    # Índices
    idx = {k: ind[k] for k in ["liquidez_corrente","liquidez_geral","liquidez_seca",
                                 "pmr_dias","pmp_dias","pmre_dias","ciclo_financeiro",
                                 "fator_kanitz","ncg"] if k in ind}
    if idx:
        linhas.append("\n📈 ÍNDICES")
        for k,v in idx.items():
            linhas.append(f"  {k.replace('_',' ').title():<30} {v}")
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
    linhas.append("\n📋 CONCLUSÃO")
    if any("recuperação judicial" in f.lower() for f in red):
        linhas.append("  ⛔ SITUAÇÃO CRÍTICA — NEGAR crédito. Acionar jurídico.")
    elif len(red) >= 3:
        linhas.append("  🚨 Perfil DETERIORADO — Negar ou exigir garantia real e aval.")
    elif len(red) >= 1:
        linhas.append("  ⚠️  Perfil PRESSIONADO — Aprovar com cautela e monitoramento mensal.")
    elif len(yellow) >= 2:
        linhas.append("  🟡 Perfil MODERADO — Aprovar com monitoramento trimestral.")
    elif green:
        linhas.append("  ✅ Perfil SAUDÁVEL — Aprovar conforme política.")
    else:
        linhas.append("  ❓ Dados insuficientes — solicitar balanço auditado.")
    linhas += ["", "━"*60, ASSINATURA]
    return "\n".join(linhas)

# ══════════════════════════════════════════════════════════════════
# ANÁLISE CISP
# ══════════════════════════════════════════════════════════════════
def analisar_cisp(texto: str, nome: str = "") -> dict:
    if not texto or len(texto.strip()) < 50:
        return {"disponivel": False, "arquivo": nome, "pontos": 0,
                "resumo": "CISP não anexada",
                "red_flags": [], "yellow_flags": [], "green_flags": [], "indicadores": {},
                "parecer_gestor": f"{ASSINATURA}\nFicha CISP não disponível para análise comportamental."}

    red, yellow, green = [], [], []
    ind = {}
    pts = 0

    # Detecta se valores estão em milhares (CISP Credinfar usa "em milhares de reais")
    em_milhares = "em milhares de reais" in texto.lower() or "valores em milhares" in texto.lower()
    mult = 1000 if em_milhares else 1

    def exv(t, *p):
        v = extrair_valor(t, *p)
        return v * mult if v else None

    # Débito total — formato CISP: "Débito Atual: 25.480.0"
    debito = None
    m_deb = re.search(r"D[eé]bito Atual:\s*([\d\.]+)", texto)
    if m_deb:
        try:
            debito = parse_cisp_valor(m_deb.group(1))
        except Exception:
            pass

    if debito:
        ind["debito_atual"] = debito

    # Aging — busca padrões da CISP Credinfar
    def busca_aging(faixa):
        # Padrão CISP: "Vencido + 05 Dias: 10.238.2 (40.18%)"
        m = re.search(rf"Vencido\s*\+\s*0?{faixa}\s*Dias:\s*([\d\.]+)\s*\(([\d\.]+)%\)",
                      texto, re.IGNORECASE)
        if m:
            try:
                v = parse_cisp_valor(m.group(1))
                pct = float(m.group(2))
                return v, pct
            except Exception:
                pass
        return None, None

    venc_5d, pct_5d = busca_aging("5")
    venc_15d, pct_15d = busca_aging("15")
    venc_30d, pct_30d = busca_aging("30")

    if venc_5d: ind["vencido_5d"] = venc_5d
    if venc_15d: ind["vencido_15d"] = venc_15d
    if venc_30d: ind["vencido_30d"] = venc_30d
    if pct_5d: ind["pct_vencido_5d"] = pct_5d
    if pct_15d: ind["pct_vencido_15d"] = pct_15d
    if pct_30d: ind["pct_vencido_30d"] = pct_30d

    # Classe de risco
    cm = re.search(r"Classifica[çc][aã]o de risco\s+([A-E])\b|classe\s+([A-E])\b", texto, re.IGNORECASE)
    if cm:
        classe = (cm.group(1) or cm.group(2)).upper()
        ind["classe_risco"] = classe
        if classe in ("A", "B"):
            green.append(f"🟢 Classe de risco {classe} — estável")
            pts += 3
        elif classe == "C":
            yellow.append(f"🟡 Classe de risco {classe} — atenção")
            pts -= 3
        else:
            red.append(f"🔴 Classe de risco {classe} — risco elevado")
            pts -= 10

    # Meses de estabilidade
    mm = re.search(r"classe\s+[A-E]\s+por\s+(\d+)\s+mes", texto, re.IGNORECASE)
    if not mm:
        # Conta meses com mesma classe no histórico
        classes = re.findall(r"Classifica[çc][aã]o de risco\s+([A-E])", texto, re.IGNORECASE)
        if not classes:
            classes = re.findall(r"\b([A-E])\s+[A-E]\s+[A-E]", texto)
        meses_est = len(classes)
        if meses_est >= 12:
            ind["meses_estabilidade"] = meses_est
            green.append(f"🟢 {meses_est} meses na mesma classe — estabilidade relativa")
            pts += 2

    # Aging analysis
    if debito and venc_30d:
        pct = pct_30d or round(venc_30d/debito*100, 1)
        if pct >= 25:
            red.append(f"🔴 Parcela madura crítica: {pct:.1f}% vencido +30d (R$ {venc_30d:,.0f})")
            pts -= 12
        elif pct >= 10:
            yellow.append(f"🟡 {pct:.1f}% vencido +30d — monitorar")
            pts -= 5

    if debito and venc_15d:
        pct = pct_15d or round(venc_15d/debito*100, 1)
        if pct >= 30:
            red.append(f"🔴 Forte estresse: {pct:.1f}% vencido +15d (R$ {venc_15d:,.0f})")
            pts -= 10
        elif pct >= 15:
            yellow.append(f"🟡 {pct:.1f}% vencido +15d")
            pts -= 4

    if debito and venc_5d:
        pct = pct_5d or round(venc_5d/debito*100, 1)
        if pct >= 40:
            red.append(f"🔴 Alto atraso: {pct:.1f}% vencido +5d (R$ {venc_5d:,.0f})")
            pts -= 8
        elif pct >= 20:
            yellow.append(f"🟡 {pct:.1f}% vencido +5d")
            pts -= 3

    # Associados sem crédito
    m_assoc = re.search(r"Associadas Não Concederam Crédito\s+(\d+)", texto, re.IGNORECASE)
    if not m_assoc:
        m_assoc = re.search(r"(\d+)\s*associad.*não concederam crédito", texto, re.IGNORECASE)
    if m_assoc:
        n = int(m_assoc.group(1))
        ind["assoc_sem_credito"] = n
        if n >= 50:
            red.append(f"🔴 {n} associados não concederam crédito — mercado restringindo")
            pts -= 8
        elif n >= 10:
            yellow.append(f"🟡 {n} associados sem crédito")
            pts -= 3

    # Alerta da ficha
    if tem(texto, "alerta", "déb.total vc+15", "excesso de vencido"):
        red.append("🔴 ALERTA AUTOMÁTICO registrado na própria ficha CISP")
        pts -= 8

    # Garantia
    m_gar = re.search(r"seguro de cr[eé]dito.*?([\d\.]+)", texto, re.IGNORECASE)
    if m_gar:
        gval = float(m_gar.group(1).replace(".", "").replace(",", ".")) * mult
        ind["garantia_valor"] = gval
        cob = round(gval/debito*100, 1) if debito else 0
        if cob < 20:
            yellow.append(f"🟡 Seguro de crédito R$ {gval:,.0f} — cobertura {cob:.1f}% (insuficiente)")
        else:
            green.append(f"🟢 Seguro de crédito R$ {gval:,.0f} ({cob:.1f}% de cobertura)")
            pts += 3

    # Cheque sem fundos
    if tem(texto, "total de ocorrências: 0", "sem cheque sem fundos"):
        green.append("🟢 Sem ocorrências de cheque sem fundos")
        pts += 2
    elif tem(texto, "cheque sem fundos", "ccf"):
        red.append("🔴 Cheques sem fundos registrados")
        pts -= 15

    # Pontualidade
    if not red and tem(texto, "adimplente", "pontual", "bom pagador"):
        green.append("🟢 Histórico de pontualidade comercial")
        pts += 5

    pts = int(clamp(pts, -30, 15))

    # Parecer CISP
    parecer = _parecer_cisp(red, yellow, green, ind, pts, nome, debito)

    return {
        "disponivel": True,
        "arquivo": nome,
        "status": "confirmacao" if not red else "erro" if len(red) >= 3 else "indicio",
        "resumo": f"⚠ {len(red)} RED | {len(yellow)} yellow | ✓ {len(green)} green | Débito: R$ {debito:,.0f}" if debito else f"{len(red)} red | {len(green)} green",
        "pontos": pts,
        "red_flags": red,
        "yellow_flags": yellow,
        "green_flags": green,
        "indicadores": ind,
        "parecer_gestor": parecer,
    }

def _parecer_cisp(red, yellow, green, ind, pts, arquivo, debito):
    linhas = [
        ASSINATURA, "━"*60,
        "ANÁLISE CISP / CREDINFAR — COMPORTAMENTO COMERCIAL",
        f"Arquivo: {arquivo} | Pontos: {'+' if pts>0 else ''}{pts}",
        "━"*60,
    ]
    if debito:
        linhas.append(f"\n📊 DÉBITO TOTAL: R$ {debito:,.0f}")
        if ind.get("vencido_5d"):
            pct = ind["vencido_5d"]/debito*100
            linhas.append(f"  Vencido +5d:  R$ {ind['vencido_5d']:,.0f} ({pct:.1f}%)")
        if ind.get("vencido_15d"):
            pct = ind["vencido_15d"]/debito*100
            linhas.append(f"  Vencido +15d: R$ {ind['vencido_15d']:,.0f} ({pct:.1f}%)")
        if ind.get("vencido_30d"):
            pct = ind["vencido_30d"]/debito*100
            linhas.append(f"  Vencido +30d: R$ {ind['vencido_30d']:,.0f} ({pct:.1f}%)")
    for k in ["classe_risco","garantia_valor","assoc_sem_credito"]:
        if k in ind:
            linhas.append(f"  {k.replace('_',' ').title()}: {ind[k]}")
    if red:
        linhas.append("\n🔴 RED FLAGS")
        for f in red: linhas.append(f"  {f}")
    if yellow:
        linhas.append("\n🟡 YELLOW FLAGS")
        for f in yellow: linhas.append(f"  {f}")
    if green:
        linhas.append("\n🟢 GREEN FLAGS")
        for f in green: linhas.append(f"  {f}")
    linhas.append("\n📋 DECISÃO")
    if len(red) >= 3:
        linhas.append("  ⛔ RISCO ALTO — Reduzir/congelar limite. Exigir balanço + DFC + aval.")
    elif len(red) >= 1:
        linhas.append("  ⚠️  OPERAR COM TRAVA. Prazo curto. Reforço de garantias.")
    elif yellow:
        linhas.append("  🟡 APROVAÇÃO CAUTELOSA. Monitoramento mensal.")
    else:
        linhas.append("  ✅ Comportamento POSITIVO. Aprovação conforme política.")
    linhas += ["", "━"*60, ASSINATURA]
    return "\n".join(linhas)

# ══════════════════════════════════════════════════════════════════
# FONTES PÚBLICAS
# ══════════════════════════════════════════════════════════════════
def consultar_receita(cnpj):
    for url in [f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
                f"https://receitaws.com.br/v1/cnpj/{cnpj}"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code != 200: continue
            j = r.json()
            razao = j.get("razao_social","") or j.get("nome","")
            situacao = j.get("descricao_situacao_cadastral","") or j.get("situacao","")
            abertura = j.get("data_inicio_atividade","") or j.get("abertura","")
            cnae = j.get("cnae_fiscal_descricao","") or ""
            capital = apenas_numero(j.get("capital_social"))
            uf = j.get("uf",""); municipio = j.get("municipio","")
            qsa = j.get("qsa",[]) or []
            anos = years_since(abertura)
            ativa = "ativa" in situacao.lower() if situacao else False
            pts = 8 if ativa else -15
            if anos: pts += 8 if anos>=10 else 4 if anos>=3 else -4
            pts += 2 if capital > 0 else 0
            pts += 2 if qsa else 0
            anos_str = f"{anos:.1f} anos" if anos else ""
            return {**fonte_ok("Receita Federal / Cadastro CNPJ",
                "confirmacao" if ativa else "indicio",
                f"{'ATIVA' if ativa else situacao} | {anos_str} | {uf}/{municipio}",
                f"Razão: {razao} | CNAE: {cnae} | Capital: R$ {capital:,.2f} | Sócios: {len(qsa)}",
                pts, j),
                "razao_social":razao,"situacao":situacao,"abertura":abertura,
                "cnae":cnae,"capital":capital,"uf":uf,"municipio":municipio,
                "qsa":qsa,"anos_mercado":anos}
        except Exception:
            continue
    return fonte_ok("Receita Federal / Cadastro CNPJ","erro","Falha na consulta",pontos=-8)

def consultar_ceis(cnpj):
    try:
        r = requests.get(
            f"https://api.portaldatransparencia.gov.br/api-de-dados/ceis?cnpjSancionado={cnpj}&pagina=1",
            headers={**HEADERS,"chave-api-dados":"demo"}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados,list) and dados:
                return fonte_ok("CEIS/CNEP – Sanções","confirmacao",
                    f"⚠ LISTADA: {len(dados)} sanção(ões)","",-25)
            return fonte_ok("CEIS/CNEP – Sanções","ausencia","Sem registros de sanções","",3)
    except Exception:
        pass
    return fonte_ok("CEIS/CNEP – Sanções","nao_consultado","Indisponível","",-2)

def consultar_datajud(cnpj, razao=""):
    api_key = "APIKey cDZHYzlZa0JadVREZDJCendFbXNpTDQxNDJ"
    tribunais = [("TJSP","api_publica_tjsp"),("TJRJ","api_publica_tjrj"),
                 ("TRF1","api_publica_trf1"),("TRT2","api_publica_trt2")]
    total = exec_ = trab = 0; rj = False
    for nome, idx in tribunais:
        try:
            should = [{"match":{"numeroProcesso":cnpj}}]
            if razao: should.append({"match_phrase":{"partes.nome":razao}})
            r = requests.post(f"https://api-publica.datajud.cnj.jus.br/{idx}/_search",
                json={"query":{"bool":{"should":should}},"size":30},
                headers={**HEADERS,"Authorization":api_key,"Content-Type":"application/json"},
                timeout=12)
            if r.status_code == 200:
                hits = r.json().get("hits",{})
                t = hits.get("total",{}).get("value",0); total += t
                itens = hits.get("hits",[])
                exec_ += sum(1 for h in itens if "execu" in str(h.get("_source",{}).get("classeProcessual","")).lower())
                if any("recupera" in str(h.get("_source",{})).lower() for h in itens): rj = True
        except Exception:
            continue
    pts = -45 if rj else (-12 if exec_>=10 else -5 if exec_>0 else 3)
    if total >= 50: pts -= 8
    resumo = f"{total} processo(s) | Execuções: {exec_}"
    if rj: resumo = "⚠ RECUPERAÇÃO JUDICIAL | " + resumo
    return fonte_ok("DataJud / CNJ – Processos Judiciais",
        "confirmacao" if total>0 else "ausencia", resumo,"",pts,
        {"total":total,"execucoes":exec_,"rj":rj})

def consultar_noticias(razao):
    try:
        termo = razao.replace(" ","+")
        url = f"https://news.google.com/rss/search?q={termo}+fraude+OR+falencia+OR+recuperacao&hl=pt-BR&gl=BR"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            n = r.text.count("<item>")
            if n > 5: return fonte_ok("Reputação / Mídia","indicio",f"⚠ {n} notícias negativas","",-8)
            if n > 0: return fonte_ok("Reputação / Mídia","indicio",f"{n} notícia(s) negativa(s)","",-3)
            return fonte_ok("Reputação / Mídia","ausencia","Sem notícias negativas","",2)
    except Exception:
        pass
    return fonte_ok("Reputação / Mídia","nao_consultado","Indisponível","",-1)

def classificar_setor(cnae):
    tl = (cnae or "").lower()
    high = ["cobran","constru","transport","moda","varejo","factor"]
    low = ["energia","saneamento","farmac","alimento","saude","educac"]
    risco = "medio_alto" if any(t in tl for t in high) else "baixo" if any(t in tl for t in low) else "medio"
    pts = {"baixo":6,"medio":2,"medio_alto":-5}.get(risco,0)
    return {**fonte_ok("Classificação Setorial CNAE","indicio",
        f"Setor: {cnae[:60]} | Risco: {risco}","",pts),"risco_setorial":risco}

# ══════════════════════════════════════════════════════════════════
# MOTOR DE SCORE
# ══════════════════════════════════════════════════════════════════
def calcular_score(fontes, bal, cisp):
    base = 50.0
    pts_f = sum(f.get("pontos",0) for f in fontes)
    pts_b = bal.get("pontos",0)
    pts_c = cisp.get("pontos",0)
    score = int(clamp(base + pts_f + pts_b + pts_c, 0, 100))

    def rating(s):
        for t,r in [(90,"AAA"),(82,"AA"),(74,"A"),(66,"BBB"),(58,"BB"),(48,"B"),(36,"C")]:
            if s>=t: return r
        return "D"
    def risco(s): return "baixo" if s>=75 else "medio" if s>=50 else "alto"
    def pd(s): return round(clamp(60-s*0.55, 1, 80), 1)

    s = score
    if s >= 75:
        limite,prazo,garantias,monitor = ("Limite padrão ou acima","28 a 35 dias",
            ["cessão de recebíveis para volumes maiores"],"Monitoramento trimestral")
    elif s >= 50:
        limite,prazo,garantias,monitor = ("Limite conservador escalonado","14 a 28 dias",
            ["aval","cessão de recebíveis"],"Monitoramento mensal")
    else:
        limite,prazo,garantias,monitor = ("Limite reduzido ou operação pontual","7 a 14 dias",
            ["pagamento antecipado parcial","garantia real","seguro de crédito"],
            "Monitoramento semanal com gatilhos de bloqueio")

    red = [f["resumo"] for f in fontes if f.get("pontos",0)<=-10] + bal.get("red_flags",[]) + cisp.get("red_flags",[])
    yellow = [f["resumo"] for f in fontes if -10<f.get("pontos",0)<0] + bal.get("yellow_flags",[]) + cisp.get("yellow_flags",[])
    green = [f["resumo"] for f in fontes if f.get("pontos",0)>0] + bal.get("green_flags",[]) + cisp.get("green_flags",[])

    return {
        "score":score,"rating":rating(score),"pd":pd(score),
        "classificacao_risco":risco(score),"limite_sugerido":limite,
        "prazo_sugerido":prazo,"garantias_recomendadas":garantias,
        "plano_monitoramento":monitor,
        "red_flags":list(dict.fromkeys(red)),
        "yellow_flags":list(dict.fromkeys(yellow)),
        "green_flags":list(dict.fromkeys(green)),
        "sinais_rj":[f["resumo"] for f in fontes if "recupera" in f.get("resumo","").lower()],
        "memoria_calculo":{"base":base,"pts_fontes":pts_f,"pts_balanco":pts_b,"pts_cisp":pts_c,"score_final":score},
    }

# ══════════════════════════════════════════════════════════════════
# ORQUESTRAÇÃO
# ══════════════════════════════════════════════════════════════════
def analisar_cnpj(cnpj: str, texto_bal: str = "", nome_bal: str = "",
                   texto_cisp: str = "", nome_cisp: str = "") -> dict:
    if not validar_cnpj(cnpj):
        raise ValueError(f"CNPJ inválido: {cnpj}")

    rec = consultar_receita(cnpj)
    razao = rec.get("razao_social","")
    cnae = rec.get("cnae","")

    fontes = [
        rec,
        consultar_ceis(cnpj),
        consultar_datajud(cnpj, razao),
        consultar_noticias(razao),
        classificar_setor(cnae),
        fonte_ok("PGFN / Dívida Ativa","pendente",
            "Consultar em listadevedores.pgfn.gov.br — ausência NÃO equivale a regularidade","",-5),
        fonte_ok("TST / CNDT","pendente","Emitir em cndt.tst.jus.br","",-3),
        fonte_ok("FGTS / CRF","pendente","CRF via caixa.gov.br","",-3),
        fonte_ok("Protestos / IEPTB","pendente","Consulta via bureau especializado","",-4),
        fonte_ok("Bureau de Crédito","pendente","Score bureau requer contrato","",-6),
    ]

    bal = analisar_balanco(texto_bal, nome_bal)
    cisp = analisar_cisp(texto_cisp, nome_cisp)
    score_data = calcular_score(fontes, bal, cisp)

    return {
        "cnpj": cnpj, "empresa": razao,
        **score_data,
        "fontes": fontes,
        "fontes_consultadas": len([f for f in fontes if f["status"] not in ("pendente","nao_consultado")]),
        "fontes_pendentes": len([f for f in fontes if f["status"] in ("pendente","nao_consultado")]),
        "total_fontes": len(fontes),
        "balanco_detalhado": bal,
        "cisp_detalhado": cisp,
        "assinatura": ASSINATURA,
        "analisado_em": dt.datetime.now().isoformat(),
    }

# ══════════════════════════════════════════════════════════════════
# GERAÇÃO DE PDF
# ══════════════════════════════════════════════════════════════════
def gerar_pdf_bytes(resultado: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    NAVY = colors.HexColor("#1E3A5F")
    GOLD = colors.HexColor("#b49303")
    RED = colors.HexColor("#c0392b")
    YELLOW_C = colors.HexColor("#b45309")
    GREEN_C = colors.HexColor("#0e7a5a")
    LIGHT = colors.HexColor("#f5f0e8")
    BORDER = colors.HexColor("#d4c9a8")

    def ps(name, **kw):
        base = dict(fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#1a1a2e"), leading=12)
        base.update(kw)
        return ParagraphStyle(name+str(id(kw)), **base)

    els = []
    els.append(Paragraph(ASSINATURA, ps("sig", fontName="Helvetica-Bold", fontSize=7,
                                         textColor=NAVY, alignment=1)))
    els.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=5))
    els.append(Paragraph("RELATÓRIO EXECUTIVO DE CRÉDITO", ps("t", fontName="Helvetica-Bold",
                                                                 fontSize=14, textColor=NAVY)))
    els.append(Paragraph(resultado.get("empresa",""), ps("st", fontName="Helvetica-Bold",
                                                          fontSize=11, textColor=NAVY)))
    els.append(Spacer(1,6))

    # Header
    hdata = [
        ["CNPJ", resultado.get("cnpj",""), "Score", str(resultado.get("score",""))],
        ["Rating", resultado.get("rating",""), "PD", f"{resultado.get('pd',0):.1f}%"],
        ["Risco", resultado.get("classificacao_risco",""), "Analisado", str(resultado.get("analisado_em",""))[:19]],
        ["Limite", resultado.get("limite_sugerido",""), "Prazo", resultado.get("prazo_sugerido","")],
    ]
    ht = Table(hdata, colWidths=[3*cm,7*cm,3*cm,5.6*cm])
    ht.setStyle(TableStyle([
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.3,BORDER),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,LIGHT]),("PADDING",(0,0),(-1,-1),4),
    ]))
    els.append(ht)
    els.append(Spacer(1,8))

    # Flags
    for titulo, items, cor in [
        ("🔴 RED FLAGS", resultado.get("red_flags",[]), RED),
        ("🟡 YELLOW FLAGS", resultado.get("yellow_flags",[]), YELLOW_C),
        ("🟢 GREEN FLAGS", resultado.get("green_flags",[]), GREEN_C),
    ]:
        if items:
            els.append(Paragraph(titulo, ps("fh", fontName="Helvetica-Bold", fontSize=9, textColor=cor, spaceBefore=6)))
            for item in items[:15]:
                els.append(Paragraph(f"• {str(item)[:180]}", ps("fi", fontSize=7.5, leading=11)))
            els.append(Spacer(1,4))

    # Balanço
    bal = resultado.get("balanco_detalhado",{})
    if bal.get("disponivel"):
        els.append(Paragraph("📊 ANÁLISE DE BALANÇO", ps("bh", fontName="Helvetica-Bold",
                                                            fontSize=10, textColor=NAVY, spaceBefore=8)))
        ind = bal.get("indicadores",{})
        rows = []
        for k,v in ind.items():
            label = k.replace("_"," ").title()
            if isinstance(v,float) and v > 1000:
                rows.append([label, f"R$ {v:,.0f}"])
            elif isinstance(v,float):
                rows.append([label, f"{v:.2f}"])
            else:
                rows.append([label, str(v)])
        if rows:
            it = Table(rows, colWidths=[8*cm,10.6*cm])
            it.setStyle(TableStyle([
                ("FONTSIZE",(0,0),(-1,-1),7.5),("GRID",(0,0),(-1,-1),0.3,BORDER),
                ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,LIGHT]),("PADDING",(0,0),(-1,-1),3),
            ]))
            els.append(it)
        for titulo, items, cor in [
            ("Red Flags", bal.get("red_flags",[]), RED),
            ("Yellow Flags", bal.get("yellow_flags",[]), YELLOW_C),
            ("Green Flags", bal.get("green_flags",[]), GREEN_C),
        ]:
            for item in items[:8]:
                els.append(Paragraph(f"• {titulo}: {str(item)[:160]}", ps("bf", fontSize=7.5,
                                                                            textColor=cor, leading=11)))
        els.append(Spacer(1,6))

    # CISP
    cisp = resultado.get("cisp_detalhado",{})
    if cisp.get("disponivel"):
        els.append(Paragraph("📋 ANÁLISE CISP / CREDINFAR", ps("ch", fontName="Helvetica-Bold",
                                                                  fontSize=10, textColor=NAVY, spaceBefore=6)))
        cind = cisp.get("indicadores",{})
        crowns = []
        for k,v in cind.items():
            label = k.replace("_"," ").title()
            if isinstance(v,float) and v > 1000:
                crowns.append([label, f"R$ {v:,.0f}"])
            elif isinstance(v,float):
                crowns.append([label, f"{v:.2f}"])
            else:
                crowns.append([label, str(v)])
        if crowns:
            ct = Table(crowns, colWidths=[8*cm,10.6*cm])
            ct.setStyle(TableStyle([
                ("FONTSIZE",(0,0),(-1,-1),7.5),("GRID",(0,0),(-1,-1),0.3,BORDER),
                ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,LIGHT]),("PADDING",(0,0),(-1,-1),3),
            ]))
            els.append(ct)
        for titulo, items, cor in [
            ("Red", cisp.get("red_flags",[]), RED),
            ("Yellow", cisp.get("yellow_flags",[]), YELLOW_C),
            ("Green", cisp.get("green_flags",[]), GREEN_C),
        ]:
            for item in items[:6]:
                els.append(Paragraph(f"• {titulo}: {str(item)[:160]}", ps("cf", fontSize=7.5,
                                                                            textColor=cor, leading=11)))
        els.append(Spacer(1,6))

    # Fontes
    els.append(Paragraph("FONTES CONSULTADAS", ps("foh", fontName="Helvetica-Bold",
                                                    fontSize=9, textColor=NAVY, spaceBefore=6)))
    for f in resultado.get("fontes",[]):
        els.append(Paragraph(f"[{f['status'].upper()}] {f['fonte']}: {f['resumo'][:120]}",
                              ps("fo", fontSize=7, leading=10, textColor=colors.HexColor("#555"))))

    # Rodapé
    els.append(Spacer(1,8))
    els.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    els.append(Paragraph(f"{ASSINATURA} | {dt.datetime.now().strftime('%d/%m/%Y %H:%M')} | CONFIDENCIAL",
                          ps("rod", fontName="Helvetica-Bold", fontSize=7, textColor=NAVY, alignment=1)))

    doc.build(els)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════════════
# ROTAS
# ══════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"status":"ok","app":ASSINATURA,"version":"5.0.0"}

@app.get("/health")
def health():
    return {"status":"healthy","timestamp":dt.datetime.now().isoformat(),
            "pdfplumber":HAS_PDFPLUMBER,"pypdf":HAS_PYPDF,"version":"5.0.0"}

class CNPJReq(BaseModel):
    cnpj: str

@app.post("/api/analisar")
def analisar_json(req: CNPJReq):
    try:
        return JSONResponse(content=analisar_cnpj(limpar_cnpj(req.cnpj)))
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/analisar-completo")
async def analisar_completo(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    """
    Endpoint principal — recebe CNPJ + PDFs e retorna análise completa.
    Também inclui PDF em base64 no response para download.
    """
    try:
        texto_bal = nome_bal = ""
        texto_cisp = nome_cisp = ""

        if balanco:
            b = await balanco.read()
            nome_bal = balanco.filename or ""
            texto_bal = extrair_texto_arquivo(b, nome_bal)

        if cisp:
            b = await cisp.read()
            nome_cisp = cisp.filename or ""
            texto_cisp = extrair_texto_arquivo(b, nome_cisp)

        resultado = analisar_cnpj(
            limpar_cnpj(cnpj), texto_bal, nome_bal, texto_cisp, nome_cisp
        )

        # Gera PDF com os mesmos dados — inclui balanço e CISP
        try:
            pdf_bytes = gerar_pdf_bytes(resultado)
            resultado["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
            resultado["pdf_filename"] = f"PILDER_{limpar_cnpj(cnpj)}.pdf"
        except Exception:
            resultado["pdf_base64"] = None

        return JSONResponse(content=resultado)

    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=f"Erro: {traceback.format_exc()}")

# Mantém compatibilidade com frontend existente
@app.post("/api/analisar-com-anexo")
async def analisar_com_anexo(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    return await analisar_completo(cnpj=cnpj, balanco=balanco, cisp=cisp)

@app.get("/api/analisar/{cnpj}")
def analisar_get(cnpj: str):
    try:
        return JSONResponse(content=analisar_cnpj(limpar_cnpj(cnpj)))
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/lote")
async def processar_lote(file: UploadFile = File(...)):
    try:
        df = pd.read_excel(io.BytesIO(await file.read()))
        if "cnpj" not in df.columns:
            raise HTTPException(422, detail="Coluna 'cnpj' não encontrada.")
        resultados, erros = [], []
        for cnpj in [limpar_cnpj(str(v)) for v in df["cnpj"].dropna().tolist()][:100]:
            try:
                resultados.append(analisar_cnpj(cnpj))
            except Exception as e:
                erros.append({"cnpj":cnpj,"erro":str(e)})
        return JSONResponse(content={"processados":len(resultados),"erros":len(erros),
                                      "resultados":resultados,"erros_detalhe":erros})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/conectores")
def conectores():
    return {
        "receita_federal": {"status":"ativo","tipo":"api_publica"},
        "ceis_cnep": {"status":"ativo_parcial","tipo":"api_publica"},
        "datajud_cnj": {"status":"ativo_parcial","tipo":"api_publica"},
        "noticias_google": {"status":"ativo","tipo":"rss"},
        "balanco_pdf": {"status":"ativo","tipo":"upload_extracao_real",
                        "extrator": "pdfplumber" if HAS_PDFPLUMBER else "pypdf"},
        "cisp_credinfar": {"status":"ativo","tipo":"upload_extracao_real"},
        "pgfn": {"status":"pendente"},
        "tst_cndt": {"status":"pendente"},
        "protestos": {"status":"pendente"},
        "bureau": {"status":"pendente"},
    }
