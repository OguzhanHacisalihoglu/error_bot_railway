# main.py (tam ve güncel versiyon – tüm komutlar bir arada)
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


def convert_pdf_to_json(pdf_path=PDF_PATH, json_path=JSON_PATH):
    doc = fitz.open(pdf_path)
    errors = {}
    for page in doc:
        text = page.get_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("ORA-") and ":" in line:
                code = line.split()[0].strip()
                explanation = " ".join(lines[i:i+5]).strip()
                errors[code] = explanation
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def load_data():
    if not os.path.exists(JSON_PATH):
        convert_pdf_to_json()
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


def search_error_code(code):
    data = load_data()
    code = code.strip().upper()
    if code in data:
        return data[code]
    for k in data:
        if code in k:
            return data[k]
    return None


def search_by_keyword(keyword):
    data = load_data()
    keyword = keyword.strip().lower()
    results = {}
    for code, text in data.items():
        if keyword in code.lower() or keyword in text.lower():
            results[code] = text
        elif keyword.replace("ora-", "") in code.lower():
            results[code] = text
        elif keyword.isdigit() and keyword in code:
            results[code] = text
    return results


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
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🔍 Lütfen bir anahtar kelime girin. Örnek: /search column")
        return
    keyword = " ".join(context.args)
    results = search_by_keyword(keyword)
    if not results:
        await update.message.reply_text(f"'{keyword}' ile ilgili sonuç bulunamadı.")
        return
    message = f"🔍 '{keyword}' için bulunan sonuçlar:\n"
    for code, text in list(results.items())[:5]:
        message += f"\n📘 {code}: {text[:150]}..."
    await update.message.reply_text(message)


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Lütfen geri bildiriminizi yazın. Örn: /feedback ORA-01017 çevirisi geliştirilmeli.")
        return
    await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"📩 Feedback from {user.username or user.first_name}:\n{message}")
    await update.message.reply_text("Teşekkürler! Geri bildiriminiz iletildi ✅")


async def reload_json_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return
    convert_pdf_to_json()
    await update.message.reply_text("✅ JSON veritabanı yeniden oluşturuldu.")


async def add_error_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Bu komutu kullanamazsınız.")
        return
    try:
        code = context.args[0].strip().upper()
        explanation = " ".join(context.args[1:]).strip()
        data = load_data()
        data[code] = explanation
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        await update.message.reply_text(f"✅ {code} başarıyla eklendi veya güncellendi.")
    except Exception as e:
        await update.message.reply_text(f"Hata oluştu: {e}")


# main.py (tam ve güncel – Google'da arama linki eklendi)
# ... önceki kodlar aynı ...

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().upper()

    if user_input.isdigit():
        user_input = f"ORA-{user_input}"
    elif user_input.startswith("ORA-") and not user_input[4:].isdigit():
        await update.message.reply_text("Geçerli bir ORA kodu girin. Örn: ORA-00904 veya sadece 904")
        return

    user = update.message.from_user

    if user_input.startswith("ORA-"):
        original_text = search_error_code(user_input)
        log_query(user.id, user.username or "Anonim", user_input)
        if original_text:
            try:
                translated_text = GoogleTranslator(source='auto', target='tr').translate(original_text)
                message = (
                    f"📘 Hata: {user_input}\n\n"
                    f"🧠 Açıklama:\n{original_text}\n\n"
                    f"🔄 Türkçe Çeviri:\n{translated_text}\n\n"
                    f"🔗 Detay: https://docs.oracle.com/error-help/db/{user_input.lower()}"
                )
            except:
                message = f"📘 {user_input}: {original_text}"

            # Google arama bağlantısı
            google_url = f"https://www.google.com/search?q={user_input}"
            message += f"\n🌐 Google'da Ara:\n{google_url}"
        else:
            message = "❗ Bu hata kodu veritabanında bulunamadı."

        await update.message.reply_text(message)
    else:
        await update.message.reply_text("❓ Lütfen geçerli bir ORA hata kodu girin. (örn: ORA-00904 ya da sadece 904)")

# main.py (tam ve güncel – eksik random, stats, popular, log_summary, download_log fonksiyonları eklendi)
# ... önceki kod devam ediyor ...

# Eksik fonksiyonları tanımlıyoruz:

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


app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("search", search_command))
app.add_handler(CommandHandler("feedback", feedback_command))
app.add_handler(CommandHandler("reload_json", reload_json_command))
app.add_handler(CommandHandler("add_error", add_error_command))
app.add_handler(CommandHandler("random", random_command))
app.add_handler(CommandHandler("stats", stats_command))
app.add_handler(CommandHandler("popular", popular_command))
app.add_handler(CommandHandler("download_log", download_log_command))
app.add_handler(CommandHandler("log_summary", log_summary_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

job_queue: JobQueue = app.job_queue
if job_queue:
    job_queue.run_repeating(log_summary_command, interval=21600, first=60)

app.run_polling()
