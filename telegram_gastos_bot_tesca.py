import os
import sqlite3
from datetime import datetime, date
from flask import Flask, request, jsonify
import requests

# =========================================================
# CONFIG
# =========================================================

# Temporalmente directo para que siga funcionando.
# Luego conviene moverlo a Render Environment y regenerarlo.
TOKEN = "8672346222:AAH8a6cW62ChlH-sgVrV1CwSoGIOmBgkdlg"

WEBHOOK_PATH = "/telegram/webhook"
DB_PATH = "gastos.db"

MONEDAS_VALIDAS = {"USD", "COP", "BS", "BS.", "VES"}
CATEGORIAS_DISPONIBLES = [
    "Transporte",
    "Alimentación",
    "Materiales",
    "Herramientas",
    "Hospedaje",
    "Logística",
    "Servicios",
    "Administración",
    "Otros",
]

# =========================================================
# APP
# =========================================================

app = Flask(__name__)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion TEXT NOT NULL,
    monto REAL NOT NULL,
    moneda TEXT NOT NULL,
    fecha TEXT NOT NULL,
    categoria TEXT NOT NULL,
    creado_en TEXT NOT NULL
)
""")
conn.commit()


# =========================================================
# HELPERS
# =========================================================

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
        return r.status_code, r.text
    except Exception as e:
        print("Error en send_message:", str(e), flush=True)
        return None, str(e)


def normalizar_moneda(moneda):
    moneda = moneda.strip().upper()
    if moneda in {"BS", "BS.", "VES"}:
        return "BS"
    return moneda


def formatear_gasto(gasto):
    return (
        f"✅ Gasto registrado\n\n"
        f"Descripción: {gasto['descripcion']}\n"
        f"Monto: {gasto['monto']:.2f} {gasto['moneda']}\n"
        f"Fecha: {gasto['fecha']}\n"
        f"Categoría: {gasto['categoria']}"
    )


def procesar_texto(texto):
    """
    Formato esperado:
    Taxi, 10 USD, 2026-04-05, Transporte
    """
    try:
        partes = [p.strip() for p in texto.split(",")]
        if len(partes) < 4:
            return None, "Formato incompleto."

        descripcion = partes[0]

        monto_partes = partes[1].split()
        if len(monto_partes) != 2:
            return None, "El monto debe venir así: 10 USD"

        monto = float(monto_partes[0])
        moneda = normalizar_moneda(monto_partes[1])

        if moneda not in MONEDAS_VALIDAS and moneda != "USD" and moneda != "COP":
            return None, "Moneda no válida. Usa USD, COP o BS."

        fecha = partes[2]
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            return None, "La fecha debe tener formato YYYY-MM-DD."

        categoria = partes[3].title()
        if categoria not in CATEGORIAS_DISPONIBLES:
            return None, (
                "Categoría no válida.\n\n"
                "Usa una de estas:\n" + "\n".join(CATEGORIAS_DISPONIBLES)
            )

        return {
            "descripcion": descripcion,
            "monto": monto,
            "moneda": moneda,
            "fecha": fecha,
            "categoria": categoria,
        }, None

    except Exception as e:
        print("Error procesar_texto:", str(e), flush=True)
        return None, "No pude interpretar el gasto."


def guardar_gasto(gasto):
    cursor.execute("""
        INSERT INTO gastos (descripcion, monto, moneda, fecha, categoria, creado_en)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        gasto["descripcion"],
        gasto["monto"],
        gasto["moneda"],
        gasto["fecha"],
        gasto["categoria"],
        datetime.now().isoformat()
    ))
    conn.commit()


def obtener_gastos_hoy():
    hoy = date.today().isoformat()
    cursor.execute("""
        SELECT descripcion, monto, moneda, fecha, categoria
        FROM gastos
        WHERE fecha = ?
        ORDER BY id DESC
    """, (hoy,))
    return cursor.fetchall()


def obtener_gastos_mes():
    mes_actual = date.today().strftime("%Y-%m")
    cursor.execute("""
        SELECT descripcion, monto, moneda, fecha, categoria
        FROM gastos
        WHERE substr(fecha, 1, 7) = ?
        ORDER BY fecha DESC, id DESC
    """, (mes_actual,))
    return cursor.fetchall()


