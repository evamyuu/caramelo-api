# 🐕 Caramelo API – Interface Agêntica para a Pessoa Idosa

> *"Todo mundo merece um caramelo do lado"*

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/python)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/atlas)
[![FIAP](https://img.shields.io/badge/FIAP-Global%20Solution%202026-red)](.)

<p align="center">
  <br />
  <img src="docs/assets/banner-github.png" alt="Banner Caramelo" width="1000"/>
  <br />
</p>

## 🐾 Sobre o Projeto

O **Caramelo** é uma interface agêntica que vira a tela do celular da pessoa idosa — um agente de IA que entende o que ela pede e **faz junto com ela**, cuidando do aparelho, da rotina e dos serviços do dia a dia, sempre com a pessoa no controle e protegendo contra golpes. Esta é a sua **API**, onde o Caramelo navega pelos serviços numa sala segura na nuvem, testa links suspeitos, responde com fonte e mapeia golpes. O app fica em [`caramelo-app`](https://github.com/evamyuu/caramelo-app).

---

## 🏗️ Arquitetura

Este projeto segue uma **arquitetura em camadas** com dependências apontando para dentro — routers chamam serviços, e serviços dependem de contratos, nunca de um fornecedor — e a **segurança decidida em código**, não pela IA:

```text
caramelo-api/
├── app/
│   ├── main.py                 # Composition root e ciclo de vida
│   ├── api/                    # Endpoints REST e WebSocket (sala segura)
│   ├── services/               # Regras de negócio: sala segura, modo guia, rotinas, links, mapa de golpes
│   ├── ai/                     # Prompts, guardrails de entrada e saída, provedores (Gemini, Claude)
│   ├── db/                     # Repositórios MongoDB Atlas e em memória
│   ├── knowledge/              # Base curada para o RAG
│   ├── integrations/           # Operadora (CAMARA) e Open Finance
│   └── core/                   # Navegador isolado (Playwright)
│
├── demo_sites/                 # Portal Cidadão fictício para demo e testes
├── tests/                      # Testes unitários e end-to-end
└── docs/                       # Arquitetura e decisões
```

---

## 🚀 Tecnologias Utilizadas

### Core Backend
- **FastAPI (Python)** - HTTP e WebSocket assíncronos
- **Playwright (Chromium)** - Sala segura: navegador isolado e descartável na nuvem

### Inteligência Artificial
- **Google Gemini** - Interpreta o pedido e conduz cada passo da navegação
- **RAG com Atlas Vector Search** - Respostas sempre com a fonte
- **Guardrails** - Contra prompt injection direta e indireta, com validação de saída

### Dados & Infraestrutura
- **MongoDB Atlas** - Base de conhecimento vetorial e eventos anônimos de golpe (agregação `$facet`)
- **Render** - API e app no ar
- **Docker** - Conteinerização e ambiente isolado
- **Pytest + Ruff** - Testes e linting

---

## 🛠️ Como Executar

### Pré-requisitos
- Python (v3.11+)
- Uma chave do Gemini e um cluster no MongoDB Atlas (opcionais: sem eles, a API roda com regras e memória local)

### Instalação e Execução

1. **Clone o repositório:**
```bash
git clone https://github.com/evamyuu/caramelo-api.git
cd caramelo-api
```

2. **Instale as dependências:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

3. **Configure as variáveis de ambiente:**
```bash
cp .env.example .env
# Edite o .env para adicionar suas credenciais (Gemini, MongoDB Atlas, etc.)
```

4. **Suba a API:**
```bash
uvicorn app.main:app --reload --env-file .env
```

A documentação interativa fica em `http://localhost:8000/docs`.

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
- **Pull Requests**: Fork → branch → PR com descrição clara

---

## 📝 Licença

Este projeto está sob licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div>
  <p>Desenvolvido com 🤎 por Caramelo</p>
</div>
