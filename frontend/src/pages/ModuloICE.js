import { useState } from "react";

function formatarCNPJ(valor) {
  const d = valor.replace(/\D/g, "").slice(0, 14);

  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

function cnpjValido(cnpj) {
  const n = cnpj.replace(/\D/g, "");

  if (n.length !== 14) return false;
  if (/^(\d)\1+$/.test(n)) return false;

  const calc = (base, pesos) =>
    base.split("").reduce((soma, digito, i) => soma + Number(digito) * pesos[i], 0);

  const p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

  const r1 = calc(n.slice(0, 12), p1) % 11;
  const d1 = r1 < 2 ? 0 : 11 - r1;

  const r2 = calc(n.slice(0, 13), p2) % 11;
  const d2 = r2 < 2 ? 0 : 11 - r2;

  return Number(n[12]) === d1 && Number(n[13]) === d2;
}

function calcularScore(dados) {
  let score = 0;
  const flags = {
    red_flags: [],
    yellow_flags: [],
    green_flags: [],
  };

  const situacao = dados.descricao_situacao_cadastral || "";
  const tipo = dados.descricao_identificador_matriz_filial || "";
  const capital = Number(dados.capital_social || 0);
  const abertura = dados.data_inicio_atividade;

  if (situacao.toUpperCase().includes("ATIVA")) {
    score += 30;
    flags.green_flags.push("Situação cadastral ativa na Receita Federal.");
  } else {
    flags.red_flags.push("Empresa não consta como ativa na Receita Federal.");
  }

  if (tipo.toUpperCase().includes("MATRIZ")) {
    score += 10;
    flags.green_flags.push("Estabelecimento matriz identificado.");
  } else {
    flags.yellow_flags.push("Empresa é filial: recomenda-se análise complementar da matriz.");
    score += 4;
  }

  if (capital >= 500000) {
    score += 15;
    flags.green_flags.push("Capital social relevante para análise cadastral.");
  } else if (capital >= 50000) {
    score += 8;
    flags.yellow_flags.push("Capital social intermediário.");
  } else {
    flags.yellow_flags.push("Capital social baixo ou não informado.");
  }

  if (abertura) {
    const ano = Number(String(abertura).slice(0, 4));
    const anos = new Date().getFullYear() - ano;

    if (anos >= 10) {
      score += 25;
      flags.green_flags.push("Empresa com mais de 10 anos de atividade.");
    } else if (anos >= 5) {
      score += 18;
      flags.green_flags.push("Empresa com mais de 5 anos de atividade.");
    } else if (anos >= 1) {
      score += 8;
      flags.yellow_flags.push("Empresa relativamente jovem.");
    } else {
      flags.red_flags.push("Empresa com menos de 1 ano de atividade.");
    }
  }

  const cnae = `${dados.cnae_fiscal || ""} ${dados.cnae_fiscal_descricao || ""}`.toLowerCase();

  if (
    cnae.includes("construção") ||
    cnae.includes("transporte") ||
    cnae.includes("eletrodomést")
  ) {
    score -= 10;
    flags.yellow_flags.push("CNAE exige atenção adicional por risco setorial.");
  } else {
    score += 10;
    flags.green_flags.push("CNAE sem sinal crítico automático neste modelo.");
  }

  score = Math.max(0, Math.min(100, Math.round(score)));

  let rating = "D";
  let risco = "CRÍTICO";
  let status = "RESTRITO";
  let pd = "Acima de 25%";

  if (score >= 85) {
    rating = "AA";
    risco = "BAIXO";
    status = "APROVADO";
    pd = "Até 3%";
  } else if (score >= 70) {
    rating = "A";
    risco = "BAIXO";
    status = "APROVADO";
    pd = "3% a 7%";
  } else if (score >= 55) {
    rating = "BBB";
    risco = "MODERADO";
    status = "APROVADO COM RESTRIÇÕES";
    pd = "7% a 15%";
  } else if (score >= 40) {
    rating = "BB";
    risco = "ALTO";
    status = "RESTRITO";
    pd = "15% a 25%";
  }

  return {
    score,
    rating,
    risco,
    status,
    pd,
    flags,
  };
}

function moeda(valor) {
  const numero = Number(valor || 0);

  if (!numero) return "—";

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(numero);
}

export default function ModuloICE() {
  const [cnpj, setCnpj] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");
  const [resultado, setResultado] = useState(null);

  async function consultar() {
    const limpo = cnpj.replace(/\D/g, "");

    setErro("");
    setResultado(null);

    if (limpo.length !== 14) {
      setErro("Digite um CNPJ com 14 dígitos.");
      return;
    }

    if (!cnpjValido(limpo)) {
      setErro("CNPJ inválido. Confira os dígitos.");
      return;
    }

    setCarregando(true);

    try {
      const resposta = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${limpo}`);

      if (!resposta.ok) {
        throw new Error("CNPJ não encontrado ou BrasilAPI indisponível.");
      }

      const dados = await resposta.json();
      const analise = calcularScore(dados);

      setResultado({
        dados,
        analise,
        gerado_em: new Date().toLocaleString("pt-BR"),
      });
    } catch (e) {
      setErro(e.message || "Erro ao consultar CNPJ.");
    } finally {
      setCarregando(false);
    }
  }

  function copiarJson() {
    if (!resultado) return;

    navigator.clipboard.writeText(JSON.stringify(resultado, null, 2));
    alert("JSON copiado para a área de transferência.");
  }

  return (
    <section className="ice-panel">
      <div className="ice-header">
        <div>
          <div className="ice-eyebrow">🕵️ ICE — Investigação de Crédito Empresarial</div>
          <div className="ice-subtitle">
            Consulta cadastral via BrasilAPI / Receita Federal com leitura inicial de risco pelo método P.I.L.D.E.R™.
          </div>
        </div>
      </div>

      <div className="ice-form">
        <label className="ice-label">CNPJ da empresa</label>

        <div className="ice-input-row">
          <input
            className="ice-input"
            value={cnpj}
            onChange={(e) => setCnpj(formatarCNPJ(e.target.value))}
            placeholder="00.000.000/0000-00"
            maxLength={18}
            inputMode="numeric"
            onKeyDown={(e) => {
              if (e.key === "Enter") consultar();
            }}
          />

          <button className="ice-btn-primary" onClick={consultar} disabled={carregando}>
            {carregando ? "Consultando..." : "Iniciar análise"}
          </button>
        </div>

        {erro && <div className="ice-error">{erro}</div>}

        <div className="ice-hint">
          Esta versão consulta a Receita Federal via BrasilAPI e gera uma análise inicial sem chamada externa de IA.
        </div>
      </div>

      {resultado && (
        <ResultadoICE resultado={resultado} onCopiar={copiarJson} />
      )}
    </section>
  );
}

function ResultadoICE({ resultado, onCopiar }) {
  const { dados, analise, gerado_em } = resultado;

  const socios = dados.qsa || [];

  return (
    <div className="ice-result">
      <div className="ice-result-hero">
        <div>
          <div className="ice-result-empresa">{dados.razao_social || "—"}</div>
          <div className="ice-result-cnpj">CNPJ: {dados.cnpj || "—"}</div>
          <div className="ice-result-meta">
            {dados.municipio || "—"}/{dados.uf || "—"} ·{" "}
            {dados.descricao_identificador_matriz_filial || "—"} ·{" "}
            {dados.descricao_situacao_cadastral || "—"}
          </div>
        </div>

        <div className="ice-result-badges">
          <div className="ice-badge" style={{ background: "#0b62c4", color: "#fff" }}>
            {analise.risco}
          </div>
          <div className="ice-badge" style={{ background: "#07894f", color: "#fff" }}>
            {analise.status}
          </div>
        </div>
      </div>

      <div className="ice-kpis">
        <div className="ice-kpi">
          <div className="ice-kpi-label">Score</div>
          <div className="ice-kpi-value">{analise.score}</div>
          <div className="ice-scorebar">
            <div className="ice-scorefill" style={{ width: `${analise.score}%` }} />
          </div>
        </div>

        <div className="ice-kpi">
          <div className="ice-kpi-label">Rating</div>
          <div className="ice-kpi-value">{analise.rating}</div>
        </div>

        <div className="ice-kpi">
          <div className="ice-kpi-label">PD Estimada</div>
          <div className="ice-kpi-value" style={{ fontSize: 18 }}>
            {analise.pd}
          </div>
        </div>

        <div className="ice-kpi">
          <div className="ice-kpi-label">Gerado em</div>
          <div className="ice-kpi-value" style={{ fontSize: 14 }}>
            {gerado_em}
          </div>
        </div>
      </div>

      <div className="ice-section-title">Dados cadastrais</div>

      <table className="ice-table">
        <tbody>
          <tr>
            <td>Razão Social</td>
            <td>{dados.razao_social || "—"}</td>
          </tr>
          <tr>
            <td>Nome Fantasia</td>
            <td>{dados.nome_fantasia || "—"}</td>
          </tr>
          <tr>
            <td>Situação</td>
            <td>{dados.descricao_situacao_cadastral || "—"}</td>
          </tr>
          <tr>
            <td>Natureza Jurídica</td>
            <td>{dados.descricao_natureza_juridica || "—"}</td>
          </tr>
          <tr>
            <td>Porte</td>
            <td>{dados.porte || "—"}</td>
          </tr>
          <tr>
            <td>Capital Social</td>
            <td>{moeda(dados.capital_social)}</td>
          </tr>
          <tr>
            <td>Data de Abertura</td>
            <td>{dados.data_inicio_atividade || "—"}</td>
          </tr>
          <tr>
            <td>CNAE Principal</td>
            <td>
              {dados.cnae_fiscal || "—"} — {dados.cnae_fiscal_descricao || "—"}
            </td>
          </tr>
          <tr>
            <td>Endereço</td>
            <td>
              {dados.logradouro || "—"}, {dados.numero || "s/n"} —{" "}
              {dados.bairro || "—"} — {dados.municipio || "—"}/{dados.uf || "—"} —{" "}
              CEP {dados.cep || "—"}
            </td>
          </tr>
        </tbody>
      </table>

      <div className="ice-flags">
        <FlagBox titulo="Red Flags" items={analise.flags.red_flags} tipo="red" />
        <FlagBox titulo="Yellow Flags" items={analise.flags.yellow_flags} tipo="yellow" />
        <FlagBox titulo="Green Flags" items={analise.flags.green_flags} tipo="green" />
      </div>

      {socios.length > 0 && (
        <>
          <div className="ice-section-title">Quadro Societário</div>

          <table className="ice-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Nome</th>
                <th>Qualificação</th>
              </tr>
            </thead>
            <tbody>
              {socios.map((s, index) => (
                <tr key={`${s.nome_socio}-${index}`}>
                  <td>{index + 1}</td>
                  <td>{s.nome_socio || s.nome || "—"}</td>
                  <td>{s.qualificacao_socio || s.qualificacao || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <div className="ice-section-title">Recomendação P.I.L.D.E.R™</div>

      <div className="ice-rec">
        <div className="ice-rec-decisao">
          {analise.status === "APROVADO"
            ? "APROVAR COM MONITORAMENTO"
            : analise.status === "APROVADO COM RESTRIÇÕES"
            ? "APROVAR COM RESTRIÇÕES"
            : "ANÁLISE COMPLEMENTAR OBRIGATÓRIA"}
        </div>

        <div className="ice-rec-obs">
          A empresa apresenta rating {analise.rating}, score {analise.score}/100 e risco{" "}
          {analise.risco}. A análise considera situação cadastral, tempo de atividade,
          tipo de estabelecimento, capital social e leitura inicial do CNAE. Para decisão
          final, recomenda-se complementar com PGFN, protestos, ações judiciais, balanço,
          comportamento de pagamento e ficha CISP/Credinfar.
        </div>

        <div className="ice-rec-grid">
          <div>
            <span className="ice-rec-key">Prazo sugerido</span>
            <span className="ice-rec-val">
              {analise.score >= 70 ? "28 dias" : analise.score >= 55 ? "14 dias" : "À vista / antecipado"}
            </span>
          </div>

          <div>
            <span className="ice-rec-key">Limite inicial</span>
            <span className="ice-rec-val">
              {analise.score >= 70 ? "Médio" : analise.score >= 55 ? "Baixo / controlado" : "Restrito"}
            </span>
          </div>

          <div>
            <span className="ice-rec-key">Reavaliação</span>
            <span className="ice-rec-val">
              {analise.score >= 70 ? "Semestral" : "90 dias"}
            </span>
          </div>
        </div>
      </div>

      <div className="ice-actions">
        <button className="ice-btn-primary" onClick={onCopiar}>
          📋 Copiar JSON
        </button>
      </div>
    </div>
  );
}

function FlagBox({ titulo, items, tipo }) {
  const cores = {
    red: { bg: "#fff1f2", border: "#ffd0d5", title: "#b4232f" },
    yellow: { bg: "#fff8e1", border: "#ffe082", title: "#7a5600" },
    green: { bg: "#e8f5e9", border: "#a5d6a7", title: "#1b5e20" },
  }[tipo];

  return (
    <div
      className="ice-flagbox"
      style={{
        background: cores.bg,
        borderColor: cores.border,
      }}
    >
      <div className="ice-flagbox-title" style={{ color: cores.title }}>
        {titulo}
      </div>

      {items && items.length > 0 ? (
        <ul className="ice-flagbox-list">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      ) : (
        <div className="ice-flagbox-empty">Nenhum apontamento.</div>
      )}
    </div>
  );
}
