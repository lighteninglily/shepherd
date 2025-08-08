# Shepherd AI - Setup Guide

## Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- Google Cloud SDK
- Git

## Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   # On Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # On macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Set up Google Cloud credentials:
   - Place the `google-credentials.json` file in the root of the project
   - Set the `GOOGLE_APPLICATION_CREDENTIALS` path in your `.env` file

## Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Set up environment variables:
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local with your configuration
   ```

## Running the Application

### Backend

```bash
# From the backend directory
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### Frontend

```bash
# From the frontend directory
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Development Workflow

### Backend

- The backend uses FastAPI with automatic API documentation:
  - Swagger UI: `http://localhost:8000/api/docs`
  - ReDoc: `http://localhost:8000/api/redoc`

### Frontend

- The frontend uses Next.js with:
  - TypeScript for type safety
  - Tailwind CSS for styling
  - React Query for data fetching
  - NextAuth.js for authentication

## Deployment

### Backend

The backend is configured for deployment to Google Cloud Run. To deploy:

```bash
# Build the Docker image
gcloud builds submit --tag gcr.io/shepherd-468202/shepherd-backend

# Deploy to Cloud Run
gcloud run deploy shepherd-backend \
  --image gcr.io/shepherd-468202/shepherd-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars=ENVIRONMENT=production
```

### Frontend

The frontend can be deployed to Vercel, Netlify, or any static hosting service that supports Next.js.

## Environment Variables

### Backend (`.env`)

```
# App
ENVIRONMENT=development
PORT=8000
CORS_ORIGINS=http://localhost:3000

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=google-credentials.json
GOOGLE_CLOUD_PROJECT=shepherd-468202

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/shepherd
```

### Frontend (`.env.local`)

```
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_APP_ENV=development

# Authentication
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret

# Google OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Project Structure

```
shepherd/
├── backend/               # FastAPI backend
│   ├── app/              # Application code
│   │   ├── api/          # API routes
│   │   ├── core/         # Core functionality
│   │   ├── models/       # Database models
│   │   ├── services/     # Business logic
│   │   └── utils/        # Utility functions
│   ├── tests/            # Test files
│   └── requirements.txt  # Python dependencies
│
└── frontend/             # Next.js frontend
    ├── app/             # App router
    ├── components/      # Reusable components
    ├── lib/            # Utility functions
    └── styles/         # Global styles
```

## Next Steps

1. Set up a PostgreSQL database
2. Configure authentication providers
3. Implement the core chat functionality
4. Add analytics and monitoring
5. Set up CI/CD pipelines
