# 🐕 Caramelo API – Guardião Digital da Pessoa Idosa

> *"O cão de guarda que mora no celular da vó"*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/python)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/atlas)
[![FIAP](https://img.shields.io/badge/FIAP-Global%20Solution%202026-red)](.)

<!-- Banner: adicione docs/assets/banner-github.png e descomente
<p align="center">
  <br />
  <img src="docs/assets/banner-github.png" alt="Banner Caramelo" width="1000"/>
  <br />
</p>
-->

## 🐾 Sobre o Projeto

O **Caramelo** é um assistente que protege e ajuda pessoas idosas no Brasil. Esta é a sua **API**: é aqui que o Caramelo abre links suspeitos longe do celular da vó e faz tarefas online junto com ela, **sempre pedindo permissão antes**. Projeto desenvolvido para a **FIAP Global Solution 2026 (CitizenTech)**. O cliente fica em [`caramelo-app`](https://github.com/evamyuu/caramelo-app).

| Funcionalidade | Status | Endpoint |
| --- | --- | --- |
| Análise isolada de links (navegador headless descartável, score explicável) | Real | `POST /api/v1/links/scan` |
| Navegação assistida com consentimento e entrega da senha para a pessoa | Real | `WS /api/v1/secure-session` |
| Score de risco de ligações (sinais ponderados e explicáveis) | Score real, ligação simulada | `POST /api/v1/calls/assess` |
| Insights anônimos de golpes (agregação no MongoDB) | Real | `GET /api/v1/insights/summary` |
| Chat com o assistente | Real quando há chave de LLM | `POST /api/v1/assistant/chat` |
| SIM Swap da operadora (CAMARA) e saldo via Open Finance | Stubs no formato real do payload | `GET /api/v1/accounts/balance` |

Documentação interativa: `http://localhost:8000/docs`.

---

## 🏗️ Arquitetura

O projeto segue uma **arquitetura em camadas com dependências apontando para dentro**: routers chamam serviços, e serviços dependem de contratos (`EventRepository`, `LLMProvider`), nunca de um fornecedor.

```text
caramelo-api/
├── app/
│   ├── main.py                 # Factory da aplicação e lifespan (composition root)
│   ├── config.py               # Configurações via variáveis de ambiente
│   ├── api/                    # Camada HTTP/WebSocket
│   │   ├── router.py           # Agregação da API v1
│   │   ├── routers/            # Um router por módulo (guard, companion, insights, secure_session, system)
│   │   ├── dependencies.py     # Injeção de dependências (repositórios)
│   │   └── schemas.py          # Modelos de requisição
│   ├── services/               # Regras de negócio: score de risco, scanner de links, sessão segura
│   ├── ai/                     # Camada de IA
│   │   ├── client.py           # Ponto de entrada agnóstico de modelo, com fallback determinístico
│   │   ├── prompts.py          # Todos os prompts, revisados em um só lugar
│   │   └── providers/          # Strategy por fornecedor: Anthropic, Gemini
│   ├── db/                     # Persistência
│   │   ├── mongo.py            # Ciclo de vida do cliente Atlas
│   │   └── repositories/       # Contrato + implementações MongoDB e em memória
│   ├── integrations/           # APIs parceiras (operadora, Open Finance) atrás de stubs
│   └── core/                   # Inicialização do navegador
│
├── demo_sites/                 # Páginas fictícias usadas na demo e nos testes e2e
├── tests/                      # Testes unitários e end-to-end
└── docs/                       # Notas de arquitetura
```

### Decisões de Design
- **Aberto para extensão** - Um novo fornecedor de IA é uma classe em `ai/providers`; um novo armazenamento é um repositório
- **A IA nunca decide a segurança** - Veredito, consentimento e credenciais são garantidos em código. O modelo só redige explicações e sugere passos de navegação, e o serviço funciona sem modelo nenhum (modo `rules`)
- **Privacidade desde a concepção** - Eventos de risco não guardam telefone, URL nem id de usuário, e expiram por índice TTL. Senhas digitadas durante a entrega são repassadas à página e nunca registradas em log nem enviadas a um modelo

Mais detalhes em [`docs/architecture.md`](docs/architecture.md) e [`SECURITY.md`](SECURITY.md).

---

## 🚀 Tecnologias Utilizadas

### Core Backend
- **FastAPI + Uvicorn** - HTTP e WebSocket assíncronos
- **Playwright (Chromium)** - Sessões de navegador descartáveis e isoladas

### Inteligência Artificial
- **Anthropic Claude / Google Gemini** - LLM plugável e opcional
- **Modo `rules`** - Fallback determinístico quando nenhuma chave está configurada

### Dados & Infraestrutura
- **MongoDB Atlas (PyMongo Async)** - Eventos de risco, agregação `$facet`, índice TTL, Stable API v1
- **Docker** - Conteinerização e ambiente isolado
- **GitHub Actions** - Integração contínua
- **Pytest + Ruff** - Testes e linting

---

## 🛠️ Como Executar

### Pré-requisitos
- Python (v3.11+)
- Docker e Docker Compose (opcional)

### Instalação e Execução

1. **Clone o repositório:**
```bash
git clone https://github.com/evamyuu/caramelo-api.git
cd caramelo-api
```

2. **Crie o ambiente virtual e instale as dependências:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

3. **Configure as variáveis de ambiente:**
```bash
cp .env.example .env
# Edite o .env para adicionar suas credenciais (Gemini, Anthropic, MongoDB Atlas, etc.)
```

| Variável | Finalidade | Padrão |
| --- | --- | --- |
| `GEMINI_API_KEY` | LLM do plano gratuito | vazio (modo `rules`) |
| `ANTHROPIC_API_KEY` | Tem prioridade sobre o Gemini | vazio |
| `MONGODB_URI` | String de conexão do Atlas | vazio (em memória) |
| `CORS_ORIGINS` | Origens web permitidas | `http://localhost:5173` |

4. **Suba a API:**
```bash
uvicorn app.main:app --reload
```

Ou com Docker (API + MongoDB local):
```bash
docker compose up --build
```

5. **Rode os testes e o lint:**
```bash
ruff check . && pytest
```

---

## 👥 Equipe

Agradecemos às seguintes pessoas que contribuíram para este projeto:

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/evamyuu">
        <img src="https://avatars.githubusercontent.com/u/109860924?v=4" width="100px;" alt="Evelin Brandão"/><br>
        <sub><b>evamyuu</b></sub>
      </a><br/>
      <sub>Full-Stack · IA + UX/UI</sub>
    </td>
    <td align="center">
      <a href="https://github.com/vncys">
        <img src="https://avatars.githubusercontent.com/u/98789877?v=4" width="100px;" alt="Vinicyus Oliveira"/><br>
        <sub><b>donax</b></sub>
      </a><br/>
      <sub>Full-Stack · Infra + UX/UI</sub>
    </td>
  </tr>
</table>

---

## 🤝 Como Contribuir

Caramelo é um projeto acadêmico open source. A melhor forma de contribuir é abrindo issues com sugestões ou bugs encontrados.

- **Issues**: Descreva o problema ou sugestão
- **Pull Requests**: Fork → branch → PR com descrição clara, seguindo [Conventional Commits](https://www.conventionalcommits.org) e rodando `ruff check . && pytest` antes

---

## 📝 Licença

Este projeto está sob licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div>
  <p>Desenvolvido com 🤎 por Caramelo</p>
</div>
