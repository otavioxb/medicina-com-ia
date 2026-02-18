# Transcricoes AlumIA

## Overview
AI-powered transcription and report generation platform serving multiple professional contexts (medical, psychological, legal, administrative). Built with FastAPI, featuring real-time audio transcription via OpenAI Whisper, AI report generation, and Word document downloads.

## Brand Identity
- **Name**: Transcricoes AlumIA
- **Colors**: Navy blue (#1e3a6e primary), Gold (#d4a843 accent)
- **Logo**: `/static/img/alumia_logo.jpeg`

## Project Architecture
- **Backend**: FastAPI (Python 3.11) with PostgreSQL database and Redis for session management
- **Frontend**: Server-rendered HTML/Jinja2 templates with Bootstrap 5 and custom CSS theme
- **Task Queue**: Celery with Redis broker for async audio transcription
- **WebSocket**: Real-time communication for live transcription updates

## Structure
```
medicina_com_ia/
  app/
    main.py              - FastAPI app entry point
    static/
      css/theme.css      - Shared AlumIA brand CSS theme
      html/              - Jinja2 HTML templates (login, cadastro, dashboard, main)
      js/                - Frontend JavaScript files
      img/               - Brand assets (AlumIA logo)
    routers/             - API route handlers
    db/                  - Database models, schemas, migrations
    modules/             - Business logic (transcription, reports, cache)
    celery_app/          - Celery async tasks
```

## Key Configuration
- App runs on port 5000
- Redis runs locally on port 6379 (started via workflow)
- PostgreSQL via Replit built-in database (DATABASE_URL)
- OpenAI API key stored as secret

## User Credentials
- Email: otavioxb@gmail.com / Password: teste1234

## Terminology Mapping
Frontend terms have been genericized while backend database schema retains original field names:
- Paciente -> Participante (frontend only)
- Consulta -> Sessao (frontend only)
- Prontuario -> Relatorio (frontend only)
- Nova Consulta -> Nova Sessao (frontend only)
- Necessidade -> Finalidade (frontend labels)

## Recent Changes (Feb 2026)
- Rebranded from "Medicina com IA" to "Transcricoes AlumIA" with official logo
- Updated theme.css with AlumIA brand colors (navy blue + gold accent)
- Replaced all medical terminology with generic terms across all HTML pages and JS files
- Added AlumIA logo to sidebar, login hero, and registration hero
- Added "Administrador" profession option in registration
- Adapted database connection to use Replit DATABASE_URL
- Updated Redis URLs from Docker hostname to localhost
- Fixed Celery worker startup (must cd into medicina_com_ia directory first)
- Added empty transcription guard to prevent AI from hallucinating report content
- Fixed download race condition with Promise-based WebSocket confirmation callback
