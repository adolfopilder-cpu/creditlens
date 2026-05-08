// src/App.js
import { useState, useEffect } from "react";
import AnalisePage from "./pages/AnalisePage";
import CarteiraPage from "./pages/CarteiraPage";
import { statusConectores } from "./hooks/useApi";
import { ConectorBadge } from "./components/ui";

export default function App() {
  const [tab, setTab] = useState("analise");
  const [conectores, setConectores] = useState(null);

  useEffect(() => {
    statusConectores().then(setConectores).catch(() => {});
  }, []);

  const ativos = conectores
    ? Object.values(conectores).filter(c => c.status === "ativo" || c.status === "ativo_parcial").length
    : null;

  return (
    <div style={{ minHeight:"100vh", background:"#060d1a",
      color:"#e2e8f0", fontFamily:"'IBM Plex Sans', 'Segoe UI', sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>

      {/* Topbar */}
      <div style={{ borderBottom:"1px solid #1e293b", padding:"0 28px",
        display:"flex", alignItems:"center", justifyContent:"space-between", height:56,
        background:"#060d1a", position:"sticky", top:0, zIndex:100 }}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:30, height:30,
            background:"linear-gradient(135deg,#3b82f6,#8b5cf6)",
            borderRadius:8, display:"flex", alignItems:"center",
            justifyContent:"center", fontSize:16, fontWeight:800, color:"#fff" }}>⬡</div>
          <span style={{ fontWeight:800, fontSize:16, letterSpacing:0.5 }}>CreditLens</span>
          <span style={{ fontSize:11, color:"#334155", fontFamily:"monospace" }}>v2.0</span>
        </div>

        <div style={{ display:"flex", gap:4 }}>
          {[
            { id:"analise", label:"🔍 Análise Pontual" },
            { id:"carteira", label:"📋 Carteira / Lote" },
            { id:"conectores", label:"⚡ Conectores" },
          ].map(({ id, label }) => (
            <button key={id} onClick={() => setTab(id)}
              style={{ background: tab===id ? "#1e293b" : "transparent",
                border:"none", color: tab===id ? "#e2e8f0" : "#475569",
                padding:"6px 16px", borderRadius:8, fontSize:12, fontWeight:600,
                cursor:"pointer" }}>
              {label}
            </button>
          ))}
        </div>

        <div style={{ fontSize:11, color:"#334155", fontFamily:"monospace" }}>
          {ativos !== null ? `${ativos} conectores ativos` : ""}
        </div>
      </div>

      {/* Conteúdo */}
      <div style={{ padding:"28px 28px", maxWidth:1300, margin:"0 auto" }}>
        {tab === "analise" && <AnalisePage />}
        {tab === "carteira" && <CarteiraPage />}
        {tab === "conectores" && (
          <div>
            <div style={{ fontSize:16, fontWeight:700, marginBottom:6 }}>Status dos Conectores</div>
            <div style={{ fontSize:12, color:"#475569", marginBottom:20 }}>
              Conectores marcados como "Pendente" são placeholders prontos para integração.
              A ausência de dados nunca é tratada como evidência positiva — o motor de score
              já aplica penalidade conservadora automaticamente.
            </div>
            {conectores ? (
              <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14 }}>
                {Object.entries(conectores).map(([key, val]) => (
                  <div key={key} style={{ background:"#0a1628", border:"1px solid #1e293b",
                    borderRadius:12, padding:18 }}>
                    <div style={{ display:"flex", justifyContent:"space-between",
                      alignItems:"center", marginBottom:10 }}>
                      <span style={{ fontSize:14, fontWeight:700,
                        textTransform:"capitalize", color:"#e2e8f0" }}>{key}</span>
                      <ConectorBadge status={val.status} />
                    </div>
                    <div style={{ fontSize:12, color:"#64748b", marginBottom:8, lineHeight:1.5 }}>
                      {val.nome}
                    </div>
                    <div style={{ fontSize:10, color:"#334155", fontFamily:"monospace",
                      background:"#060d1a", borderRadius:6, padding:"6px 8px" }}>
                      tipo: {val.tipo}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color:"#475569", fontSize:13 }}>
                Backend offline — conectores não disponíveis.
                Certifique-se de que a API está rodando.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
