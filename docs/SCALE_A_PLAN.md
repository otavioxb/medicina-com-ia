# Proposta A — Plano de Escalabilidade (incremental)

Objetivo: reduzir conexões/transações no Postgres durante transcrição concorrente.

## Fase 0 — Medir (antes de mudar)

- [ ] Instrumentar contagem de queries por sessão (pelo menos logs por endpoint)
- [ ] Medir QPS no endpoint `/transcriptions/...` (polling)
- [ ] Medir conexões no Postgres (`pg_stat_activity`) durante 1 sessão e durante N sessões

## Fase 1 — Redis para parcial (sem alterar UX)

- [ ] Criar estrutura em Redis:
  - `session:{sessao_id}:partial_text` (string)
  - `session:{sessao_id}:chunks_done` (set) (ou stream)
  - TTL >= 12h (alinhado com sessão)
- [ ] Worker escreve parcial no Redis ao concluir chunk
- [ ] Backend `/transcriptions/...` lê primeiro do Redis (fallback Postgres)

## Fase 2 — Reduzir writes no Postgres (checkpoint)

- [ ] Persistir no Postgres apenas:
  - ao parar gravação, ou
  - a cada X segundos (ex: 30–60s), ou
  - a cada N chunks
- [ ] Manter tabela final como “fonte de verdade” para relatório

## Fase 3 — Push (remover polling)

- [ ] Backend publica update via WebSocket/SSE quando Redis recebe novo parcial
- [ ] Frontend atualiza UI por eventos (não por polling constante)

## Fase 4 — Hardening

- [ ] Timeouts, retries, idempotência por chunk_id
- [ ] Observabilidade (latência transcrição, taxa de erro, backlog)

