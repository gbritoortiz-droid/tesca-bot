import os
import sqlite3
from flask import Flask, request
import requests

TOKEN = TOKEN = "8672346222:AAH8a6cW62ChlH-sgVrV1CwSoGIOmBgkdlg"
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
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        print("sendMessage status:", r.status_code, flush=True)
        print("sendMessage body:", r.text, flush=True)
    except Exception as e:
        print("Error en send_message:", str(e), flush=True)

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
        print("Error procesar_texto:", str(e), flush=True)
        return None

@app.route("/", methods=["GET"])
def home():
    return "Bot activo", 200

@app.route(WEBHOOK_PATH, methods=["GET"])
def webhook_get():
    return "Webhook activo", 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        print("Webhook data:", data, flush=True)

        if not data:
            return "no data", 200

        if "message" not in data:
            print("No hay 'message' en el update", flush=True)
            return "ok", 200

        msg = data["message"]
        chat_id = msg["chat"]["id"]

        if "text" not in msg:
            send_message(chat_id, "Por ahora solo proceso texto.")
            return "ok", 200

        texto = msg["text"].strip()
        print("Texto recibido:", texto, flush=True)

        if texto == "/start":
            send_message(
                chat_id,
                "Bot TESCA activo 💼\n\n"
                "Envía el gasto así:\n"
                "Taxi, 10 USD, 2026-04-05, Transporte"
            )
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
                "Formato inválido.\n\n"
                "Usa este formato:\n"
                "Taxi, 10 USD, 2026-04-05, Transporte"
            )

        return "ok", 200

    except Exception as e:
        print("Error general en webhook:", str(e), flush=True)
        return "error", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
