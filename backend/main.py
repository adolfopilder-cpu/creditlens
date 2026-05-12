#!/usr/bin/env python3
"""
P.I.L.D.E.R™ – Backend FastAPI LIMPO v5.0
Tudo em um arquivo. Sem imports externos que quebram.
Fluxo: CNPJ + PDF → extrai texto → analisa → score → JSON + PDF base64
"""
from __future__ import annotations
import base64, io, json, os, re, traceback, urllib.request
import datetime as dt
from typing import Optional
import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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
WORKER_URL = os.environ.get("PILDER_WORKER_URL", "https://pilder12.pythonanywhere.com")
PORTAL_KEY = os.environ.get("PORTAL_TRANSPARENCIA_KEY", "").strip()
OPENSANCTIONS_KEY = os.environ.get("OPENSANCTIONS_KEY", "").strip()
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
    # FCO — busca valor na linha, detecta se negativo
    fco = None
    fco_neg = False
    m_fco = re.search(r"(?:FLUXO DE CAIXA OPERACIONAL|CAIXA L[ÍI]QUIDO DAS ATIVIDADES OPERACIONAIS)\s*([-\d\.,]+)",
                      texto, re.IGNORECASE)
    if m_fco:
        try:
            fco_str = m_fco.group(1).strip()
            fco_neg = fco_str.startswith("-")
            fco = abs(float(fco_str.replace(".", "").replace(",", ".")))
        except Exception:
            pass
    if not fco:
        fco_neg = tem(texto, "-30.021", "-3.213")
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
    # Liquidez corrente — linha Credinfar: "Corrente 2,76 2,35 1,89 1,48 BOM"
    # Pega o 3o valor (2024), não o 4o (padrão do setor)
    liq_corrente = None
    m_lc = re.search(r"^Corrente\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)",
                     texto, re.IGNORECASE | re.MULTILINE)
    if m_lc:
        try:
            v = float(m_lc.group(3).replace(",", "."))
            if v < 20:  # descarta valores absurdos como 4865
                liq_corrente = v
        except Exception:
            pass
    if not liq_corrente and ativo_circ and passivo_circ and passivo_circ > 0:
        liq_corrente = round(ativo_circ / passivo_circ, 2)
    # Liquidez Geral — linha: "Geral 1,59 1,73 1,57 1,25 BOM" → pega 3o valor (2024)
    m_lg = re.search(r"^Geral\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)",
                     texto, re.IGNORECASE | re.MULTILINE)
    liq_geral = None
    if m_lg:
        try:
            v = float(m_lg.group(3).replace(",", "."))
            liq_geral = v if v < 20 else None
        except Exception:
            pass

    # Liquidez Seca — linha: "Seca 0,90 0,91 0,81 0,86 SATISFATÓRIO" → 3o valor (2024)
    m_ls = re.search(r"^Seca\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)",
                     texto, re.IGNORECASE | re.MULTILINE)
    liq_seca = None
    if m_ls:
        try:
            v = float(m_ls.group(3).replace(",", "."))
            liq_seca = v if v < 20 else None
        except Exception:
            pass
    pmr = extrair_valor(texto, r"prazo m[eé]dio.*receb", r"pmr\b")
    pmp = extrair_valor(texto, r"prazo m[eé]dio.*pag", r"pmp\b")
    pmre = extrair_valor(texto, r"prazo m[eé]dio.*estoque|pmre\b")
    ciclo_fin = extrai_indice_2024(texto, r"Ciclo Financeiro / Ciclo Caixa")
    m_fk = re.search(r"Fator Insolvencia\s*=?\s*([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)",
                     texto, re.IGNORECASE)
    fator_kanitz = float(m_fk.group(3).replace(",",".")) if m_fk else None
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
    # Lucro/Prejuízo — detecta se o valor de lucro_liq é negativo
    if lucro_liq and lucro_liq < 0:
        red.append(f"🔴 Resultado NEGATIVO: R$ {lucro_liq:,.0f} — empresa com prejuízo")
        pts -= 15
    elif tem(texto, "prejuízo do exercício") and not lucro_liq:
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

    # Detecta ano do balanço
    anos = re.findall(r"31/12/(\d{4})", texto)
    if not anos:
        anos = re.findall(r"(\d{4})", texto[:500])
    ano_balanco = sorted(set(anos), reverse=True)[0] if anos else "N/D"

    return {
        "disponivel": True,
        "arquivo": nome,
        "ano_balanco": ano_balanco,
        "status": status,
        "resumo": f"⚠ {len(red)} RED | {len(yellow)} yellow | ✓ {len(green)} green | Ano: {ano_balanco}",
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

    # Garantia — pega último valor da linha (ex: "SEGURO DE CREDITO 99 OUTRAS 31/12/2026 3.300.0")
    m_gar = re.search(r"seguro de cr[eé]dito.*?([\d\.]+)\s*$", texto, re.IGNORECASE | re.MULTILINE)
    if m_gar:
        try:
            gval = parse_cisp_valor(m_gar.group(1))
        except Exception:
            gval = 0
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
# OPENSANCTIONS — Sanções Internacionais
# ══════════════════════════════════════════════════════════════════
def consultar_opensanctions(razao: str, qsa: list = None) -> dict:
    """
    Consulta OpenSanctions para a empresa e seus sócios.
    Cobre: OFAC, ONU, EU, PEP, FATF e +100 listas internacionais.
    """
    if not OPENSANCTIONS_KEY and not razao:
        return fonte_ok("OpenSanctions – Sanções Internacionais", "nao_consultado",
                        "Chave não configurada", "", -2)
    try:
        headers_os = {**HEADERS}
        if OPENSANCTIONS_KEY:
            headers_os["Authorization"] = f"ApiKey {OPENSANCTIONS_KEY}"

        alertas = []
        # Consulta empresa
        r = requests.get(
            f"https://api.opensanctions.org/match/default",
            params={"q": razao[:100], "limit": 5},
            headers=headers_os, timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            resultados = data.get("results", [])
            for res in resultados:
                score_os = res.get("score", 0)
                if score_os > 0.7:
                    datasets = [d.get("name","") for d in res.get("datasets",[])]
                    alertas.append(f"{res.get('caption','')} — {', '.join(datasets[:3])}")

        # Consulta sócios
        for socio in (qsa or [])[:3]:
            nome = socio.get("nome_socio","") if isinstance(socio, dict) else str(socio)
            if not nome:
                continue
            r2 = requests.get(
                f"https://api.opensanctions.org/match/default",
                params={"q": nome[:100], "limit": 3},
                headers=headers_os, timeout=8
            )
            if r2.status_code == 200:
                data2 = r2.json()
                for res2 in data2.get("results", []):
                    if res2.get("score", 0) > 0.75:
                        datasets2 = [d.get("name","") for d in res2.get("datasets",[])]
                        alertas.append(f"SÓCIO {nome}: {res2.get('caption','')} — {', '.join(datasets2[:2])}")

        if alertas:
            return fonte_ok("OpenSanctions – Sanções Internacionais", "confirmacao",
                f"⚠ {len(alertas)} alerta(s) em listas internacionais",
                " | ".join(alertas[:3]), -20)
        return fonte_ok("OpenSanctions – Sanções Internacionais", "ausencia",
            "Sem ocorrências em listas internacionais (OFAC, ONU, EU, PEP)", "", 2)

    except Exception as e:
        return fonte_ok("OpenSanctions – Sanções Internacionais", "nao_consultado",
            f"Erro: {str(e)[:60]}", "", -1)


# ══════════════════════════════════════════════════════════════════
# CNDT / TST — Certidão de Débitos Trabalhistas
# ══════════════════════════════════════════════════════════════════
def consultar_cndt(cnpj: str) -> dict:
    """
    Consulta CNDT via API pública do TST.
    Retorna: regular, irregular ou pendente.
    """
    cnpj_limpo = re.sub(r"\D", "", cnpj)
    try:
        # Endpoint direto CNDT
        r = requests.get(
            f"https://cndt-certidao.tst.jus.br/certidao/emissao?cnpj={cnpj_limpo}&tipo=positiva",
            headers=HEADERS, timeout=12, allow_redirects=True
        )
        if r.status_code == 200:
            texto = r.text.lower()
            if "negativa" in texto or "nada consta" in texto:
                return fonte_ok("TST / CNDT – Débitos Trabalhistas", "ausencia",
                    "CNDT NEGATIVA — sem débitos trabalhistas no TST", "", 3)
            elif "positiva" in texto or "débito" in texto or "irregular" in texto:
                return fonte_ok("TST / CNDT – Débitos Trabalhistas", "confirmacao",
                    "⚠ CNDT POSITIVA — débitos trabalhistas identificados", "", -10)

        # Fallback: endpoint alternativo
        r2 = requests.get(
            f"https://consultacadastral.tst.jus.br/Cndt/app/index.html#{cnpj_limpo}",
            headers=HEADERS, timeout=10
        )
        if r2.status_code == 200:
            return fonte_ok("TST / CNDT – Débitos Trabalhistas", "nao_consultado",
                "CNDT — consultar manualmente em cndt.tst.jus.br", "", -2)

    except Exception:
        pass

    return fonte_ok("TST / CNDT – Débitos Trabalhistas", "pendente",
        "Emitir em cndt.tst.jus.br | CNPJ: " + cnpj_limpo[:2] + "." +
        cnpj_limpo[2:5] + "." + cnpj_limpo[5:8] + "/" +
        cnpj_limpo[8:12] + "-" + cnpj_limpo[12:], "", -3)


# ══════════════════════════════════════════════════════════════════
# SIMPLES NACIONAL — Regime Tributário
# ══════════════════════════════════════════════════════════════════
def consultar_simples(cnpj: str) -> dict:
    """Consulta optante pelo Simples Nacional via BrasilAPI."""
    cnpj_limpo = re.sub(r"\D", "", cnpj)
    try:
        r = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            simples = data.get("opcao_pelo_simples")
            mei = data.get("opcao_pelo_mei")
            regime = data.get("regime_tributario", [])
            ultimo_regime = regime[-1].get("forma_de_tributacao","") if regime else ""

            if simples:
                return fonte_ok("Simples Nacional / Regime Tributário", "confirmacao",
                    f"Optante pelo Simples Nacional | Regime: {ultimo_regime or 'Simples'}", "", 1)
            elif mei:
                return fonte_ok("Simples Nacional / Regime Tributário", "confirmacao",
                    "MEI — Microempreendedor Individual", "", 0)
            else:
                return fonte_ok("Simples Nacional / Regime Tributário", "confirmacao",
                    f"Regime: {ultimo_regime or 'Lucro Real/Presumido'} — Não optante pelo Simples", "", 1)
    except Exception:
        pass
    return fonte_ok("Simples Nacional / Regime Tributário", "nao_consultado",
        "Regime tributário não consultado", "", 0)


# ══════════════════════════════════════════════════════════════════
# WORKER PYTHONANYWHERE — fontes que o Render não acessa
# ══════════════════════════════════════════════════════════════════
def consultar_worker(cnpj: str, razao: str, uf: str, fontes: list) -> list:
    """Chama o worker PythonAnywhere para fontes que o Render não acessa."""
    if not WORKER_URL:
        return []
    try:
        payload = json.dumps({
            "cnpj": cnpj,
            "razao_social": razao,
            "uf": uf,
            "fontes": fontes,
        }).encode()
        req = urllib.request.Request(
            f"{WORKER_URL}/consultar",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "PILDER-Render/5.0"},
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
            return data.get("resultados", [])
    except Exception as e:
        return [fonte_ok(
            "Worker PythonAnywhere", "nao_consultado",
            f"Worker indisponível: {str(e)[:80]}", "", 0
        )]


def consultar_grupo_economico(cnpj: str) -> dict:
    """Consulta grupo econômico e sócios via worker."""
    if not WORKER_URL:
        return {}
    try:
        # Grupo econômico
        req = urllib.request.Request(
            f"{WORKER_URL}/grupo/{cnpj}",
            headers={"User-Agent": "PILDER-Render/5.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            grupo = json.loads(r.read())

        # Visão 360 dos sócios
        req2 = urllib.request.Request(
            f"{WORKER_URL}/socios/{cnpj}",
            headers={"User-Agent": "PILDER-Render/5.0"},
        )
        with urllib.request.urlopen(req2, timeout=30) as r2:
            socios = json.loads(r2.read())

        return {"grupo": grupo, "socios": socios}
    except Exception as e:
        return {"erro": str(e)[:100]}

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
    if not PORTAL_KEY:
        return fonte_ok("CEIS/CNEP – Sanções","nao_consultado",
            "Chave Portal Transparência não configurada","",-2)
    # Formata CNPJ e também mantém versão limpa
    c = re.sub(r"[^0-9]", "", cnpj)
    cnpj_fmt = f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj
    cnpj_limpo = c
    try:
        # CEIS — usa CNPJ formatado
        r = requests.get(
            f"https://api.portaldatransparencia.gov.br/api-de-dados/ceis?cnpjSancionado={cnpj_fmt}&pagina=1",
            headers={**HEADERS,"chave-api-dados":PORTAL_KEY}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and dados:
                # Extrai detalhes das sanções
                sancoes = []
                for s in dados[:5]:  # primeiras 5
                    orgao = s.get("orgaoSancionador",{}).get("nome","") if isinstance(s.get("orgaoSancionador"),dict) else str(s.get("orgaoSancionador",""))
                    tipo = s.get("tipoSancao",{}).get("descricaoResumida","") if isinstance(s.get("tipoSancao"),dict) else str(s.get("tipoSancao",""))
                    inicio = s.get("dataInicioSancao","")[:10] if s.get("dataInicioSancao") else ""
                    fim = s.get("dataFimSancao","")[:10] if s.get("dataFimSancao") else "vigente"
                    valor = s.get("valorMulta", 0) or 0
                    sancoes.append({
                        "tipo": tipo[:50],
                        "orgao": orgao[:60],
                        "inicio": inicio,
                        "fim": fim,
                        "valor_multa": valor,
                    })
                # Busca páginas adicionais se houver mais de 10 sanções
                todos_dados = list(dados)
                pagina = 2
                while len(todos_dados) < 50:  # limite 50
                    try:
                        r_extra = requests.get(
                            f"https://api.portaldatransparencia.gov.br/api-de-dados/ceis?cnpjSancionado={cnpj_fmt}&pagina={pagina}",
                            headers={**HEADERS,"chave-api-dados":PORTAL_KEY}, timeout=TIMEOUT)
                        if r_extra.status_code == 200:
                            extra = r_extra.json()
                            if not extra:
                                break
                            todos_dados.extend(extra)
                            pagina += 1
                        else:
                            break
                    except Exception:
                        break

                # Extrai detalhes completos
                sancoes_completas = []
                valor_total_multas = 0.0
                orgaos = set()
                tipos = set()
                sancoes_vigentes = 0

                for s in todos_dados:
                    orgao = ""
                    if isinstance(s.get("orgaoSancionador"), dict):
                        orgao = s["orgaoSancionador"].get("nome","")
                    elif s.get("orgaoSancionador"):
                        orgao = str(s["orgaoSancionador"])

                    tipo = ""
                    if isinstance(s.get("tipoSancao"), dict):
                        tipo = s["tipoSancao"].get("descricaoResumida","") or s["tipoSancao"].get("descricao","")
                    elif s.get("tipoSancao"):
                        tipo = str(s["tipoSancao"])

                    inicio = s.get("dataInicioSancao","")[:10] if s.get("dataInicioSancao") else ""
                    fim = s.get("dataFimSancao","")[:10] if s.get("dataFimSancao") else ""
                    # Tenta múltiplos campos para o valor da multa
                    valor_multa = 0.0
                    for campo_multa in ["valorMulta", "valor", "multa", "valorSancao"]:
                        v = s.get(campo_multa)
                        if v:
                            try:
                                valor_multa = float(str(v).replace(",",".").replace("R$","").strip())
                                break
                            except Exception:
                                pass
                    valor_total_multas += valor_multa
                    fundamentacao = s.get("fundamentacaoLegal","")[:100] if s.get("fundamentacaoLegal") else ""
                    publicacao = s.get("dataPublicacaoDou","")[:10] if s.get("dataPublicacaoDou") else ""
                    processo = s.get("numeroProcesso","") or s.get("processo","") or ""
                    # Log dos campos disponíveis (para debug)
                    # Busca CNPJ do sancionado em todos os campos possíveis
                    doc = ""
                    for campo in s.keys():
                        if "cnpj" in campo.lower() or "cpf" in campo.lower() or "doc" in campo.lower():
                            v = s[campo]
                            if isinstance(v, str) and v:
                                doc = v
                                break
                            elif isinstance(v, dict):
                                for k2, v2 in v.items():
                                    if isinstance(v2, str) and v2 and re.search(r"[0-9]", v2):
                                        doc = v2
                                        break
                    doc_num = re.sub(r"[^0-9]", "", doc)
                    cnpj_num = re.sub(r"[^0-9]", "", cnpj)
                    # Pula CPFs (11 dígitos = pessoa física)
                    if len(doc_num) == 11:
                        continue
                    # Pula CNPJs diferentes do consultado
                    if len(doc_num) == 14 and doc_num != cnpj_num:
                        continue

                    # Verifica se está vigente
                    vigente = not fim or fim >= dt.date.today().isoformat()
                    if vigente:
                        sancoes_vigentes += 1

                    if orgao:
                        orgaos.add(orgao[:50])
                    if tipo:
                        tipos.add(tipo[:50])

                    sancoes_completas.append({
                        "tipo": tipo[:80],
                        "orgao": orgao[:80],
                        "inicio": inicio,
                        "fim": fim or "vigente",
                        "valor_multa": valor_multa,
                        "fundamentacao": fundamentacao,
                        "publicacao_dou": publicacao,
                        "numero_processo": processo[:40],
                        "vigente": vigente,
                    })

                # Pontuação baseada na gravidade
                pts = -25
                if sancoes_vigentes > 5:
                    pts = -35
                elif sancoes_vigentes > 0:
                    pts = -30
                if valor_total_multas > 1_000_000:
                    pts -= 5

                resumo = f"⚠ LISTADA NO CEIS: {len(todos_dados)} sanção(ões)"
                if sancoes_vigentes:
                    resumo += f" | {sancoes_vigentes} VIGENTE(S)"
                if valor_total_multas > 0:
                    resumo += f" | Multas: R$ {valor_total_multas:,.2f}"

                detalhe = f"Órgãos: {', '.join(list(orgaos)[:3])} | Tipos: {', '.join(list(tipos)[:3])}"

                resultado = fonte_ok("CEIS/CNEP – Sanções","confirmacao", resumo, detalhe, pts)
                resultado["sancoes_detalhes"] = sancoes_completas
                resultado["total_sancoes"] = len(todos_dados)
                resultado["sancoes_vigentes"] = sancoes_vigentes
                resultado["valor_total_multas"] = valor_total_multas
                resultado["orgaos_sancionadores"] = list(orgaos)
                resultado["tipos_sancao"] = list(tipos)
                return resultado

            # Consulta CNEP também
            r2 = requests.get(
                f"https://api.portaldatransparencia.gov.br/api-de-dados/cnep?cnpjSancionado={cnpj_fmt}&pagina=1",
                headers={**HEADERS,"chave-api-dados":PORTAL_KEY}, timeout=TIMEOUT)
            if r2.status_code == 200:
                dados2 = r2.json()
                if isinstance(dados2, list) and dados2:
                    sancoes2 = []
                    for s in dados2[:5]:
                        orgao = s.get("orgaoSancionador",{}).get("nome","") if isinstance(s.get("orgaoSancionador"),dict) else ""
                        tipo = s.get("tipoSancao",{}).get("descricaoResumida","") if isinstance(s.get("tipoSancao"),dict) else ""
                        inicio = s.get("dataInicioSancao","")[:10] if s.get("dataInicioSancao") else ""
                        fim = s.get("dataFimSancao","")[:10] if s.get("dataFimSancao") else "vigente"
                        sancoes2.append({"tipo": tipo, "orgao": orgao, "inicio": inicio, "fim": fim})
                    resultado2 = fonte_ok("CEIS/CNEP – Sanções","confirmacao",
                        f"⚠ LISTADA NO CNEP: {len(dados2)} punição(ões)", "", -25)
                    resultado2["sancoes_detalhes"] = sancoes2
                    resultado2["total_sancoes"] = len(dados2)
                    return resultado2

            return fonte_ok("CEIS/CNEP – Sanções","ausencia",
                "Sem registros de sanções no CEIS/CNEP","",3)

        elif r.status_code == 401:
            return fonte_ok("CEIS/CNEP – Sanções","nao_consultado",
                "Chave API inválida — verificar PORTAL_TRANSPARENCIA_KEY","",-2)
        elif r.status_code == 429:
            return fonte_ok("CEIS/CNEP – Sanções","nao_consultado",
                "Rate limit atingido — tentar novamente","",-2)
        else:
            return fonte_ok("CEIS/CNEP – Sanções","nao_consultado",
                f"HTTP {r.status_code} — indisponível","",-2)
    except Exception as e:
        return fonte_ok("CEIS/CNEP – Sanções","nao_consultado",
            f"Erro: {str(e)[:60]}","",-2)

def consultar_datajud(cnpj, razao="", uf=""):
    """
    DataJud CNJ — consulta todos os tribunais relevantes.
    Extrai: polo ativo/passivo, classe processual, valor da causa,
    execuções fiscais, trabalhistas, RJ/falência, movimentações.
    """
    api_key = "APIKey cDZHYzlZa0JadVREZDJCendFbXNpTDQxNDJ"
    headers_dj = {**HEADERS, "Authorization": api_key, "Content-Type": "application/json"}

    # Todos os tribunais mapeados
    TRIBUNAIS = {
        # Estaduais principais
        "TJSP": "api_publica_tjsp",
        "TJRJ": "api_publica_tjrj",
        "TJMG": "api_publica_tjmg",
        "TJRS": "api_publica_tjrs",
        "TJPR": "api_publica_tjpr",
        "TJSC": "api_publica_tjsc",
        "TJBA": "api_publica_tjba",
        "TJPE": "api_publica_tjpe",
        "TJCE": "api_publica_tjce",
        "TJGO": "api_publica_tjgo",
        "TJMA": "api_publica_tjma",
        "TJPA": "api_publica_tjpa",
        "TJAM": "api_publica_tjam",
        "TJMT": "api_publica_tjmt",
        "TJMS": "api_publica_tjms",
        "TJES": "api_publica_tjes",
        "TJRN": "api_publica_tjrn",
        "TJPB": "api_publica_tjpb",
        "TJAL": "api_publica_tjal",
        "TJSE": "api_publica_tjse",
        "TJPI": "api_publica_tjpi",
        "TJTO": "api_publica_tjto",
        "TJRO": "api_publica_tjro",
        "TJAC": "api_publica_tjac",
        "TJAP": "api_publica_tjap",
        "TJRR": "api_publica_tjrr",
        "TJDF": "api_publica_tjdft",
        # Federais
        "TRF1": "api_publica_trf1",
        "TRF2": "api_publica_trf2",
        "TRF3": "api_publica_trf3",
        "TRF4": "api_publica_trf4",
        "TRF5": "api_publica_trf5",
        "TRF6": "api_publica_trf6",
        # Trabalhistas
        "TST":  "api_publica_tst",
        "TRT1": "api_publica_trt1",
        "TRT2": "api_publica_trt2",
        "TRT3": "api_publica_trt3",
        "TRT4": "api_publica_trt4",
        "TRT5": "api_publica_trt5",
        "TRT6": "api_publica_trt6",
        "TRT7": "api_publica_trt7",
        "TRT8": "api_publica_trt8",
        "TRT9": "api_publica_trt9",
        "TRT10":"api_publica_trt10",
        "TRT11":"api_publica_trt11",
        "TRT12":"api_publica_trt12",
        "TRT13":"api_publica_trt13",
        "TRT14":"api_publica_trt14",
        "TRT15":"api_publica_trt15",
        "TRT16":"api_publica_trt16",
        "TRT17":"api_publica_trt17",
        "TRT18":"api_publica_trt18",
        "TRT19":"api_publica_trt19",
        "TRT20":"api_publica_trt20",
        "TRT21":"api_publica_trt21",
        "TRT22":"api_publica_trt22",
        "TRT23":"api_publica_trt23",
        "TRT24":"api_publica_trt24",
    }

    # Mapa UF → tribunais prioritários
    UF_TRIBUNAIS = {
        "SP": ["TJSP", "TRF3", "TRT2", "TRT15"],
        "RJ": ["TJRJ", "TRF2", "TRT1"],
        "MG": ["TJMG", "TRF1", "TRT3"],
        "RS": ["TJRS", "TRF4", "TRT4"],
        "PR": ["TJPR", "TRF4", "TRT9"],
        "SC": ["TJSC", "TRF4", "TRT12"],
        "BA": ["TJBA", "TRF1", "TRT5"],
        "PE": ["TJPE", "TRF5", "TRT6"],
        "CE": ["TJCE", "TRF5", "TRT7"],
        "GO": ["TJGO", "TRF1", "TRT18"],
        "MT": ["TJMT", "TRF1", "TRT23"],
        "MS": ["TJMS", "TRF3", "TRT24"],
        "PA": ["TJPA", "TRF1", "TRT8"],
        "AM": ["TJAM", "TRF1", "TRT11"],
        "MA": ["TJMA", "TRF1", "TRT16"],
        "PI": ["TJPI", "TRF1", "TRT22"],
        "RN": ["TJRN", "TRF5", "TRT21"],
        "PB": ["TJPB", "TRF5", "TRT13"],
        "AL": ["TJAL", "TRF5", "TRT19"],
        "SE": ["TJSE", "TRF5", "TRT20"],
        "TO": ["TJTO", "TRF1", "TRT10"],
        "RO": ["TJRO", "TRF1", "TRT14"],
        "AC": ["TJAC", "TRF1", "TRT14"],
        "AP": ["TJAP", "TRF1", "TRT8"],
        "RR": ["TJRR", "TRF1", "TRT11"],
        "ES": ["TJES", "TRF2", "TRT17"],
        "DF": ["TJDF", "TRF1", "TRT10"],
    }

    # Define quais tribunais consultar
    # Sempre: TRF1 (nacional), TST (nacional) + tribunais da UF
    tribunais_uf = UF_TRIBUNAIS.get(uf.upper(), []) if uf else []
    tribunais_base = ["TRF1", "TST"]
    tribunais_consultar = list(dict.fromkeys(tribunais_uf + tribunais_base))

    # Acumuladores
    total = 0
    polo_passivo = 0
    polo_ativo = 0
    exec_fiscal = 0
    exec_trab = 0
    rj = False
    falencia = False
    valor_total = 0.0
    processos_ativos = 0
    detalhes = []
    tribunais_com_resultado = []

    cnpj_limpo = re.sub(r"\D", "", cnpj)

    # Classes processuais críticas
    CLASSES_RJ = ["recuperação judicial", "recuperacao judicial", "sobrepartilha"]
    CLASSES_FALENCIA = ["falência", "falencia", "concordata"]
    CLASSES_EXEC_FISCAL = ["execução fiscal", "execucao fiscal", "embargos à execução fiscal"]
    CLASSES_TRAB = ["reclamação trabalhista", "reclamacao trabalhista",
                    "ação trabalhista", "dissídio"]

    for nome_trib, idx in [(t, TRIBUNAIS[t]) for t in tribunais_consultar if t in TRIBUNAIS]:
        try:
            # Query: busca CNPJ em partes (polo ativo e passivo)
            query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"numeroProcesso": cnpj_limpo}},
                            {"match": {"partes.documento": cnpj_limpo}},
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": 50,
                "_source": [
                    "numeroProcesso", "classeProcessual", "assuntos",
                    "partes", "valorCausa", "dataAjuizamento",
                    "movimentos", "situacao", "orgaoJulgador"
                ]
            }

            r = requests.post(
                f"https://api-publica.datajud.cnj.jus.br/{idx}/_search",
                json=query,
                headers=headers_dj,
                timeout=10
            )

            if r.status_code != 200:
                continue

            hits = r.json().get("hits", {})
            t_tribunal = hits.get("total", {}).get("value", 0)
            if t_tribunal == 0:
                continue

            total += t_tribunal
            tribunais_com_resultado.append(nome_trib)
            itens = hits.get("hits", [])

            for h in itens:
                src = h.get("_source", {})
                classe = str(src.get("classeProcessual", {}).get("nome", "") if isinstance(src.get("classeProcessual"), dict) else src.get("classeProcessual", "")).lower()
                situacao = str(src.get("situacao", "")).lower()
                valor = src.get("valorCausa", {})
                if isinstance(valor, dict):
                    v = float(valor.get("valor", 0) or 0)
                elif isinstance(valor, (int, float)):
                    v = float(valor)
                else:
                    v = 0.0
                valor_total += v

                # Polo ativo/passivo
                partes = src.get("partes", []) or []
                for parte in partes:
                    doc = str(parte.get("documento", "") or "")
                    polo = str(parte.get("polo", "") or "").upper()
                    if cnpj_limpo in doc.replace(".", "").replace("/", "").replace("-", ""):
                        if polo in ("P", "PASSIVO", "RÉU", "REU", "EXECUTADO"):
                            polo_passivo += 1
                        elif polo in ("A", "ATIVO", "AUTOR", "EXEQUENTE"):
                            polo_ativo += 1

                # Situação
                if situacao in ("ativo", "em andamento", "em tramitação"):
                    processos_ativos += 1

                # Classificação
                if any(c in classe for c in CLASSES_RJ):
                    rj = True
                if any(c in classe for c in CLASSES_FALENCIA):
                    falencia = True
                if any(c in classe for c in CLASSES_EXEC_FISCAL):
                    exec_fiscal += 1
                if any(c in classe for c in CLASSES_TRAB):
                    exec_trab += 1

                # Detalhe
                if v > 0 or rj or falencia or exec_fiscal:
                    num = src.get("numeroProcesso", "")
                    detalhes.append({
                        "tribunal": nome_trib,
                        "numero": num,
                        "classe": classe,
                        "valor": v,
                        "situacao": situacao,
                    })

        except Exception:
            continue

    # Score
    if rj or falencia:
        pts = -45
    elif exec_fiscal >= 5 or polo_passivo >= 20:
        pts = -15
    elif exec_fiscal >= 1 or polo_passivo >= 5:
        pts = -8
    elif total >= 10:
        pts = -4
    elif total > 0:
        pts = -2
    else:
        pts = 3

    if valor_total > 1_000_000:
        pts -= 5
    elif valor_total > 500_000:
        pts -= 3

    # Resumo
    resumo_partes = []
    if rj:
        resumo_partes.append("⚠ RECUPERAÇÃO JUDICIAL DETECTADA")
    if falencia:
        resumo_partes.append("⚠ FALÊNCIA DETECTADA")
    resumo_partes.append(f"{total} processo(s)")
    if tribunais_com_resultado:
        resumo_partes.append(f"Tribunais: {', '.join(tribunais_com_resultado)}")
    if polo_passivo:
        resumo_partes.append(f"Polo passivo: {polo_passivo}")
    if polo_ativo:
        resumo_partes.append(f"Polo ativo: {polo_ativo}")
    if exec_fiscal:
        resumo_partes.append(f"Exec. fiscal: {exec_fiscal}")
    if exec_trab:
        resumo_partes.append(f"Trabalhistas: {exec_trab}")
    if valor_total > 0:
        resumo_partes.append(f"Valor total: R$ {valor_total:,.0f}")

    if not resumo_partes or (len(resumo_partes) == 1 and "processo(s)" in resumo_partes[0]):
        resumo = f"0 processo(s) | Execuções: 0 | Trabalhistas: 0 | Tribunais: {', '.join(tribunais_consultar[:4])}"
    else:
        resumo = " | ".join(resumo_partes)
    detalhe = f"Processos ativos: {processos_ativos} | Tribunais consultados: {len(tribunais_consultar)} ({', '.join(tribunais_consultar)})"

    return fonte_ok(
        "DataJud / CNJ – Processos Judiciais",
        "confirmacao" if total > 0 else "ausencia",
        resumo, detalhe, pts,
        {
            "total": total,
            "polo_passivo": polo_passivo,
            "polo_ativo": polo_ativo,
            "exec_fiscal": exec_fiscal,
            "exec_trabalhista": exec_trab,
            "rj": rj,
            "falencia": falencia,
            "valor_total": valor_total,
            "processos_ativos": processos_ativos,
            "tribunais_com_resultado": tribunais_com_resultado,
            "detalhes": detalhes[:10],
        }
    )

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

# ══════════════════════════════════════════════════════════════════
# PARSER CND — CERTIDÃO NEGATIVA DE DÉBITOS RECEITA/PGFN
# ══════════════════════════════════════════════════════════════════
def analisar_cnd(texto: str, nome: str = "") -> dict:
    """
    Lê o PDF da CND (Certidão Negativa de Débitos) Receita Federal / PGFN.
    Classifica: Negativa / Positiva com efeitos / Positiva
    """
    if not texto or len(texto.strip()) < 50:
        return {
            "disponivel": False, "arquivo": nome,
            "tipo": None, "validade": None, "pontos": -3,
            "resumo": "CND não anexada — regularidade fiscal não confirmada",
            "red_flags": [], "yellow_flags": ["CND não anexada — solicitar ao cliente"],
            "green_flags": [],
        }

    tl = texto.lower()

    # Detecta tipo da certidão
    if "negativa de débitos" in tl or "certidão negativa" in tl:
        if "positiva com efeitos de negativa" in tl or "efeitos de negativa" in tl:
            tipo = "positiva_efeitos_negativa"
        else:
            tipo = "negativa"
    elif "positiva de débitos" in tl or "certidão positiva" in tl:
        tipo = "positiva"
    elif "parcelamento" in tl or "suspen" in tl:
        tipo = "positiva_efeitos_negativa"
    else:
        tipo = "desconhecido"

    # Extrai validade
    validade = None
    m_val = re.search(r"v[aá]lid[ao]?\s*(?:at[eé]|:)?\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    if not m_val:
        m_val = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
    if m_val:
        validade = m_val.group(1)

    # Extrai código de controle
    codigo = None
    m_cod = re.search(r"c[oó]digo\s*(?:de\s*)?controle[:\s]+([A-Z0-9\.\-]+)", texto, re.IGNORECASE)
    if m_cod:
        codigo = m_cod.group(1).strip()

    # Conta emissões (indicador comportamental)
    emissoes = None
    m_em = re.search(r"(\d+)\s*emiss[oõ]", texto, re.IGNORECASE)
    if m_em:
        emissoes = int(m_em.group(1))

    # Verifica validade
    vencida = False
    if validade:
        try:
            from datetime import datetime
            dt_val = datetime.strptime(validade, "%d/%m/%Y")
            vencida = dt_val.date() < dt.date.today()
        except Exception:
            pass

    # Score e flags
    red, yellow, green = [], [], []

    if tipo == "negativa" and not vencida:
        pts = 8
        green.append(f"🟢 CND NEGATIVA — empresa regular perante Receita Federal e PGFN")
        if validade:
            green.append(f"🟢 Válida até: {validade}")
    elif tipo == "positiva_efeitos_negativa":
        pts = -5
        yellow.append("🟡 CND Positiva com efeitos de negativa — débitos com exigibilidade suspensa")
        yellow.append("🟡 Possível parcelamento, garantia ou suspensão judicial — verificar natureza")
        if validade:
            yellow.append(f"🟡 Válida até: {validade}")
    elif tipo == "positiva":
        pts = -20
        red.append("🔴 CND POSITIVA — empresa com débitos fiscais ativos junto à Receita/PGFN")
        red.append("🔴 Situação fiscal irregular — exigir regularização antes da aprovação")
    elif vencida:
        pts = -8
        red.append(f"🔴 CND VENCIDA em {validade} — solicitar nova emissão")
    else:
        pts = -3
        yellow.append("🟡 Tipo de certidão não identificado — verificar documento original")

    # Indicador comportamental de emissões
    if emissoes and emissoes > 20:
        yellow.append(f"🟡 {emissoes} emissões registradas — empresa em captação ativa de crédito/licitações")
    elif emissoes and emissoes > 10:
        yellow.append(f"🟡 {emissoes} emissões — monitorar finalidade")

    TIPO_LABEL = {
        "negativa": "NEGATIVA ✅",
        "positiva_efeitos_negativa": "POSITIVA COM EFEITOS DE NEGATIVA ⚠️",
        "positiva": "POSITIVA ❌",
        "desconhecido": "TIPO NÃO IDENTIFICADO",
    }

    return {
        "disponivel": True,
        "arquivo": nome,
        "tipo": tipo,
        "tipo_label": TIPO_LABEL.get(tipo, tipo),
        "validade": validade,
        "vencida": vencida,
        "codigo_controle": codigo,
        "emissoes": emissoes,
        "pontos": pts,
        "resumo": f"CND {TIPO_LABEL.get(tipo, tipo)}" + (f" | Válida até: {validade}" if validade else ""),
        "red_flags": red,
        "yellow_flags": yellow,
        "green_flags": green,
    }


# ══════════════════════════════════════════════════════════════════
# PARSER CRF — CERTIFICADO DE REGULARIDADE FGTS / CAIXA
# ══════════════════════════════════════════════════════════════════
def analisar_crf(texto: str, nome: str = "") -> dict:
    """
    Lê o PDF do CRF (Certificado de Regularidade do FGTS) da Caixa Econômica.
    """
    if not texto or len(texto.strip()) < 50:
        return {
            "disponivel": False, "arquivo": nome,
            "tipo": None, "validade": None, "pontos": -2,
            "resumo": "CRF/FGTS não anexado — regularidade trabalhista não confirmada",
            "red_flags": [], "yellow_flags": ["CRF/FGTS não anexado — solicitar ao cliente"],
            "green_flags": [],
        }

    tl = texto.lower()

    # Detecta situação
    if "regular" in tl and ("certificado" in tl or "crf" in tl):
        if "irregular" in tl:
            situacao = "irregular"
        else:
            situacao = "regular"
    elif "irregular" in tl or "débito" in tl or "pendência" in tl:
        situacao = "irregular"
    elif "certificado de regularidade" in tl:
        situacao = "regular"
    else:
        situacao = "desconhecido"

    # Extrai validade
    validade = None
    for padrao in [r"v[aá]lid[ao]?\s*(?:at[eé]|:)?\s*(\d{2}/\d{2}/\d{4})",
                   r"validade[:\s]+(\d{2}/\d{2}/\d{4})",
                   r"(\d{2}/\d{2}/\d{4})"]:
        m = re.search(padrao, texto, re.IGNORECASE)
        if m:
            validade = m.group(1)
            break

    # Extrai número do certificado
    numero = None
    m_num = re.search(r"n[uú]mero[:\s]+([A-Z0-9\.\-\/]+)", texto, re.IGNORECASE)
    if m_num:
        numero = m_num.group(1).strip()

    # Verifica vencimento
    vencida = False
    if validade:
        try:
            dt_val = dt.datetime.strptime(validade, "%d/%m/%Y")
            vencida = dt_val.date() < dt.date.today()
        except Exception:
            pass

    red, yellow, green = [], [], []

    if situacao == "regular" and not vencida:
        pts = 4
        green.append("🟢 CRF/FGTS REGULAR — empresa em dia com obrigações do FGTS")
        if validade:
            green.append(f"🟢 Válido até: {validade}")
        if numero:
            green.append(f"🟢 Certificado: {numero}")
    elif vencida:
        pts = -4
        red.append(f"🔴 CRF/FGTS VENCIDO em {validade} — solicitar nova emissão")
        yellow.append("🟡 Verificar regularidade atual em consulta-crf.caixa.gov.br")
    elif situacao == "irregular":
        pts = -10
        red.append("🔴 CRF/FGTS IRREGULAR — empresa com débitos de FGTS em aberto")
        red.append("🔴 Risco trabalhista elevado — pode indicar problemas com folha de pagamento")
    else:
        pts = -2
        yellow.append("🟡 Situação CRF não identificada — verificar documento original")

    return {
        "disponivel": True,
        "arquivo": nome,
        "situacao": situacao,
        "validade": validade,
        "vencida": vencida,
        "numero_certificado": numero,
        "pontos": pts,
        "resumo": f"CRF/FGTS {'REGULAR' if situacao == 'regular' else 'IRREGULAR' if situacao == 'irregular' else 'N/D'}" + (f" | Válido até: {validade}" if validade else ""),
        "red_flags": red,
        "yellow_flags": yellow,
        "green_flags": green,
    }

def analisar_cnpj(cnpj: str, texto_bal: str = "", nome_bal: str = "",
                   texto_cisp: str = "", nome_cisp: str = "",
                   texto_cnd: str = "", nome_cnd: str = "",
                   texto_crf: str = "", nome_crf: str = "",
                   uf: str = "") -> dict:
    if not validar_cnpj(cnpj):
        raise ValueError(f"CNPJ inválido: {cnpj}")

    rec = consultar_receita(cnpj)
    razao = rec.get("razao_social","")
    cnae = rec.get("cnae","")
    # Pega UF real da Receita Federal (ex: PA para Okajima)
    uf_real = rec.get("uf","") or uf or "SP"

    # QSA para OpenSanctions
    qsa_raw = rec.get("raw", {}).get("qsa", []) if isinstance(rec.get("raw"), dict) else []

    fontes = [
        rec,
        consultar_ceis(cnpj),
        consultar_opensanctions(razao, qsa_raw),
        consultar_datajud(cnpj, razao, uf_real),
        consultar_noticias(razao),
        classificar_setor(cnae),
        consultar_cndt(cnpj),
        consultar_simples(cnpj),
    ]

    # Chama worker PythonAnywhere para PGFN + Junta + Grupo + Sócios
    worker_fontes = consultar_worker(cnpj, razao, uf_real, ["pgfn", "junta"])
    if worker_fontes:
        fontes.extend(worker_fontes)
    else:
        fontes.append(fonte_ok("PGFN / Dívida Ativa","pendente",
            "Consultar em listadevedores.pgfn.gov.br — ausência NÃO equivale a regularidade","",-5))

    # Consulta grupo econômico e sócios
    grupo_data = consultar_grupo_economico(cnpj)

    fontes.extend([
        fonte_ok("FGTS / CRF","pendente","CRF via caixa.gov.br","",-3),
        fonte_ok("Protestos / IEPTB","pendente","Consulta via bureau especializado","",-4),
        fonte_ok("Bureau de Crédito","pendente","Score bureau requer contrato","",-6),
    ])

    bal = analisar_balanco(texto_bal, nome_bal)
    cisp = analisar_cisp(texto_cisp, nome_cisp)
    cnd = analisar_cnd(texto_cnd, nome_cnd)
    crf = analisar_crf(texto_crf, nome_crf)

    # Adiciona CND e CRF às fontes
    if cnd["disponivel"]:
        fontes.append(fonte_ok(
            "CND — Certidão Receita/PGFN", "confirmacao" if cnd["tipo"] == "negativa"
            else "indicio" if cnd["tipo"] == "positiva_efeitos_negativa" else "erro",
            cnd["resumo"], "", cnd["pontos"]
        ))
    else:
        fontes.append(fonte_ok(
            "CND — Certidão Receita/PGFN", "pendente",
            "Não anexada — solicitar ao cliente ou emitir em servicos.receitafederal.gov.br",
            "", -3
        ))

    if crf["disponivel"]:
        fontes.append(fonte_ok(
            "CRF/FGTS — Caixa Econômica", "confirmacao" if crf["situacao"] == "regular"
            else "erro",
            crf["resumo"], "", crf["pontos"]
        ))
    else:
        fontes.append(fonte_ok(
            "CRF/FGTS — Caixa Econômica", "pendente",
            "Não anexado — solicitar ao cliente ou emitir em consulta-crf.caixa.gov.br",
            "", -2
        ))

    score_data = calcular_score(fontes, bal, cisp)

    # Gera flags de grupo econômico
    grupo = grupo_data.get("grupo", {})
    socios_360 = grupo_data.get("socios", {})

    if grupo.get("alerta_grupo"):
        score_data["red_flags"] = score_data.get("red_flags", []) + [
            f"🔴 GRUPO ECONÔMICO: {grupo.get('total',0)} estabelecimentos detectados — limite deve ser calculado para o GRUPO"
        ]
        cross = grupo.get("cross_default", {})
        if cross:
            score_data["yellow_flags"] = score_data.get("yellow_flags", []) + [
                f"🟡 Cross-default: {len(cross)} sócio(s) em múltiplos CNPJs do grupo"
            ]

    if socios_360.get("tem_alertas"):
        for alerta in socios_360.get("alertas_socios", []):
            score_data["red_flags"] = score_data.get("red_flags", []) + [f"🔴 SÓCIO: {alerta}"]

    return {
        "cnpj": cnpj, "empresa": razao,
        **score_data,
        "fontes": fontes,
        "fontes_consultadas": len([f for f in fontes if f["status"] not in ("pendente","nao_consultado")]),
        "fontes_pendentes": len([f for f in fontes if f["status"] in ("pendente","nao_consultado")]),
        "total_fontes": len(fontes),
        "balanco_detalhado": bal,
        "cisp_detalhado": cisp,
        "cnd_detalhado": cnd,
        "crf_detalhado": crf,
        "grupo_economico": grupo,
        "socios_360": socios_360,
        "assinatura": ASSINATURA,
        "analisado_em": dt.datetime.now().isoformat(),
    }

# ══════════════════════════════════════════════════════════════════
# GERAÇÃO DE PDF
# ══════════════════════════════════════════════════════════════════

# Constantes de cor para PDF
ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"
W = A4[0] - 3*cm  # largura útil para tabelas PDF
NAVY_C  = colors.HexColor("#1E3A5F")
GOLD_C  = colors.HexColor("#b49303")
RED_C   = colors.HexColor("#c0392b")
YEL_C   = colors.HexColor("#b45309")
GRN_C   = colors.HexColor("#0e7a5a")
LIGHT_C = colors.HexColor("#f5f0e8")
BGRED_C = colors.HexColor("#fff0ee")
BGYL_C  = colors.HexColor("#fff8ee")
BGGRN_C = colors.HexColor("#edfaf5")
BORD_C  = colors.HexColor("#d4c9a8")
MUTED_C = colors.HexColor("#6b6b7b")
BLACK_C = colors.HexColor("#1a1a2e")

# Aliases para uso na função gerar_pdf_executivo
NAVY = NAVY_C; GOLD = GOLD_C; RED = RED_C; YEL = YEL_C; GRN = GRN_C
LIGHT = LIGHT_C; BGRED = BGRED_C; BGYL = BGYL_C; BGGRN = BGGRN_C
BORD = BORD_C; WHITE = colors.white; BLACK = BLACK_C; MUTED = MUTED_C

def ps(name, **kw):
    """Cria ParagraphStyle para PDF."""
    from reportlab.lib.styles import ParagraphStyle
    base = dict(fontName="Helvetica", fontSize=8, textColor=BLACK_C, leading=12)
    base.update(kw)
    return ParagraphStyle(name + str(id(kw)), **base)

def secao(titulo):
    """Retorna elementos de seção para PDF."""
    return [
        Spacer(1, 8),
        Paragraph(titulo, ps("sec", fontName="Helvetica-Bold", fontSize=9,
                              textColor=GOLD, leading=14)),
        HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=4),
    ]

def fmt_r(v):
    if v is None: return "—"
    try: return f"R$ {float(v):,.0f}"
    except: return str(v)

def fmt_pct(v):
    if v is None: return "—"
    try: return f"{float(v):.1f}%"
    except: return str(v)

def fmt_mult(v):
    if v is None: return "—"
    try: return f"{float(v):.2f}×"
    except: return str(v)


def gerar_pdf_executivo(resultado: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.2*cm, bottomMargin=1.2*cm)

    els = []
    ind = resultado.get("balanco_detalhado", {}).get("indicadores", {})
    cisp_ind = resultado.get("cisp_detalhado", {}).get("indicadores", {})
    empresa = resultado.get("empresa", "")
    cnpj = resultado.get("cnpj", "")
    bal = resultado.get("balanco_detalhado", {})
    cisp = resultado.get("cisp_detalhado", {})

    # ═══ CABEÇALHO ═══════════════════════════════════════════════════
    els.append(Paragraph(ASSINATURA, ps("sig", fontName="Helvetica-Bold",
                                         fontSize=7, textColor=NAVY, alignment=TA_CENTER)))
    els.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=5))
    els.append(Paragraph("RELATÓRIO EXECUTIVO DE CRÉDITO — ANÁLISE INDIVIDUAL",
                          ps("t", fontName="Helvetica-Bold", fontSize=14, textColor=NAVY)))
    ano_bal = resultado.get("balanco_detalhado", {}).get("ano_balanco", "")
    subtitulo_empresa = f"{empresa}"
    if ano_bal and ano_bal != "N/D":
        subtitulo_empresa += f"  |  Balanço base: 31/12/{ano_bal}"
    els.append(Paragraph(subtitulo_empresa, ps("st", fontName="Helvetica-Bold",
                                      fontSize=11, textColor=NAVY, spaceAfter=3)))

    # Dados cadastrais
    score = resultado.get("score", 0)
    rating = resultado.get("rating", "D")
    pd_val = resultado.get("pd", 0)
    risco = resultado.get("classificacao_risco", "alto")
    sc_color = GRN if score >= 75 else YEL if score >= 50 else RED

    cad = Table([
        [Paragraph(f"CNPJ: <b>{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}</b>", ps("c1")),
         Paragraph(f"Data-base: <b>{dt.date.today().strftime('%d/%m/%Y')}</b>", ps("c1")),
         Paragraph(f"Gerado em: <b>{dt.datetime.now().strftime('%d/%m/%Y %H:%M')}</b>", ps("c1"))],
    ], colWidths=[W*0.35, W*0.32, W*0.33])
    cad.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),8), ("PADDING",(0,0),(-1,-1),3),
    ]))
    els.append(cad)
    els.append(Spacer(1,6))

    # Painel de score
    score_data = Table([
        [Paragraph(f"<b>{score}</b>", ps("sc", fontName="Helvetica-Bold",
                                          fontSize=32, textColor=sc_color, alignment=TA_CENTER)),
         Paragraph(f"<b>{rating}</b>", ps("rat", fontName="Helvetica-Bold",
                                           fontSize=28, textColor=sc_color, alignment=TA_CENTER)),
         Paragraph(f"<b>{pd_val:.1f}%</b>", ps("pd", fontName="Helvetica-Bold",
                                                  fontSize=22, textColor=RED, alignment=TA_CENTER)),
         Paragraph(f"<b>{risco.upper()}</b>", ps("ris", fontName="Helvetica-Bold",
                                                   fontSize=14, textColor=RED, alignment=TA_CENTER)),
        ],
        [Paragraph("Score", ps("sl", alignment=TA_CENTER, textColor=MUTED, fontSize=8)),
         Paragraph("Rating", ps("sl2", alignment=TA_CENTER, textColor=MUTED, fontSize=8)),
         Paragraph("PD Estimada", ps("sl3", alignment=TA_CENTER, textColor=MUTED, fontSize=8)),
         Paragraph("Risco", ps("sl4", alignment=TA_CENTER, textColor=MUTED, fontSize=8)),
        ],
    ], colWidths=[W*0.2]*4)
    score_data.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,BORD),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[LIGHT, WHITE]),
        ("PADDING",(0,0),(-1,-1),6),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
    ]))
    els.append(score_data)
    els.append(Spacer(1,6))

    # Recomendação
    rec = Table([
        [Paragraph("<b>LIMITE SUGERIDO</b>", ps("rl", fontSize=8, textColor=MUTED)),
         Paragraph("<b>PRAZO</b>", ps("rp", fontSize=8, textColor=MUTED)),
         Paragraph("<b>MONITORAMENTO</b>", ps("rm", fontSize=8, textColor=MUTED)),
         Paragraph("<b>GARANTIAS</b>", ps("rg", fontSize=8, textColor=MUTED))],
        [Paragraph(resultado.get("limite_sugerido",""), ps("rv")),
         Paragraph(resultado.get("prazo_sugerido",""), ps("rv2")),
         Paragraph(resultado.get("plano_monitoramento",""), ps("rv3")),
         Paragraph(" | ".join(resultado.get("garantias_recomendadas",[])), ps("rv4"))],
    ], colWidths=[W*0.28, W*0.15, W*0.32, W*0.25])
    rec.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,BORD),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[LIGHT, WHITE]),
        ("PADDING",(0,0),(-1,-1),5),
        ("FONTSIZE",(0,0),(-1,-1),8),
    ]))
    els.append(rec)

    # ═══ ANÁLISE FINANCEIRA ══════════════════════════════════════════
    if bal.get("disponivel"):
        els += secao("ANÁLISE FINANCEIRA — BALANÇO E DEMONSTRATIVO DE RESULTADO")

        # DRE com % ROL
        receita_liq = ind.get("receita_liquida", 0) or 1

        def pct_rol(v):
            if not v or not receita_liq: return "—"
            return f"({v/receita_liq*100:.1f}%)"

        def obs_dre(item, valor):
            obs = {
                "Receita Bruta": "Faturamento total antes das deduções",
                "Deduções": "Devoluções + impostos sobre vendas",
                "Receita Líquida (ROL)": "Base de cálculo das margens",
                "CMV / CPI": "Custo das mercadorias vendidas",
                "Lucro Bruto": f"Margem bruta: {fmt_pct(ind.get('margem_bruta'))}",
                "Desp. Comerciais": "Vendas, marketing e comissões",
                "Desp. Administrativas": "Overhead e estrutura",
                "Desp. Financeiras Líq.": "Custo da dívida bancária",
                "Lucro Operacional": "Resultado antes do financeiro",
                "Lucro Líquido": f"Margem líquida: {fmt_pct(ind.get('margem_liquida'))}",
                "EBITDA": "Geração operacional de caixa",
                "FCO (Fluxo Caixa Op.)": "Caixa gerado/consumido nas operações",
            }
            return obs.get(item, "")

        dre_items = [
            ("Receita Bruta", ind.get("receita_bruta")),
            ("Receita Líquida (ROL)", ind.get("receita_liquida")),
            ("CMV / CPI", ind.get("cmv")),
            ("Lucro Bruto", ind.get("lucro_bruto")),
            ("Desp. Comerciais", ind.get("desp_vendas")),
            ("Desp. Administrativas", ind.get("desp_admin")),
            ("Desp. Financeiras Líq.", ind.get("desp_financeiras")),
            ("EBITDA", ind.get("ebitda")),
            ("Lucro Líquido", ind.get("lucro_liquido")),
            ("FCO (Fluxo Caixa Op.)", ind.get("fco")),
        ]
        dre_rows = []
        for item, valor in dre_items:
            if valor is None: continue
            neg = valor < 0 if isinstance(valor, (int,float)) else False
            cor = RED if neg else BLACK
            dre_rows.append([
                Paragraph(item, ps("di")),
                Paragraph(fmt_r(abs(valor) if valor else valor), ps("dv", alignment=TA_RIGHT,
                    textColor=RED if neg else BLACK,
                    fontName="Helvetica-Bold" if item in ("Lucro Líquido","Receita Líquida (ROL)","EBITDA") else "Helvetica")),
                Paragraph(pct_rol(valor), ps("dp", alignment=TA_RIGHT, textColor=MUTED, fontSize=7)),
                Paragraph(obs_dre(item, valor), ps("do", fontSize=7, textColor=MUTED)),
            ])

        if dre_rows:
            els.append(Paragraph("2.1 — DRE Resumida", ps("sh", fontName="Helvetica-Bold",
                                                            fontSize=9, textColor=NAVY)))
            els.append(Spacer(1,3))
            t = Table([["Item","Valor (R$)","% ROL","Observação"]] + dre_rows,
                      colWidths=[W*0.28, W*0.20, W*0.10, W*0.42])
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),
                ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,-1),8),
                ("GRID",(0,0),(-1,-1),0.3,BORD),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("ALIGN",(1,0),(2,-1),"RIGHT"),
                ("PADDING",(0,0),(-1,-1),4),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ]))
            els.append(t)
            els.append(Spacer(1,8))

        # BP Resumido
        def obs_bp(item, valor):
            ativo_t = ind.get("ativo_total",1) or 1
            pct = f"{abs(valor)/ativo_t*100:.1f}% do ativo" if valor and ativo_t else ""
            obs = {
                "ATIVO TOTAL": f"Base de análise",
                "Caixa e Disponível": f"{pct} — {'Baixo' if valor and valor/ativo_t < 0.05 else 'Adequado'}",
                "Clientes": f"{pct} — Prazo médio de recebimento",
                "Estoques": f"{pct} — Distribuidor: giro é chave",
                "Patrimônio Líquido": f"{pct} — {'Empresa capitalizada' if valor and valor/ativo_t > 0.4 else 'Atenção ao nível de capitalização'}",
                "Empréstimos CP": f"{pct} — {'Mínimo' if valor and valor < 1000000 else 'Avaliar custo e vencimentos'}",
                "Capital de Giro": "Ativo Circ. - Passivo Circ.",
                "NCG": "Necessidade de financiamento do giro",
            }
            return obs.get(item, pct)

        bp_items = [
            ("ATIVO TOTAL", ind.get("ativo_total")),
            ("Caixa e Disponível", ind.get("caixa_disponivel")),
            ("Clientes", ind.get("clientes")),
            ("Estoques", ind.get("estoques")),
            ("Patrimônio Líquido", ind.get("patrimonio_liquido")),
            ("Capital Social", ind.get("capital_social")),
            ("Empréstimos CP", ind.get("emprestimos_cp")),
            ("Capital de Giro", ind.get("capital_giro")),
            ("NCG", ind.get("ncg")),
        ]
        bp_rows = []
        for item, valor in bp_items:
            if valor is None: continue
            bold = item in ("ATIVO TOTAL","Patrimônio Líquido")
            bp_rows.append([
                Paragraph(item, ps("bi", fontName="Helvetica-Bold" if bold else "Helvetica")),
                Paragraph(fmt_r(valor), ps("bv", alignment=TA_RIGHT,
                    fontName="Helvetica-Bold" if bold else "Helvetica")),
                Paragraph(obs_bp(item, valor), ps("bo", fontSize=7, textColor=MUTED)),
            ])

        if bp_rows:
            els.append(Paragraph("2.2 — Balanço Patrimonial Resumido", ps("sh", fontName="Helvetica-Bold",
                                                                            fontSize=9, textColor=NAVY)))
            els.append(Spacer(1,3))
            t = Table([["Conta","Valor (R$)","Observação"]] + bp_rows,
                      colWidths=[W*0.30, W*0.22, W*0.48])
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),
                ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,-1),8),
                ("GRID",(0,0),(-1,-1),0.3,BORD),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("ALIGN",(1,0),(1,-1),"RIGHT"),
                ("PADDING",(0,0),(-1,-1),4),
            ]))
            els.append(t)
            els.append(Spacer(1,8))

        # Indicadores-chave
        def classif_ind(nome, valor):
            classifs = {
                "liquidez_corrente": lambda v: ("BOM — margem confortável", GRN) if v>=1.5 else ("ACEITÁVEL", YEL) if v>=1.0 else ("ATENÇÃO", RED),
                "liquidez_geral": lambda v: ("BOM", GRN) if v>=1.2 else ("ATENÇÃO", YEL),
                "liquidez_seca": lambda v: ("SATISFATÓRIO", GRN) if v>=0.8 else ("ATENÇÃO", YEL),
                "margem_bruta": lambda v: ("BOA para distribuidora", GRN) if v>=20 else ("COMPRIMIDA", RED) if v<15 else ("MODERADA", YEL),
                "margem_liquida": lambda v: ("SAUDÁVEL", GRN) if v>=5 else ("APERTADA", YEL) if v>=2 else ("CRÍTICA", RED),
                "ciclo_financeiro": lambda v: ("EXCELENTE", GRN) if v<=30 else ("PÉSSIMO", RED) if v>90 else ("ATENÇÃO", YEL),
                "fator_kanitz": lambda v: ("SOLVENTE", GRN) if v>0 else ("INSOLVÊNCIA", RED),
                "pl_sobre_ativo": lambda v: ("EXCELENTE — empresa capitalizada", GRN) if v>=40 else ("BOM", YEL),
            }
            fn = classifs.get(nome)
            if fn and valor is not None:
                try: return fn(float(valor))
                except: pass
            return ("—", MUTED)

        idx_items = [
            ("Liquidez corrente (AC/PC)", "liquidez_corrente", fmt_mult),
            ("Liquidez imediata (Disp./PC)", "liquidez_imediata", fmt_mult),
            ("Liquidez geral", "liquidez_geral", fmt_mult),
            ("Capital de giro líquido", "capital_giro", fmt_r),
            ("PL / Ativo total", "pl_sobre_ativo", fmt_pct),
            ("Margem bruta", "margem_bruta", fmt_pct),
            ("Margem líquida", "margem_liquida", fmt_pct),
            ("Ciclo financeiro (dias)", "ciclo_financeiro", lambda v: f"{v:.0f} dias" if v else "—"),
            ("Fator Kanitz", "fator_kanitz", lambda v: f"{v:.2f}" if v else "—"),
        ]
        idx_rows = []
        for label, key, fmt_fn in idx_items:
            val = ind.get(key)
            if val is None: continue
            cl_text, cl_color = classif_ind(key, val)
            idx_rows.append([
                Paragraph(label, ps("ii")),
                Paragraph(fmt_fn(val), ps("iv", alignment=TA_RIGHT, fontName="Helvetica-Bold")),
                Paragraph(cl_text, ps("ic", textColor=cl_color, fontName="Helvetica-Bold", fontSize=7)),
            ])

        if idx_rows:
            els.append(Paragraph("2.3 — Indicadores-Chave", ps("sh", fontName="Helvetica-Bold",
                                                                  fontSize=9, textColor=NAVY)))
            els.append(Spacer(1,3))
            t = Table([["Indicador","Valor","Classificação"]] + idx_rows,
                      colWidths=[W*0.40, W*0.18, W*0.42])
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),
                ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,-1),8),
                ("GRID",(0,0),(-1,-1),0.3,BORD),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("ALIGN",(1,0),(1,-1),"RIGHT"),
                ("PADDING",(0,0),(-1,-1),4),
            ]))
            els.append(t)

    # ═══ ANÁLISE CISP ════════════════════════════════════════════════
    if cisp.get("disponivel"):
        els += secao("ANÁLISE CISP / CREDINFAR — COMPORTAMENTO COMERCIAL")

        debito = cisp_ind.get("debito_atual", 0) or 1

        cisp_rows = [
            ("Débito atual total", fmt_r(cisp_ind.get("debito_atual")),
             "Exposição total no mercado"),
            ("Vencido +5 dias", fmt_r(cisp_ind.get("vencido_5d")),
             f"{fmt_pct(cisp_ind.get('pct_vencido_5d'))} — {'🔴 Nível alto' if (cisp_ind.get('pct_vencido_5d') or 0)>=40 else '🟡 Atenção'}"),
            ("Vencido +15 dias", fmt_r(cisp_ind.get("vencido_15d")),
             f"{fmt_pct(cisp_ind.get('pct_vencido_15d'))} — {'🔴 Sinal forte de estresse' if (cisp_ind.get('pct_vencido_15d') or 0)>=30 else '🟡 Monitorar'}"),
            ("Vencido +30 dias", fmt_r(cisp_ind.get("vencido_30d")),
             f"{fmt_pct(cisp_ind.get('pct_vencido_30d'))} — {'🔴 Parcela madura crítica' if (cisp_ind.get('pct_vencido_30d') or 0)>=25 else '🟡 Atenção'}"),
            ("Classe de risco", str(cisp_ind.get("classe_risco","—")),
             f"Estável por {cisp_ind.get('meses_estabilidade','—')} meses" if cisp_ind.get("meses_estabilidade") else "Verificar histórico"),
            ("Garantia / Seguro", fmt_r(cisp_ind.get("garantia_valor")),
             f"Cobertura: {cisp_ind.get('garantia_valor',0)/debito*100:.1f}% da exposição" if cisp_ind.get("garantia_valor") else "Sem garantia registrada"),
            ("Assoc. sem crédito (30d)", str(cisp_ind.get("assoc_sem_credito","—")),
             "🔴 Mercado restringindo crédito" if (cisp_ind.get("assoc_sem_credito") or 0)>=50 else "Monitorar evolução"),
        ]

        t = Table([["Indicador","Valor","Leitura"]] +
                  [[Paragraph(r[0], ps("ci")),
                    Paragraph(r[1], ps("cv", alignment=TA_RIGHT, fontName="Helvetica-Bold")),
                    Paragraph(r[2], ps("cl", fontSize=7, textColor=MUTED))] for r in cisp_rows],
                  colWidths=[W*0.30, W*0.22, W*0.48])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),NAVY),
            ("TEXTCOLOR",(0,0),(-1,0),WHITE),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("GRID",(0,0),(-1,-1),0.3,BORD),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
            ("ALIGN",(1,0),(1,-1),"RIGHT"),
            ("PADDING",(0,0),(-1,-1),4),
        ]))
        els.append(t)

    # ═══ FLAGS ═══════════════════════════════════════════════════════
    els += secao("FLAGS DE RISCO E SINAIS POSITIVOS")

    red_f = resultado.get("red_flags", [])
    yel_f = resultado.get("yellow_flags", [])
    grn_f = resultado.get("green_flags", [])
    max_f = max(len(red_f), len(yel_f), len(grn_f), 1)

    flag_header = [
        Paragraph("🔴 RED FLAGS", ps("fh", fontName="Helvetica-Bold", fontSize=9, textColor=RED)),
        Paragraph("🟡 YELLOW FLAGS", ps("fh2", fontName="Helvetica-Bold", fontSize=9, textColor=YEL)),
        Paragraph("🟢 GREEN FLAGS", ps("fh3", fontName="Helvetica-Bold", fontSize=9, textColor=GRN)),
    ]
    flag_rows = [flag_header]
    for i in range(max_f):
        r = Paragraph(f"• {red_f[i]}", ps("fr", fontSize=7, textColor=colors.HexColor("#7f1d1d"), leading=11)) if i<len(red_f) else Paragraph("", ps("fe"))
        y = Paragraph(f"• {yel_f[i]}", ps("fy", fontSize=7, textColor=colors.HexColor("#78350f"), leading=11)) if i<len(yel_f) else Paragraph("", ps("fe2"))
        g = Paragraph(f"• {grn_f[i]}", ps("fg", fontSize=7, textColor=colors.HexColor("#064e3b"), leading=11)) if i<len(grn_f) else Paragraph("", ps("fe3"))
        flag_rows.append([r, y, g])

    tf = Table(flag_rows, colWidths=[W/3]*3)
    tf.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,0), BGRED),
        ("BACKGROUND",(1,0),(1,0), BGYL),
        ("BACKGROUND",(2,0),(2,0), BGGRN),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE, LIGHT]),
        ("GRID",(0,0),(-1,-1),0.3,BORD),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("PADDING",(0,0),(-1,-1),5),
    ]))
    els.append(tf)

    # ═══ MEMÓRIA DE CÁLCULO ══════════════════════════════════════════
    els += secao("MEMÓRIA DE CÁLCULO DO SCORE")

    mem = resultado.get("memoria_calculo", {})
    mem_rows = []
    for k, v in mem.items():
        if k == "score_final": continue
        label = k.replace("_"," ").title()
        sinal = "+" if isinstance(v,(int,float)) and v > 0 else ""
        cor = GRN if isinstance(v,(int,float)) and v > 0 else RED if isinstance(v,(int,float)) and v < 0 else BLACK
        mem_rows.append([
            Paragraph(label, ps("mk")),
            Paragraph(f"{sinal}{v}", ps("mv", fontName="Helvetica-Bold", textColor=cor, alignment=TA_RIGHT)),
        ])
    mem_rows.append([
        Paragraph("SCORE FINAL", ps("mf", fontName="Helvetica-Bold", textColor=NAVY)),
        Paragraph(str(mem.get("score_final","")),
                  ps("mfv", fontName="Helvetica-Bold", fontSize=14,
                     textColor=sc_color, alignment=TA_RIGHT)),
    ])

    tm = Table(mem_rows, colWidths=[W*0.7, W*0.3])
    tm.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("GRID",(0,0),(-1,-1),0.3,BORD),
        ("ROWBACKGROUNDS",(0,0),(-1,-2),[WHITE,LIGHT]),
        ("BACKGROUND",(0,-1),(-1,-1),NAVY),
        ("TEXTCOLOR",(0,-1),(-1,-1),WHITE),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("PADDING",(0,0),(-1,-1),4),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),
    ]))
    els.append(tm)

    # ═══ CEIS/CNEP — SANÇÕES DETALHADAS ════════════════════════════════
    fontes_resultado = resultado.get("fontes", [])
    fonte_ceis = next((f for f in fontes_resultado if "CEIS" in f.get("fonte","")), {})
    sancoes_lista = fonte_ceis.get("sancoes_detalhes", [])

    if sancoes_lista:
        els += secao("SANÇÕES — CEIS/CNEP (Portal da Transparência)")
        total_s = fonte_ceis.get("total_sancoes", len(sancoes_lista))
        vigentes = fonte_ceis.get("sancoes_vigentes", 0)
        valor_multas = fonte_ceis.get("valor_total_multas", 0)

        # Resumo
        resumo_txt = f"Total: {total_s} sanção(ões)"
        if vigentes:
            resumo_txt += f" | Vigentes: {vigentes}"
        if valor_multas > 0:
            resumo_txt += f" | Multas: R$ {valor_multas:,.2f}"
        els.append(Paragraph(resumo_txt,
            ps("sr", fontName="Helvetica-Bold", fontSize=9, textColor=RED)))
        els.append(Spacer(1,6))

        # Filtra apenas vigentes para exibição no PDF
        sancoes_vigentes_lista = [s for s in sancoes_lista if s.get("vigente")]
        sancoes_exibir = sancoes_vigentes_lista if sancoes_vigentes_lista else sancoes_lista
        total_exibir = len(sancoes_exibir)

        if sancoes_vigentes_lista:
            els.append(Paragraph(
                f"Exibindo apenas sanções VIGENTES ({len(sancoes_vigentes_lista)} de {total_s} total)",
                ps("sv2", fontName="Helvetica-Bold", fontSize=8, textColor=RED)))
            els.append(Spacer(1,4))

        # Tabela de sanções vigentes
        rows = [["Tipo","Órgão Sancionador","Início","Fim","Multa (R$)"]]
        for s in sancoes_exibir[:20]:  # max 20 vigentes
            multa = s.get("valor_multa", 0) or 0
            rows.append([
                Paragraph(s.get("tipo","")[:50], ps("sc", fontSize=6)),
                Paragraph(s.get("orgao","")[:50], ps("so", fontSize=6)),
                s.get("inicio","")[:10],
                s.get("fim","")[:10],
                Paragraph(
                    f"R$ {multa:,.2f}" if multa > 0 else "—",
                    ps("sm", fontSize=6,
                        textColor=RED if multa > 0 else MUTED,
                        fontName="Helvetica-Bold" if multa > 0 else "Helvetica")
                ),
            ])

        tc = Table(rows, colWidths=[5*cm, 5*cm, 2*cm, 2*cm, 3*cm])
        tc.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),RED),
            ("TEXTCOLOR",(0,0),(-1,0),WHITE),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),6),
            ("GRID",(0,0),(-1,-1),0.3,BORD),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
            ("PADDING",(0,0),(-1,-1),3),
            ("ALIGN",(2,0),(4,-1),"CENTER"),
        ]))
        els.append(tc)
        els.append(Spacer(1,4))

        # Valor total das multas
        valor_total = fonte_ceis.get("valor_total_multas", 0)
        if valor_total > 0:
            els.append(Paragraph(
                f"Total de multas: R$ {valor_total:,.2f}",
                ps("vt", fontName="Helvetica-Bold", fontSize=8, textColor=RED)))
        else:
            els.append(Paragraph(
                "Valores de multa não informados nos registros do CEIS — consultar processo administrativo",
                ps("vt2", fontSize=7, textColor=MUTED)))

        if total_exibir > 20:
            els.append(Paragraph(
                f"* Exibindo 20 de {total_exibir} sanções vigentes. Lista completa em portaldatransparencia.gov.br",
                ps("sn", fontSize=7, textColor=MUTED)))
        els.append(Spacer(1,8))

    # ═══ GRUPO ECONÔMICO ════════════════════════════════════════════════
    grupo = resultado.get("grupo_economico", {})
    socios_360 = resultado.get("socios_360", {})

    if grupo.get("total", 0) > 1 or socios_360.get("total_socios", 0) > 0:
        els += secao("GRUPO ECONÔMICO E VISÃO 360 DOS SÓCIOS")

        filiais = grupo.get("filiais", [])
        if filiais:
            els.append(Paragraph("Estabelecimentos do Grupo",
                ps("sh", fontName="Helvetica-Bold", fontSize=9, textColor=NAVY)))
            els.append(Spacer(1,3))
            fil_rows = [["CNPJ","Município/UF","Abertura","Situação"]]
            for fi in filiais:
                sit = fi.get("situacao","")
                fil_rows.append([
                    fi.get("cnpj",""),
                    f"{fi.get('municipio','')}/{fi.get('uf','')}",
                    fi.get("abertura","")[:10],
                    Paragraph(sit, ps("fs", fontSize=7,
                        textColor=GRN if sit=="ATIVA" else RED,
                        fontName="Helvetica-Bold")),
                ])
            tf = Table(fil_rows, colWidths=[4*cm,4*cm,3*cm,3.5*cm])
            tf.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),
                ("GRID",(0,0),(-1,-1),0.3,BORD),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("PADDING",(0,0),(-1,-1),3),
            ]))
            els.append(tf)
            els.append(Spacer(1,4))

        cross = grupo.get("cross_default", {})
        if cross:
            els.append(Paragraph(
                f"⚠ Cross-default: {len(cross)} sócio(s) em múltiplos CNPJs — calcular limite pelo GRUPO",
                ps("cd", fontName="Helvetica-Bold", fontSize=8, textColor=YEL)))
            els.append(Spacer(1,4))

        socios = socios_360.get("socios", {})
        if socios:
            els.append(Paragraph("Visão 360 — Sócios",
                ps("sh", fontName="Helvetica-Bold", fontSize=9, textColor=NAVY)))
            els.append(Spacer(1,3))
            soc_rows = [["Sócio","Qualificação","Empresas","Processos","Alertas"]]
            for nome, info in socios.items():
                alertas = " | ".join(info.get("alertas",[]))[:60] if info.get("alertas") else "—"
                proc = info.get("processos_tjsp", info.get("processos", 0))
                soc_rows.append([
                    Paragraph(nome[:28], ps("sn", fontSize=7, fontName="Helvetica-Bold")),
                    Paragraph(info.get("qualificacao","")[:20], ps("sq", fontSize=7)),
                    str(len(info.get("empresas",[]))),
                    Paragraph(str(proc), ps("sp", fontSize=7,
                        textColor=RED if proc>10 else YEL if proc>0 else GRN,
                        fontName="Helvetica-Bold")),
                    Paragraph(alertas, ps("sa", fontSize=7,
                        textColor=YEL if alertas!="—" else MUTED)),
                ])
            ts = Table(soc_rows, colWidths=[4*cm,3*cm,2*cm,2*cm,6.5*cm])
            ts.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),
                ("GRID",(0,0),(-1,-1),0.3,BORD),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("ALIGN",(2,0),(3,-1),"CENTER"),("PADDING",(0,0),(-1,-1),3),
            ]))
            els.append(ts)
            els.append(Spacer(1,6))

    # ═══ FONTES ══════════════════════════════════════════════════════
    els += secao("FONTES CONSULTADAS — FRAMEWORK P.I.L.D.E.R™")

    STATUS_LABEL = {
        "confirmacao":"✓ CONFIRMADO","ausencia":"○ SEM OCORRÊNCIA",
        "indicio":"⚡ INDÍCIO","pendente":"⏳ PENDENTE",
        "nao_consultado":"— NÃO CONSULTADO","erro":"✗ ERRO",
    }
    STATUS_COLOR_MAP = {
        "confirmacao":GRN,"ausencia":GRN,"indicio":YEL,
        "pendente":MUTED,"nao_consultado":MUTED,"erro":RED,
    }

    fonte_rows = [["#","Fonte","Status","Pts","Resumo"]]
    for i, f in enumerate(resultado.get("fontes",[])):
        status = f.get("status","")
        pts = f.get("pontos",0)
        cor = STATUS_COLOR_MAP.get(status, MUTED)
        fonte_rows.append([
            Paragraph(str(i+1), ps("fn", alignment=TA_CENTER, fontSize=7)),
            Paragraph(f.get("fonte",""), ps("ff", fontSize=7)),
            Paragraph(STATUS_LABEL.get(status, status), ps("fs", fontSize=7, textColor=cor, fontName="Helvetica-Bold")),
            Paragraph(f"{'+' if pts>0 else ''}{pts}", ps("fp", fontSize=7, alignment=TA_RIGHT,
                textColor=GRN if pts>0 else RED if pts<0 else MUTED, fontName="Helvetica-Bold")),
            Paragraph(f.get("resumo","")[:100], ps("fr2", fontSize=7, textColor=MUTED)),
        ])

    tf2 = Table(fonte_rows, colWidths=[0.8*cm, 5*cm, 3*cm, 1*cm, W-9.8*cm])
    tf2.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),NAVY),
        ("TEXTCOLOR",(0,0),(-1,0),WHITE),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("GRID",(0,0),(-1,-1),0.3,BORD),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
        ("PADDING",(0,0),(-1,-1),3),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(3,0),(3,-1),"RIGHT"),
        ("ALIGN",(0,0),(0,-1),"CENTER"),
    ]))
    els.append(tf2)

    # ═══ RODAPÉ ══════════════════════════════════════════════════════
    els.append(Spacer(1,10))
    els.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    els.append(Paragraph(
        f"{ASSINATURA} | {dt.datetime.now().strftime('%d/%m/%Y %H:%M')} | CONFIDENCIAL",
        ps("rod", fontName="Helvetica-Bold", fontSize=7, textColor=NAVY, alignment=TA_CENTER)
    ))

    doc.build(els)
    return buf.getvalue()



