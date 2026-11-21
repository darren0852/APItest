@echo off
echo [1/4] Starting local infrastructure...
cd /d C:\Users\ngdar\Desktop\APIgateway\infra
docker compose --profile dev up -d
cd /d C:\Users\ngdar\Desktop\APIgateway

echo [2/4] Starting FastAPI Backend (port 8000)...
set PYTHONIOENCODING=utf-8
set ENABLE_INTERNAL_MOCK=true
start "FastAPI" /min cmd /c "cd apps\api && python -m uvicorn main:app --port 8000 > ..\..\fastapi_run.log 2>&1"

echo [3/4] Starting Next.js Frontend (port 3000)...
cd /d C:\Users\ngdar\Desktop\APIgateway\apps\web
if not exist node_modules npm install
npm run build
start "Next.js" /min cmd /c "cd /d C:\Users\ngdar\Desktop\APIgateway\apps\web && npm run start"
cd /d C:\Users\ngdar\Desktop\APIgateway

echo [4/4] Waiting for services...
timeout /t 8 /nobreak > nul

curl -s -o nul -w "FastAPI 8000: %%{http_code}\n" http://localhost:8000/health
curl -s -o nul -w "Mock 9000: %%{http_code}\n" http://localhost:9000/v1/chat/completions
curl -s -o nul -w "Web 3000: %%{http_code}\n" http://localhost:3000

echo All local services started!
pause
