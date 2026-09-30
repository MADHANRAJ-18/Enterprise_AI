@echo off
title Enterprise AI Assistant Launcher
echo ===================================================
echo Starting Enterprise AI Assistant Services...
echo ===================================================

echo [1/2] Launching FastAPI Backend on port 8000...
start "Backend - FastAPI" cmd /k "cd backend && python -m uvicorn main:app --reload --port 8000"

echo [2/2] Launching React + Vite Frontend on port 5173...
start "Frontend - Vite" cmd /k "cd frontend && npm run dev"

echo.
echo Both servers are starting:
echo  - Backend API:   http://127.0.0.1:8000/docs
echo  - Frontend Web:  http://localhost:5173
echo ===================================================
