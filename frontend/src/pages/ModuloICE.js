import { useState, useRef } from "react";
export default function ModuloICE() {

// ─── Utilitários ────────────────────────────────────────────────────────────

function formatarCNPJ(v) {
  const d = v.replace(/\D/g, "").slice(0, 14);
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

function cnpjValido(cnpj) {
  const n = cnpj.replace(/\D/g, "");
  if (n.length !== 14 || /^(\d)\1+$/.test(n)) return false;
  const calc = (s, pesos) =>
    s.split("").reduce((acc, d, i) => acc + parseInt(d) * pesos[i], 0);
  const p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const r1 = calc(n.slice(0, 12), p1) % 11;
  const d1 = r1 < 2 ? 0 : 11 - r1;
  const r2 = calc(n.slice(0, 13), p2) % 11;
  const d2 = r2 < 2 ? 0 : 11 - r2;
  return parseInt(n[12]) === d1 && parseInt(n[13]) === d2;
}

async function buscarBrasilAPI(cnpj) {
  const n = cnpj.replace(/\D/g, "");
  const r = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${n}`);
  if (!r.ok) throw new Error("CNPJ não encontrado ou API indisponível.");
  return r.json();
}

function mapearDados(raw) {
  const fmtCapital = (v) => {
    if (!v) return "—";
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
  };
  const socios = (raw.qsa || []).map((s) => ({
    nome: s.nome_socio || s.nome || "—",
    qualificacao: s.qualificacao_socio || s.qualificacao || "—",
    documento_mascarado: s.cpf_representante_legal || "***",
  }));
  return {
    gerado_em: new Date().toLocaleString("pt-BR"),
    resumo: {
      empresa: raw.razao_social || "—",
      cnpj: raw.cnpj || "—",
      situacao_cadastral: raw.descricao_situacao_cadastral || "—",
      tipo_estabelecimento: raw.descricao_identificador_matriz_filial || "—",
      municipio: raw.municipio || "—",
      uf: raw.uf || "—",
    },
    cadastro: {
      tipo_estabelecimento: raw.descricao_identificador_matriz_filial || "—",
      cnae_principal: raw.cnae_fiscal_descricao
        ? `${raw.cnae_fiscal} – ${raw.cnae_fiscal_descricao}`
        : raw.cnae_fiscal || "—",
      data_inicio_atividade: raw.data_inicio_atividade || "—",
      capital_social: fmtCapital(raw.capital_social),
      porte: raw.porte || "—",
      natureza_juridica: raw.descricao_natureza_juridica || raw.natureza_juridica || "—",
      nome_fantasia: raw.nome_fantasia || "—",
      email: raw.email || "—",
      telefone: raw.ddd_telefone_1
        ? `(${raw.ddd_telefone_1}) ${raw.telefone_1 || ""}`
        : "—",
      logradouro: raw.logradouro
        ? `${raw.logradouro}, ${raw.numero || "s/n"} – ${raw.bairro || ""}`
        : "—",
      cep: raw.cep || "—",
      cnaes_secundarios: (raw.cnaes_secundarios || [])
        .slice(0, 5)
        .map((c) => `${c.codigo} – ${c.descricao}`)
        .join("; ") || "—",
    },
    qsa: {
      quantidade_socios: socios.length,
      socios,
    },
    fontes_consultadas: [
      {
        icone: "✔",
        descricao: "Receita Federal / BrasilAPI",
        status: "CONSULTADO",
        resumo: "Dados cadastrais carregados com sucesso",
      },
    ],
  };
}

// ─── Passos de análise ──────────────────────────────────────────────────────

const PASSOS = [
  { id: 1, label: "Consulta BrasilAPI / Receita Federal", icon: "🏛️" },
  { id: 2, label: "Análise situação cadastral", icon: "📋" },
  { id: 3, label: "Verificação quadro societário", icon: "👥" },
  { id: 4, label: "Leitura CNAE e atividade econômica", icon: "🏭" },
  { id: 5, label: "Avaliação capital social e porte", icon: "💰" },
  { id: 6, label: "Mapeamento de risco setorial", icon: "🗺️" },
  { id: 7, label: "Sinalização de red/yellow/green flags", icon: "🚦" },
  { id: 8, label: "Cálculo de score e rating", icon: "📊" },
  { id: 9, label: "Geração de recomendação executiva", icon: "⚖️" },
  { id: 10, label: "Montagem do dashboard de crédito", icon: "📄" },
];

// ─── Prompt para o Claude ────────────────────────────────────────────────────

function montarPrompt(dados) {
  return `Você é um analista sênior de crédito corporativo brasileiro especializado em avaliação de risco de PMEs.

Com base nos dados cadastrais abaixo, execute uma análise executiva completa e retorne SOMENTE um objeto JSON válido (sem markdown, sem explicações externas).

DADOS CADASTRAIS:
${JSON.stringify(dados, null, 2)}

Retorne EXATAMENTE este JSON preenchido (sem nenhum texto antes ou depois):

{
  "gerado_em": "${dados.gerado_em}",
  "resumo": {
    "empresa": "${dados.resumo.empresa}",
    "cnpj": "${dados.resumo.cnpj}",
    "score": <número inteiro 0-100>,
    "rating": "<AAA|AA|A|BBB|BB|B|CCC|D>",
    "risco": "<BAIXO|MODERADO|ALTO|CRÍTICO>",
    "pd_estimado": "<percentual ex: 12%>",
    "status": "<APROVADO|RESTRITO>",
    "tipo_estabelecimento": "${dados.resumo.tipo_estabelecimento}",
    "situacao_cadastral": "${dados.resumo.situacao_cadastral}",
    "municipio": "${dados.resumo.municipio}",
    "uf": "${dados.resumo.uf}"
  },
  "cadastro": {
    "tipo_estabelecimento": "${dados.cadastro.tipo_estabelecimento}",
    "cnae_principal": "${dados.cadastro.cnae_principal}",
    "data_inicio_atividade": "${dados.cadastro.data_inicio_atividade}",
    "capital_social": "${dados.cadastro.capital_social}",
    "porte": "${dados.cadastro.porte}",
    "natureza_juridica": "${dados.cadastro.natureza_juridica}"
  },
  "mapa_risco": {
    "financeiro": "<Baixo|Médio|Alto>",
    "juridico": "<Baixo|Médio|Alto>",
    "operacional": "<Baixo|Médio|Alto>",
    "comportamental": "<Baixo|Médio|Alto>"
  },
  "flags": {
    "red_flags": ["<lista de alertas críticos ou array vazio>"],
    "yellow_flags": ["<lista de pontos de atenção ou array vazio>"],
    "green_flags": ["<lista de pontos positivos ou array vazio>"]
  },
  "qsa": {
    "quantidade_socios": ${dados.qsa.quantidade_socios},
    "socios": ${JSON.stringify(dados.qsa.socios)}
  },
  "fontes_consultadas": [
    { "icone": "✔", "descricao": "Receita Federal / BrasilAPI", "status": "CONSULTADO", "resumo": "Dados cadastrais carregados com sucesso" },
    { "icone": "⏳", "descricao": "PGFN / Dívida Ativa", "status": "A PREENCHER", "resumo": "" },
    { "icone": "⏳", "descricao": "Protestos (Cartório)", "status": "A PREENCHER", "resumo": "" },
    { "icone": "⏳", "descricao": "Serasa / SPC", "status": "A PREENCHER", "resumo": "" },
    { "icone": "⏳", "descricao": "Processos Judiciais (TJ)", "status": "A PREENCHER", "resumo": "" },
    { "icone": "⏳", "descricao": "Balanço / DRE", "status": "A PREENCHER", "resumo": "" }
  ],
  "recomendacao": {
    "decisao": "<decisão executiva ex: APROVAR COM MONITORAMENTO>",
    "limite_sugerido": "<ALTO|MÉDIO|BAIXO|CONDICIONAL>",
    "prazo": "<ex: 28-35 dias>",
    "garantias": "<ex: Aval dos sócios e duplicata mercantil>",
    "observacao": "<parágrafo executivo com justificativa da decisão, riscos identificados e pontos de atenção>"
  },
  "monitoramento": {
    "frequencia": "<MENSAL|TRIMESTRAL|SEMESTRAL>",
    "gatilhos": ["<lista de gatilhos de alerta para monitoramento>"]
  }
}

CRITÉRIOS DE ANÁLISE:
- Score: considere situação cadastral (ativa=+30), tempo de atividade (>5 anos=+20, >10 anos=+30), capital social, porte, número de sócios, CNAE (setores de risco têm penalidade)
- Situação ATIVA em MATRIZ com capital alto = menor risco
- FILIAL exige análise complementar da MATRIZ
- CNAEs de risco elevado: construção civil, transporte, comércio varejista de eletrodomésticos
- Gere red_flags reais com base nos dados (ex: filial sem capital, CNAE de risco, empresa jovem < 1 ano)
- Green_flags baseados em pontos positivos reais dos dados
- A observação deve ter ao menos 3 linhas com análise executiva fundamentada`;
}

// ─── Componente principal ────────────────────────────────────────────────────

export default function ModuloICE() {
  const [cnpj, setCnpj] = useState("");
  const [etapa, setEtapa] = useState("idle"); // idle | buscando | analisando | concluido | erro
  const [passoAtual, setPassoAtual] = useState(0);
  const [erro, setErro] = useState("");
  const [dadosBrutos, setDadosBrutos] = useState(null);
  const [jsonFinal, setJsonFinal] = useState(null);
  const timeouts = useRef([]);

  function limpar() {
    timeouts.current.forEach(clearTimeout);
    timeouts.current = [];
    setCnpj("");
    setEtapa("idle");
    setPassoAtual(0);
    setErro("");
    setDadosBrutos(null);
    setJsonFinal(null);
  }

  async function executar() {
    const cnpjLimpo = cnpj.replace(/\D/g, "");
    if (cnpjLimpo.length !== 14) {
      setErro("CNPJ deve ter 14 dígitos.");
      return;
    }
    if (!cnpjValido(cnpj)) {
      setErro("CNPJ inválido. Verifique os dígitos verificadores.");
      return;
    }

    setErro("");
    setJsonFinal(null);
    setPassoAtual(0);
    setEtapa("buscando");

    // Passo 1: BrasilAPI
    let raw;
    try {
      raw = await buscarBrasilAPI(cnpj);
    } catch (e) {
      setErro(e.message || "Falha ao consultar a Receita Federal.");
      setEtapa("erro");
      return;
    }

    const dados = mapearDados(raw);
    setDadosBrutos(dados);
    setEtapa("analisando");

    // Animação de passos (passos 2–9 são simulados enquanto a API responde)
    for (let i = 1; i <= 9; i++) {
      const t = setTimeout(() => setPassoAtual(i), i * 700);
      timeouts.current.push(t);
    }

    // Chamada à API Claude
    let jsonResultado;
    try {
      const resp = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          messages: [{ role: "user", content: montarPrompt(dados) }],
        }),
      });
      const data = await resp.json();
      const texto = (data.content || [])
        .filter((b) => b.type === "text")
        .map((b) => b.text)
        .join("");
      const limpo = texto.replace(/```json|```/g, "").trim();
      jsonResultado = JSON.parse(limpo);
    } catch (e) {
      setErro("Falha na análise com IA. Tente novamente.");
      setEtapa("erro");
      return;
    }

    // Aguarda a animação dos passos terminar
    const tempoRestante = Math.max(0, 9 * 700 - (Date.now() % 10000));
    await new Promise((r) => setTimeout(r, tempoRestante + 500));

    setPassoAtual(10);
    setTimeout(() => {
      setJsonFinal(jsonResultado);
      setEtapa("concluido");
    }, 600);
  }

  function abrirDashboard() {
    if (!jsonFinal) return;
    const json = encodeURIComponent(JSON.stringify(jsonFinal, null, 2));
    // Abre o dashboard HTML de consulta pelo celular em nova aba com o JSON na URL
    // Alternativa: copia para clipboard e instrui o usuário
    navigator.clipboard
      .writeText(JSON.stringify(jsonFinal, null, 2))
      .then(() => alert("JSON copiado! Cole no campo 'JSON completo do dashboard' na tela de consulta."))
      .catch(() => alert("Copie o JSON abaixo e cole no dashboard."));
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <section className="ice-panel">
      {/* Cabeçalho */}
      <div className="ice-header">
        <div>
          <div className="ice-eyebrow">🔍 ICE — Investigação de Crédito Empresarial</div>
          <div className="ice-subtitle">
            Consulta automática à Receita Federal + análise executiva por IA. Gera o JSON pronto
            para o dashboard de crédito.
          </div>
        </div>
        {etapa === "concluido" && (
          <button className="ice-btn-secondary" onClick={limpar}>
            Nova consulta
          </button>
        )}
      </div>

      {/* Formulário de entrada */}
      {(etapa === "idle" || etapa === "erro") && (
        <div className="ice-form">
          <label className="ice-label">CNPJ da empresa</label>
          <div className="ice-input-row">
            <input
              className="ice-input"
              value={cnpj}
              onChange={(e) => setCnpj(formatarCNPJ(e.target.value))}
              onKeyDown={(e) => e.key === "Enter" && executar()}
              placeholder="00.000.000/0000-00"
              maxLength={18}
              inputMode="numeric"
            />
            <button className="ice-btn-primary" onClick={executar}>
              Iniciar análise
            </button>
          </div>
          {erro && <div className="ice-error">{erro}</div>}
          <div className="ice-hint">
            Digite o CNPJ e pressione Enter ou clique em "Iniciar análise". Os dados são
            consultados diretamente na Receita Federal via BrasilAPI (gratuito, sem login).
          </div>
        </div>
      )}

      {/* Progresso animado */}
      {(etapa === "buscando" || etapa === "analisando") && (
        <div className="ice-progress">
          <div className="ice-progress-title">
            {etapa === "buscando"
              ? "Consultando Receita Federal..."
              : "Analisando dados com IA..."}
          </div>
          <div className="ice-steps">
            {PASSOS.map((p, i) => {
              const concluido = i < passoAtual;
              const ativo = i === passoAtual;
              return (
                <div
                  key={p.id}
                  className={`ice-step ${concluido ? "done" : ativo ? "active" : "pending"}`}
                >
                  <div className="ice-step-icon">
                    {concluido ? "✓" : ativo ? <span className="ice-spinner" /> : p.icon}
                  </div>
                  <div className="ice-step-label">{p.label}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Resultado */}
      {etapa === "concluido" && jsonFinal && (
        <ResultadoICE dados={jsonFinal} onCopiar={abrirDashboard} />
      )}
    </section>
  );
}

// ─── Componente de resultado ─────────────────────────────────────────────────

function ResultadoICE({ dados, onCopiar }) {
  const [jsonAberto, setJsonAberto] = useState(false);
  const r = dados.resumo || {};
  const score = Math.max(0, Math.min(100, Number(r.score || 0)));

  const corRisco = {
    BAIXO: "#07894f",
    MODERADO: "#f4b400",
    ALTO: "#f07500",
    CRÍTICO: "#db4437",
  }[r.risco] || "#6c7a89";

  const corStatus = r.status === "APROVADO" ? "#07894f" : "#db4437";

  return (
    <div className="ice-result">
      {/* Hero do resultado */}
      <div className="ice-result-hero">
        <div>
          <div className="ice-result-empresa">{r.empresa}</div>
          <div className="ice-result-cnpj">CNPJ: {r.cnpj}</div>
          <div className="ice-result-meta">
            {r.municipio}/{r.uf} · {r.tipo_estabelecimento} · {r.situacao_cadastral}
          </div>
        </div>
        <div className="ice-result-badges">
          <div className="ice-badge" style={{ background: corRisco, color: "#fff" }}>
            {r.risco}
          </div>
          <div className="ice-badge" style={{ background: corStatus, color: "#fff" }}>
            {r.status}
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="ice-kpis">
        <div className="ice-kpi">
          <div className="ice-kpi-label">Score</div>
          <div className="ice-kpi-value">{score}</div>
          <div className="ice-scorebar">
            <div
              className="ice-scorefill"
              style={{ width: `${score}%` }}
            />
          </div>
        </div>
        <div className="ice-kpi">
          <div className="ice-kpi-label">Rating</div>
          <div className="ice-kpi-value">{r.rating || "—"}</div>
        </div>
        <div className="ice-kpi">
          <div className="ice-kpi-label">PD Estimada</div>
          <div className="ice-kpi-value">{r.pd_estimado || "—"}</div>
        </div>
        <div className="ice-kpi">
          <div className="ice-kpi-label">Prazo sugerido</div>
          <div className="ice-kpi-value" style={{ fontSize: "16px" }}>
            {dados.recomendacao?.prazo || "—"}
          </div>
        </div>
      </div>

      {/* Mapa de risco */}
      <div className="ice-section-title">Mapa de Risco</div>
      <div className="ice-mapa">
        {Object.entries(dados.mapa_risco || {}).map(([k, v]) => (
          <div
            key={k}
            className="ice-mapa-item"
            style={{
              borderColor:
                v === "Alto" ? "#db4437" : v === "Médio" ? "#f4b400" : "#07894f",
            }}
          >
            <div className="ice-mapa-dim">{k.charAt(0).toUpperCase() + k.slice(1)}</div>
            <div
              className="ice-mapa-val"
              style={{
                color: v === "Alto" ? "#db4437" : v === "Médio" ? "#b26b00" : "#07894f",
              }}
            >
              {v}
            </div>
          </div>
        ))}
      </div>

      {/* Flags */}
      <div className="ice-flags">
        <FlagBox tipo="red" titulo="Red Flags" items={dados.flags?.red_flags} />
        <FlagBox tipo="yellow" titulo="Yellow Flags" items={dados.flags?.yellow_flags} />
        <FlagBox tipo="green" titulo="Green Flags" items={dados.flags?.green_flags} />
      </div>

      {/* Recomendação */}
      <div className="ice-section-title">Recomendação Executiva</div>
      <div className="ice-rec">
        <div className="ice-rec-decisao">{dados.recomendacao?.decisao}</div>
        <div className="ice-rec-obs">{dados.recomendacao?.observacao}</div>
        <div className="ice-rec-grid">
          <div>
            <span className="ice-rec-key">Limite sugerido</span>
            <span className="ice-rec-val">{dados.recomendacao?.limite_sugerido}</span>
          </div>
          <div>
            <span className="ice-rec-key">Garantias</span>
            <span className="ice-rec-val">{dados.recomendacao?.garantias}</span>
          </div>
          <div>
            <span className="ice-rec-key">Monitoramento</span>
            <span className="ice-rec-val">{dados.monitoramento?.frequencia}</span>
          </div>
        </div>
      </div>

      {/* Quadro societário */}
      {dados.qsa?.socios?.length > 0 && (
        <>
          <div className="ice-section-title">
            Quadro Societário ({dados.qsa.quantidade_socios} sócio(s))
          </div>
          <table className="ice-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Qualificação</th>
                <th>Documento</th>
              </tr>
            </thead>
            <tbody>
              {dados.qsa.socios.map((s, i) => (
                <tr key={i}>
                  <td>{s.nome}</td>
                  <td>{s.qualificacao}</td>
                  <td>{s.documento_mascarado}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Fontes consultadas */}
      <div className="ice-section-title">Fontes Consultadas</div>
      <table className="ice-table">
        <thead>
          <tr>
            <th></th>
            <th>Fonte</th>
            <th>Status</th>
            <th>Resultado</th>
          </tr>
        </thead>
        <tbody>
          {(dados.fontes_consultadas || []).map((f, i) => (
            <tr key={i}>
              <td>{f.icone}</td>
              <td>{f.descricao}</td>
              <td>
                <span
                  className="ice-fonte-status"
                  style={{
                    color: f.status === "CONSULTADO" ? "#07894f" : "#6c7a89",
                  }}
                >
                  {f.status}
                </span>
              </td>
              <td style={{ color: "#6c7a89", fontStyle: f.resumo ? "normal" : "italic" }}>
                {f.resumo || "A preencher manualmente"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Gatilhos de monitoramento */}
      {dados.monitoramento?.gatilhos?.length > 0 && (
        <>
          <div className="ice-section-title">Gatilhos de Monitoramento</div>
          <ul className="ice-gatilhos">
            {dados.monitoramento.gatilhos.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </>
      )}

      {/* Ações */}
      <div className="ice-actions">
        <button className="ice-btn-primary" onClick={onCopiar}>
          📋 Copiar JSON para o Dashboard
        </button>
        <button
          className="ice-btn-secondary"
          onClick={() => setJsonAberto(!jsonAberto)}
        >
          {jsonAberto ? "Ocultar JSON" : "Ver JSON completo"}
        </button>
      </div>

      {jsonAberto && (
        <pre className="ice-json-pre">
          {JSON.stringify(dados, null, 2)}
        </pre>
      )}

      <div className="ice-footer-note">
        Análise gerada automaticamente. Fontes marcadas como "A PREENCHER" devem ser
        consultadas manualmente antes da decisão final de crédito.
      </div>
    </div>
  );
}

function FlagBox({ tipo, titulo, items }) {
  const cores = {
    red: { bg: "#fff1f2", border: "#ffd0d5", titulo: "#b4232f", bullet: "#db4437" },
    yellow: { bg: "#fff8e1", border: "#ffe082", titulo: "#7a5600", bullet: "#f4b400" },
    green: { bg: "#e8f5e9", border: "#a5d6a7", titulo: "#1b5e20", bullet: "#0f9d58" },
  }[tipo];

  return (
    <div
      className="ice-flagbox"
      style={{ background: cores.bg, borderColor: cores.border }}
    >
      <div className="ice-flagbox-title" style={{ color: cores.titulo }}>
        {titulo}
      </div>
      {items && items.length > 0 ? (
        <ul className="ice-flagbox-list">
          {items.map((item, i) => (
            <li key={i} style={{ color: "#1b2430" }}>
              <span style={{ color: cores.bullet }}>●</span> {item}
            </li>
          ))}
        </ul>
      ) : (
        <div className="ice-flagbox-empty">Nenhum apontamento.</div>
      )}
    </div>
  );
}


*/
