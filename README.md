<div align="center">

# 📜 The Reader Codex

**Personal Reading Tracker • Local-First • Offline Ready • Google Sync Optional**

O **The Reader Codex** é um aplicativo desktop para organizar e acompanhar livros, mangás, manhwas, HQs, artigos e outras obras sem perder o ponto em que a leitura parou.

O sistema utiliza **SQLite como fonte principal dos dados**, permitindo funcionamento totalmente offline, com sincronização opcional através do **Google Sheets e Google Drive**.

**Read. Track. Continue.**

</div>

---

## ✨ Funcionalidades

- 📚 Cadastro, edição e organização de livros, mangás, manhwas, HQs e outras obras
- 🖼️ Capas personalizadas, com troca e remoção
- 📖 Controle de progresso por **páginas ou capítulos**
- ⚡ Atualização rápida de progresso nos cards e detalhes
- ⭐ Favoritos separados da avaliação
- 🌟 Avaliação de **0,5 a 5 estrelas**
- 🏷️ Categorias e tags personalizadas
- 📝 Sinopse e notas pessoais
- 🔗 Link direto para leitura no navegador padrão
- 🔍 Busca e filtros por título, categoria, tags, status de leitura e status da obra
- 🕘 Histórico de leitura
- 🎯 Metas de leitura
- 📊 Estatísticas da biblioteca
- 📅 Calendário e acompanhamento de lançamentos
- 💤 Pausa automática por inatividade configurável
- 📴 Funcionamento totalmente offline
- ☁️ Sincronização bidirecional opcional com Google
- 💾 Backup JSON, ZIP completo com capas e backups automáticos locais
- 🔄 Migração automática de bancos SQLite de versões anteriores

---

## 🎨 Interface

A interface desktop é construída com **PySide6 / Qt 6** e utiliza o tema visual **Nocturne Folio**.

---

## 🛠️ Tecnologias

- **Python 3.10+ 64-bit**
- **PySide6 / Qt 6**
- **SQLite**
- **Pillow**
- **PyInstaller**
- **Inno Setup 6/7**
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

Isso permite que toda a biblioteca continue disponível sem internet. Quando a sincronização está habilitada, as alterações locais podem ser enviadas posteriormente para a nuvem.

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

Requer **Python 3.10+ 64-bit**.

Crie o ambiente virtual:

```powershell
python -m venv .venv
```

No Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Execute:

```powershell
python main.py
```

O banco SQLite será criado automaticamente na primeira execução.

---

## 🪟 Gerando o instalador Windows

O projeto utiliza:

**PyInstaller → Inno Setup → instalador `.exe`**

Instale previamente:

- Python 3.10+ 64-bit
- Inno Setup 6 ou 7

No PowerShell, dentro da pasta do projeto:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build-installer.ps1
```

O script:

1. lê automaticamente a versão de `app/version.py`
2. cria ou reutiliza `.venv-build`
3. instala e atualiza as dependências
4. executa os testes automatizados
5. gera o aplicativo com PyInstaller
6. localiza o Inno Setup
7. passa a versão atual para o Inno Setup
8. gera o instalador final

O resultado fica em:

```text
installer-output/
└── TheReaderCodex-Setup-X.X.X.exe
```

---

## 📂 Dados do usuário

Banco, capas, backups, logs, configurações, credenciais locais e tokens ficam separados dos arquivos do aplicativo.

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

Também é possível utilizar **service account**, desde que a planilha e a pasta do Drive tenham as permissões necessárias.

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
- sincronização dos campos de publicação, agenda e link de leitura
- atualização remota de capas
- funcionamento offline

---

## 💾 Backup

O sistema possui três formas principais de proteção dos dados.

### JSON
Exporta os metadados estruturados.

### ZIP completo
Exporta os metadados e as capas da biblioteca.
É o formato recomendado para transferência entre computadores.

### Backup automático
O sistema também gera backups locais com rotação das versões mais recentes.
Antes de uma restauração feita pela interface, a biblioteca atual é protegida com um backup preventivo.

---

## 🧪 Testes

Execute:

```powershell
python -W error::ResourceWarning -m unittest discover -s tests -v
```

A suíte atual possui **43 testes automatizados** e cobre, entre outros:

- primeira execução vazia
- CRUD de obras
- categorias e tipo de progresso
- tags e filtros
- avaliações em meia estrela
- progresso por páginas e capítulos
- status de leitura e status de publicação
- datas brasileiras
- agendas semanal, quinzenal e mensal
- lançamentos de ontem, hoje e amanhã
- capítulos pendentes
- hiato preservando agenda
- pausa automática por inatividade
- metas e histórico
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