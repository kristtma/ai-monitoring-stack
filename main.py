# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import random
import time
from prometheus_fastapi_instrumentator import Instrumentator
import uvicorn

templates = Jinja2Templates(directory="templates")
app = FastAPI(title="AI Monitoring Stack — Backend API")
Instrumentator().instrument(app).expose(app)

_memory_leak_storage: list = []
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
@app.get("/health")
async def health():
    return {"status": "healthy"}

# ДОБАВЬТЕ ЭТОТ ENDPOINT для healthcheck
@app.get("/ping")
async def ping():
    return {"ping": "pong"}
@app.post("/compute/matrix")
def compute(request: Request, size: int = Form(...)):
    arr1 = []
    arr2 = []
    for i in range(size):
        arr = []
        for j in range(size):
            arr.append(random.randint(1, 101))
        arr1.append(arr)

    for i in range(size):
        arr = []
        for j in range(size):
            arr.append(random.randint(1, 101))
        arr2.append(arr)
    arr3 = []
    for i in range(size):
        arr = []
        for j in range(size):
            sum = 0
            for k in range(size):
                sum += arr1[i][k] * arr2[k][j]
            arr.append(sum)
        arr3.append(arr)
    return templates.TemplateResponse("index.html", {"request": request, "result": arr3})
@app.post("/security/hash")
def hash_str(request: Request, size: int = Form(...),string:  str = Form(...)):
    res = string
    for i in range (size):
        res = str(hash(res))
    result = {
        "original" : string,
        "hash_text": res
    }
    return templates.TemplateResponse("index.html", {"request": request, "result": result})

@app.post("/reports/list")
def generate_list(request: Request, size: int = Form(...)):
    huge_data = [
        {
            "id": i,
            "status": random.choice(["success", "error", "pending"]),
            "price": round(random.uniform(10.5, 1000.0), 2)
        }
        for i in range(size)
    ]
    result = {
        "status": "success",
        "count": len(huge_data),
        "sample": huge_data[:2] if size > 0 else []
    }
    return templates.TemplateResponse("index.html", {"request": request, "result": result})


@app.get("/api/users")
def get_users():
    time.sleep(random.uniform(0.01, 0.1))
    users = [
        {"id": i, "name": f"user_{i}", "status": random.choice(["active", "inactive"])}
        for i in range(random.randint(5, 20))
    ]
    return JSONResponse(content={"users": users, "count": len(users)})


@app.post("/test/memory_leak")
def trigger_memory_leak(chunks: int = 10):
    chunk_size = 100_000
    for _ in range(chunks):
        _memory_leak_storage.append([0] * chunk_size)
    used_mb = len(_memory_leak_storage) * chunk_size * 8 / 1024 / 1024
    return JSONResponse(content={
        "message": f"Добавлено {chunks} блоков. Занято ~{used_mb:.1f} MB",
        "total_chunks": len(_memory_leak_storage),
    })


@app.delete("/test/memory_leak")
def clear_memory_leak():
    count = len(_memory_leak_storage)
    _memory_leak_storage.clear()
    return JSONResponse(content={"message": "Память очищена", "cleared_chunks": count})