def obtener_ultimos_gastos(limite=10):
    cursor.execute("""
        SELECT descripcion, monto, moneda, fecha, categoria
        FROM gastos
        ORDER BY id DESC
        LIMIT ?
    """, (limite,))
    return cursor.fetchall()


def resumir_por_moneda(gastos):
    resumen = {}
    for _, monto, moneda, _, _ in gastos:
        resumen[moneda] = resumen.get(moneda, 0) + monto
    return resumen


def texto_lista_gastos(titulo, gastos):
    if not gastos:
        return f"{titulo}\n\nNo hay gastos registrados."

    lineas = [titulo, ""]
    for descripcion, monto, moneda, fecha, categoria in gastos:
        lineas.append(f"- {fecha} | {descripcion} | {monto:.2f} {moneda} | {categoria}")

    resumen = resumir_por_moneda(gastos)
    lineas.append("")
    lineas.append("Totales:")
    for moneda, total in resumen.items():
        lineas.append(f"- {total:.2f} {moneda}")

    return "\n".join(lineas)


# =========================================================
# ROUTES
# =========================================================

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
            return jsonify({"ok": True, "note": "sin data"}), 200

        msg = data.get("message")
        if not msg:
            return jsonify({"ok": True, "note": "sin message"}), 200

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        texto = msg.get("text", "").strip()

        print("chat_id:", chat_id, flush=True)
        print("texto:", texto, flush=True)

        if not chat_id:
            return jsonify({"ok": True, "note": "sin chat_id"}), 200

        if texto == "/start":
            send_message(
                chat_id,
                "Bot TESCA activo 💼\n\n"
                "Envía tus gastos así:\n"
                "Taxi, 10 USD, 2026-04-05, Transporte\n\n"
                "Comandos:\n"
                "/ayuda\n"
                "/hoy\n"
                "/mes\n"
                "/ultimos\n"
                "/categorias"
            )
            return jsonify({"ok": True, "action": "start"}), 200

        if texto == "/ayuda":
            send_message(
                chat_id,
                "Formato de carga:\n"
                "Descripción, monto moneda, fecha, categoría\n\n"
                "Ejemplo:\n"
                "Taxi, 10 USD, 2026-04-05, Transporte\n\n"
                "Monedas permitidas:\n"
                "- USD\n"
                "- COP\n"
                "- BS\n\n"
                "Comandos disponibles:\n"
                "/hoy\n"
                "/mes\n"
                "/ultimos\n"
                "/categorias"
            )
            return jsonify({"ok": True, "action": "ayuda"}), 200

        if texto == "/categorias":
            send_message(
                chat_id,
                "Categorías disponibles:\n\n" + "\n".join(f"- {c}" for c in CATEGORIAS_DISPONIBLES)
            )
            return jsonify({"ok": True, "action": "categorias"}), 200

        if texto == "/hoy":
            gastos = obtener_gastos_hoy()
            send_message(chat_id, texto_lista_gastos("📅 Gastos de hoy", gastos))
            return jsonify({"ok": True, "action": "hoy"}), 200

        if texto == "/mes":
            gastos = obtener_gastos_mes()
            send_message(chat_id, texto_lista_gastos("📊 Gastos del mes", gastos))
            return jsonify({"ok": True, "action": "mes"}), 200

        if texto == "/ultimos":
            gastos = obtener_ultimos_gastos(10)
            send_message(chat_id, texto_lista_gastos("🧾 Últimos gastos", gastos))
            return jsonify({"ok": True, "action": "ultimos"}), 200

        gasto, error = procesar_texto(texto)
        if gasto:
            guardar_gasto(gasto)
            send_message(chat_id, formatear_gasto(gasto))
            return jsonify({"ok": True, "action": "gasto_guardado"}), 200

        send_message(
            chat_id,
            f"❌ {error}\n\n"
            "Ejemplo correcto:\n"
            "Taxi, 10 USD, 2026-04-05, Transporte"
        )
        return jsonify({"ok": True, "action": "formato_invalido"}), 200

    except Exception as e:
        print("Error general en webhook:", str(e), flush=True)
        return jsonify({"ok": False, "error": str(e)}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
