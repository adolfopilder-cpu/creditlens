// src/hooks/useApi.js
const API_BASE = process.env.REACT_APP_API_URL || "";

export async function analisarCNPJ(cnpj) {
  const res = await fetch(`${API_BASE}/api/analisar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cnpj }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erro HTTP ${res.status}`);
  }
  return res.json();
}

export async function analisarComAnexo(cnpj, balanco, cisp) {
  const form = new FormData();
  form.append("cnpj", cnpj);
  if (balanco) form.append("balanco", balanco);
  if (cisp) form.append("cisp", cisp);
  const res = await fetch(`${API_BASE}/api/analisar-com-anexo`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erro HTTP ${res.status}`);
  }
  return res.json();
}

export async function processarLote(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/lote`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erro HTTP ${res.status}`);
  }
  return res.json();
}

export async function statusConectores() {
  const res = await fetch(`${API_BASE}/api/conectores`);
  return res.json();
}

export async function baixarPDF(cnpj) {
  const res = await fetch(`${API_BASE}/api/pdf/${cnpj}`);
  const data = await res.json();
  const bytes = atob(data.pdf_base64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  const blob = new Blob([arr], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = data.filename;
  a.click();
  URL.revokeObjectURL(url);
}
