# Portero de Andrés - Guía ultra simple

## Qué hace?
Tu WhatsApp -> resumen en Telegram -> tú decides si respondo como tú.

## PASO 1 - Ya lo hiciste ✅
Bot @portero_Andy97_bot creado y token revocado. Bien.

## PASO 2 - Conseguir tu TELEGRAM_CHAT_ID (1 min)
1. En Telegram busca @userinfobot
2. Dale /start
3. Te dará un número tipo 123456789
4. Ese es tu TELEGRAM_CHAT_ID. Apúntalo en .env

## PASO 3 - Subir el código a internet (gratis)
Opción más fácil: Vercel
1. Crea cuenta en vercel.com con GitHub
2. Crea nuevo proyecto -> Importa esta carpeta portero_bot
3. En Settings -> Environment Variables pega tus tokens (NUNCA en el código público):
   - TELEGRAM_TOKEN
   - TELEGRAM_CHAT_ID
   - VERIFY_TOKEN = portero_andres_123
4. Deploy. Te dará una URL tipo https://portero-andres.vercel.app

## PASO 4 - Conectar WhatsApp (5 min)
1. Ve a developers.facebook.com -> tu app Portero Carl
2. WhatsApp -> Configuración -> Webhook
3. URL: https://tu-url.vercel.app/webhook
4. Verify Token: portero_andres_123
5. Suscríbete a "messages"
6. Copia el "Phone Number ID" y el "Access Token temporal" -> pégalos en Vercel env vars como WHATSAPP_PHONE_ID y WHATSAPP_TOKEN

## PASO 5 - Conectar Telegram webhook
En tu navegador pega esto (cambia TU_URL y TU_TOKEN):
https://api.telegram.org/botTU_TOKEN/setWebhook?url=https://TU_URL.vercel.app/telegram

Si dice {"ok":true} ya está.

## Listo!
Manda un WhatsApp a tu número Business y te llegará el resumen a @portero_Andy97_bot

Interruptor: en Vercel puedes parar el deployment para modo OFF, o añade en Telegram un comando /off

¿Dudas? Pregunta.
