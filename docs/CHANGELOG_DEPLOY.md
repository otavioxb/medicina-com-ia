# Changelog de Deploy (manual)

Formato: data/hora UTC + resumo do que mudou.

## 2026-03-08
- Migração do proxy para apontar `transcricao.alumia.tech` para o novo stack (FastAPI/Celery).
- Backups criados do legado e configs nginx.
- Correções:
  - acentuação PT-BR no cadastro/dashboard
  - normalização de profissão no dashboard
  - correção de JS no parar gravação
  - correção de OPENAI_API_KEY inválida
  - inclusão de novas finalidades médicas
  - prompts médicos adicionados em `app/modules/prompts.yaml`

