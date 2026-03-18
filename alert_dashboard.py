from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os
from datetime import datetime
from typing import List, Dict

app = FastAPI(title="AI Monitoring Incident Dashboard")

# Папка для логов
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "alerts_history.json")

# Убедимся, что папка существует
os.makedirs(LOG_DIR, exist_ok=True)

# Хранилище алертов в памяти (для быстрого отображения)
# Структура: { "firing": [...], "resolved": [...] }
active_alerts: List[Dict] = []
history_alerts: List[Dict] = []

def save_to_file(data: dict, status: str):
    """Сохраняет алерт в JSON файл с историей"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "data": data
    }
    
    # Читаем существующий файл или создаем новый
    history = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except json.JSONDecodeError:
            history = []
    
    history.append(entry)
    
    # Сохраняем обратно (храним последние 100 записей, чтобы файл не раздувался)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-100:], f, indent=2, ensure_ascii=False)
@app.post("/alert")
async def receive_alert(request: Request):
    """Эндпоинт для приема алертов от Alertmanager"""
    data = await request.json()
    status = data.get("status", "unknown")
    
    print(f"[{datetime.now()}] Received alert: {status} - {data.get('groupLabels', {}).get('alertname')}")
    
    save_to_file(data, status)
    
    global active_alerts 
    
    if status == "firing":
        for alert in data.get("alerts", []):
            exists = any(a.get('labels') == alert.get('labels') and a.get('status') == 'firing' for a in active_alerts)
            if not exists:
                active_alerts.append(alert)
                
    elif status == "resolved":
        labels_to_remove = [a.get('labels') for a in data.get("alerts", [])]
        active_alerts = [a for a in active_alerts if a.get('labels') not in labels_to_remove]
        
        for alert in data.get("alerts", []):
            alert['resolved_at'] = datetime.now().isoformat()
            history_alerts.append(alert)

    return JSONResponse(content={"status": "ok"})

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница дашборда"""
    
    # Генерируем HTML прямо здесь для простоты (можно вынести в template)
    firing_count = len(active_alerts)
    color_class = "bg-red-600" if firing_count > 0 else "bg-green-600"
    status_text = "SYSTEM CRITICAL" if firing_count > 0 else "ALL SYSTEMS NORMAL"
    
    alerts_html = ""
    if active_alerts:
        for alert in active_alerts:
            labels = alert.get('labels', {})
            annotations = alert.get('annotations', {})
            starts_at = alert.get('startsAt', 'Unknown')
            
            severity = labels.get('severity', 'unknown')
            sev_color = "red" if severity == "critical" else "orange" if severity == "warning" else "blue"
            
            alerts_html += f"""
            <div class="border-l-4 border-{sev_color}-500 bg-gray-800 p-4 mb-4 rounded shadow">
                <div class="flex justify-between items-start">
                    <h3 class="text-xl font-bold text-white">{labels.get('alertname', 'Unknown Alert')}</h3>
                    <span class="px-2 py-1 text-xs font-semibold text-white bg-{sev_color}-600 rounded uppercase">{severity}</span>
                </div>
                <p class="text-gray-300 mt-2">{annotations.get('description', 'No description')}</p>
                <div class="mt-3 text-sm text-gray-400">
                    <p><strong>Service:</strong> {labels.get('service', 'N/A')}</p>
                    <p><strong>Started at:</strong> {starts_at}</p>
                    <p><strong>Details:</strong> {annotations.get('summary', '')}</p>
                </div>
            </div>
            """
    else:
        alerts_html = "<div class='text-center text-gray-500 py-10'><p class='text-xl'>No active alerts. System is healthy.</p></div>"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Incident Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <meta http-equiv="refresh" content="10"> <!-- Автообновление каждые 10 сек -->
    </head>
    <body class="bg-gray-900 text-white font-sans">
        <div class="container mx-auto p-6">
            <header class="mb-8 flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-bold">🚨 AI Monitoring Incident Dashboard</h1>
                    <p class="text-gray-400 mt-1">Real-time alert visualization & logging</p>
                </div>
                <div class="{color_class} px-6 py-3 rounded-lg shadow-lg text-center">
                    <p class="text-sm font-semibold uppercase tracking-wider">Status</p>
                    <p class="text-2xl font-bold">{status_text}</p>
                    <p class="text-sm opacity-80">Active Alerts: {firing_count}</p>
                </div>
            </header>

            <main>
                <h2 class="text-2xl font-semibold mb-4 border-b border-gray-700 pb-2">Active Incidents</h2>
                {alerts_html}
            </main>

            <footer class="mt-12 pt-6 border-t border-gray-800 text-center text-gray-500 text-sm">
                <p>Logs are being saved to: <code class="bg-gray-800 px-2 py-1 rounded">logs/alerts_history.json</code></p>
                <p class="mt-2">Data provided by Prometheus Alertmanager</p>
            </footer>
        </div>
    </body>
    </html>
    """
    return html_content

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)