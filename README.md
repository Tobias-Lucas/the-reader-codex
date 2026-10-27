<div align="center">

# 📜 The Reader Codex

**Personal Reading Tracker • Local-First • Offline Ready • Google Sync Optional**

O **The Reader Codex** é um aplicativo desktop para organizar e acompanhar livros, mangás, manhwas, HQs, artigos e outras obras sem perder o ponto em que a leitura parou.

O sistema utiliza **SQLite como fonte principal dos dados**, permitindo funcionamento totalmente offline, com sincronização opcional através do **Google Sheets e Google Drive**.

**Read. Track. Continue.**

</div>

---

## ✨ Funcionalidades

- 📚 Cadastro e organização de livros, mangás, manhwas, HQs e outras obras
- 🖼️ Capas personalizadas para cada obra
- 📖 Controle de progresso por **páginas ou capítulos**
- ⚡ Atualização rápida de progresso
- ⭐ Favoritos separados da avaliação
- 🌟 Avaliação de **0,5 a 5 estrelas**
- 🏷️ Categorias e tags personalizadas
- 📝 Sinopse e notas pessoais
- 🔗 Link direto para leitura
- 🔍 Busca e filtros por título, categoria, tags e status
- 🕘 Histórico de leitura
- 🎯 Metas de leitura
- 📊 Estatísticas da biblioteca
- 📅 Calendário e acompanhamento de lançamentos
- 📴 Funcionamento totalmente offline
- ☁️ Sincronização opcional com Google
- 💾 Backup completo da biblioteca
- 🔄 Migração automática de bancos de versões anteriores

---

## 📖 Acompanhamento de leitura

O The Reader Codex separa o **status da obra** do seu **status pessoal de leitura**.

### Status da obra

- Em lançamento
- Completo
- Em hiato
- Cancelado

### Status de leitura

- Quero ler
- Lendo
- Pausado
- Concluído
- Abandonado

Para obras seriadas, o sistema destaca o **último capítulo lido**, acompanha capítulos pendentes e pode calcular previsões de novos lançamentos.

---

## 🛠️ Tecnologias

- **Python 3.10+**
- **PySide6 / Qt 6**
- **SQLite**
- **Pillow**
- **PyInstaller**
- **Inno Setup**
- **Google Sheets API**
- **Google Drive API**
- **Google OAuth 2.0**

---

## 🧱 Arquitetura

```text
        PySide6 / Qt 6 UI
                │
                ▼
          Application Layer
                │
                ▼
             SQLite
          Local Database
                │
                ▼
            Sync Engine
          ┌─────┴─────┐
          ▼           ▼
   Google Sheets   Google Drive
     Metadados        Capas
```

A aplicação trabalha sempre primeiro com o banco local.

Isso significa que toda a biblioteca continua disponível mesmo sem internet. Quando a sincronização está habilitada, as alterações locais podem ser enviadas posteriormente para a nuvem.

---

## 📁 Estrutura

```text
the-reader-codex/
│
├── main.py
├── requirements.txt
├── requirements-build.txt
├── TheReaderCodex.spec
├── build-installer.ps1
├── BUILD_INSTALLER.md
│
├── app/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   ├── ui/
│   └── utils/
│
├── assets/
│   └── icons/
│
├── installer/
│   └── TheReaderCodex.iss
│
├── tests/
│
└── data/
    └── .gitkeep
```

---

## 🚀 Executando em desenvolvimento

Clone o projeto:

```bash
git clone https://github.com/SEU-USUARIO/the-reader-codex.git
cd the-reader-codex
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
```

### Linux / macOS

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

## 🪟 Gerando o instalador Windows

O projeto utiliza:

**PyInstaller → Inno Setup → instalador `.exe`**