def gerar_pdf_bytes(resultado: dict) -> bytes:
    """Wrapper — usa gerar_pdf_executivo (estilo Disdal com ano do balanço)."""
    return gerar_pdf_executivo(resultado)

# ROTAS
# ══════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"status":"ok","app":ASSINATURA,"version":"5.0.0"}

@app.get("/debug-env")
def debug_env():
    """Diagnóstico temporário — remover após resolver."""
    key = PORTAL_KEY or ""
    return {
        "portal_key_length": len(key),
        "portal_key_start": key[:4] if key else "VAZIO",
        "portal_key_end": key[-4:] if len(key) > 4 else "CURTO",
        "portal_key_has_spaces": " " in key,
        "worker_url": WORKER_URL[:30] if WORKER_URL else "VAZIO",
    }

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

        texto_cnd = nome_cnd = ""
        texto_crf = nome_crf = ""

        texto_cnd = nome_cnd = texto_crf = nome_crf = ""

        # Pega UF da Receita para chamar o worker correto
        rec_tmp = consultar_receita(limpar_cnpj(cnpj))
        uf_empresa = rec_tmp.get("uf", "SP") if rec_tmp else "SP"

        resultado = analisar_cnpj(
            limpar_cnpj(cnpj), texto_bal, nome_bal, texto_cisp, nome_cisp,
            texto_cnd, nome_cnd, texto_crf, nome_crf,
            uf=uf_empresa
        )

        # Gera PDF com os mesmos dados — inclui balanço e CISP
        try:
            pdf_bytes = gerar_pdf_bytes(resultado)
            # Garante encoding ASCII limpo
            b64 = base64.b64encode(pdf_bytes).decode("ascii")
            # Valida o base64 gerado
            base64.b64decode(b64)
            resultado["pdf_base64"] = b64
            resultado["pdf_filename"] = f"PILDER_{limpar_cnpj(cnpj)}.pdf"
        except Exception as pdf_err:
            resultado["pdf_base64"] = None
            resultado["pdf_erro"] = str(pdf_err)[:200]

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

@app.post("/api/pdf-download")
async def pdf_download(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    """Gera PDF e retorna como arquivo para download direto."""
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

        pdf_bytes = gerar_pdf_bytes(resultado)
        filename = f"PILDER_{limpar_cnpj(cnpj)}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes)),
            }
        )
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
