# Architecture

Este documento descreve a arquitetura atual do **The Reader Codex** e as decisões técnicas adotadas durante sua evolução.

---

## Visão Geral

O projeto segue uma abordagem **local-first**.

```text
┌──────────────────────┐
│    CustomTkinter UI  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│        SQLite        │
│   Local Database     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│      Sync Engine     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Remote Provider    │
│ Google / Adapter API │
└──────────────────────┘
```

A interface não depende diretamente de serviços externos.

Todas as operações são realizadas primeiro no banco local.

---

## Por que Local-First?

A primeira versão do projeto utilizava diretamente Google Sheets e Google Drive.

Fluxo inicial:

```text
UI
 ↓
Google APIs
```

Isso funcionava, mas criava alguns problemas:

- dependência de internet;
- latência da API afetando a interface;
- maior acoplamento ao Google;
- dificuldade para executar o projeto sem credenciais;
- menor resiliência a falhas de rede.

A arquitetura foi então alterada para:

```text
UI
 ↓
SQLite
 ↓
Sync Engine
 ↓
Remote Provider
```

Com isso, o aplicativo pode continuar funcionando mesmo sem internet.

---

## Camadas

### UI

Responsável pela apresentação e interação com o usuário.

Localização:

```text
app/ui/
app/components/
```

A UI não deve executar consultas SQL diretamente.

---

### Models

Representam as principais entidades do domínio.

Exemplo:

```text
Work
```

Campos típicos:

```text
id
name
category
progress_unit
progress_current
progress_total
status
release_day
synopsis
created_at
updated_at
```

Localização:

```text
app/models/
```

---

### Repository

Responsável pela persistência local.

Localização:

```text
app/repositories/
```

Exemplo:

```python
repository.list_all()
repository.create(...)
repository.increment_progress(...)
```

Essa camada isola a aplicação dos detalhes do SQLite.

---

### Sync Engine

Responsável por sincronizar dados locais com serviços remotos.

Localização:

```text
app/services/
```

Estados previstos:

```text
PENDING_CREATE
PENDING_UPDATE
PENDING_DELETE
SYNCED
```

---

## Estratégia de Sincronização

Fluxo básico:

```text
Usuário altera dado
        │
        ▼
SQLite salva localmente
        │
        ▼
Registro fica pendente
        │
        ▼
Internet disponível
        │
        ▼
Sync Engine processa
        │
        ▼
Remote Provider
        │
        ▼
Registro marcado como SYNCED
```

---

## IDs

As entidades utilizam UUID.

Exemplo:

```text
6fb8ea92-ec84-4c35-a422-f72063c53db8
```

Isso reduz conflitos entre registros criados em diferentes dispositivos.

---

## Controle de Atualização

Cada entidade possui campos como:

```text
created_at
updated_at
deleted_at
```

O campo `updated_at` pode ser usado na resolução de conflitos.

A estratégia inicial é:

```text
last write wins
```

Ou seja, a versão mais recente substitui a mais antiga.

No futuro, algumas entidades podem utilizar regras específicas por campo.

---

## Exclusão Lógica

Para sincronização, exclusões devem preferencialmente utilizar `deleted_at` em vez de apagar imediatamente o registro.

Exemplo:

```text
deleted_at = 2026-09-28T14:35:00Z
```

Assim, outros dispositivos também podem receber a informação de remoção.

---

## Capas

As capas devem ser mantidas em cache local.

Estrutura prevista:

```text
data/
└── cache/
    └── covers/
```

A versão remota pode permanecer no Google Drive ou em outro provider.

---

## Threading

Chamadas remotas não devem bloquear a thread principal do CustomTkinter.

Fluxo:

```text
UI Thread
   │
   └── Background Worker
            │
            ▼
        Sync Engine
```

A UI deve ser atualizada novamente através do loop principal.

---

## Providers Remotos

O Sync Engine foi pensado para aceitar adapters.

Exemplos futuros:

```text
GoogleSheetsAdapter
GoogleDriveAdapter
RESTAdapter
WebDAVAdapter
```

A UI e o SQLite não devem precisar ser alterados para trocar de provider.

---

## Princípios do Projeto

- local-first;
- offline-first;
- baixo acoplamento;
- componentes reutilizáveis;
- separação de responsabilidades;
- fácil instalação;
- possibilidade de extensão futura.
