"""
Portero de Andrés - WhatsApp -> Telegram Gatekeeper
- Recibe mensajes de WhatsApp Cloud API
- Resume quién es + qué quiere
- Te lo manda a tu bot de Telegram con botones: Responder como yo / Ignorar / Respondo yo

Deploy: Vercel / Render / Railway (gratis)
"""

import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN: RELLENA ESTO EN TU SERVIDOR, NO COMPARTAS ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # tu nuevo token de @portero_Andy97_bot
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # tu ID de Telegram (lo sacamos luego)
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")  # token de WhatsApp Cloud API
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")  # Phone Number ID de Meta
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "portero_andres_123")  # para verificar webhook en Meta
# Para el resumen con IA (puedes usar OpenAI, Groq, o Meta AI)
AI_API_KEY = os.getenv("AI_API_KEY")

# Memoria simple de mensajes pendientes: msg_id -> datos originales
pending_messages = {}

def send_to_telegram(text, whatsapp_from, message_id):
    """Manda el resumen a tu Telegram con botones"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Responder como yo", "callback_data": f"auto_{message_id}"},
                {"text": "⏭️ Ignorar", "callback_data": f"ignore_{message_id}"}
            ],
            [
                {"text": "💬 Respondo yo (abrir WhatsApp)", "callback_data": f"manual_{message_id}"}
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
    print("Telegram response:", r.text)
    return r

def summarize_message(sender, message_text):
    """Aquí va tu lógica de resumen. Simple por ahora, luego le metemos IA 100% tú"""
    # Si quieres 100% clon, aquí llamarías a OpenAI con tu prompt personalizado
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

# --- WEBHOOK VERIFICATION (Meta te pide esto una vez) ---
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# --- RECEPCIÓN DE MENSAJES WHATSAPP ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("Incoming:", data)
    
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            msg = entry["messages"][0]
            from_number = msg["from"]
            msg_id = msg["id"]
            text = msg.get("text", {}).get("body", "")
            profile_name = entry.get("contacts", [{}])[0].get("profile", {}).get("name", from_number)

            # Guardamos para luego
            pending_messages[msg_id] = {"from": from_number, "text": text, "name": profile_name}
            
            # Creamos resumen
            resumen = summarize_message(profile_name, text)
            
            # Lo mandamos a Telegram
            send_to_telegram(resumen, from_number, msg_id)
            
    except Exception as e:
        print("Error:", e)
    
    return jsonify({"status": "ok"}), 200

# --- RESPUESTA DESDE TELEGRAM (cuando pulsas botones) ---
@app.route("/telegram", methods=["POST"])
def telegram_callback():
    data = request.get_json()
    print("Telegram callback:", data)
    
    if "callback_query" in data:
        cb = data["callback_query"]
        action_data = cb["data"]  # ej: auto_abc123
        action, msg_id = action_data.split("_", 1)
        chat_id = cb["message"]["chat_id"]
        
        original = pending_messages.get(msg_id)
        if not original:
            return jsonify({"status": "no msg"}), 200

        if action == "auto":
            # Aquí respondería como tú - personaliza este texto con tu prompt clon
            respuesta_clon = f"eyy {original['name']}! ahora mismo estoy liado jaja luego te digo bien vale? "
            reply_whatsapp(original["from"], respuesta_clon)
            
            # Confirma en Telegram
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"✅ Respondido como tú a {original['name']}"})
        
        elif action == "ignore":
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"⏭️ Ignorado mensaje de {original['name']}"})
        
        elif action == "manual":
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"💬 Vale, te toca responder tú a {original['from']} en WhatsApp"})

    return jsonify({"status": "ok"}), 200

@app.route("/")
def home():
    return "Portero de Andrés activo - ON 🟢"

if __name__ == "__main__":
    app.run(port=5000)
