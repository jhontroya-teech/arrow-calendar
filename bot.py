import os
import logging
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

clientes = []

MONTHS_ES = {
    1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
    7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"
}
MONTHS_MAP = {v.lower():k for k,v in MONTHS_ES.items()}

def format_date(d):
    return f"{d.day} {MONTHS_ES[d.month]} {d.year}"

def add_cliente(nombre, celular, direccion, detalle, meses=5):
    hoy = datetime.now()
    segunda = hoy + relativedelta(months=meses)
    c = {
        "nombre": nombre,
        "celular": celular,
        "direccion": direccion,
        "detalle": detalle,
        "fecha1": format_date(hoy),
        "fecha2": format_date(segunda),
        "fecha1_obj": hoy,
        "fecha2_obj": segunda
    }
    clientes.append(c)
    return c

def parse_limpieza(text):
    words = text.split()
    idx = next((i for i,w in enumerate(words) if w.lower()=="limpieza"), 0) + 1
    resto = words[idx:]
    celular = ""
    nombre_w, dir_w, det_w = [], [], []
    cel_rx = re.compile(r'^0\d{9}$')
    lugares = ['guasmo','urdesa','alborada','kennedy','norte','sur','centro',
               'samborondon','cdla','av','calle','mz','villa','sauces',
               'mapasingue','bastion','garzota','ceibos','policentro','febres']
    phase = 'nombre'
    for w in resto:
        if cel_rx.match(w):
            celular = w
            if phase == 'nombre':
                phase = 'lugar'
        elif phase == 'nombre' and any(l in w.lower() for l in lugares):
            phase = 'lugar'
            dir_w.append(w)
        elif phase == 'nombre':
            nombre_w.append(w)
        elif phase == 'lugar' and len(dir_w) >= 2:
            phase = 'detalle'
            det_w.append(w)
        elif phase == 'lugar':
            dir_w.append(w)
        else:
            det_w.append(w)
    return {
        "nombre": ' '.join(nombre_w) or 'Cliente',
        "celular": celular,
        "direccion": ' '.join(dir_w),
        "detalle": ' '.join(det_w)
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Hola Jhon, soy tu asistente Arrow Company*\n\n"
        "Escríbeme así:\n\n"
        "🧹 *Agendar limpieza:*\n"
        "`limpieza dra diana medina 0987738569 guasmo central aire muy sucio`\n\n"
        "📅 *Ver agenda:*\n"
        "`qué tengo esta semana`\n"
        "`limpiezas de junio`\n\n"
        "📋 *Ver clientes:*\n"
        "`/clientes`\n\n"
        "🤖 *Cualquier pregunta con IA:*\n"
        "Escribe lo que necesites"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def clientes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not clientes:
        await update.message.reply_text("No tienes clientes registrados aún.")
        return
    texto = "📋 *Tus clientes:*\n\n"
    for i, c in enumerate(clientes, 1):
        texto += (
            f"*{i}. {c['nombre']}*\n"
            f"📱 {c['celular']}\n"
            f"📍 {c['direccion']}\n"
            f"📝 {c['detalle']}\n"
            f"1ra limpieza: {c['fecha1']}\n"
            f"🔄 2da limpieza: *{c['fecha2']}*\n\n"
        )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    lower = texto.lower()

    # AGENDAR LIMPIEZA
    if "limpieza" in lower:
        data = parse_limpieza(texto)
        meses = int(context.bot_data.get("meses", 5))
        c = add_cliente(data["nombre"], data["celular"], data["direccion"], data["detalle"], meses)
        resp = (
            f"✅ *Limpieza registrada*\n\n"
            f"👤 *{c['nombre']}*\n"
            f"📱 {c['celular'] or '—'}\n"
            f"📍 {c['direccion'] or '—'}\n"
            f"📝 {c['detalle'] or '—'}\n\n"
            f"📅 1ra limpieza: *{c['fecha1']}*\n"
            f"🔄 2da limpieza: *{c['fecha2']}*"
        )
        await update.message.reply_text(resp, parse_mode="Markdown")
        return

    # VER SEMANA
    if any(w in lower for w in ["semana","qué tengo","que tengo","tengo hoy"]):
        hoy = datetime.now()
        semana = [c for c in clientes if 0 <= (c["fecha1_obj"] - hoy).days <= 7]
        if not semana:
            await update.message.reply_text("No tienes limpiezas esta semana.")
        else:
            resp = "📅 *Esta semana:*\n\n"
            for c in semana:
                resp += f"• *{c['nombre']}* — {c['direccion']} ({c['fecha1']})\n"
            await update.message.reply_text(resp, parse_mode="Markdown")
        return

    # VER MES
    mes_encontrado = next((m for m in MONTHS_MAP if m in lower), None)
    if mes_encontrado:
        mes_num = MONTHS_MAP[mes_encontrado]
        limpiezas = [c for c in clientes if c["fecha1_obj"].month == mes_num]
        if not limpiezas:
            await update.message.reply_text(f"No hay limpiezas en {mes_encontrado.capitalize()}.")
        else:
            resp = f"🧹 *Limpiezas de {mes_encontrado.capitalize()}:*\n\n"
            for c in limpiezas:
                resp += f"• *{c['nombre']}* — {c['direccion']} ({c['fecha1']})\n"
            await update.message.reply_text(resp, parse_mode="Markdown")
        return

    # IA GEMINI
    try:
        prompt = (
            f"Eres el asistente de Jhon Jairo, técnico de aires acondicionados "
            f"en Guayaquil, Ecuador. Su empresa es Arrow Company. "
            f"Responde breve y útil en español.\n"
            f"Pregunta: {texto}"
        )
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        await update.message.reply_text("No pude procesar esa consulta. Intenta de nuevo.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clientes", clientes_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

