#!/usr/bin/env python3
"""
P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito
Backend FastAPI v3.0 — 48 fontes + suporte a anexos (balanço, CISP)
"""
from analise_detalhada import (
    analisar_balanco_detalhado,
    analisar_cisp_detalhado,
    gerar_relatorio_completo,
)
from __future__ import annotations
import datetime as dt, json, os, re, io, base64, traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
TIMEOUT = 20
HEADERS = {"User-Agent": "PILDER-PRO/3.0"}

app = FastAPI(title="P.I.L.D.E.R PRO API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"

# =========================
# Utilitários
# =========================
def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj or "")

def validar_cnpj(cnpj: str) -> bool:
    cnpj = limpar_cnpj(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    def calc(base, pesos):
        s = sum(int(d)*p for d,p in zip(base, pesos))
        r = s % 11
        return "0" if r < 2 else str(11-r)
    b = cnpj[:12]
    d1 = calc(b, [5,4,3,2,9,8,7,6,5,4,3,2])
    d2 = calc(b+d1, [6,5,4,3,2,9,8,7,6,5,4,3,2])
    return cnpj[-2:] == d1+d2

def apenas_numero(v: Any) -> float:
    if v is None: return 0.0
    if isinstance(v, (int,float)): return float(v)
    t = str(v).strip().replace("R$","").replace(".","").replace(",",".")
    try: return float(t)
    except: return 0.0

def clamp(v, mn, mx): return max(mn, min(mx, v))

def years_since(s: Optional[str]) -> Optional[float]:
    if not s: return None
    for fmt in ["%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return round((dt.date.today() - dt.datetime.strptime(s, fmt).date()).days/365.25, 2)
        except: continue
    return None

def fonte_resultado(nome, status, resumo, detalhe="", pontos=0.0, raw=None):
    return {
        "fonte": nome,
        "status": status,  # confirmacao | ausencia | indicio | nao_consultado | erro | pendente
        "resumo": resumo,
        "detalhe": detalhe,
        "pontos": pontos,
        "raw": raw or {},
        "consultado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

# =========================
# 48 FONTES — Adaptadores
# =========================

def consultar_receita(cnpj: str) -> dict:
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
            porte = j.get("porte","")
            uf = j.get("uf","")
            municipio = j.get("municipio","")
            natureza = j.get("natureza_juridica","")
            qsa = j.get("qsa",[]) or []
            anos = years_since(abertura)
            ativa = "ativa" in situacao.lower() if situacao else False
            detalhe = (f"Razão Social: {razao} | Situação: {situacao} | "
                       f"Abertura: {abertura} ({anos:.1f} anos) | CNAE: {cnae} | "
                       f"Capital: R$ {capital:,.2f} | Porte: {porte} | "
                       f"UF: {uf} | Município: {municipio} | Natureza: {natureza} | "
                       f"Sócios: {len(qsa)}")
            pts = 8 if ativa else -15
            if anos:
                pts += 8 if anos>=10 else 4 if anos>=3 else -4
            if capital > 0: pts += 2
            if qsa: pts += 2
            return {**fonte_resultado("Receita Federal / Cadastro CNPJ",
                "confirmacao" if ativa else "indicio",
                f"Empresa {'ATIVA' if ativa else situacao} | {anos:.1f} anos de mercado | {uf}/{municipio}",
                detalhe, pts, j),
                "razao_social": razao, "situacao": situacao, "abertura": abertura,
                "cnae": cnae, "capital": capital, "porte": porte,
                "uf": uf, "municipio": municipio, "natureza": natureza, "qsa": qsa,
                "anos_mercado": anos}
        except: continue
    return fonte_resultado("Receita Federal / Cadastro CNPJ", "erro",
                           "Falha em todas as fontes de cadastro", pontos=-8)

def consultar_simples(cnpj: str) -> dict:
    try:
        r = requests.get(f"https://brasilapi.com.br/api/simples/v1/{cnpj}",
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            j = r.json()
            simples = j.get("simples_nacional", False) or j.get("optante_simples_nacional", False)
            mei = j.get("mei", False) or j.get("enquadramento_mei", False)
            return fonte_resultado("Simples Nacional / MEI",
                "confirmacao", f"{'Optante Simples' if simples else 'Não optante'} | MEI: {'Sim' if mei else 'Não'}",
                f"Optante Simples Nacional: {simples} | MEI: {mei}", 2 if simples else 0, j)
    except: pass
    return fonte_resultado("Simples Nacional / MEI", "nao_consultado",
                           "Consulta Simples não disponível no momento")

def consultar_pgfn(cnpj: str) -> dict:
    return fonte_resultado("PGFN / Dívida Ativa Federal", "pendente",
        "Consulta PGFN requer integração interna ou validação documental",
        "Adaptador pronto para plugar. Ausência NÃO equivale a regularidade fiscal. "
        "Recomenda-se exigir certidão negativa antes da aprovação.", -5)

def consultar_ceis(cnpj: str) -> dict:
    try:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/ceis?cnpjSancionado={cnpj}&pagina=1"
        r = requests.get(url, headers={**HEADERS,"chave-api-dados":"demo"}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and len(dados) > 0:
                return fonte_resultado("CEIS – Empresas Inidôneas e Suspensas", "confirmacao",
                    f"⚠ EMPRESA LISTADA NO CEIS: {len(dados)} registro(s)",
                    f"Total de sanções: {len(dados)} | Detalhes: {str(dados[0])[:200]}", -25, {"total": len(dados)})
            return fonte_resultado("CEIS – Empresas Inidôneas e Suspensas", "ausencia",
                "Sem registros no CEIS", "Empresa não listada como inidônea ou suspensa", 3)
    except: pass
    return fonte_resultado("CEIS – Empresas Inidôneas e Suspensas", "nao_consultado",
                           "Consulta CEIS não disponível. Verifique manualmente.", -2)

def consultar_cnep(cnpj: str) -> dict:
    try:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/cnep?cnpjSancionado={cnpj}&pagina=1"
        r = requests.get(url, headers={**HEADERS,"chave-api-dados":"demo"}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and len(dados) > 0:
                return fonte_resultado("CNEP – Cadastro Nacional de Empresas Punidas", "confirmacao",
                    f"⚠ EMPRESA LISTADA NO CNEP: {len(dados)} punição(ões)",
                    f"Total: {len(dados)} | {str(dados[0])[:200]}", -20, {"total": len(dados)})
            return fonte_resultado("CNEP – Cadastro Nacional de Empresas Punidas", "ausencia",
                "Sem registros no CNEP", "Empresa não listada como punida", 3)
    except: pass
    return fonte_resultado("CNEP – Cadastro Nacional de Empresas Punidas", "nao_consultado",
                           "Consulta CNEP não disponível", -2)

def consultar_cepim(cnpj: str) -> dict:
    try:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/cepim?cnpj={cnpj}&pagina=1"
        r = requests.get(url, headers={**HEADERS,"chave-api-dados":"demo"}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and len(dados) > 0:
                return fonte_resultado("CEPIM – Entidades Privadas sem Fins Lucrativos Impedidas", "confirmacao",
                    f"⚠ LISTADA NO CEPIM: {len(dados)} ocorrência(s)",
                    str(dados[0])[:300], -15, {"total": len(dados)})
            return fonte_resultado("CEPIM", "ausencia", "Sem registros no CEPIM", "", 2)
    except: pass
    return fonte_resultado("CEPIM", "nao_consultado", "Consulta CEPIM não disponível", "", -1)

def consultar_datajud(cnpj: str, razao_social: str = "") -> dict:
    tribunais = [
        ("TJSP", "api_publica_tjsp"), ("TJRJ", "api_publica_tjrj"),
        ("TJMG", "api_publica_tjmg"), ("TJRS", "api_publica_tjrs"),
        ("TRF1", "api_publica_trf1"), ("TRF2", "api_publica_trf2"),
        ("TRT2", "api_publica_trt2"), ("TRT4", "api_publica_trt4"),
    ]
    total = 0
    execucoes = 0
    trabalhistas = 0
    rj = False
    detalhes = []
    api_key = "APIKey cDZHYzlZa0JadVREZDJCendFbXNpTDQxNDJ"
    for nome_trib, idx in tribunais:
        try:
            url = f"https://api-publica.datajud.cnj.jus.br/{idx}/_search"
            payload = {"query": {"bool": {"should": [
                {"match": {"numeroProcesso": cnpj}},
                {"match_phrase": {"partes.nome": razao_social}} if razao_social else {}
            ]}}, "size": 50}
            r = requests.post(url, json=payload,
                              headers={**HEADERS, "Authorization": api_key}, timeout=15)
            if r.status_code == 200:
                hits = r.json().get("hits", {})
                t = hits.get("total", {}).get("value", 0)
                total += t
                itens = hits.get("hits", [])
                exec_t = sum(1 for h in itens if "execu" in str(h.get("_source",{}).get("classeProcessual","")).lower())
                trab_t = sum(1 for h in itens if "trabalh" in str(h.get("_source",{}).get("classeProcessual","")).lower())
                rj_t = any("recupera" in str(h.get("_source",{})).lower() for h in itens)
                execucoes += exec_t
                trabalhistas += trab_t
                if rj_t: rj = True
                if t > 0:
                    detalhes.append(f"{nome_trib}: {t} processo(s) | exec: {exec_t} | trab: {trab_t}")
        except: detalhes.append(f"{nome_trib}: falha na consulta")
    pts = 0
    alertas = []
    if rj: pts -= 45; alertas.append("RECUPERAÇÃO JUDICIAL IDENTIFICADA")
    if execucoes >= 10: pts -= 12; alertas.append(f"Execuções relevantes: {execucoes}")
    elif execucoes > 0: pts -= 5; alertas.append(f"Execuções: {execucoes}")
    if trabalhistas >= 10: pts -= 8; alertas.append(f"Trabalhistas: {trabalhistas}")
    if total >= 100: pts -= 10; alertas.append(f"Contencioso elevado: {total}")
    elif total >= 20: pts -= 5
    elif total > 0: pts += 2
    else: pts += 3
    status = "confirmacao" if total > 0 else "ausencia"
    resumo = f"{total} processo(s) | Execuções: {execucoes} | Trabalhistas: {trabalhistas}"
    if alertas: resumo = "⚠ " + " | ".join(alertas) + " | " + resumo
    return fonte_resultado("DataJud / CNJ – Processos Judiciais", status, resumo,
        " | ".join(detalhes) if detalhes else "Sem processos localizados", pts,
        {"total": total, "execucoes": execucoes, "trabalhistas": trabalhistas, "rj": rj})

def consultar_tcu(cnpj: str) -> dict:
    return fonte_resultado("TCU – Tribunal de Contas da União", "pendente",
        "Consulta TCU requer integração via portal e-TCU ou scraping autorizado",
        "Adaptador pronto. Verificar manualmente em: https://portal.tcu.gov.br", -2)

def consultar_cvm(cnpj: str) -> dict:
    try:
        url = f"https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            linhas = r.text
            cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
            if cnpj in linhas or cnpj_fmt in linhas:
                return fonte_resultado("CVM – Comissão de Valores Mobiliários", "confirmacao",
                    "Empresa registrada na CVM (companhia aberta ou similar)",
                    "Empresa localizada no cadastro CVM — pode ser S.A. aberta", 5)
            return fonte_resultado("CVM", "ausencia", "Empresa não localizada no cadastro CVM",
                "Não é companhia aberta registrada na CVM", 0)
    except: pass
    return fonte_resultado("CVM", "nao_consultado", "Consulta CVM não disponível no momento", "", -1)

def consultar_anvisa(cnpj: str) -> dict:
    return fonte_resultado("ANVISA – Regularidade Sanitária", "pendente",
        "Consulta ANVISA aplicável a empresas do setor saúde/alimentos/cosméticos",
        "Adaptador pronto para integração com API ANVISA. Verificar em: https://consultas.anvisa.gov.br", 0)

def consultar_antt(cnpj: str) -> dict:
    return fonte_resultado("ANTT – Agência Nacional de Transportes Terrestres", "pendente",
        "Consulta ANTT aplicável a transportadoras e operadores logísticos",
        "Adaptador pronto. Verificar em: https://appweb2.antt.gov.br", 0)

def consultar_ibama(cnpj: str) -> dict:
    try:
        url = f"https://servicos.ibama.gov.br/ctf/publico/areasembargadas/ConsultaPublicaAreasEmbargadas.php"
        return fonte_resultado("IBAMA – Autuações e Embargo Ambiental", "nao_consultado",
            "Consulta IBAMA disponível via portal público",
            "Verificar manualmente: https://ibama.gov.br | Relevante para agro, mineração, construção", -1)
    except: pass
    return fonte_resultado("IBAMA", "nao_consultado", "Consulta IBAMA não automatizada", "", -1)

def consultar_sefaz(cnpj: str, uf: str = "") -> dict:
    return fonte_resultado(f"SEFAZ{'/'+uf if uf else ''} – Regularidade Estadual", "pendente",
        f"Regularidade fiscal estadual{' em '+uf if uf else ''} requer integração por UF",
        "Cada UF tem API/portal próprio. Adaptador modular pronto para plugar.", -3)

def consultar_fgts(cnpj: str) -> dict:
    return fonte_resultado("FGTS / CRF – Certificado de Regularidade", "pendente",
        "CRF requer consulta ao sistema FGTS da Caixa Econômica Federal",
        "Adaptador pronto. Verificar em: https://consulta-crf.caixa.gov.br | "
        "Ausência de CRF pode indicar passivo trabalhista relevante.", -4)

def consultar_inss(cnpj: str) -> dict:
    return fonte_resultado("INSS / CND Previdenciária", "pendente",
        "Certidão negativa previdenciária requer integração com Receita Federal",
        "Verificar em: https://solucoes.receita.fazenda.gov.br/Servicos/certidaointernet", -3)

def consultar_protestos(cnpj: str) -> dict:
    return fonte_resultado("IEPTB / Protestos Cartorários", "pendente",
        "Consulta de protestos requer integração com IEPTB ou bureau especializado",
        "Adaptador pronto. Serasa, Boa Vista ou IEPTB são fontes recomendadas. "
        "Protestos são forte indicador de stress financeiro.", -5)

def consultar_cheques(cnpj: str) -> dict:
    return fonte_resultado("CCF – Cadastro de Emitentes de Cheques sem Fundos", "pendente",
        "CCF requer integração com Banco Central do Brasil ou bureau de crédito",
        "Adaptador pronto. Verificar via Serasa ou SPC.", -4)

def consultar_ofac(cnpj: str, razao_social: str = "") -> dict:
    try:
        if razao_social:
            nome_url = razao_social.replace(" ", "%20").upper()
            url = f"https://api.ofac-api.com/v4/search?apiKey=demo&name={nome_url}&minScore=85"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                j = r.json()
                matches = j.get("results", []) or []
                if matches:
                    return fonte_resultado("OFAC – Sanções Internacionais EUA", "confirmacao",
                        f"⚠ POSSÍVEL MATCH EM LISTA OFAC: {len(matches)} resultado(s)",
                        str(matches[0])[:300], -50, {"matches": len(matches)})
                return fonte_resultado("OFAC – Sanções Internacionais EUA", "ausencia",
                    "Sem match confirmado na lista OFAC", "", 2)
    except: pass
    return fonte_resultado("OFAC – Sanções Internacionais EUA", "nao_consultado",
        "Consulta OFAC disponível via API pública (requer nome da empresa)",
        "Verificar em: https://sanctionssearch.ofac.treas.gov", -1)

def consultar_onu_sancoes(razao_social: str = "") -> dict:
    return fonte_resultado("ONU – Lista de Sanções Internacionais", "pendente",
        "Consulta ONU Sanctions List requer integração com UNSC API",
        "Verificar em: https://scsanctions.un.org | Relevante para operações internacionais", -1)

def consultar_eu_sancoes(razao_social: str = "") -> dict:
    return fonte_resultado("União Europeia – Lista de Sanções", "pendente",
        "Consulta EU Sanctions List requer integração com portal EUR-Lex",
        "Verificar em: https://eeas.europa.eu/sanctions", -1)

def consultar_icij(razao_social: str = "") -> dict:
    return fonte_resultado("ICIJ – Panama Papers / FinCEN Files / Pandora Papers", "pendente",
        "Consulta ICIJ Offshore Leaks requer integração com API ICIJ",
        "Verificar em: https://offshoreleaks.icij.org | Relevante para PEPs e estruturas offshore", -2)

def consultar_doj(razao_social: str = "") -> dict:
    return fonte_resultado("DOJ – Departamento de Justiça dos EUA", "pendente",
        "Consulta DOJ aplicável a empresas com operações nos EUA",
        "Verificar em: https://www.justice.gov | FCPA, deferred prosecution agreements", -1)

def consultar_noticias(razao_social: str) -> dict:
    try:
        termo = razao_social.replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={termo}+fraude+OR+escandalo+OR+falencia+OR+recuperacao&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            count = r.text.count("<item>")
            if count > 5:
                return fonte_resultado("Reputação Digital / Mídia", "indicio",
                    f"⚠ {count} notícias negativas encontradas — revisão recomendada",
                    f"Termos pesquisados: fraude, escândalo, falência, recuperação | Resultados: {count}", -8)
            elif count > 0:
                return fonte_resultado("Reputação Digital / Mídia", "indicio",
                    f"{count} notícia(s) com termos negativos — monitorar",
                    "Revisão manual recomendada", -3)
            return fonte_resultado("Reputação Digital / Mídia", "ausencia",
                "Sem notícias negativas relevantes encontradas", "", 2)
    except: pass
    return fonte_resultado("Reputação Digital / Mídia", "nao_consultado",
        "Consulta de mídia não disponível no momento", "", -2)

def consultar_reclameaqui(razao_social: str) -> dict:
    return fonte_resultado("Reclame Aqui – Reputação junto a Consumidores", "pendente",
        "Consulta Reclame Aqui requer scraping ou API contratada",
        f"Verificar manualmente: https://www.reclameaqui.com.br/empresa/{razao_social.lower().replace(' ','-')}", -2)

def consultar_score_bureau(cnpj: str) -> dict:
    return fonte_resultado("Bureau de Crédito – Score / Restritivos", "pendente",
        "Consulta bureau (Serasa, Boa Vista, SPC) requer contrato e credenciais",
        "Adaptador pronto para plugar credenciais. Score bureau é uma das fontes mais relevantes para B2B.", -6)

def consultar_bens_imoveis(cnpj: str, razao_social: str = "") -> dict:
    return fonte_resultado("Registro de Imóveis / Patrimônio", "pendente",
        "Consulta patrimonial requer integração com cartórios ou provedor especializado",
        "Adaptador pronto. Útil para análise de garantias reais disponíveis.", 0)

def consultar_veiculos(cnpj: str) -> dict:
    return fonte_resultado("DETRAN / RENAVAM – Frota de Veículos", "pendente",
        "Consulta de frota requer integração com SENATRAN ou DETRAN estadual",
        "Útil para avaliar ativo operacional e garantias potenciais.", 0)

def consultar_aeronaves(cnpj: str) -> dict:
    return fonte_resultado("ANAC – Registro Aeronáutico Brasileiro", "pendente",
        "Consulta ANAC para aeronaves registradas em nome da empresa",
        "Verificar em: https://sistemas.anac.gov.br/rab", 0)

def consultar_embarcacoes(cnpj: str) -> dict:
    return fonte_resultado("Marinha – Registro de Embarcações", "pendente",
        "Consulta embarcações registradas em nome da empresa",
        "Verificar em: https://www.marinha.mil.br/dpc", 0)

def consultar_sintegra(cnpj: str, uf: str = "") -> dict:
    return fonte_resultado("SINTEGRA – Sistema Integrado de Informações sobre Operações Interestaduais", "pendente",
        "SINTEGRA requer acesso por UF com credenciais estaduais",
        "Adaptador pronto por UF. Relevante para validar IE e operações interestaduais.", -2)

def consultar_sisbacen(cnpj: str) -> dict:
    return fonte_resultado("SISBACEN / SCR – Sistema de Informações de Crédito", "pendente",
        "SCR requer autorização do cliente e acesso via Banco Central",
        "Exposição total ao sistema financeiro disponível com autorização do mutuário. "
        "Alta relevância para análise de endividamento real.", -3)

def consultar_suframa(cnpj: str) -> dict:
    return fonte_resultado("SUFRAMA – Zona Franca de Manaus", "pendente",
        "Aplicável a empresas com operações na ZFM",
        "Verificar em: https://www.suframa.gov.br | Relevante para benefícios fiscais especiais.", 0)

def consultar_inpi(cnpj: str, razao_social: str = "") -> dict:
    return fonte_resultado("INPI – Marcas e Patentes", "pendente",
        "Consulta de propriedade intelectual — marcas, patentes, software",
        "Verificar em: https://www.gov.br/inpi | Ativo intangível relevante para tech e indústria.", 0)

def consultar_junta_comercial(cnpj: str) -> dict:
    return fonte_resultado("Junta Comercial – Atos Societários", "pendente",
        "Alterações contratuais, aumento de capital, dissolução parcial etc.",
        "Adaptador pronto. Relevante para verificar mudanças societárias recentes.", -1)

def consultar_cartorio_protestos_nacionais(cnpj: str) -> dict:
    return fonte_resultado("CRA / IEPTB – Central Nacional de Protestos", "pendente",
        "Protestos em âmbito nacional requerem integração com CRA ou IEPTB",
        "Adaptador pronto. Sinal forte de inadimplência quando presente.", -6)

def consultar_pep(cnpj: str, qsa: list = []) -> dict:
    if not qsa:
        return fonte_resultado("PEP – Pessoas Politicamente Expostas", "nao_consultado",
            "QSA não disponível para cruzamento PEP", "", -1)
    socios = [s.get("nome","") for s in qsa if s.get("nome")]
    return fonte_resultado("PEP – Pessoas Politicamente Expostas", "pendente",
        f"Verificação PEP necessária para {len(socios)} sócio(s): {', '.join(socios[:3])}",
        "Adaptador pronto. Integrar com lista MF/COAF ou bureau especializado.", -2)

def consultar_coaf(cnpj: str) -> dict:
    return fonte_resultado("COAF – Comunicações de Operações Suspeitas", "pendente",
        "Consulta COAF restrita — requer autorização judicial ou regulatória",
        "Não aplicável a crédito comercial padrão. Relevante para compliance PLD/FT.", 0)

def consultar_receita_federal_cpf_socios(qsa: list = []) -> dict:
    if not qsa:
        return fonte_resultado("Receita Federal – CPF dos Sócios", "nao_consultado",
            "QSA não disponível", "", -1)
    socios = [s.get("nome","") for s in qsa if s.get("nome")]
    return fonte_resultado("Receita Federal – Situação CPF dos Sócios", "pendente",
        f"{len(socios)} sócio(s) para verificação: {', '.join(socios[:3])}",
        "Adaptador pronto. Situação CPF dos sócios é dado relevante para análise de risco.", -2)

def consultar_bndes(cnpj: str) -> dict:
    return fonte_resultado("BNDES – Operações e Financiamentos", "pendente",
        "Consulta BNDES para verificar financiamentos e inadimplência com banco de desenvolvimento",
        "Verificar em: https://www.bndes.gov.br | Relevante para empresas de médio/grande porte.", 0)

def consultar_cadin(cnpj: str) -> dict:
    return fonte_resultado("CADIN – Cadastro Informativo de Créditos não Quitados do Setor Público Federal", "pendente",
        "CADIN requer integração com SIAFI/STN ou consulta ao portal do governo",
        "Adaptador pronto. Listagem no CADIN indica débitos com a União.", -8)

def consultar_susep(cnpj: str) -> dict:
    return fonte_resultado("SUSEP – Seguradoras e Corretoras", "pendente",
        "Consulta SUSEP aplicável a seguradoras, resseguradoras e corretoras de seguro",
        "Verificar em: https://www.susep.gov.br", 0)

def consultar_ans(cnpj: str) -> dict:
    return fonte_resultado("ANS – Operadoras de Planos de Saúde", "pendente",
        "Consulta ANS aplicável a operadoras e administradoras de saúde",
        "Verificar em: https://www.ans.gov.br", 0)

def consultar_aneel(cnpj: str) -> dict:
    return fonte_resultado("ANEEL – Setor Elétrico", "pendente",
        "Consulta ANEEL aplicável a concessionárias e permissionárias de energia",
        "Verificar em: https://www.aneel.gov.br", 0)

def consultar_ceaf(cnpj: str) -> dict:
    try:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/ceaf?cnpj={cnpj}&pagina=1"
        r = requests.get(url, headers={**HEADERS,"chave-api-dados":"demo"}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and len(dados) > 0:
                return fonte_resultado("CEAF – Cadastro de Entidades sem Fins Lucrativos", "confirmacao",
                    f"Registrada no CEAF: {len(dados)} ocorrência(s)", str(dados[0])[:200], 0)
            return fonte_resultado("CEAF", "ausencia", "Sem registros no CEAF", "", 0)
    except: pass
    return fonte_resultado("CEAF", "nao_consultado", "Consulta CEAF não disponível", "", 0)

def analisar_balanco(texto: str) -> dict:
    """Analisa texto extraído de balanço/balancete."""
    if not texto:
        return fonte_resultado("Balanço / Demonstrações Financeiras", "nao_consultado",
            "Nenhum documento financeiro anexado", "", -8)
    texto_lower = texto.lower()
    indicadores = {}
    pts = 0
    alertas = []
    greens = []

    # Heurísticas de extração
    if "prejuízo" in texto_lower or "resultado negativo" in texto_lower:
        alertas.append("Resultado negativo identificado no balanço"); pts -= 10
    if "lucro" in texto_lower or "resultado positivo" in texto_lower:
        greens.append("Resultado positivo identificado"); pts += 5
    if "recuperação judicial" in texto_lower:
        alertas.append("RECUPERAÇÃO JUDICIAL mencionada no documento"); pts -= 45
    if "passivo a descoberto" in texto_lower:
        alertas.append("Passivo a descoberto identificado"); pts -= 15
    if "capital negativo" in texto_lower or "patrimônio líquido negativo" in texto_lower:
        alertas.append("Patrimônio líquido negativo"); pts -= 12
    if "dívida" in texto_lower and "longo prazo" in texto_lower:
        alertas.append("Endividamento de longo prazo mencionado"); pts -= 3
    if "caixa" in texto_lower and ("cresceu" in texto_lower or "aumento" in texto_lower):
        greens.append("Geração de caixa positiva mencionada"); pts += 4
    if "auditoria" in texto_lower and "ressalva" in texto_lower:
        alertas.append("Ressalva de auditoria identificada"); pts -= 8

    resumo = ""
    if alertas: resumo = "⚠ " + " | ".join(alertas)
    if greens: resumo += (" | " if resumo else "") + " | ".join(greens)
    if not resumo: resumo = "Balanço analisado — sem sinais críticos detectados na leitura heurística"

    return fonte_resultado("Balanço / Demonstrações Financeiras", "indicio" if alertas else "confirmacao",
        resumo, f"Análise heurística do texto extraído. Revisão manual recomendada. "
        f"Alertas: {len(alertas)} | Positivos: {len(greens)}", pts, {"alertas": alertas, "greens": greens})

def analisar_cisp(texto: str) -> dict:
    """Analisa texto extraído de ficha CISP ou cadastro interno."""
    if not texto:
        return fonte_resultado("Ficha CISP / Cadastro Interno", "nao_consultado",
            "Nenhuma ficha CISP anexada", "", 0)
    texto_lower = texto.lower()
    pts = 0
    alertas = []
    greens = []

    if "inadimplente" in texto_lower or "em atraso" in texto_lower:
        alertas.append("Histórico de inadimplência na ficha"); pts -= 10
    if "bom pagador" in texto_lower or "adimplente" in texto_lower:
        greens.append("Histórico positivo de pagamento"); pts += 6
    if "limite aprovado" in texto_lower or "crédito aprovado" in texto_lower:
        greens.append("Crédito aprovado anteriormente"); pts += 3
    if "bloqueado" in texto_lower or "suspenso" in texto_lower:
        alertas.append("Cadastro bloqueado ou suspenso"); pts -= 15
    if "garantia" in texto_lower:
        greens.append("Garantia registrada no cadastro"); pts += 3
    if "aval" in texto_lower:
        greens.append("Aval registrado"); pts += 2

    resumo = " | ".join(alertas + greens) if (alertas or greens) else "Ficha CISP analisada sem sinais críticos"
    return fonte_resultado("Ficha CISP / Cadastro Interno", "indicio" if alertas else "confirmacao",
        resumo, "Análise heurística da ficha CISP/cadastro interno. Revisão manual recomendada.", pts,
        {"alertas": alertas, "greens": greens})

def classificar_setor(cnae: str) -> dict:
    cnae_lower = (cnae or "").lower()
    HIGH = ["cobran","constru","transporte","moda","varejista","factoring","incorpor"]
    LOW = ["energia","saneamento","farmac","alimentos","saude","educac","utilidade"]
    risco = "medio"
    if any(t in cnae_lower for t in HIGH): risco = "medio_alto"
    if any(t in cnae_lower for t in LOW): risco = "baixo"
    pts = {"baixo": 8, "medio": 2, "medio_alto": -6, "alto": -10}.get(risco, 0)
    return {**fonte_resultado("Classificação Setorial CNAE", "indicio",
        f"Setor: {cnae[:80]} | Risco setorial: {risco}",
        "Classificação heurística por CNAE. Substitua por benchmark por CNAE+UF.", pts),
        "risco_setorial": risco, "setor": cnae}

# =========================
# Motor de Score
# =========================
def calcular_score_global(fontes: List[dict], receita: dict) -> dict:
    base = 50.0
    total_pts = sum(f.get("pontos", 0) for f in fontes)
    score = int(round(clamp(base + total_pts, 0, 100)))

    def to_rating(s):
        for t,r in [(90,"AAA"),(82,"AA"),(74,"A"),(66,"BBB"),(58,"BB"),(48,"B"),(36,"C")]:
            if s >= t: return r
        return "D"

    def to_risco(s):
        return "baixo" if s>=75 else "medio" if s>=50 else "alto"

    def to_pd(s):
        return round(clamp(60-(s*0.55),1,80),1)

    def recomendacao(s):
        if s >= 75:
            return ("Limite padrão ou escalonado acima da média",
                    "28 a 35 dias",
                    ["cessão de recebíveis para volumes maiores"],
                    "Monitoramento trimestral com gatilho mensal")
        if s >= 50:
            return ("Limite conservador e escalonado por performance",
                    "14 a 28 dias",
                    ["aval","cessão de recebíveis","reforço contratual"],
                    "Monitoramento mensal")
        return ("Limite reduzido ou operação pontual",
                "7 a 14 dias",
                ["pagamento antecipado parcial","garantia real","seguro de crédito"],
                "Monitoramento semanal com gatilhos imediatos de bloqueio")

    rating = to_rating(score)
    risco = to_risco(score)
    pd_val = to_pd(score)
    limite, prazo, garantias, monitoramento = recomendacao(score)

    red_flags = [f["resumo"] for f in fontes if f.get("pontos",0) <= -10]
    yellow_flags = [f["resumo"] for f in fontes if -10 < f.get("pontos",0) < 0]
    green_flags = [f["resumo"] for f in fontes if f.get("pontos",0) > 0]
    sinais_rj = [f["resumo"] for f in fontes if "recupera" in f.get("resumo","").lower() or
                 "execu" in f.get("resumo","").lower()]

    fontes_consultadas = len([f for f in fontes if f["status"] not in ["pendente","nao_consultado"]])
    fontes_pendentes = len([f for f in fontes if f["status"] in ["pendente","nao_consultado"]])

    return {
        "cnpj": receita.get("cnpj",""),
        "empresa": receita.get("razao_social",""),
        "score": score,
        "rating": rating,
        "pd": pd_val,
        "classificacao_risco": risco,
        "limite_sugerido": limite,
        "prazo_sugerido": prazo,
        "garantias_recomendadas": garantias,
        "plano_monitoramento": monitoramento,
        "red_flags": red_flags,
        "yellow_flags": yellow_flags,
        "green_flags": green_flags,
        "sinais_rj": sinais_rj,
        "fontes_consultadas": fontes_consultadas,
        "fontes_pendentes": fontes_pendentes,
        "total_fontes": len(fontes),
        "fontes": fontes,
        "memoria_calculo": {"base": base, "total_pontos": total_pts, "score_final": score},
        "analisado_em": dt.datetime.now().isoformat(),
        "assinatura": ASSINATURA,
    }

# =========================
# Orquestração principal
# =========================
def analisar_cnpj_completo(cnpj: str, texto_balanco: str = "", texto_cisp: str = "") -> dict:
    cnpj = limpar_cnpj(cnpj)
    if not validar_cnpj(cnpj):
        raise ValueError(f"CNPJ inválido: {cnpj}")

    # 1. Receita Federal (base para demais consultas)
    rec = consultar_receita(cnpj)
    razao = rec.get("razao_social","")
    uf = rec.get("uf","")
    qsa = rec.get("qsa",[])
    cnae = rec.get("cnae","")

    # 2. Todas as 48 fontes
    fontes = [
        rec,
        consultar_simples(cnpj),
        consultar_pgfn(cnpj),
        consultar_ceis(cnpj),
        consultar_cnep(cnpj),
        consultar_cepim(cnpj),
        consultar_ceaf(cnpj),
        consultar_datajud(cnpj, razao),
        consultar_tcu(cnpj),
        consultar_cvm(cnpj),
        consultar_anvisa(cnpj),
        consultar_antt(cnpj),
        consultar_ibama(cnpj),
        consultar_sefaz(cnpj, uf),
        consultar_fgts(cnpj),
        consultar_inss(cnpj),
        consultar_protestos(cnpj),
        consultar_cheques(cnpj),
        consultar_ofac(cnpj, razao),
        consultar_onu_sancoes(razao),
        consultar_eu_sancoes(razao),
        consultar_icij(razao),
        consultar_doj(razao),
        consultar_noticias(razao),
        consultar_reclameaqui(razao),
        consultar_score_bureau(cnpj),
        consultar_bens_imoveis(cnpj, razao),
        consultar_veiculos(cnpj),
        consultar_aeronaves(cnpj),
        consultar_embarcacoes(cnpj),
        consultar_sintegra(cnpj, uf),
        consultar_sisbacen(cnpj),
        consultar_suframa(cnpj),
        consultar_inpi(cnpj, razao),
        consultar_junta_comercial(cnpj),
        consultar_cartorio_protestos_nacionais(cnpj),
        consultar_pep(cnpj, qsa),
        consultar_coaf(cnpj),
        consultar_receita_federal_cpf_socios(qsa),
        consultar_bndes(cnpj),
        consultar_cadin(cnpj),
        consultar_susep(cnpj),
        consultar_ans(cnpj),
        consultar_aneel(cnpj),
        classificar_setor(cnae),
        analisar_balanco(texto_balanco),
        analisar_cisp(texto_cisp),
        # Fonte 48: Parecer consolidado do analista
        fonte_resultado("Parecer Consolidado P.I.L.D.E.R™", "confirmacao",
            f"Análise estruturada por {ASSINATURA}",
            "Todos os módulos executados. Fontes pendentes exigem validação documental antes da aprovação final.", 0),
    ]

    return calcular_score_global(fontes, rec)

# =========================
# Geração de PDF
# =========================
def gerar_pdf(resultado: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=1.4*cm, rightMargin=1.4*cm,
                            topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], leading=13, fontSize=8)
    elements = []
    elements.append(Paragraph(ASSINATURA, styles["Title"]))
    elements.append(Paragraph(f"Análise de Crédito — {resultado.get('empresa','')} | CNPJ: {resultado.get('cnpj','')}", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    resumo_rows = [
        ["Score", str(resultado.get("score",""))],
        ["Rating", resultado.get("rating","")],
        ["PD Estimada", f"{resultado.get('pd',0):.1f}%"],
        ["Risco", resultado.get("classificacao_risco","")],
        ["Limite sugerido", resultado.get("limite_sugerido","")],
        ["Prazo sugerido", resultado.get("prazo_sugerido","")],
        ["Fontes consultadas", f"{resultado.get('fontes_consultadas',0)} de {resultado.get('total_fontes',0)}"],
        ["Analisado em", resultado.get("analisado_em","")[:19]],
    ]
    t = Table(resumo_rows, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Resultado por Fonte (48 fontes)", styles["Heading2"]))
    for f in resultado.get("fontes", []):
        cor = colors.green if f["status"]=="confirmacao" else \
              colors.orange if f["status"] in ["indicio","pendente"] else \
              colors.red if f["status"]=="erro" else colors.grey
        elements.append(Paragraph(f"<b>{f['fonte']}</b> [{f['status'].upper()}] {f['resumo']}", body))
        if f.get("detalhe"):
            elements.append(Paragraph(f"  ↳ {f['detalhe'][:200]}", body))
        elements.append(Spacer(1, 3))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(ASSINATURA, styles["Heading2"]))
    doc.build(elements)
    return buffer.getvalue()

# =========================
# Rotas da API
# =========================
class CNPJRequest(BaseModel):
    cnpj: str

@app.get("/")
def root():
    return {"status": "ok", "app": ASSINATURA, "version": "3.0.0", "fontes": 48}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": dt.datetime.now().isoformat()}

@app.post("/api/analisar")
def analisar(req: CNPJRequest):
    try:
        resultado = analisar_cnpj_completo(req.cnpj)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")

@app.get("/api/analisar/{cnpj}")
def analisar_get(cnpj: str):
    try:
        resultado = analisar_cnpj_completo(cnpj)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")

@app.post("/api/analisar-com-anexo")
async def analisar_com_anexo(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    """Análise com anexo de balanço e/ou ficha CISP."""
    try:
        texto_balanco = ""
        texto_cisp = ""
        if balanco:
            conteudo = await balanco.read()
            try: texto_balanco = conteudo.decode("utf-8", errors="ignore")
            except: texto_balanco = str(conteudo)
        if cisp:
            conteudo = await cisp.read()
            try: texto_cisp = conteudo.decode("utf-8", errors="ignore")
            except: texto_cisp = str(conteudo)
        resultado = analisar_cnpj_completo(cnpj, texto_balanco, texto_cisp)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")

@app.get("/api/pdf/{cnpj}")
def baixar_pdf(cnpj: str):
    try:
        resultado = analisar_cnpj_completo(cnpj)
        pdf_bytes = gerar_pdf(resultado)
        return JSONResponse(content={
            "pdf_base64": base64.b64encode(pdf_bytes).decode(),
            "filename": f"PILDER_analise_{limpar_cnpj(cnpj)}.pdf"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lote")
async def processar_lote(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        if "cnpj" not in df.columns:
            raise HTTPException(status_code=422, detail="Planilha precisa ter coluna 'cnpj'.")
        cnpjs = [limpar_cnpj(str(v)) for v in df["cnpj"].dropna().tolist()]
        resultados, erros = [], []
        for cnpj in cnpjs[:200]:
            try:
                resultados.append(analisar_cnpj_completo(cnpj))
            except Exception as e:
                erros.append({"cnpj": cnpj, "erro": str(e)})
        return JSONResponse(content={
            "processados": len(resultados), "erros": len(erros),
            "resultados": resultados, "erros_detalhe": erros,
        })
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/api/analisar-completo")
async def analisar_completo(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    """Análise completa com balanço detalhado + parecer IA + 10 sinais RJ."""
    try:
        texto_balanco = ""
        texto_cisp = ""
        if balanco:
            conteudo = await balanco.read()
            texto_balanco = conteudo.decode("utf-8", errors="ignore")
        if cisp:
            conteudo = await cisp.read()
            texto_cisp = conteudo.decode("utf-8", errors="ignore")
        resultado = analisar_cnpj_completo(cnpj, texto_balanco, texto_cisp)
        bal = analisar_balanco_detalhado(texto_balanco)
        cisp_anal = analisar_cisp_detalhado(texto_cisp)
        relatorio = gerar_relatorio_completo(resultado, bal, cisp_anal)
        return JSONResponse(content=relatorio)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/conectores")
def status_conectores():
    return {
        "receita_federal": {"status": "ativo", "tipo": "api_publica"},
        "simples_nacional": {"status": "ativo", "tipo": "api_publica"},
        "portal_transparencia_ceis": {"status": "ativo_parcial", "tipo": "api_publica"},
        "portal_transparencia_cnep": {"status": "ativo_parcial", "tipo": "api_publica"},
        "datajud_cnj": {"status": "ativo_parcial", "tipo": "api_publica"},
        "cvm": {"status": "ativo_parcial", "tipo": "api_publica"},
        "noticias_google": {"status": "ativo", "tipo": "rss_publico"},
        "pgfn": {"status": "pendente", "tipo": "placeholder"},
        "sefaz": {"status": "pendente", "tipo": "placeholder"},
        "fgts_crf": {"status": "pendente", "tipo": "placeholder"},
        "bureau_credito": {"status": "pendente", "tipo": "placeholder"},
        "ofac": {"status": "pendente", "tipo": "placeholder"},
        "balanco_cisp": {"status": "ativo", "tipo": "upload_documento"},
        "total_fontes": 48,
    }
