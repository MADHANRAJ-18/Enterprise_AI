# Enterprise AI Assistant

An Enterprise-grade AI Knowledge Assistant powered by React + Vite frontend and FastAPI + LangGraph + FAISS backend.

## Project Structure

```
Enterprise_AI_Assisstant/
├── frontend/          # React frontend (Vite, TailwindCSS, Framer Motion)
│   ├── src/           # Components, pages, router, services, context
│   ├── package.json   # Frontend dependencies
│   ├── .env           # Frontend environment variables
│   └── ...
├── backend/           # FastAPI backend (Groq LLM, FAISS vector search, Supabase)
│   ├── api/           # Endpoints for documents, processing, chat, and RAG
│   ├── database/      # Database client setup
│   ├── models/        # Pydantic schemas
│   ├── processing/    # Embeddings & document processing pipeline
│   ├── services/      # LLM and RAG services
│   ├── main.py        # FastAPI server entry point
│   ├── requirements.txt # Python dependencies
│   └── ...
└── start.bat          # Script to run frontend dev server
```

## Running the Application

### 1. Frontend Setup & Run
Navigating to the `frontend` folder:
```bash
cd frontend
npm install
npm run dev
```
Or run `start.bat` from the root directory.

### 2. Backend Setup & Run
Navigating to the `backend` folder:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
Backend API docs will be available at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
