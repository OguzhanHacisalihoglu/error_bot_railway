# main.py (tam komut paketi: /random, /stats, /popular, /download_log, /log_summary)
import os
import json
import random
import asyncio
import fitz  # PyMuPDF
import csv
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import (ApplicationBuilder, ContextTypes,
                          CommandHandler, MessageHandler, filters, JobQueue)
from deep_translator import GoogleTranslator

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
JSON_PATH = "oracle_errors.json"
PDF_PATH = "oracle_errors.pdf"
LOG_PATH = "query_log.json"
LOG_CSV_PATH = "query_log.csv"


def load_data():
    if not os.path.exists(JSON_PATH):
        return {}
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def log_query(user_id, username, code):
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.append({"user_id": user_id, "username": username, "code": code})
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_log_to_csv():
    if not os.path.exists(LOG_PATH):
        return False
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        return False
    with open(LOG_CSV_PATH, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["user_id", "username", "code"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for entry in data:
            writer.writerow(entry)
    return True


# Komutlar
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Merhaba!\n\n"
        "Ben Oracle hata kodlarını açıklayan bir botum.\n\n"
        "🧰 Kullanım:\n"
        "- ORA-00904 gibi bir hata kodu gönder.\n"
        "- /search [kelime] → içerik ara\n"
        "- /popular → en sık arananlar\n"
        "- /stats → bot kullanım istatistikleri\n"
        "- /random → rastgele hata göster\n"
        "- /feedback [mesaj] → öneri gönder\n"
        "- /download_log → log csv dosyasını indir (sadece admin)\n"
        "- /log_summary → log özeti göster (sadece admin)"
    )


async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data:
        await update.message.reply_text("Veri tabanı boş.")
        return
    code = random.choice(list(data.keys()))
    text = data[code]
    try:
        translated = GoogleTranslator(source='auto', target='tr').translate(text)
        message = f"🎲 Rastgele Hata: {code}\n\n📘 Orijinal:\n{text}\n\n🔄 Türkçe:\n{translated}"
    except:
        message = f"🎲 Rastgele Hata: {code}\n\n📘 Açıklama:\n{text}"
    await update.message.reply_text(message)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(LOG_PATH):
        await update.message.reply_text("Henüz istatistik yok.")
        return
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    total_queries = len(data)
    unique_users = len(set(d['user_id'] for d in data))
    await update.message.reply_text(f"📈 Toplam sorgu: {total_queries}\n👥 Kullanıcı sayısı: {unique_users}")


async def popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(LOG_PATH):
        await update.message.reply_text("Henüz sorgu yapılmadı.")
        return
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    counter = {}
    for d in data:
        code = d['code']
        counter[code] = counter.get(code, 0) + 1
    sorted_codes = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    message = "🔥 En çok aranan 5 hata kodu:\n"
    for i, (code, count) in enumerate(sorted_codes[:5], 1):
        message += f"{i}. {code} – {count} sorgu\n"
    await update.message.reply_text(message)


async def download_log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Bu komutu kullanamazsınız.")
        return
    if export_log_to_csv():
        with open(LOG_CSV_PATH, "rb") as file:
            await update.message.reply_document(document=InputFile(file, filename="query_log.csv"))
    else:
        await update.message.reply_text("Log verisi bulunamadı veya boş.")


async def log_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Bu komutu kullanamazsınız.")
        return
    if not os.path.exists(LOG_PATH):
        await update.message.reply_text("Log verisi bulunamadı.")
        return
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        await update.message.reply_text("Log boş.")
        return
    summary = "🗒️ Son 5 sorgu:\n"
    for entry in data[-5:]:
        summary += f"👤 @{entry['username']} → {entry['code']}\n"
    await update.message.reply_text(summary)


# Botu başlat
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("random", random_command))
app.add_handler(CommandHandler("stats", stats_command))
app.add_handler(CommandHandler("popular", popular_command))
app.add_handler(CommandHandler("download_log", download_log_command))
app.add_handler(CommandHandler("log_summary", log_summary_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: c.application.create_task(handle_message(u, c))))

job_queue: JobQueue = app.job_queue
if job_queue:
    job_queue.run_repeating(send_log_summary, interval=21600, first=60)

app.run_polling()
