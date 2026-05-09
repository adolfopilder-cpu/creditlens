"""
P.I.L.D.E.R™ – Novos Conectores Gratuitos v1.0
1. TST / CNDT — Certidão Negativa de Débitos Trabalhistas
2. OpenSanctions — OFAC + ONU + EU + PEP em uma API
3. PGFN Lista de Devedores — endpoint público
4. Receita Federal CND — certidão via SERPRO ConectaGov
"""
from __future__ import annotations
import re
import json
import datetime as dt
import urllib.request
import urllib.parse
from typing import Optional

HEADERS_BASE = {
    "User-Agent": "PILDER-PRO/3.0",
    "Accept": "application/json",
}
TIMEOUT = 20
ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"


def fonte_resultado(nome, status, resumo, detalhe="", pontos=0.0, raw=None):
    return {
        "fonte": nome, "status": status, "resumo": resumo,
        "detalhe": detalhe, "pontos": pontos, "raw": raw or {},
        "consultado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


# =============================================================================
# 1. TST / CNDT — Certidão Negativa de Débitos Trabalhistas
# =============================================================================
def consultar_cndt_tst(cnpj: str, razao_social: str = "") -> dict:
    """
    Consulta CNDT via DataJud CNJ (endpoint TST público).
    Verifica processos trabalhistas e execuções no TST.
    """
    api_key = "APIKey cDZHYzlZa0JadVREZDJCendFbXNpTDQxNDJ"

    # Tenta DataJud TST
    try:
        url = "https://api-publica.datajud.cnj.jus.br/api_publica_tst/_search"
        should = [{"match": {"numeroProcesso": cnpj}}]
        if razao_social:
            should.append({"match_phrase": {"partes.nome": razao_social}})

        payload = json.dumps({
            "query": {"bool": {"should": should}},
            "size": 50
        }).encode()

        req = urllib.request.Request(
            url, data=payload,
            headers={**HEADERS_BASE,
                     "Content-Type": "application/json",
                     "Authorization": api_key}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
            hits = data.get("hits", {})
            total = hits.get("total", {}).get("value", 0)
            itens = hits.get("hits", [])

            execucoes = sum(
                1 for h in itens
                if any(t in str(h.get("_source", {}).get("classeProcessual", "")).lower()
                       for t in ["execu", "cumprimento"])
            )
            recursos = sum(
                1 for h in itens
                if "recurso" in str(h.get("_source", {}).get("classeProcessual", "")).lower()
            )

            pts = 0
            if execucoes >= 5:
                pts = -12
                status = "confirmacao"
                resumo = f"⚠ {execucoes} execução(ões) trabalhista(s) no TST | Total: {total}"
            elif total > 0:
                pts = -5
                status = "indicio"
                resumo = f"{total} processo(s) no TST | Execuções: {execucoes} | Recursos: {recursos}"
            else:
                pts = 3
                status = "ausencia"
                resumo = "Sem processos localizados no TST"

            return fonte_resultado(
                "TST / CNDT — Débitos Trabalhistas", status, resumo,
                f"Total TST: {total} | Execuções: {execucoes} | Recursos: {recursos}",
                pts, {"total": total, "execucoes": execucoes, "recursos": recursos}
            )

    except Exception as e:
        pass

    # Fallback: tenta endpoint CNDT direto
    try:
        cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
        url2 = f"https://cndt.tst.jus.br/CNDT/consultaEmpresaNova.do?parametros={urllib.parse.quote(cnpj_fmt)}"
        req2 = urllib.request.Request(url2, headers=HEADERS_BASE)
        with urllib.request.urlopen(req2, timeout=TIMEOUT) as r:
            content = r.read().decode("utf-8", errors="ignore")
            if "negativa" in content.lower() or "nada consta" in content.lower():
                return fonte_resultado(
                    "TST / CNDT — Débitos Trabalhistas", "confirmacao",
                    "CNDT Negativa — sem débitos trabalhistas confirmados",
                    "Certidão negativa emitida pelo portal TST", 5
                )
            elif "positiva" in content.lower() or "débito" in content.lower():
                return fonte_resultado(
                    "TST / CNDT — Débitos Trabalhistas", "confirmacao",
                    "⚠ CNDT Positiva — débitos trabalhistas identificados",
                    "Certidão positiva — verificar valor e situação", -15
                )
    except Exception:
        pass

    return fonte_resultado(
        "TST / CNDT — Débitos Trabalhistas", "pendente",
        "Consulta CNDT disponível em cndt.tst.jus.br — verificar manualmente",
        "Adaptador pronto. Emitir CNDT em: https://cndt.tst.jus.br | "
        "Obrigações trabalhistas no passivo devem ser conciliadas.", -3
    )


# =============================================================================
# 2. OpenSanctions — OFAC + ONU + EU + PEP + Listas internacionais
# =============================================================================
def consultar_opensanctions(razao_social: str, cnpj: str = "") -> dict:
    """
    Consulta OpenSanctions — cobre OFAC, ONU, EU, PEP e 100+ listas.
    Gratuito para uso não-comercial. Requer chave para uso intensivo.
    API: https://api.opensanctions.org
    """
    if not razao_social or len(razao_social.strip()) < 3:
        return fonte_resultado(
            "OpenSanctions — Sanções Internacionais (OFAC/ONU/EU/PEP)",
            "nao_consultado",
            "Razão social não disponível para consulta",
            "", -1
        )

    # Endpoint de busca por nome (sem chave, limitado mas funcional)
    try:
        nome_clean = razao_social.strip().upper()
        # Remove sufixos comuns que reduzem precisão
        for sufixo in [" LTDA", " S.A.", " S/A", " EIRELI", " ME", " EPP", " SA"]:
            nome_clean = nome_clean.replace(sufixo, "")
        nome_clean = nome_clean.strip()

        params = urllib.parse.urlencode({
            "q": nome_clean,
            "limit": 10,
            "schema": "Company",
            "datasets": "sanctions,pep,crime",
        })
        url = f"https://api.opensanctions.org/entities/?{params}"

        req = urllib.request.Request(url, headers={
            **HEADERS_BASE,
            "Referer": "https://www.opensanctions.org/",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
            results = data.get("results", [])
            total = data.get("total", {}).get("value", 0) if isinstance(data.get("total"), dict) else data.get("total", 0)

            if not results or total == 0:
                return fonte_resultado(
                    "OpenSanctions — Sanções Internacionais (OFAC/ONU/EU/PEP)",
                    "ausencia",
                    f"Sem match em listas de sanções internacionais para '{nome_clean}'",
                    "Consultadas: OFAC, ONU, EU, PEP e 100+ listas globais", 3
                )

            # Analisa os matches
            matches_fortes = []
            datasets_encontrados = set()
            for res in results:
                props = res.get("properties", {})
                datasets = res.get("datasets", [])
                datasets_encontrados.update(datasets)
                nome_match = props.get("name", [""])[0] if props.get("name") else ""
                # Verifica similaridade básica
                if any(part in nome_match.upper() for part in nome_clean.split()[:2]):
                    matches_fortes.append({
                        "nome": nome_match,
                        "datasets": datasets,
                        "id": res.get("id", ""),
                    })

            if matches_fortes:
                listas = ", ".join(sorted(datasets_encontrados)[:5])
                return fonte_resultado(
                    "OpenSanctions — Sanções Internacionais (OFAC/ONU/EU/PEP)",
                    "confirmacao",
                    f"⚠ {len(matches_fortes)} MATCH(ES) EM LISTAS DE SANÇÕES: {listas}",
                    f"Matches: {[m['nome'] for m in matches_fortes[:3]]} | "
                    f"Listas: {listas} | Verificação manual obrigatória antes de qualquer operação",
                    -50,
                    {"matches": matches_fortes, "datasets": list(datasets_encontrados)}
                )
            else:
                return fonte_resultado(
                    "OpenSanctions — Sanções Internacionais (OFAC/ONU/EU/PEP)",
                    "ausencia",
                    f"Sem match confirmado em listas de sanções ({total} resultado(s) sem similaridade suficiente)",
                    "Consultadas: OFAC, ONU, EU Sanctions, PEP globais", 2
                )

    except urllib.error.HTTPError as e:
        if e.code == 429:
            return fonte_resultado(
                "OpenSanctions — Sanções Internacionais (OFAC/ONU/EU/PEP)",
                "nao_consultado",
                "Limite de requisições atingido — configure chave API em opensanctions.org",
                "Plano gratuito: 100 req/dia. Para carteira maior, assinar plano pago.", -2
            )
        return fonte_resultado(
            "OpenSanctions — Sanções Internacionais (OFAC/ONU/EU/PEP)",
            "nao_consultado",
            f"Erro HTTP {e.code} na consulta OpenSanctions",
            "Verificar manualmente em: https://www.opensanctions.org/search/", -2
        )
    except Exception as e:
        return fonte_resultado(
            "OpenSanctions — Sanções Internacionais (OFAC/ONU/EU/PEP)",
            "nao_consultado",
            "Consulta OpenSanctions indisponível no momento",
            f"Erro: {str(e)[:100]} | Verificar em: https://www.opensanctions.org/search/", -1
        )


def consultar_pep_opensanctions(qsa: list, cnpj: str = "") -> dict:
    """
    Verifica sócios (QSA) em listas de PEP via OpenSanctions.
    """
    if not qsa:
        return fonte_resultado(
            "OpenSanctions PEP — Pessoas Politicamente Expostas",
            "nao_consultado",
            "QSA não disponível para cruzamento PEP", "", -1
        )

    socios = [s.get("nome", "") for s in qsa if s.get("nome")]
    if not socios:
        return fonte_resultado(
            "OpenSanctions PEP — Pessoas Politicamente Expostas",
            "nao_consultado",
            "Nomes dos sócios não disponíveis", "", -1
        )

    matches_pep = []
    for socio in socios[:5]:  # Limita para não estourar rate limit
        try:
            params = urllib.parse.urlencode({
                "q": socio,
                "limit": 5,
                "schema": "Person",
                "datasets": "pep",
            })
            url = f"https://api.opensanctions.org/entities/?{params}"
            req = urllib.request.Request(url, headers=HEADERS_BASE)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                results = data.get("results", [])
                for res in results:
                    props = res.get("properties", {})
                    nome_match = props.get("name", [""])[0] if props.get("name") else ""
                    # Verifica se nome bate
                    partes_socio = socio.upper().split()
                    if len(partes_socio) >= 2 and all(
                        p in nome_match.upper() for p in partes_socio[:2]
                    ):
                        matches_pep.append({
                            "socio": socio,
                            "match": nome_match,
                            "datasets": res.get("datasets", []),
                        })
        except Exception:
            continue

    if matches_pep:
        return fonte_resultado(
            "OpenSanctions PEP — Pessoas Politicamente Expostas",
            "confirmacao",
            f"⚠ {len(matches_pep)} SÓCIO(S) IDENTIFICADO(S) COMO PEP: "
            f"{', '.join(m['socio'] for m in matches_pep)}",
            "Operação com PEP exige diligência reforçada conforme COAF/BACEN. "
            "Documentar base legal e aprovação de compliance.",
            -20,
            {"matches": matches_pep}
        )

    return fonte_resultado(
        "OpenSanctions PEP — Pessoas Politicamente Expostas",
        "ausencia",
        f"{len(socios)} sócio(s) verificado(s) — sem match em lista PEP",
        f"Sócios consultados: {', '.join(socios[:3])}", 3
    )


# =============================================================================
# 3. PGFN Lista de Devedores — endpoint público
# =============================================================================
def consultar_pgfn_lista(cnpj: str) -> dict:
    """
    Consulta a Lista de Devedores da PGFN via endpoint público.
    Tenta 3 estratégias em sequência.
    """

    # Estratégia 1: endpoint interno do portal listadevedores
    try:
        url = f"https://www.listadevedores.pgfn.gov.br/api/v1/contribuinte/{cnpj}"
        req = urllib.request.Request(url, headers={
            **HEADERS_BASE,
            "Referer": "https://www.listadevedores.pgfn.gov.br/",
            "Origin": "https://www.listadevedores.pgfn.gov.br",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
            return _processar_pgfn_response(data, cnpj, "Lista de Devedores PGFN (API)")
    except Exception:
        pass

    # Estratégia 2: Portal da Transparência com chave demo
    try:
        url2 = f"https://api.portaldatransparencia.gov.br/api-de-dados/pgfn?cpfCnpj={cnpj}&pagina=1"
        req2 = urllib.request.Request(url2, headers={
            **HEADERS_BASE,
            "chave-api-dados": "demo",
        })
        with urllib.request.urlopen(req2, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
            if isinstance(data, list) and len(data) > 0:
                total_divida = sum(
                    float(str(item.get("valorConsolidado", 0)).replace(",", "."))
                    for item in data if item.get("valorConsolidado")
                )
                return fonte_resultado(
                    "PGFN / Dívida Ativa Federal",
                    "confirmacao",
                    f"⚠ EMPRESA LISTADA NA PGFN: {len(data)} inscrição(ões) | "
                    f"Valor total: R$ {total_divida:,.2f}",
                    f"Naturezas: {set(item.get('tipoDevedor','') for item in data[:5])}",
                    -25, {"inscricoes": len(data), "valor_total": total_divida}
                )
            elif isinstance(data, list) and len(data) == 0:
                return fonte_resultado(
                    "PGFN / Dívida Ativa Federal", "ausencia",
                    "Sem inscrições na Dívida Ativa Federal (Portal Transparência)",
                    "Consulta via Portal da Transparência — resultado negativo", 4
                )
    except Exception:
        pass

    # Estratégia 3: Dados abertos por UF (download sob demanda — placeholder informativo)
    return fonte_resultado(
        "PGFN / Dívida Ativa Federal", "pendente",
        "Consulta PGFN não automatizada — verificar em listadevedores.pgfn.gov.br",
        "Endpoint público disponível mas bloqueado por CORS/auth no ambiente atual. "
        "Acesse: https://www.listadevedores.pgfn.gov.br e busque pelo CNPJ. "
        "AUSÊNCIA NÃO EQUIVALE A REGULARIDADE — exigir certidão negativa formal.",
        -5
    )


def _processar_pgfn_response(data: dict, cnpj: str, fonte_nome: str) -> dict:
    """Processa resposta da API PGFN."""
    if not data:
        return fonte_resultado(
            f"PGFN / Dívida Ativa Federal ({fonte_nome})",
            "ausencia",
            "Sem registros na Lista de Devedores PGFN",
            "Empresa não localizada como devedora ativa", 4
        )

    # Tenta extrair valor e natureza
    valor = data.get("valorTotalConsolidado") or data.get("valorTotal") or 0
    natureza = data.get("tipoDevedor") or data.get("naturezaDebito") or "não especificada"
    situacao = data.get("situacao") or data.get("descricaoSituacao") or ""

    try:
        valor_f = float(str(valor).replace(",", ".").replace(".", ""))
    except Exception:
        valor_f = 0.0

    if valor_f > 0 or data:
        return fonte_resultado(
            f"PGFN / Dívida Ativa Federal ({fonte_nome})",
            "confirmacao",
            f"⚠ EMPRESA LISTADA NA PGFN | Valor: R$ {valor_f:,.2f} | Natureza: {natureza}",
            f"Situação: {situacao} | Natureza: {natureza} | Valor: R$ {valor_f:,.2f}",
            -25, {"valor": valor_f, "natureza": natureza, "situacao": situacao}
        )

    return fonte_resultado(
        f"PGFN / Dívida Ativa Federal ({fonte_nome})",
        "ausencia",
        "Sem débitos ativos na PGFN", "", 4
    )


# =============================================================================
# 4. Receita Federal CND — via gov.br público
# =============================================================================
def consultar_cnd_receita(cnpj: str) -> dict:
    """
    Tenta consultar situação fiscal via Receita Federal / Regularize.
    Estratégia: leitura do status via API pública disponível.
    """
    # Tenta via BrasilAPI que já retorna situação cadastral
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
        req = urllib.request.Request(url, headers=HEADERS_BASE)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
            situacao = data.get("descricao_situacao_cadastral", "") or ""
            ativa = "ativa" in situacao.lower()

            if not ativa and situacao:
                return fonte_resultado(
                    "CND / Regularidade Fiscal Federal", "indicio",
                    f"⚠ Situação cadastral irregular: {situacao} — risco de irregularidade fiscal",
                    "Empresa com situação cadastral não-ativa pode ter restrições fiscais", -10
                )
            return fonte_resultado(
                "CND / Regularidade Fiscal Federal", "indicio",
                "Situação cadastral ativa — CND formal requer emissão via gov.br",
                "Acesse: https://solucoes.receita.fazenda.gov.br/Servicos/certidaointernet "
                "para emitir CND válida. Situação cadastral ativa é condição necessária mas não suficiente.",
                0
            )
    except Exception as e:
        return fonte_resultado(
            "CND / Regularidade Fiscal Federal", "pendente",
            "CND requer emissão formal em: solucoes.receita.fazenda.gov.br",
            "Exigir certidão negativa antes da aprovação para operações relevantes.", -3
        )


# =============================================================================
# EXPORTAÇÃO — lista de todos os novos conectores
# =============================================================================
NOVOS_CONECTORES = {
    "cndt_tst": consultar_cndt_tst,
    "opensanctions": consultar_opensanctions,
    "opensanctions_pep": consultar_pep_opensanctions,
    "pgfn_lista": consultar_pgfn_lista,
    "cnd_receita": consultar_cnd_receita,
}


def status_novos_conectores() -> dict:
    return {
        "cndt_tst": {
            "nome": "TST / CNDT — Certidão Débitos Trabalhistas",
            "status": "ativo_parcial",
            "tipo": "api_publica_cnj",
            "url": "https://cndt.tst.jus.br",
            "custo": "gratuito",
        },
        "opensanctions": {
            "nome": "OpenSanctions — OFAC + ONU + EU + PEP (100+ listas)",
            "status": "ativo",
            "tipo": "api_publica",
            "url": "https://api.opensanctions.org",
            "custo": "gratuito até 100 req/dia | pago para volume maior",
        },
        "opensanctions_pep": {
            "nome": "OpenSanctions PEP — Sócios Politicamente Expostos",
            "status": "ativo",
            "tipo": "api_publica",
            "url": "https://api.opensanctions.org",
            "custo": "gratuito até 100 req/dia",
        },
        "pgfn_lista": {
            "nome": "PGFN / Lista de Devedores",
            "status": "ativo_parcial",
            "tipo": "api_publica",
            "url": "https://www.listadevedores.pgfn.gov.br",
            "custo": "gratuito",
        },
        "cnd_receita": {
            "nome": "CND / Regularidade Fiscal Federal",
            "status": "indicio",
            "tipo": "api_publica_indireta",
            "url": "https://solucoes.receita.fazenda.gov.br",
            "custo": "gratuito",
        },
    }
