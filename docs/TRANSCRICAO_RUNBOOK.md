# Transcrição AlumIA — Runbook / Documentação Viva

Este documento é a **fonte de verdade operacional** do deploy do serviço `transcricao.alumia.tech` no servidor.

> Regra de ouro: **não registrar segredos (tokens/keys) em texto puro no Git**.
> Registre apenas **nomes de variáveis**, formatos e onde configurar.

---

## 1) Ambiente

- **URL pública:** https://transcricao.alumia.tech
- **Servidor:** Droplet/VM (Ubuntu) acessado como `root`
- **Acesso SSH (no OpenClaw):**
  - Usamos uma chave `ed25519` gerada no host OpenClaw.
  - A *public key* foi adicionada ao servidor em `/root/.ssh/authorized_keys`.

### Pastas principais no servidor

- **Projeto (repo):** `/root/deploy/medicina-com-ia`
- **App (compose / build):** `/root/deploy/medicina-com-ia/medicina_com_ia`
- **Backups (legado e configs):** `/root/BACKUPS/`

### Serviços/containers

Stack **novo** (docker compose project: `medicina_com_ia`):
- `fastapi_app` (backend + estáticos)
- `celery_worker`
- `celery_beat`
- `medicina_com_ia-db-1` (Postgres)
- `medicina_com_ia-redis-1` (Redis)
- `init_db` (job de inicialização / migração inicial)

Stack **legado** (mantido):
- `flask_app` (+ worker, postgres, redis do legado)

> Política de segurança/rollback (Otavio): **não deletar o legado**.
> Só remover mediante ordem explícita.

---

## 2) Configuração (variáveis de ambiente)

### Arquivo `.env` efetivo do serviço novo

Local: `/root/deploy/medicina-com-ia/medicina_com_ia/.env`

Variáveis esperadas (exemplos de nomes; **não colocar valores no Git**):
- `OPENAI_API_KEY` — necessário para transcrição (Whisper via OpenAI)
- `CADASTRO_TOKENS` — tokens permitidos para cadastro (CSV)

Banco/Redis (forma atual):
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DB_HOST` (deve ser `db` dentro do compose)
- `DB_PORT` (5432)
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `REDIS_BROKER_URL` (deve ser `redis://redis:6379/0`)

> Observação: o arquivo `.env` é **local do servidor** e não deve ir pro repositório.

---

## 3) Reverse proxy / TLS

- O TLS termina no **nginx**.
- VHost: `/etc/nginx/sites-available/transcricao.alumia.tech`
- Upstream atual (novo serviço): `proxy_pass http://127.0.0.1:8001;`

O backend do compose roda em `:8000` dentro do container, exposto no host em:
- `8001 -> 8000` (para o nginx)

---

## 4) Git workflow (pedido do Otavio)

- O estado estável atual deve ficar salvo no **`main`**.
- Desenvolvimento deve acontecer em branch **feature**.

Branches:
- `main` — estável
- `feature/scale-a` — desenvolvimento da Proposta A (escala)

---

## 5) Histórico resumido do que já foi corrigido

### UX / PT-BR / Profissão
- Correção de acentuação em telas (`cadastro.html`, `dashboard.html`).
- Normalização de profissão no dashboard (`dashboard.js`).
- Normalização no fluxo de sessão para “Finalidades” (mapeando `medico` → `Médico`).
- Ajuste no banco para corrigir `users.profissao` quando necessário.

### Transcrição
- Corrigido `OPENAI_API_KEY` inválida (401) e reiniciado stack.

### Bug de parar gravação
- Corrigido JS: variável `duracaoConsultaParcial` inexistente ao parar gravação.

### Novas finalidades médicas
- Adicionadas:
  - Consulta de Dermatologia
  - Exame de Colonoscopia
  - Exame de Endoscopia Digestiva Alta

### Prompts
- Prompts são carregados de: `medicina_com_ia/app/modules/prompts.yaml`

---

## 6) Proposta A (escala) — objetivo

Reduzir carga no Postgres em cenários de múltiplos usuários simultâneos:

Problema atual:
- a cada ~8s um chunk gera transcrição e persistência frequente no Postgres,
- polling do frontend bate em endpoints repetidamente,
- número de conexões/transações cresce muito.

Direção (Proposta A):
1) **Redis como store de transcrição parcial** (com TTL)
2) **Checkpoint no Postgres** (persistência consolidada por intervalo / ao final)
3) **Push via WebSocket/SSE** (reduzir/abolir polling)

---

## 7) Checklist operacional

### Reiniciar stack (aplicar `.env` novo)

```bash
cd /root/deploy/medicina-com-ia/medicina_com_ia
docker compose -p medicina_com_ia up -d --force-recreate
```

### Ver logs

```bash
docker logs fastapi_app --tail 200
docker logs celery_worker --tail 200
```

### Ver status

```bash
docker compose -p medicina_com_ia ps
```

---

## 8) TODO (próximos passos)

Ver `docs/SCALE_A_PLAN.md`.

