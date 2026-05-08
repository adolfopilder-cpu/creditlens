// src/pages/AnalisePage.js — P.I.L.D.E.R™ v3.0
import { useState } from "react";
import { baixarPDF } from "../hooks/useApi";

const API = process.env.REACT_APP_API_URL || "";
const ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito";

const STATUS_COLOR = {
  confirmacao: "#10b981", ausencia: "#6ee7b7", indicio: "#f59e0b",
  pendente: "#475569", nao_consultado: "#334155", erro: "#ef4444",
};
const STATUS_LABEL = {
  confirmacao: "✓ Confirmado", ausencia: "○ Sem ocorrência", indicio: "⚡ Indício",
  pendente: "⏳ Pendente", nao_consultado: "— Não consultado", erro: "✗ Erro",
};
const RATING_COLOR = {
  AAA:"#10b981",AA:"#34d399",A:"#6ee7b7",BBB:"#fbbf24",BB:"#f59e0b",B:"#f97316",C:"#ef4444",D:"#7f1d1d"
};
const RISCO_COLOR = { baixo:"#10b981", medio:"#f59e0b", alto:"#ef4444" };

function fmt(cnpj) {
  const d = cnpj.replace(/\D/g,"").slice(0,14);
  return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/,"$1.$2.$3/$4-$5");
}

function ScoreGauge({ score }) {
  const color = score>=75?"#10b981":score>=50?"#f59e0b":"#ef4444";
  const bg = score>=75?"#064e3b":score>=50?"#451a03":"#450a0a";
  const deg = score*3.6;
  return (
    <div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:8}}>
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="50" fill="none" stroke="#1e293b" strokeWidth="10"/>
        <circle cx="60" cy="60" r="50" fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={`${(deg/360)*314.16} 314.16`}
          strokeDashoffset="78.54" strokeLinecap="round"/>
        <text x="60" y="55" textAnchor="middle" fill={color} fontSize="28" fontWeight="800" fontFamily="monospace">{score}</text>
        <text x="60" y="75" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="monospace">/ 100</text>
      </svg>
    </div>
  );
}

function Badge({ label, color }) {
  return <span style={{background:`${color}22`,color,border:`1px solid ${color}44`,
    borderRadius:5,padding:"3px 10px",fontWeight:700,fontSize:12,fontFamily:"monospace",letterSpacing:1}}>{label}</span>;
}

