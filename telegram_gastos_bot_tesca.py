import os
import sqlite3
from flask import Flask, request
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_PATH = "/telegram/webhook"

app = Flask(__name__)

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
    r = requests.post(url, json={"chat_id": chat_id, "text": text})
    print("sendMessage status:", r.status_code)
    print("sendMessage body:", r.text)

def procesar_texto(texto):
    try:
        partes = [p.strip() for p in texto.split(",")]
        if len(partes) < 4:
            return None

        monto_partes = partes[1].split()
        if len(monto_partes) < 2:
            return None

        return {
            "descripcion": partes[0],
            "monto": float(monto_partes[0]),
            "moneda": monto_partes[1],
            "fecha": partes[2],
            "categoria": partes[3]
        }
    except Exception as e:
        print("Error procesar_texto:", str(e))
        return None

@app.route("/", methods=["GET"])
def home():
    return "Bot activo", 200

@app.route(WEBHOOK_PATH, methods=["GET"])
def webhook_get():
    return "Webhook activo", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    print("Webhook data:", data)

    if not data:
        return "no data", 200

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]

        if "text" in msg:
            texto = msg["text"]
            print("Texto recibido:", texto)

            if texto == "/start":
                send_message(chat_id, "Bot TESCA activo 💼")
                return "ok", 200

            gasto = procesar_texto(texto)

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

                send_message(
                    chat_id,
                    f"✅ Gasto registrado\n\n"
                    f"Descripción: {gasto['descripcion']}\n"
                    f"Monto: {gasto['monto']} {gasto['moneda']}\n"
                    f"Fecha: {gasto['fecha']}\n"
                    f"Categoría: {gasto['categoria']}"
                )
            else:
                send_message(
                    chat_id,
                    "Formato inválido.\nUsa:\nTaxi, 10 USD, 2026-04-05, Transporte"
                )

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
