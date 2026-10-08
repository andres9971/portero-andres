"""
Portero de Andrés - WhatsApp -> Telegram Gatekeeper
Versión Final - con test-telegram y manejo de mensajes normales
"""

import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "portero_andres_123")

pending_messages = {}

def send_to_telegram(text, whatsapp_from, message_id, sender_name=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    safe_from = whatsapp_from[-15:]
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Responder como yo", "callback_data": f"auto|{safe_from}"},
                {"text": "⏭️ Ignorar", "callback_data": f"ignore|{safe_from}"}
            ],
            [
                {"text": "💬 Respondo yo", "callback_data": f"manual|{safe_from}"}
            ]
        ]
    }
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "reply_markup": keyboard,
        "parse_mode": "Markdown"
    }
    r = requests.post(url, json=payload)
    print(f"Telegram response to {TELEGRAM_CHAT_ID}:", r.text, f"TOKEN exists: {bool(TELEGRAM_TOKEN)}")
    return r

def summarize_message(sender, message_text):
    lower = message_text.lower()
    importancia = "tranqui"
    if any(x in lower for x in ["urgente", "ayuda", "hospital", "trabajo", "pago", "jefe", "entrega"]):
        importancia = "⚠️ IMPORTANTE"
    resumen = f"""📩 *Nuevo mensaje*

*De:* {sender}
*Asunto:* {message_text[:80]}
*Vibe:* {importancia}

*Mensaje completo:*
_{message_text}_

¿qué hacemos?"""
    return resumen

def reply_whatsapp(to_number, text):
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "text": {"body": text}
    }
    r = requests.post(url, headers=headers, json=data)
    print("WhatsApp reply:", r.text)
    return r

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    print(f"VERIFY attempt: mode={mode} token={token} expected={VERIFY_TOKEN} challenge={challenge}")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("VERIFY OK")
        return challenge, 200
    print("VERIFY FAILED")
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("Incoming WHATSAPP:", data)
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            msg = entry["messages"][0]
            from_number = msg["from"]
            msg_id = msg["id"]
            text = msg.get("text", {}).get("body", "") or msg.get("button", {}).get("text", "") or str(msg)
            profile_name = entry.get("contacts", [{}])[0].get("profile", {}).get("name", from_number)
            print(f"Message from {profile_name} {from_number}: {text}")
            pending_messages[from_number] = {"from": from_number, "text": text, "name": profile_name}
            pending_messages[msg_id] = {"from": from_number, "text": text, "name": profile_name}
            resumen = summarize_message(profile_name, text)
            send_to_telegram(resumen, from_number, msg_id, profile_name)
        else:
            print("No messages in value, maybe status update:", entry)
    except Exception as e:
        print("Error webhook:", e, "data:", data)
    return jsonify({"status": "ok"}), 200

@app.route("/telegram", methods=["POST"])
def telegram_callback():
    data = request.get_json()
    print("Telegram callback:", data)
    # Mensaje normal (ej: /start, hola) - confirma que Telegram funciona
    if "message" in data:
        msg = data["message"]
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")
        print(f"Mensaje normal de Telegram chat {chat_id}: {text}")
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": f"🟢 Portero activo! Tu CHAT_ID es {chat_id}\nTu PHONE_ID es {WHATSAPP_PHONE_ID}\n\nManda un WhatsApp al +1 (555) 655-0619 para probar.\n\nPrueba también: https://portero-andres.vercel.app/test-telegram"})
        return jsonify({"status": "ok"}), 200

    if "callback_query" in data:
        cb = data["callback_query"]
        action_data = cb["data"]
        if "|" in action_data:
            action, from_number = action_data.split("|", 1)
            msg_id = from_number
        else:
            try:
                action, msg_id = action_data.split("_", 1)
            except:
                action = action_data
                msg_id = ""
            from_number = None
        cb_message = cb.get("message", {})
        chat_id = cb_message.get("chat", {}).get("id") or cb_message.get("chat_id") or TELEGRAM_CHAT_ID
        original = None
        if from_number:
            original = pending_messages.get(from_number) or pending_messages.get(msg_id)
        else:
            original = pending_messages.get(msg_id)
            if original:
                from_number = original["from"]
        if not original and from_number:
            original = {"from": from_number, "text": "(no guardado)", "name": from_number}
        if not original:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"⚠️ Servidor reiniciado, perdí el mensaje. Número: {from_number or msg_id}"})
            return jsonify({"status": "no msg"}), 200
        if action == "auto":
            respuesta_clon = f"eyy {original['name']}! ahora mismo estoy liado jaja luego te digo bien vale? "
            reply_whatsapp(original["from"], respuesta_clon)
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"✅ Respondido como tú a {original['name']}"})
        elif action == "ignore":
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"⏭️ Ignorado mensaje de {original['name']}"})
        elif action == "manual":
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"💬 Vale, te toca responder tú a {original['from']} en WhatsApp"})
    return jsonify({"status": "ok"}), 200

@app.route("/test-telegram")
def test_telegram():
    try:
        r = send_to_telegram("📩 *PRUEBA* - Si ves esto en Telegram, el bot ya funciona!\n\nAhora falta que Meta mande el webhook de WhatsApp.", "34600000000", "test123", "Test User")
        return f"Enviado a Telegram: {r.text} | CHAT_ID={TELEGRAM_CHAT_ID}", 200
    except Exception as e:
        return f"Error: {e}", 500

@app.route("/")
def home():
    return f"Portero de Andrés activo - ON 🟢 | CHAT_ID={TELEGRAM_CHAT_ID} | PHONE_ID={WHATSAPP_PHONE_ID} | VERIFY={VERIFY_TOKEN}"

if __name__ == "__main__":
    app.run(port=5000)
