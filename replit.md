# Medicina com IA

## Overview
Medical AI transcription application built with FastAPI. Users can record consultations, transcribe audio via OpenAI Whisper, generate reports with AI, and download them as Word documents.

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
      css/theme.css      - Shared modern CSS theme
      html/              - Jinja2 HTML templates (login, cadastro, dashboard, main)
      js/                - Frontend JavaScript files
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

## Recent Changes (Feb 2026)
- Adapted database connection to use Replit DATABASE_URL
- Updated Redis URLs from Docker hostname to localhost
- Modernized all 4 frontend pages with new CSS theme (Inter font, glass cards, gradient backgrounds)
- Created shared theme.css for consistent styling
- Added loading states and improved UX on login/register forms