function FonteRow({ fonte, idx }) {
  const [open, setOpen] = useState(false);
  const color = STATUS_COLOR[fonte.status] || "#475569";
  const pts = fonte.pontos || 0;
  return (
    <div style={{borderBottom:"1px solid #1e293b11"}}>
      <div onClick={()=>setOpen(o=>!o)} style={{display:"flex",alignItems:"center",
        gap:10,padding:"10px 16px",cursor:"pointer",
        background: open?"#0f172a":"transparent",
        transition:"background 0.15s"}}>
        <span style={{fontSize:11,color:"#334155",fontFamily:"monospace",minWidth:24}}>{idx+1}</span>
        <span style={{flex:1,fontSize:12,fontWeight:600,color:"#e2e8f0"}}>{fonte.fonte}</span>
        <span style={{fontSize:10,background:`${color}22`,color,border:`1px solid ${color}33`,
          borderRadius:20,padding:"2px 8px",fontWeight:700,whiteSpace:"nowrap"}}>
          {STATUS_LABEL[fonte.status]||fonte.status}
        </span>
        <span style={{fontSize:12,fontFamily:"monospace",fontWeight:700,minWidth:40,textAlign:"right",
          color:pts>0?"#34d399":pts<0?"#f87171":"#64748b"}}>
          {pts>0?"+":""}{pts}
        </span>
        <span style={{color:"#334155",fontSize:12}}>{open?"▲":"▼"}</span>
      </div>
      {open && (
        <div style={{padding:"10px 16px 14px 50px",background:"#060d1a"}}>
          <div style={{fontSize:12,color:"#94a3b8",marginBottom:6,lineHeight:1.6}}>
            <b style={{color:"#e2e8f0"}}>Resumo:</b> {fonte.resumo}
          </div>
          {fonte.detalhe && (
            <div style={{fontSize:11,color:"#64748b",marginBottom:6,lineHeight:1.5,
              background:"#0a1628",borderRadius:6,padding:"8px 12px",
              borderLeft:`2px solid ${color}`}}>
              {fonte.detalhe}
            </div>
          )}
          <div style={{fontSize:10,color:"#334155",fontFamily:"monospace"}}>
            Consultado em: {fonte.consultado_em} | Pontuação: {pts>0?"+":""}{pts}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalisePage() {
  const [cnpj, setCnpj] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [balanco, setBalanco] = useState(null);
  const [cisp, setCisp] = useState(null);
  const [filtroFonte, setFiltroFonte] = useState("todas");
  const [buscaFonte, setBuscaFonte] = useState("");

  async function handleAnalise(e) {
    e.preventDefault();
    if (!cnpj) return;
    setLoading(true); setErro(""); setResultado(null);
    try {
      let res;
      if (balanco || cisp) {
        const form = new FormData();
        form.append("cnpj", cnpj);
        if (balanco) form.append("balanco", balanco);
        if (cisp) form.append("cisp", cisp);
        res = await fetch(`${API}/api/analisar-com-anexo`, {method:"POST", body:form});
      } else {
        res = await fetch(`${API}/api/analisar`, {
          method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({cnpj})
        });
      }
      if (!res.ok) {
        const err = await res.json().catch(()=>({}));
        throw new Error(err.detail || `Erro HTTP ${res.status}`);
      }
      setResultado(await res.json());
    } catch(err) {
      setErro(err.message);
    } finally { setLoading(false); }
  }

  async function handlePDF() {
    setPdfLoading(true);
    try { await baixarPDF(cnpj); }
    catch(e) { setErro("Erro ao gerar PDF: "+e.message); }
    finally { setPdfLoading(false); }
  }

  const r = resultado;
  const fontesFiltradas = r?.fontes?.filter(f => {
    const matchFiltro = filtroFonte==="todas" || f.status===filtroFonte;
    const matchBusca = !buscaFonte || f.fonte.toLowerCase().includes(buscaFonte.toLowerCase());
    return matchFiltro && matchBusca;
  }) || [];

  return (
    <div>
      {/* Formulário */}
      <div style={{background:"#0a1628",border:"1px solid #1e293b",borderRadius:14,padding:24,marginBottom:20}}>
        <div style={{fontSize:11,color:"#475569",fontWeight:700,letterSpacing:1.2,
          textTransform:"uppercase",marginBottom:4}}>{ASSINATURA}</div>
        <div style={{fontSize:16,fontWeight:800,marginBottom:16}}>Análise de Crédito por CNPJ</div>
        <form onSubmit={handleAnalise} style={{display:"flex",flexDirection:"column",gap:14}}>
          <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
            <input value={fmt(cnpj)} onChange={e=>setCnpj(e.target.value.replace(/\D/g,""))}
              placeholder="00.000.000/0000-00" maxLength={18}
              style={{flex:1,minWidth:220,background:"#060d1a",border:"1px solid #1e293b",
                borderRadius:8,padding:"10px 14px",color:"#e2e8f0",fontSize:15,
                fontFamily:"monospace",letterSpacing:1,outline:"none"}} />
            <button type="submit" disabled={loading||cnpj.length<14}
              style={{background:cnpj.length<14?"#1e293b":"linear-gradient(135deg,#3b82f6,#6366f1)",
                border:"none",borderRadius:8,padding:"10px 28px",color:"#fff",
                fontWeight:700,fontSize:14,cursor:cnpj.length<14?"not-allowed":"pointer",
                whiteSpace:"nowrap"}}>
              {loading?"Analisando...":"🔍 Analisar"}
            </button>
            {r && (
              <button type="button" onClick={handlePDF} disabled={pdfLoading}
                style={{background:"#0f172a",border:"1px solid #334155",borderRadius:8,
                  padding:"10px 18px",color:"#94a3b8",fontSize:13,cursor:"pointer",fontWeight:600}}>
                {pdfLoading?"Gerando...":"⬇ PDF"}
              </button>
            )}
          </div>

          {/* Anexos */}
          <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
            <label style={{display:"flex",flexDirection:"column",gap:4,flex:1,minWidth:200}}>
              <span style={{fontSize:11,color:"#475569",fontWeight:600,textTransform:"uppercase",letterSpacing:1}}>
                📎 Balanço / DRE (opcional)
              </span>
              <div style={{background:"#060d1a",border:`1px solid ${balanco?"#3b82f6":"#1e293b"}`,
                borderRadius:8,padding:"8px 12px",cursor:"pointer",fontSize:12,color:"#64748b"}}>
                <input type="file" accept=".pdf,.txt,.csv,.xlsx,.xls"
                  onChange={e=>setBalanco(e.target.files?.[0]||null)}
                  style={{display:"none"}} id="inp-balanco"/>
                <label htmlFor="inp-balanco" style={{cursor:"pointer",color:balanco?"#3b82f6":"#64748b"}}>
                  {balanco?`✓ ${balanco.name}`:"Clique para anexar balanço ou DRE"}
                </label>
              </div>
            </label>
            <label style={{display:"flex",flexDirection:"column",gap:4,flex:1,minWidth:200}}>
              <span style={{fontSize:11,color:"#475569",fontWeight:600,textTransform:"uppercase",letterSpacing:1}}>
                📋 Ficha CISP / Cadastro (opcional)
              </span>
              <div style={{background:"#060d1a",border:`1px solid ${cisp?"#8b5cf6":"#1e293b"}`,
                borderRadius:8,padding:"8px 12px",cursor:"pointer",fontSize:12,color:"#64748b"}}>
                <input type="file" accept=".pdf,.txt,.csv,.xlsx,.xls"
                  onChange={e=>setCisp(e.target.files?.[0]||null)}
                  style={{display:"none"}} id="inp-cisp"/>
                <label htmlFor="inp-cisp" style={{cursor:"pointer",color:cisp?"#8b5cf6":"#64748b"}}>
                  {cisp?`✓ ${cisp.name}`:"Clique para anexar ficha CISP"}
                </label>
              </div>
            </label>
          </div>
        </form>
        {erro && (
          <div style={{marginTop:12,padding:12,background:"#450a0a33",
            border:"1px solid #ef444433",borderRadius:8,color:"#f87171",fontSize:13}}>
            {erro}
          </div>
        )}
      </div>

      {loading && (
        <div style={{textAlign:"center",padding:"40px 0",color:"#475569"}}>
          <div style={{fontSize:13,marginBottom:12}}>Consultando 48 fontes...</div>
          <div style={{width:40,height:40,border:"3px solid #1e293b",
            borderTop:"3px solid #3b82f6",borderRadius:"50%",
            animation:"spin 0.8s linear infinite",margin:"0 auto"}}/>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}

      {r && (
        <>
          {/* Header empresa */}
          <div style={{background:"#0a1628",border:"1px solid #1e293b",borderRadius:14,padding:24,marginBottom:16}}>
            <div style={{fontSize:10,color:"#334155",fontWeight:700,letterSpacing:1,marginBottom:8}}>{ASSINATURA}</div>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",flexWrap:"wrap",gap:16}}>
              <div style={{flex:1}}>
                <div style={{fontSize:22,fontWeight:800,marginBottom:4}}>{r.empresa||"—"}</div>
                <div style={{fontSize:12,color:"#475569",fontFamily:"monospace",marginBottom:3}}>
                  {fmt(r.cnpj)} · {r.dados?.receita?.uf||""} · {r.dados?.receita?.municipio||""}
                </div>
                <div style={{fontSize:11,color:"#334155"}}>{r.fontes?.[0]?.raw?.cnae_fiscal_descricao||""}</div>
                <div style={{fontSize:11,color:"#475569",marginTop:4}}>
                  {r.fontes_consultadas} de {r.total_fontes} fontes consultadas · {r.fontes_pendentes} pendentes
                </div>
              </div>
              <div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:12}}>
                <ScoreGauge score={r.score} />
                <div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"center"}}>
                  <Badge label={r.rating} color={RATING_COLOR[r.rating]||"#94a3b8"} />
                  <Badge label={r.classificacao_risco?.toUpperCase()} color={RISCO_COLOR[r.classificacao_risco]||"#94a3b8"} />
                  <Badge label={`PD ${r.pd}%`} color={r.pd>35?"#ef4444":r.pd>25?"#f59e0b":"#10b981"} />
                </div>
              </div>
            </div>
          </div>

          {/* KPIs */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:10,marginBottom:16}}>
            {[
              {l:"Score",v:r.score,c:r.score>=75?"#10b981":r.score>=50?"#f59e0b":"#ef4444"},
              {l:"Rating",v:r.rating,c:RATING_COLOR[r.rating]},
              {l:"PD Estimada",v:`${r.pd}%`,c:r.pd>35?"#ef4444":r.pd>25?"#f59e0b":"#10b981"},
              {l:"Fontes OK",v:`${r.fontes_consultadas}/${r.total_fontes}`,c:"#a78bfa"},
            ].map(({l,v,c})=>(
              <div key={l} style={{background:"#0f172a",border:"1px solid #1e293b",borderRadius:10,padding:"14px 16px"}}>
                <div style={{fontSize:10,color:"#475569",fontWeight:700,textTransform:"uppercase",letterSpacing:1,marginBottom:4}}>{l}</div>
                <div style={{fontSize:24,fontWeight:800,color:c,fontFamily:"monospace"}}>{v}</div>
              </div>
            ))}
          </div>

          {/* Recomendação */}
          <div style={{background:"#0a1628",border:"1px solid #1e293b",borderRadius:12,padding:18,marginBottom:16}}>
            <div style={{fontSize:11,color:"#475569",fontWeight:700,textTransform:"uppercase",letterSpacing:1,marginBottom:12}}>
              Recomendação de Crédito
            </div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
              <div>
                <div style={{fontSize:10,color:"#334155",marginBottom:3}}>LIMITE SUGERIDO</div>
                <div style={{fontSize:12,fontWeight:600,color:"#e2e8f0"}}>{r.limite_sugerido}</div>
              </div>
              <div>
                <div style={{fontSize:10,color:"#334155",marginBottom:3}}>PRAZO</div>
                <div style={{fontSize:12,fontWeight:600,color:"#e2e8f0"}}>{r.prazo_sugerido}</div>
              </div>
              <div>
                <div style={{fontSize:10,color:"#334155",marginBottom:3}}>MONITORAMENTO</div>
                <div style={{fontSize:12,fontWeight:600,color:"#e2e8f0"}}>{r.plano_monitoramento}</div>
              </div>
              <div style={{gridColumn:"1/-1"}}>
                <div style={{fontSize:10,color:"#334155",marginBottom:6}}>GARANTIAS RECOMENDADAS</div>
                <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                  {r.garantias_recomendadas?.map((g,i)=>(
                    <span key={i} style={{background:"#1e293b",borderRadius:6,
                      padding:"3px 10px",fontSize:11,color:"#94a3b8"}}>{g}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Flags */}
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:10,marginBottom:16}}>
            {[
              {t:"🔴 Red Flags",items:r.red_flags,c:"#ef4444"},
              {t:"🟡 Yellow Flags",items:r.yellow_flags,c:"#f59e0b"},
              {t:"🟢 Green Flags",items:r.green_flags,c:"#10b981"},
            ].map(({t,items,c})=>(
              <div key={t} style={{background:"#0f172a",borderRadius:10,padding:14}}>
                <div style={{fontSize:11,fontWeight:700,color:c,marginBottom:8}}>{t} ({items?.length||0})</div>
                {!items?.length
                  ? <div style={{fontSize:11,color:"#334155"}}>Nenhum</div>
                  : items.map((f,i)=>(
                    <div key={i} style={{fontSize:11,color:"#64748b",marginBottom:4,
                      paddingLeft:8,borderLeft:`2px solid ${c}55`}}>{f}</div>
                  ))
                }
              </div>
            ))}
          </div>

          {/* Sinais RJ */}
          {r.sinais_rj?.length > 0 && (
            <div style={{background:"#450a0a22",border:"1px solid #ef444433",
              borderRadius:12,padding:16,marginBottom:16}}>
              <div style={{fontSize:12,fontWeight:700,color:"#f97316",marginBottom:8}}>
                ⚠ Sinais de Stress / Recuperação Judicial
              </div>
              {r.sinais_rj.map((s,i)=>(
                <div key={i} style={{fontSize:12,color:"#fca5a5",marginBottom:4}}>• {s}</div>
              ))}
            </div>
          )}

          {/* 48 FONTES — Relatório detalhado */}
          <div style={{background:"#0a1628",border:"1px solid #1e293b",borderRadius:14,overflow:"hidden",marginBottom:16}}>
            <div style={{padding:"16px 20px",borderBottom:"1px solid #1e293b",
              display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:10}}>
              <div>
                <div style={{fontSize:14,fontWeight:700}}>Relatório por Fonte — 48 Fontes P.I.L.D.E.R™</div>
                <div style={{fontSize:11,color:"#475569",marginTop:2}}>
                  Clique em cada fonte para ver o detalhe completo da consulta
                </div>
              </div>
              <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                <input value={buscaFonte} onChange={e=>setBuscaFonte(e.target.value)}
                  placeholder="Buscar fonte..."
                  style={{background:"#060d1a",border:"1px solid #1e293b",borderRadius:6,
                    padding:"6px 10px",color:"#e2e8f0",fontSize:12,outline:"none",width:150}}/>
                <select value={filtroFonte} onChange={e=>setFiltroFonte(e.target.value)}
                  style={{background:"#060d1a",border:"1px solid #1e293b",borderRadius:6,
                    padding:"6px 10px",color:"#94a3b8",fontSize:12}}>
                  <option value="todas">Todas</option>
                  <option value="confirmacao">✓ Confirmado</option>
                  <option value="ausencia">○ Sem ocorrência</option>
                  <option value="indicio">⚡ Indício</option>
                  <option value="pendente">⏳ Pendente</option>
                  <option value="nao_consultado">— Não consultado</option>
                  <option value="erro">✗ Erro</option>
                </select>
                <span style={{fontSize:11,color:"#334155",alignSelf:"center"}}>
                  {fontesFiltradas.length} fonte(s)
                </span>
              </div>
            </div>

            {/* Legenda */}
            <div style={{padding:"8px 16px",borderBottom:"1px solid #1e293b",
              display:"flex",gap:16,flexWrap:"wrap"}}>
              {Object.entries(STATUS_LABEL).map(([k,v])=>(
                <span key={k} style={{fontSize:10,color:STATUS_COLOR[k],fontWeight:600}}>{v}</span>
              ))}
            </div>

            {fontesFiltradas.map((f,i)=>(
              <FonteRow key={f.fonte} fonte={f} idx={r.fontes?.indexOf(f)||i} />
            ))}
          </div>

          {/* Memória de cálculo */}
          <details style={{background:"#0a1628",border:"1px solid #1e293b",borderRadius:12,padding:16,marginBottom:16}}>
            <summary style={{cursor:"pointer",fontSize:12,color:"#475569",fontWeight:700,
              letterSpacing:1,textTransform:"uppercase"}}>Memória de Cálculo</summary>
            <div style={{marginTop:10,display:"flex",gap:10,flexWrap:"wrap"}}>
              {r.memoria_calculo && Object.entries(r.memoria_calculo).map(([k,v])=>(
                <div key={k} style={{background:"#0f172a",borderRadius:8,padding:"8px 14px"}}>
                  <div style={{fontSize:10,color:"#475569",marginBottom:2,textTransform:"capitalize"}}>{k}</div>
                  <div style={{fontSize:16,fontWeight:700,fontFamily:"monospace",
                    color:typeof v==="number"&&v>0?"#34d399":v<0?"#f87171":"#94a3b8"}}>
                    {typeof v==="number"?(v>0?`+${v}`:v):v}
                  </div>
                </div>
              ))}
            </div>
          </details>

          {/* Assinatura final */}
          <div style={{textAlign:"center",padding:"16px 0",
            fontSize:11,color:"#334155",fontWeight:600,letterSpacing:1}}>
            {ASSINATURA}
          </div>
        </>
      )}
    </div>
  );
}
