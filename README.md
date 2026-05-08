# CreditLens v2.0
**Pipeline de Análise de Crédito por CNPJ — Web App Completo**

---

## Arquitetura

```
creditlens/
├── backend/          → FastAPI + Python (deploy no Render)
│   ├── main.py       → Pipeline completo de crédito
│   └── requirements.txt
└── frontend/         → React (deploy no Vercel)
    ├── src/
    │   ├── App.js
    │   ├── hooks/useApi.js
    │   ├── pages/AnalisePage.js
    │   ├── pages/CarteiraPage.js
    │   └── components/ui.js
    └── public/index.html
```

---

## Módulo de Crédito — Integridade Garantida

O motor de score (`ScoreEngine`) avalia **6 dimensões**:

| Dimensão     | Conector         | Status          | Peso máx |
|--------------|------------------|-----------------|----------|
| Cadastral    | BrasilAPI/ReceitaWS | ✓ Ativo      | +26 pts  |
| Fiscal       | PGFN             | Placeholder     | +12 pts  |
| Judicial     | DataJud/CNJ      | Ativo parcial   | +3 pts   |
| Reputação    | —                | Placeholder     | +4 pts   |
| Setorial     | CNAE heurístico  | ✓ Ativo         | +8 pts   |
| Financeiro   | ERP/Balanço      | Placeholder     | +8 pts   |

**Princípio conservador:** conector ausente = penalidade (nunca aprovação tácita).

---

## Deploy — Passo a Passo

### 1. Backend no Render (gratuito)

1. Acesse https://render.com e crie conta
2. New → Web Service → conecte seu GitHub
3. Selecione a pasta `backend/`
4. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment:** Python 3.11
5. Deploy → copie a URL gerada (ex: `https://creditlens-api.onrender.com`)

### 2. Frontend no Vercel (gratuito)

1. Acesse https://vercel.com e crie conta
2. New Project → importe o repositório
3. Selecione a pasta `frontend/` como Root Directory
4. Em **Environment Variables**, adicione:
   - `REACT_APP_API_URL` = URL do Render (passo anterior)
5. Deploy → seu app está no ar!

---

## Rodando localmente

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API disponível em: http://localhost:8000
Docs automáticas: http://localhost:8000/docs

### Frontend
```bash
cd frontend
cp .env.example .env
npm install
npm start
```
App disponível em: http://localhost:3000

---

## Endpoints da API

| Método | Endpoint              | Descrição                        |
|--------|-----------------------|----------------------------------|
| GET    | `/health`             | Status da API                    |
| POST   | `/api/analisar`       | Análise pontual `{"cnpj":"..."}`  |
| GET    | `/api/analisar/{cnpj}`| Análise pontual via GET           |
| POST   | `/api/lote`           | Upload Excel (coluna: cnpj)      |
| GET    | `/api/pdf/{cnpj}`     | Gera PDF da análise              |
| GET    | `/api/conectores`     | Status dos conectores            |

---

## Conectores — Como Evoluir

Cada adaptador em `main.py` é independente. Para plugar um novo:

```python
class PGFNAdapter:
    @staticmethod
    def consultar(cnpj: str) -> FiscalData:
        # Substitua este bloco pela sua integração
        r = requests.get(f"https://sua-api-pgfn.com/{cnpj}")
        ...
        return FiscalData(pgfn_listado=..., evidence=Evidence(...))
```

O motor de score já sabe interpretar os status:
`confirmacao | ausencia | indicio | evidencia | nao_consultado | erro`

---

## Próximas Evoluções Sugeridas

- [ ] Autenticação (login por time)
- [ ] Histórico de análises (banco de dados)
- [ ] Agendamento de reprocessamento da carteira
- [ ] Alerta automático por e-mail/WhatsApp
- [ ] Score por matriz (CNPJ raiz + filiais)
- [ ] Integração PGFN via certidão automatizada
- [ ] Leitura de balanço/balancete em Excel

---

*CreditLens v2.0 — Adolfo | Crédito & Cobrança Pro*
