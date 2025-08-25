import html
from uuid import uuid4
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import InlineQueryResultArticle, InputTextMessageContent,InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, InlineQueryHandler,CallbackQueryHandler
from services.api_client import list_jobs
from config import TELEGRAM_TOKEN


def format_time(iso_time):
    if not iso_time:
        return "Unknown"
    try:
        data = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return data.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_time

def is_new_job(scraped_at):
    if not scraped_at:
        return False
    try:
        scraped_time = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        time_diff = datetime.now() - scraped_time.replace(tzinfo=None)
        is_new = time_diff.total_seconds() < 86400
        return is_new

    except ValueError:
        return False

def clean_text(text):
    text = BeautifulSoup(text, "html.parser").get_text()
    text = text.replace("\\n", "\n").replace("\r", "")
    return text

def format_job_details(job):
    title = html.escape(job.get("title", "No title"))
    company = html.escape(job.get("company", "Unknown"))
    posted = format_time(job.get("posted_at", ""))
    url = job.get("url", "")

    description = clean_text(job.get("description", "No description"))

    text = f"💼 <b>{title}</b>\n🏢 <i>{company}</i>\n🕒 {posted}\n\n{description}\n"
    if url:
        text += f"\n👉 <a href='{url}'>Apply here</a>"

    return text[:4000]

async def build_inline_result(job):
    title = html.escape(job.get("title", "No title"))
    company = html.escape(job.get("company", "Unknown"))
    url = job.get("url", "")
    posted = format_time(job.get("posted_at", ""))
    desc = clean_text(job.get("description", ""))[:3000]
    short_desc = html.escape(desc + ("..." if len(desc) > 3000 else ""))

    text = f"💼 <b>{title}</b>\n🏢 <i>{company}</i>\n📅 {posted}\n\n📝 {short_desc}"

    return InlineQueryResultArticle(
        id=str(uuid4()),
        title=title,
        description=f"{company} • {url}",
        input_message_content=InputTextMessageContent(text, parse_mode=ParseMode.HTML),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Ishni ochish", url=url or "https://t.me/IT_park_first_bot")]])
    )

async def start(update, context):
    await update.message.reply_text(
        "Salom! 👋\n\nMen ish e’lonlarini topuvchi botman.\n"
        "🔎 Qidirish uchun: @IT_park_first_bot <so'rov>\n"
        "📌 /latest - eng so‘nggi ishlar"
    )

async def send_jobs(update, page: int = 1):
    data = await list_jobs(search="", page=page)
    jobs = data.get("results", [])[:10]

    if not jobs:
        msg = "❌ Ishlar topilmadi."
        if update.callback_query:
            await update.callback_query.message.edit_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    keyboard = []

    for j in jobs:
        if is_new_job(j.get("scraped_at")):
            prefix = "🆕 "
        else:
            prefix = ""

        btn_text = prefix + j.get("title") + " @" + j.get("company")
        button = InlineKeyboardButton(text=btn_text, callback_data=f"job_{j.get('id')}_{page}")
        keyboard.append([button])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page-1}"))
    if data.get("next"):
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{page+1}"))
    if nav:
        keyboard.append(nav)

    markup = InlineKeyboardMarkup(keyboard)
    text = f"📋 Eng so‘nggi ishlar — <b>{page}-sahifa</b>"
    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)

async def show_job_detail(update, job, page: int):
    text = format_job_details(job)
    keyboard = [
        [InlineKeyboardButton("🌐 Ishni ochish", url=job.get("url", "https://t.me/IT_park_first_bot"))],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"page_{page}")]
    ]
    await update.callback_query.message.edit_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
    )

async def callback_handler(update, context):
    data = update.callback_query.data
    if data.startswith("page_"):
        await send_jobs(update, int(data.split("_")[1]))
    elif data.startswith("job_"):
        job_id, page = data.split("_")[1:]
        data = await list_jobs(search="", page=int(page))
        job = None
        for j in data.get("results", []):
            if str(j.get("id")) == job_id:
                job = j
                break
        if job:
            await show_job_detail(update, job, int(page))
        else:
            await update.callback_query.message.edit_text("❌ Ish topilmadi.")

async def latest(update, context):
    await send_jobs(update, page=1)

async def inline_query(update, context):
    query = update.inline_query.query.strip()
    page = int(update.inline_query.offset or "1")
    data = await list_jobs(search=query, page=page)
    results = data.get("results", [])

    if not results:
        await update.inline_query.answer([
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="❌ Hech narsa topilmadi",
                input_message_content=InputTextMessageContent("Kechirasiz, ish topilmadi.")
            )
        ], cache_time=5, is_personal=True)
        return

    articles = []
    for job in results:
        article = await build_inline_result(job)
        articles.append(article)

    if data.get("next"):
        next_offset = str(page + 1)
    else:
        next_offset = ""

    await update.inline_query.answer(
        articles,
        cache_time=5,
        is_personal=True,
        next_offset=next_offset
    )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(InlineQueryHandler(inline_query))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
