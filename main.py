from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import random

templates = Jinja2Templates(directory="templates")
app = FastAPI()
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
        for i in range (size)
    ]
    result = {
        "status": "success",
        "count": len(huge_data),
        "sample": huge_data[:2] if size > 0 else []  # Покажем первые 2 для примера
    }
    return templates.TemplateResponse("index.html", {"request": request, "result": result})