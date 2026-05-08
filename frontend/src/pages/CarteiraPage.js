// src/pages/CarteiraPage.js
import { useState, useMemo } from "react";
import { processarLote } from "../hooks/useApi";
import {
  ScoreBadge, RatingBadge, RiscoTag, FlagList, KpiCard,
  Spinner, RATING_ORDER, RATING_COLOR, RISCO_COLOR
} from "../components/ui";

function RatingDistBar({ data }) {
  const counts = RATING_ORDER
    .map(r => ({ rating: r, count: data.filter(d => d.rating === r).length }))
    .filter(x => x.count > 0);
  const max = Math.max(...counts.map(x => x.count), 1);
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
      {counts.map(({ rating, count }) => (
        <div key={rating} style={{ display:"flex", alignItems:"center", gap:8 }}>
          <div style={{ width:30, textAlign:"right", fontFamily:"monospace",
            fontSize:11, fontWeight:700, color:RATING_COLOR[rating] }}>{rating}</div>
          <div style={{ flex:1, height:18, background:"#1e293b", borderRadius:4 }}>
            <div style={{ width:`${(count/max)*100}%`, height:"100%",
              background:`${RATING_COLOR[rating]}bb`, borderRadius:4,
              display:"flex", alignItems:"center", paddingLeft:6 }}>
              <span style={{ fontSize:10, fontWeight:700, color:"#fff" }}>{count}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CarteiraPage() {
  const [resultados, setResultados] = useState([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");
  const [search, setSearch] = useState("");
  const [filterRisco, setFilterRisco] = useState("todos");
  const [sortBy, setSortBy] = useState("score");
  const [sortDir, setSortDir] = useState("asc");
  const [selected, setSelected] = useState(null);
  const [processInfo, setProcessInfo] = useState(null);

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true); setErro(""); setResultados([]); setProcessInfo(null);
    try {
      const resp = await processarLote(file);
      setResultados(resp.resultados || []);
      setProcessInfo({ processados: resp.processados, erros: resp.erros });
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  const filtered = useMemo(() => {
    let d = resultados;
    if (search) d = d.filter(x =>
      x.empresa?.toLowerCase().includes(search.toLowerCase()) || x.cnpj?.includes(search));
    if (filterRisco !== "todos") d = d.filter(x => x.classificacao_risco === filterRisco);
    return [...d].sort((a, b) => {
      let va = a[sortBy], vb = b[sortBy];
      if (sortBy === "rating") { va = RATING_ORDER.indexOf(a.rating); vb = RATING_ORDER.indexOf(b.rating); }
      if (typeof va === "string") { va = va.toLowerCase(); vb = vb?.toLowerCase(); }
      return sortDir === "asc" ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });
  }, [resultados, search, filterRisco, sortBy, sortDir]);

  function toggleSort(col) {
    if (sortBy === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortBy(col); setSortDir("asc"); }
  }

  const alto = resultados.filter(x => x.classificacao_risco === "alto").length;
  const medio = resultados.filter(x => x.classificacao_risco === "medio").length;
  const baixo = resultados.filter(x => x.classificacao_risco === "baixo").length;
  const avgScore = resultados.length
    ? Math.round(resultados.reduce((s, x) => s + x.score, 0) / resultados.length) : 0;
  const comRj = resultados.filter(x => x.sinais_rj?.length > 0).length;

  function exportarExcel() {
    const rows = [
      ["CNPJ","Empresa","Score","Rating","PD%","Risco","Prazo","Sinais RJ","Red Flags","Green Flags"],
      ...resultados.map(r => [
        r.cnpj, r.empresa, r.score, r.rating, r.pd,
        r.classificacao_risco, r.prazo_sugerido,
        r.sinais_rj?.join("; "), r.red_flags?.join("; "), r.green_flags?.join("; ")
      ])
    ];
    const csv = rows.map(r => r.map(c => `"${c ?? ""}"`).join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type:"text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "creditlens_carteira.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  const thStyle = (col) => ({
    padding:"10px 14px", textAlign:"left", fontSize:10, fontWeight:700,
    color:"#475569", letterSpacing:1, textTransform:"uppercase", cursor:"pointer",
    userSelect:"none", borderBottom:"1px solid #1e293b",
    background: sortBy === col ? "#0f172a" : "transparent", whiteSpace:"nowrap"
  });

  return (
    <div>
      {/* Upload */}
      <div style={{ background:"#0a1628", border:"1px solid #1e293b",
        borderRadius:14, padding:24, marginBottom:24 }}>
        <div style={{ fontSize:14, fontWeight:700, marginBottom:4, color:"#94a3b8" }}>
          Processamento em Lote
        </div>
        <div style={{ fontSize:12, color:"#475569", marginBottom:16 }}>
          Envie um Excel com coluna <code style={{ color:"#a78bfa" }}>cnpj</code> para analisar toda a carteira.
        </div>
        <div style={{ display:"flex", gap:12, alignItems:"center", flexWrap:"wrap" }}>
          <label style={{ background:"linear-gradient(135deg,#3b82f6,#6366f1)",
            borderRadius:8, padding:"10px 22px", color:"#fff", fontWeight:700,
            fontSize:13, cursor:"pointer" }}>
            📂 Carregar Planilha
            <input type="file" accept=".xlsx,.xls" onChange={handleUpload}
              style={{ display:"none" }} />
          </label>
          {resultados.length > 0 && (
            <button onClick={exportarExcel}
              style={{ background:"#0f172a", border:"1px solid #334155",
                borderRadius:8, padding:"10px 18px", color:"#94a3b8",
                fontSize:13, cursor:"pointer", fontWeight:600 }}>
              ⬇ Exportar CSV
            </button>
          )}
          {processInfo && (
            <span style={{ fontSize:12, color:"#475569" }}>
              ✓ {processInfo.processados} processados
              {processInfo.erros > 0 && ` · ${processInfo.erros} erros`}
            </span>
          )}
        </div>
        {erro && (
          <div style={{ marginTop:12, padding:12, background:"#450a0a33",
            border:"1px solid #ef444433", borderRadius:8,
            color:"#f87171", fontSize:13 }}>{erro}</div>
        )}
      </div>

      {loading && <Spinner />}

      {resultados.length > 0 && (
        <>
          {/* KPIs */}
          <div style={{ display:"flex", gap:12, marginBottom:20, flexWrap:"wrap" }}>
            <KpiCard label="Score Médio" value={avgScore} color="#a78bfa" sub="carteira" />
            <KpiCard label="Risco Alto" value={alto}
              sub={`${Math.round(alto/resultados.length*100)}%`} color="#f87171" />
            <KpiCard label="Risco Médio" value={medio}
              sub={`${Math.round(medio/resultados.length*100)}%`} color="#fbbf24" />
            <KpiCard label="Risco Baixo" value={baixo}
              sub={`${Math.round(baixo/resultados.length*100)}%`} color="#34d399" />
            <KpiCard label="Sinais RJ" value={comRj} color="#f97316" sub="atenção imediata" />
            <KpiCard label="Total" value={resultados.length} color="#94a3b8" sub="CNPJs" />
          </div>

          <div style={{ display:"grid", gridTemplateColumns:"1fr 240px", gap:16, marginBottom:20 }}>
            {/* Tabela */}
            <div style={{ background:"#0a1628", border:"1px solid #1e293b",
              borderRadius:14, overflow:"hidden" }}>
              <div style={{ padding:"12px 16px", borderBottom:"1px solid #1e293b",
                display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
                <input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Buscar empresa ou CNPJ..."
                  style={{ background:"#060d1a", border:"1px solid #1e293b",
                    borderRadius:7, padding:"7px 12px", color:"#e2e8f0",
                    fontSize:13, flex:1, minWidth:160, outline:"none" }} />
                <select value={filterRisco} onChange={e => setFilterRisco(e.target.value)}
                  style={{ background:"#060d1a", border:"1px solid #1e293b",
                    borderRadius:7, padding:"7px 10px", color:"#94a3b8", fontSize:12 }}>
                  <option value="todos">Todos os riscos</option>
                  <option value="alto">Alto</option>
                  <option value="medio">Médio</option>
                  <option value="baixo">Baixo</option>
                </select>
                <span style={{ fontSize:11, color:"#334155" }}>{filtered.length} empresas</span>
              </div>
              <div style={{ overflowX:"auto" }}>
                <table style={{ width:"100%", borderCollapse:"collapse" }}>
                  <thead>
                    <tr>
                      {[["empresa","Empresa"],["score","Score"],["rating","Rating"],
                        ["pd","PD%"],["classificacao_risco","Risco"]].map(([col,lbl]) => (
                        <th key={col} style={thStyle(col)} onClick={() => toggleSort(col)}>
                          {lbl} {sortBy===col ? (sortDir==="asc"?"↑":"↓") : ""}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((row, i) => (
                      <tr key={row.cnpj}
                        onClick={() => setSelected(selected?.cnpj === row.cnpj ? null : row)}
                        style={{ cursor:"pointer",
                          background: selected?.cnpj===row.cnpj ? "#1e293b"
                            : i%2===0 ? "#0a1628" : "#0d1f38",
                          borderBottom:"1px solid #1e293b11" }}>
                        <td style={{ padding:"10px 14px", fontSize:13, fontWeight:500,
                          maxWidth:220, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
                          {row.sinais_rj?.length > 0 &&
                            <span style={{ color:"#f97316", marginRight:5, fontSize:10 }}>⚠</span>}
                          {row.empresa}
                          <div style={{ fontSize:10, color:"#334155", fontFamily:"monospace" }}>
                            {row.cnpj}
                          </div>
                        </td>
                        <td style={{ padding:"10px 14px" }}><ScoreBadge score={row.score} /></td>
                        <td style={{ padding:"10px 14px" }}><RatingBadge rating={row.rating} /></td>
                        <td style={{ padding:"10px 14px", fontFamily:"monospace", fontSize:12,
                          color: row.pd>35?"#f87171":row.pd>25?"#fbbf24":"#34d399" }}>
                          {row.pd?.toFixed(1)}%
                        </td>
                        <td style={{ padding:"10px 14px" }}>
                          <RiscoTag risco={row.classificacao_risco} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Sidebar */}
            <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
              <div style={{ background:"#0a1628", border:"1px solid #1e293b",
                borderRadius:14, padding:18 }}>
                <div style={{ fontSize:10, color:"#475569", fontWeight:700,
                  letterSpacing:1.2, textTransform:"uppercase", marginBottom:12 }}>
                  Distribuição Rating
                </div>
                <RatingDistBar data={resultados} />
              </div>
            </div>
          </div>

          {/* Detalhe selecionado */}
          {selected && (
            <div style={{ background:"#0a1628", border:"1px solid #3b82f633",
              borderRadius:14, padding:24, marginBottom:20 }}>
              <div style={{ display:"flex", justifyContent:"space-between",
                alignItems:"flex-start", marginBottom:20 }}>
                <div>
                  <div style={{ fontSize:18, fontWeight:800, marginBottom:4 }}>
                    {selected.empresa}
                  </div>
                  <div style={{ fontSize:12, color:"#475569", fontFamily:"monospace" }}>
                    {selected.cnpj}
                  </div>
                </div>
                <div style={{ display:"flex", gap:10, alignItems:"center" }}>
                  <ScoreBadge score={selected.score} />
                  <RatingBadge rating={selected.rating} />
                  <RiscoTag risco={selected.classificacao_risco} />
                  <button onClick={() => setSelected(null)}
                    style={{ background:"none", border:"none", color:"#475569",
                      cursor:"pointer", fontSize:20 }}>×</button>
                </div>
              </div>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14 }}>
                <FlagList title="🟢 Green Flags" items={selected.green_flags} color="#10b981" />
                <FlagList title="🟡 Yellow Flags" items={selected.yellow_flags} color="#f59e0b" />
                <FlagList title="🔴 Red Flags" items={selected.red_flags} color="#ef4444" />
              </div>
              {selected.sinais_rj?.length > 0 && (
                <div style={{ marginTop:14, background:"#450a0a22",
                  border:"1px solid #ef444433", borderRadius:10, padding:14 }}>
                  <div style={{ fontSize:11, fontWeight:700, color:"#f97316", marginBottom:8 }}>
                    ⚠ Sinais de Stress / RJ
                  </div>
                  {selected.sinais_rj.map((s, i) => (
                    <div key={i} style={{ fontSize:12, color:"#fca5a5", marginBottom:4 }}>• {s}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {!loading && resultados.length === 0 && (
        <div style={{ textAlign:"center", padding:"60px 0", color:"#334155" }}>
          <div style={{ fontSize:40, marginBottom:16 }}>📋</div>
          <div style={{ fontSize:14 }}>Carregue uma planilha Excel com coluna <code>cnpj</code> para começar</div>
        </div>
      )}
    </div>
  );
}
