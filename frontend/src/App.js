// src/App.js
import { useState, useEffect } from "react";
import AnalisePage from "./pages/AnalisePage";
import CarteiraPage from "./pages/CarteiraPage";
import PilderHero from "./components/PilderHero";
import { statusConectores } from "./hooks/useApi";
import { ConectorBadge } from "./components/ui";

export default function App() {
  const [tab, setTab] = useState("analise");
  const [conectores, setConectores] = useState(null);

  useEffect(() => {
    statusConectores().then(setConectores).catch(() => {});
  }, []);

  const ativos = conectores
    ? Object.values(conectores).filter(c => c?.status === "ativo" || c?.status === "ativo_parcial").length
    : null;

  const BG = "#f5f0e8";
  const CARD = "#ffffff";
  const BORDER = "#d4c9a8";
  const TEXT = "#1a1a2e";
  const MUTED = "#6b6b7b";
  const GOLD = "#b49303";
  const NAVY = "#1E3A5F";

  return (
    <div style={{ minHeight: "100vh", background: BG, color: TEXT,
      fontFamily: "'IBM Plex Sans', 'Segoe UI', sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>

      {/* Topbar */}
      <div style={{ borderBottom: `1px solid ${BORDER}`, padding: "0 28px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: 54, background: NAVY, position: "sticky", top: 0, zIndex: 100,
        boxShadow: "0 2px 12px #00000022" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30,
            background: `linear-gradient(135deg, ${NAVY}, ${GOLD})`,
            borderRadius: 8, display: "flex", alignItems: "center",
            justifyContent: "center", fontSize: 15, fontWeight: 900,
            color: "#fff", fontFamily: "Georgia, serif" }}>P</div>
          <span style={{ fontWeight: 800, fontSize: 15, letterSpacing: 1, color: "#fff" }}>
            P.I.L.D.E.R™
          </span>
          <span style={{ fontSize: 10, color: "#94a3b8", fontFamily: "monospace" }}>
            Análise de Crédito v3.0
          </span>
        </div>

        <div style={{ display: "flex", gap: 4 }}>
          {[
            { id: "analise", label: "🔍 Análise Pontual" },
            { id: "carteira", label: "📋 Carteira / Lote" },
            { id: "conectores", label: "⚡ Conectores" },
          ].map(({ id, label }) => (
            <button key={id} onClick={() => setTab(id)} style={{
              background: tab === id ? "#ffffff22" : "transparent",
              border: tab === id ? "1px solid #ffffff44" : "1px solid transparent",
              color: tab === id ? "#fff" : "#94a3b8",
              padding: "6px 16px", borderRadius: 8,
              fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
              {label}
            </button>
          ))}
        </div>

        <div style={{ fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>
          {ativos !== null ? `${ativos} conectores ativos` : ""}
        </div>
      </div>

      {/* Conteúdo */}
      <div style={{ padding: "28px 28px", maxWidth: 1300, margin: "0 auto" }}>
        {tab === "analise" && (
          <>
            <PilderHero />
            <AnalisePage />
          </>
        )}
        {tab === "carteira" && <CarteiraPage />}
        {tab === "conectores" && (
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6, color: NAVY }}>
              Status dos Conectores — 48 Fontes P.I.L.D.E.R™
            </div>
            <div style={{ fontSize: 12, color: MUTED, marginBottom: 20 }}>
              Conectores "Pendente" são adaptadores prontos para integração.
              Ausência de dados nunca equivale a regularidade.
            </div>
            {conectores ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
                {Object.entries(conectores).filter(([k]) => k !== "total_fontes").map(([key, val]) => (
                  <div key={key} style={{ background: CARD, border: `1px solid ${BORDER}`,
                    borderRadius: 12, padding: 16 }}>
                    <div style={{ display: "flex", justifyContent: "space-between",
                      alignItems: "center", marginBottom: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 700,
                        textTransform: "capitalize", color: NAVY }}>
                        {key.replace(/_/g, " ")}
                      </span>
                      <ConectorBadge status={val?.status} />
                    </div>
                    <div style={{ fontSize: 10, color: MUTED,
                      fontFamily: "monospace", background: BG,
                      borderRadius: 6, padding: "4px 8px" }}>
                      tipo: {val?.tipo}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: MUTED, fontSize: 13 }}>Backend offline.</div>
            )}
            <div style={{ marginTop: 20, padding: 16, background: NAVY,
              borderRadius: 12, textAlign: "center",
              fontSize: 12, color: GOLD, fontWeight: 700, letterSpacing: 1 }}>
              P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito — 48 Fontes
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