No PowerShell, dentro da pasta do projeto:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build-installer.ps1
```

O script:

1. cria o ambiente de build
2. instala as dependências
3. executa os testes automatizados
4. gera o aplicativo com PyInstaller
5. localiza o Inno Setup
6. gera o instalador final

O resultado fica em:

```text
installer-output/
└── TheReaderCodex-Setup-X.X.X.exe
```

O instalador cria:

- entrada no Menu Iniciar
- desinstalador
- opção de atalho na Área de Trabalho
- instalação separada dos dados pessoais

---

## 📂 Dados do usuário

Em desenvolvimento:

```text
data/
├── reader.db
├── covers/
├── backups/
└── settings.json
```

No aplicativo instalado no Windows:

```text
%LOCALAPPDATA%\TheReaderCodex\
```

Banco, capas, backups, configurações e tokens ficam separados dos arquivos do aplicativo.

Dessa forma, atualizar ou reinstalar o programa não apaga a biblioteca.

---

## ☁️ Sincronização Google

A sincronização é opcional.

Sem uma conta Google configurada, o The Reader Codex continua funcionando normalmente de forma local.

### OAuth Desktop

É o método recomendado.

No Google Cloud:

1. habilite a **Google Sheets API**
2. habilite a **Google Drive API**
3. crie um **OAuth Client ID**
4. escolha o tipo **Desktop app**
5. baixe o arquivo JSON

Depois, no The Reader Codex:

```text
Configurações
→ Credenciais Google
→ Selecionar JSON
→ Testar conexão
```

Na primeira autorização, o navegador será aberto para login na conta Google.

---

## 📊 Google Sheets

Quando configurado, o sistema utiliza as abas:

```text
Works
Categories
Goals
History
Meta
```

Se nenhuma planilha tiver sido informada, o aplicativo pode localizar ou criar automaticamente a estrutura necessária.

Os metadados ficam no **Google Sheets** e as capas ficam no **Google Drive**.

---

## 🔄 Sincronização

O fluxo básico é:

```text
SQLite local
      │
      ▼
 Sync Engine
      │
      ├── Google Sheets
      │      Metadados
      │
      └── Google Drive
             Capas
```

A sincronização suporta:

- alterações locais pendentes
- sincronização automática
- sincronização manual
- resolução de conflitos por `updated_at`
- propagação de exclusões
- atualização remota de capas
- funcionamento offline

---

## 💾 Backup

O sistema possui três formas principais de proteção dos dados.

### JSON

Exporta os metadados estruturados.

```text
library.json
```

### ZIP completo

Exporta:

```text
metadados
+
capas
```

É o formato recomendado para transferência entre computadores.

### Backup automático

O sistema também pode gerar backups locais automaticamente e manter as versões mais recentes.

---

## 🧪 Testes

Execute:

```bash
python -m unittest discover -s tests -v
```

A suíte automatizada cobre, entre outros:

- primeira execução vazia
- CRUD de obras
- categorias
- tags
- filtros
- avaliações em meia estrela
- progresso por páginas e capítulos
- status de leitura
- status de publicação
- datas
- agendas de lançamento
- capítulos pendentes
- metas
- histórico
- migração de banco
- backup e restauração
- Google Sync
- conflitos de sincronização
- sincronização de capas

---

## 🔐 Privacidade

O The Reader Codex segue uma arquitetura **local-first**.

Por padrão:

- sua biblioteca fica no seu computador
- nenhuma conta Google é obrigatória
- a sincronização pode permanecer desativada
- credenciais e tokens não são incluídos no código-fonte nem no instalador
- backups e banco de dados não fazem parte dos pacotes distribuídos

---

## 🤝 Contribuindo

Contribuições são bem-vindas.

Para contribuir:

1. faça um fork do projeto
2. crie uma branch para sua alteração
3. faça os commits
4. envie um Pull Request

---

## 📝 Licença

Distribuído sob a licença **MIT**.

---

<div align="center">

### 📜 The Reader Codex

**Read. Track. Continue.**

Uma biblioteca pessoal para você sempre saber onde parou.

</div>