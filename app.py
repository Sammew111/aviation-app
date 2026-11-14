import csv, json, os, math, io, base64, secrets
from typing import Optional
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from passlib.context import CryptContext

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
FORECAST = os.path.join(DATA, "Колесов_Данил_Александрович_my_forecast.csv")
ROUTES = os.path.join(DATA, "routes.csv")

app = FastAPI(title="Решись Авиа — прогноз спроса")
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")

def load_routes():
    with open(ROUTES, encoding="utf-8") as f:
        return {r["route"]: {
            "name": r["name"],
            "base_price": float(r["base_price"]),
            "price_sensitivity": float(r["price_sensitivity"]),
            "price_min": float(r["price_min"]),
            "price_max": float(r["price_max"]),
        } for r in csv.DictReader(f)}

def load_forecast():
    rows = []
    with open(FORECAST, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

ROUTES_DB = load_routes()
FORECAST_DB = load_forecast()
INDEX = {(r["route"], r["date"]): r for r in FORECAST_DB}
QUANTILES = ["0.1","0.2","0.3","0.4","0.5","0.6","0.7","0.8","0.9"]

def demand_at_price(row, q, price):
    base_demand = float(row[f"{q}_base_demand"])
    base_price = ROUTES_DB[row["route"]]["base_price"]
    sens = ROUTES_DB[row["route"]]["price_sensitivity"]
    return max(0.0, base_demand - sens * (price - base_price))

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS_FILE = os.path.join(DATA, "users.json")
TOKENS = {}

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_users(u):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(u, f, ensure_ascii=False, indent=2)

class Credentials(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=4)

@app.post("/api/register")
def register(c: Credentials):
    users = load_users()
    if c.username in users:
        raise HTTPException(400, "Пользователь уже существует")
    users[c.username] = pwd_ctx.hash(c.password)
    save_users(users)
    return {"ok": True}

@app.post("/api/login")
def login(c: Credentials):
    users = load_users()
    hashed = users.get(c.username)
    if not hashed or not pwd_ctx.verify(c.password, hashed):
        raise HTTPException(401, "Неверный логин или пароль")
    token = secrets.token_hex(16)
    TOKENS[token] = c.username
    return {"token": token, "username": c.username}

def current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Требуется авторизация")
    token = authorization.split(" ", 1)[1]
    user = TOKENS.get(token)
    if not user:
        raise HTTPException(401, "Недействительный токен")
    return user

@app.get("/api/me")
def me(user: str = Depends(current_user)):
    return {"username": user}

class ForecastRequest(BaseModel):
    origin: str
    destination: str
    date: str
    price: float

def route_key(origin, destination):
    return f"{origin.upper()}-{destination.upper()}"

@app.post("/api/forecast")
def forecast(req: ForecastRequest):
    key = route_key(req.origin, req.destination)
    if (key, req.date) not in INDEX:
        raise HTTPException(404, "Рейс не найден")
    row = INDEX[(key, req.date)]
    seats = int(row["seats"])
    wish = demand_at_price(row, "0.5", req.price)
    bought = min(seats, wish)
    scenarios = [{"quantile": float(q), "demand": round(demand_at_price(row, q, req.price), 2)} for q in QUANTILES]
    return {"route": key, "route_name": ROUTES_DB[key]["name"], "date": req.date,
            "seats": seats, "price": req.price, "wish": round(wish, 2),
            "bought": round(bought, 2), "scenarios": scenarios}

@app.post("/api/chart")
def chart(req: ForecastRequest):
    key = route_key(req.origin, req.destination)
    if (key, req.date) not in INDEX:
        raise HTTPException(404, "Рейс не найден")
    row = INDEX[(key, req.date)]
    seats = int(row["seats"])
    qs = [float(q) for q in QUANTILES]
    demands = [demand_at_price(row, q, req.price) for q in QUANTILES]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(qs, demands, marker="o", color="#2563eb", label="Спрос при цене")
    ax.axhline(seats, color="#ef4444", linestyle="--", label=f"Мест: {seats}")
    ax.set_xlabel("Квантиль прогноза"); ax.set_ylabel("Спрос (чел.)")
    ax.set_title(f"{ROUTES_DB[key]['name']} — {req.date}\nЦена: {req.price:.0f} ₽")
    ax.grid(alpha=0.3); ax.legend()
    buf = io.BytesIO(); fig.tight_layout(); fig.savefig(buf, format="png", dpi=110); plt.close(fig)
    return {"image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}

@app.get("/")
def root():
    return FileResponse(os.path.join(BASE, "static", "index.html"))