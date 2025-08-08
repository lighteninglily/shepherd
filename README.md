# Shepherd AI

A pastoral AI companion for spiritual guidance and support, built with modern web technologies.

## Project Structure

```
shepherd/
├── backend/           # FastAPI Python backend
├── frontend/         # Next.js React frontend
├── docs/             # Project documentation
└── scripts/          # Utility scripts
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google Cloud SDK
- Docker (for containerization)

### Environment Setup

1. Clone the repository
2. Set up the backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Set up the frontend:
   ```bash
   cd frontend
   npm install
   ```

## Configuration

Create `.env` files in both `backend/` and `frontend/` directories using the provided `.env.example` files.

## Development

### Backend

```bash
cd backend
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm run dev
```

## Deployment

See `DEPLOYMENT.md` for detailed deployment instructions.

## License

This project is proprietary and confidential.
