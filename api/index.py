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

# En Vercel serverless el dict se borra entre peticiones, así que no lo usamos como memoria principal
# Guardamos el último mensaje en memoria por si coincide en la misma instancia, pero los botones llevan el número dentro
pending_messages = {}

def send_to_telegram(text, whatsapp_from, message_id, sender_name=""):
    """Manda el resumen a tu Telegram con botones - 100% stateless para que no se borre en Vercel"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Truco: metemos el número de WhatsApp DENTRO del botón, así no dependemos de la memoria de Vercel
    # Telegram solo deja 64 caracteres por botón, así que usamos formato corto: accion|numero
    # Ej: auto|34612204265
    safe_from = whatsapp_from[-15:]  # últimos 15 dígitos por si es largo
    
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

            # Guardamos por si es la misma instancia (fallback)
            pending_messages[from_number] = {"from": from_number, "text": text, "name": profile_name}
            pending_messages[msg_id] = {"from": from_number, "text": text, "name": profile_name}
            
            # Creamos resumen
            resumen = summarize_message(profile_name, text)
            
            # Lo mandamos a Telegram (ahora con número dentro del botón)
            send_to_telegram(resumen, from_number, msg_id, profile_name)
            
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
        action_data = cb["data"]  # nuevo formato: auto|34612... o formato viejo auto_abc123
        # Soporte para los 2 formatos
        if "|" in action_data:
            action, from_number = action_data.split("|", 1)
            msg_id = from_number
        else:
            action, msg_id = action_data.split("_", 1)
            from_number = None

        cb_message = cb.get("message", {})
        # chat_id puede estar en message.chat.id
        chat_id = cb_message.get("chat", {}).get("id") or cb_message.get("chat_id") or TELEGRAM_CHAT_ID
        
        # Intentamos recuperar datos originales (si seguimos en misma instancia de Vercel)
        original = None
        if from_number:
            original = pending_messages.get(from_number) or pending_messages.get(msg_id)
        else:
            original = pending_messages.get(msg_id)
            if original:
                from_number = original["from"]

        # Si no tenemos original (Vercel reinició), usamos lo que viene en el botón
        if not original and from_number:
            original = {"from": from_number, "text": "(mensaje original no guardado en esta instancia)", "name": from_number}

        if not original:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": "⚠️ Se reinició el servidor y perdí el mensaje original. Pero el número era " + (from_number or msg_id)})
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
