// src/App.js
import { useState, useEffect } from "react";
import AnalisePage from "./pages/AnalisePage";
import CarteiraPage from "./pages/CarteiraPage";
import ModuloICE from "./pages/ModuloICE";
import PilderHero from "./components/PilderHero";
import { statusConectores } from "./hooks/useApi";
import { ConectorBadge } from "./components/ui";

export default function App() {
  const [tab, setTab] = useState("ice");
  const [conectores, setConectores] = useState(null);

  useEffect(() => {
    statusConectores().then(setConectores).catch(() => {});
  }, []);

  const ativos = conectores
    ? Object.values(conectores).filter(
        (c) => c?.status === "ativo" || c?.status === "ativo_parcial"
      ).length
    : null;

  const BG = "#f5f0e8";
  const CARD = "#ffffff";
  const BORDER = "#d4c9a8";
  const TEXT = "#1a1a2e";
  const MUTED = "#6b6b7b";
  const GOLD = "#b49303";
  const NAVY = "#1E3A5F";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: BG,
        color: TEXT,
        fontFamily:
          "Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      {/* TOPO */}
      <header
        style={{
          background: NAVY,
          color: "#fff",
          padding: "14px 24px",
          borderBottom: `4px solid ${GOLD}`,
          position: "sticky",
          top: 0,
          zIndex: 50,
          boxShadow: "0 8px 20px rgba(0,0,0,0.16)",
        }}
      >
        <div
          style={{
            maxWidth: 1400,
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div>
            <div
              style={{
                fontSize: 18,
                fontWeight: 800,
                letterSpacing: "0.04em",
              }}
            >
              P.I.L.D.E.R™ CreditLens
            </div>
            <div
              style={{
                fontSize: 11,
                color: "#cbd5e1",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Análise de Crédito B2B — V2.1
            </div>
          </div>

          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {[
              { id: "analise", label: "🔍 Análise Pontual" },
              { id: "carteira", label: "📋 Carteira / Lote" },
              { id: "conectores", label: "⚡ Conectores" },
              { id: "ice", label: "🕵️ ICE · Investigação" },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                style={{
                  background: tab === id ? "#ffffff22" : "transparent",
                  border:
                    tab === id
                      ? "1px solid #ffffff44"
                      : "1px solid transparent",
                  color: tab === id ? "#fff" : "#94a3b8",
                  padding: "6px 16px",
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <div
            style={{
              fontSize: 12,
              color: "#e2e8f0",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span
              style={{
                background: "#ffffff18",
                border: "1px solid #ffffff33",
                borderRadius: 999,
                padding: "5px 10px",
              }}
            >
              {ativos === null ? "Carregando fontes..." : `${ativos}+ conectores ativos`}
            </span>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section
        style={{
          maxWidth: 1400,
          margin: "0 auto",
          padding: "22px 24px 0",
        }}
      >
        <PilderHero />
      </section>

      {/* CONTEÚDO */}
      <main
        style={{
          maxWidth: 1400,
          margin: "0 auto",
          padding: "20px 24px 40px",
        }}
      >
        {tab === "analise" && (
          <div
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              borderRadius: 18,
              padding: 18,
              boxShadow: "0 12px 30px rgba(30,58,95,0.08)",
            }}
          >
            <AnalisePage />
          </div>
        )}

        {tab === "carteira" && (
          <div
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              borderRadius: 18,
              padding: 18,
              boxShadow: "0 12px 30px rgba(30,58,95,0.08)",
            }}
          >
            <CarteiraPage />
          </div>
        )}

{tab === "ice" && (
  <div
    style={{
      background: CARD,
      border: `1px solid ${BORDER}`,
      borderRadius: 18,
      padding: 18,
      boxShadow: "0 12px 30px rgba(30,58,95,0.08)",
    }}
  >
    <ModuloICE />
  </div>
)}        

        {tab === "conectores" && (
          <div
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              borderRadius: 18,
              padding: 22,
              boxShadow: "0 12px 30px rgba(30,58,95,0.08)",
            }}
          >
            <div style={{ marginBottom: 18 }}>
              <h2
                style={{
                  margin: 0,
                  color: NAVY,
                  fontSize: 22,
                  fontWeight: 800,
                }}
              >
                Status dos Conectores
              </h2>
              <p
                style={{
                  margin: "6px 0 0",
                  color: MUTED,
                  fontSize: 14,
                }}
              >
                Visão executiva das fontes públicas e integrações disponíveis no
                CreditLens.
              </p>
            </div>

            {!conectores && (
              <div
                style={{
                  padding: 18,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: 12,
                  color: MUTED,
                }}
              >
                Carregando status dos conectores...
              </div>
            )}

            {conectores && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: 12,
                }}
              >
                {Object.entries(conectores).map(([nome, info]) => (
                  <div
                    key={nome}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 14,
                      padding: 14,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 800,
                        color: NAVY,
                        marginBottom: 8,
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                      }}
                    >
                      {nome}
                    </div>

                    <ConectorBadge status={info?.status} />

                    {info?.mensagem && (
                      <div
                        style={{
                          marginTop: 8,
                          fontSize: 12,
                          color: MUTED,
                          lineHeight: 1.4,
                        }}
                      >
                        {info.mensagem}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* RODAPÉ */}
      <footer
        style={{
          maxWidth: 1400,
          margin: "0 auto",
          padding: "0 24px 28px",
          color: MUTED,
          fontSize: 12,
          textAlign: "center",
        }}
      >
        P.I.L.D.E.R™ — Método estruturado de análise e gestão de crédito ·
        Adolfo Pildervasser · Adolfo Financeiro
      </footer>
    </div>
  );
}
