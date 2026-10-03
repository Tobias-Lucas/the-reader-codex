<div align="center">

# 📜 The Reader Codex

**Personal Reading Tracker • Local-First • Offline Ready**

O **The Reader Codex** é um gerenciador pessoal de leituras criado para acompanhar livros, mangás, HQs e outras obras sem perder o ponto em que a leitura parou.

O projeto começou integrado diretamente ao Google Sheets e evoluiu para uma arquitetura **local-first**, utilizando SQLite como fonte principal dos dados e permitindo funcionamento offline.

</div>

---

## ✨ Funcionalidades

- 📚 Organização de livros, mangás, HQs e outras categorias
- 📖 Controle de progresso por páginas ou capítulos
- ⚡ Atualização rápida de progresso
- 🕘 Histórico de leitura
- 📴 Funcionamento offline
- ☁️ Arquitetura preparada para sincronização em nuvem
- 🔄 Controle de alterações pendentes de sincronização
- 🎨 Interface desktop com CustomTkinter
- 🔍 Estrutura preparada para busca, filtros e categorias dinâmicas

---

## 🛠️ Tecnologias

- **Python 3.10+**
- **CustomTkinter**
- **SQLite**
- **Pillow**
- **UUID**
- **Threading**
- **Google Sheets API**
- **Google Drive API**

---

## 🧱 Arquitetura

```text
CustomTkinter UI
       │
       ▼
     SQLite
       │
       ▼
   Sync Engine
       │
       ▼
 Remote Provider
```

A aplicação trabalha primeiro com o banco local.

Isso permite que a biblioteca continue funcionando normalmente sem internet e que as alterações sejam sincronizadas posteriormente.

Mais detalhes em [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 📁 Estrutura

```text
the-reader-codex/
│
├── main.py
├── requirements.txt
│
├── app/
│   ├── ui/
│   ├── components/
│   ├── models/
│   ├── repositories/
│   └── services/
│
└── data/
    └── reader.db
```

---

## 🚀 Executando

Clone o projeto:

```bash
git clone https://github.com/SEU-USUARIO/the-reader-codex.git
cd the-reader-codex
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

No Windows:

```bash
.venv\Scripts\activate
```

No Linux/macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute:

```bash
python main.py
```

O banco SQLite será criado automaticamente na primeira execução.

---

## 🤝 Contribuindo

Toda ajuda é bem-vinda! Para contribuir, basta fazer um fork do projeto, criar a sua branch com as alterações e enviar um Pull Request.

---

## 📝 Licença

Distribuído sob a licença **MIT**.

<div align="center">

**Read. Track. Continue.**

</div>
