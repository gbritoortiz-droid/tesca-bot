
import os
import sqlite3
from datetime import datetime
from flask import Flask, request
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

WEBHOOK_PATH = "/telegram/webhook"

app = Flask(__name__)

# DB
conn = sqlite3.connect("gastos.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY,
    descripcion TEXT,
    monto REAL,
    moneda TEXT,
    categoria TEXT,
    fecha TEXT
)
""")
conn.commit()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def procesar_texto(texto):
    try:
        partes = texto.split(",")
        return {
            "descripcion": partes[0].strip(),
            "monto": float(partes[1].strip().split()[0]),
            "moneda": partes[1].strip().split()[1],
            "fecha": partes[2].strip(),
            "categoria": partes[3].strip()
        }
    except:
        return None

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]

        if "text" in msg:
            if msg["text"] == "/start":
                send_message(chat_id, "Bot TESCA activo 💼")
                return "ok"

            gasto = procesar_texto(msg["text"])

            if gasto:
                cursor.execute("""
                INSERT INTO gastos (descripcion, monto, moneda, categoria, fecha)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    gasto["descripcion"],
                    gasto["monto"],
                    gasto["moneda"],
                    gasto["categoria"],
                    gasto["fecha"]
                ))
                conn.commit()

                send_message(chat_id, "✅ Gasto registrado")
            else:
                send_message(chat_id, "Formato inválido")

    return "ok"

@app.route("/")
def home():
    return "Bot activo"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
