# Shepherd AI - Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Backend Deployment](#backend-deployment)
4. [Frontend Deployment](#frontend-deployment)
5. [Database Setup](#database-setup)
6. [Domain & SSL](#domain--ssl)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Monitoring & Logging](#monitoring--logging)
9. [Backup Strategy](#backup-strategy)
10. [Scaling](#scaling)

## Prerequisites

### Backend
- Python 3.9+
- PostgreSQL 13+
- Redis (for caching and background tasks)
- Docker (optional, for containerization)

### Frontend
- Node.js 18+
- npm or yarn

### Infrastructure
- Cloud provider account (Google Cloud, AWS, or Azure)
- Domain name
- SSL certificate

## Environment Setup

### Backend Environment Variables
Create a `.env` file in the backend directory with the following variables:

```env
# App
APP_ENV=production
SECRET_KEY=your-secret-key-here
DEBUG=false
ALLOWED_HOSTS=.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/shepherd

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET=your-jwt-secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Email (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-email-password
EMAIL_FROM=noreply@yourdomain.com

# Google Cloud (if using)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# OpenAI API (if applicable)
OPENAI_API_KEY=your-openai-api-key
```

### Frontend Environment Variables
Create a `.env.local` file in the frontend directory:

```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
NEXT_PUBLIC_SENTRY_DSN=your-sentry-dsn
```

## Backend Deployment

### Option 1: Docker (Recommended)

1. Build the Docker image:
   ```bash
   docker build -t shepherd-backend -f backend/Dockerfile .
   ```

2. Run the container:
   ```bash
   docker run -d \
     --name shepherd-backend \
     -p 8000:8000 \
     --env-file backend/.env \
     shepherd-backend
   ```

### Option 2: Manual Deployment

1. Install dependencies:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Run migrations:
   ```bash
   alembic upgrade head
   ```

3. Start the server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

## Frontend Deployment

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Build the application:
   ```bash
   npm run build
   ```

3. Start the production server:
   ```bash
   npm start
   ```

### Using Vercel (Recommended for Next.js)

1. Connect your GitHub/GitLab repository to Vercel
2. Set up environment variables in the Vercel dashboard
3. Deploy!

## Database Setup

### PostgreSQL

1. Create a production database:
   ```sql
   CREATE DATABASE shepherd_production;
   CREATE USER shepherd_user WITH PASSWORD 'secure-password';
   GRANT ALL PRIVILEGES ON DATABASE shepherd_production TO shepherd_user;
   ```

2. Run migrations:
   ```bash
   alembic upgrade head
   ```

### Redis

1. Install Redis:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   
   # macOS
   brew install redis
   ```

2. Start Redis:
   ```bash
   sudo systemctl start redis
   ```

## Domain & SSL

1. Point your domain to your server's IP address
2. Set up Nginx or Caddy as a reverse proxy
3. Obtain SSL certificates using Let's Encrypt:
   ```bash
   # Using certbot
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```

## CI/CD Pipeline

Example GitHub Actions workflow (`.github/workflows/deploy.yml`):

```yaml
name: Deploy

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
          
      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/postgres
        run: |
          cd backend
          pytest -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to production
        run: |
          # Add your deployment commands here
          echo "Deploying to production..."
```

## Monitoring & Logging

### Backend Logs
- Use structlog for structured logging
- Configure log rotation
- Set up log aggregation (e.g., ELK stack, Papertrail)

### Application Performance Monitoring (APM)
- Set up Sentry for error tracking
- Configure Prometheus and Grafana for metrics
- Set up alerts for critical issues

## Backup Strategy

### Database Backups
```bash
# Daily backup
0 3 * * * pg_dump -U postgres shepherd_production > /backups/shepherd_$(date +%Y%m%d).sql

# Weekly backup rotation
0 4 * * 0 find /backups -name "*.sql" -mtime +30 -delete
```

### Media Files
- Set up regular backups of uploaded files
- Consider using a cloud storage service with versioning

## Scaling

### Horizontal Scaling
- Set up a load balancer
- Configure multiple backend instances
- Use Redis for session storage

### Caching
- Implement Redis caching for frequent queries
- Use CDN for static assets
- Enable HTTP caching headers

### Database
- Set up read replicas for read-heavy workloads
- Implement connection pooling
- Monitor and optimize slow queries

## Maintenance

### Scheduled Tasks
- Set up cron jobs for periodic tasks
- Implement database maintenance tasks
- Schedule regular backups

### Security Updates
- Set up automatic security updates
- Regularly update dependencies
- Perform security audits

## Support

### Documentation
- Keep API documentation up to date
- Maintain a changelog
- Document known issues and workarounds

### Monitoring
- Set up uptime monitoring
- Configure error tracking
- Monitor performance metrics
