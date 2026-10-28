import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from telegram import BotCommand, Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# RS Team Bangladesh Premium Telegram AI Bot
# Secrets must be configured as Render environment variables, never in this file.

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("rs-team-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "RJteam1").strip().lstrip("@").lower()
try:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0") or "0")
except ValueError:
    ADMIN_USER_ID = 0

DATA_FILE = Path(os.getenv("DATA_FILE", "bot_data.json"))
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
MODEL_CANDIDATES = list(dict.fromkeys([
    DEFAULT_MODEL,
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]))

SYSTEM_PROMPT = os.getenv(
    "AI_SYSTEM_PROMPT",
    "You are RS Team Bangladesh Premium AI Bot, a helpful and respectful assistant. "
    "Reply naturally in the language used by the user: Bengali for Bengali, simple "
    "Bengali/Banglish for Banglish, and English for English. Answer questions clearly. "
    "Do not invent facts, links, prices, or claims. If you are unsure, say so. "
    "Keep replies suitable for a Telegram chat and reasonably concise."
)

DEFAULT_COMMANDS = {
    "about": "RS Team Bangladesh Premium AI Bot. Owner: @RJteam1",
    "rules": "কমিউনিটিতে সবাইকে সম্মান করুন। স্প্যাম, প্রতারণা ও অন্যের গোপনীয়তা লঙ্ঘন করবেন না।",
    "contact": "যোগাযোগ: @RJteam1",
}

# Avoid storing unlimited data or a conversation history in this starter bot.
DEFAULT_DATA: dict[str, Any] = {
    "ai_enabled": True,
    "custom_commands": {},
}


def load_data() -> dict[str, Any]:
    try:
        if DATA_FILE.exists():
            loaded = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = DEFAULT_DATA.copy()
                data.update(loaded)
                if not isinstance(data.get("custom_commands"), dict):
                    data["custom_commands"] = {}
                return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load JSON data: %s", exc)
    return DEFAULT_DATA.copy()


DATA = load_data()


def save_data() -> None:
    """Write JSON atomically to reduce the chance of a partially written file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    temp_file.write_text(
        json.dumps(DATA, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_file.replace(DATA_FILE)


def is_admin(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    if ADMIN_USER_ID and user.id == ADMIN_USER_ID:
        return True
    return bool(user.username and user.username.lower() == ADMIN_USERNAME)


async def require_admin(update: Update) -> bool:
    if is_admin(update):
        return True
    if update.effective_message:
        await update.effective_message.reply_text(
            "⛔ এই কমান্ডটি শুধু বটের অনুমোদিত Admin ব্যবহার করতে পারবেন।"
        )
    return False


async def refresh_command_menu(application: Application) -> None:
    commands = [
        BotCommand("start", "বট চালু করুন"),
        BotCommand("help", "কমান্ড তালিকা"),
        BotCommand("commands", "সব কমান্ড দেখুন"),
        BotCommand("ai", "AI Reply ON/OFF"),
        BotCommand("addcommand", "নতুন কমান্ড যোগ করুন (Admin)"),
        BotCommand("delcommand", "কাস্টম কমান্ড মুছুন (Admin)"),
        BotCommand("broadcast", "বার্তা পাঠান (Admin)"),
        BotCommand("about", "বটের পরিচিতি"),
        BotCommand("rules", "কমিউনিটি নিয়ম"),
        BotCommand("contact", "Owner-এর সাথে যোগাযোগ"),
    ]
    try:
        await application.bot.set_my_commands(commands)
    except Exception:
        logger.exception("Could not update Telegram command menu")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🤖 স্বাগতম RS Team Bangladesh Premium AI Bot-এ!\n\n"
        "আমি মেসেজের উত্তর দিতে Gemini AI ব্যবহার করি।\n"
        "কমান্ড দেখতে /help লিখুন।"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📚 RS Team Bangladesh — Command Center\n\n"
        "/start — বট চালু\n"
        "/help — সাহায্য\n"
        "/commands — সব কমান্ড\n"
        "/ai on — AI Auto Reply চালু (Admin)\n"
        "/ai off — AI Auto Reply বন্ধ (Admin)\n"
        "/addcommand name | উত্তর — কাস্টম কমান্ড যোগ (Admin)\n"
        "/delcommand name — কাস্টম কমান্ড মুছুন (Admin)\n"
        "/broadcast বার্তা — যে চ্যাটে কমান্ড দেবেন, সেই চ্যাটে বার্তা পাঠায় (Admin)\n"
        "/about — বটের পরিচিতি\n"
        "/rules — কমিউনিটি নিয়ম\n"
        "/contact — Owner যোগাযোগ\n\n"
        "নতুন কমান্ডের উদাহরণ:\n"
        "/addcommand welcome | RS Team Bangladesh-এ স্বাগতম!"
    )
    await update.effective_message.reply_text(text)


async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["📋 কমান্ড তালিকা:"]
    for name, answer in DEFAULT_COMMANDS.items():
        lines.append(f"/{name} — {answer}")
    custom = DATA.get("custom_commands", {})
    if custom:
        lines.append("\n🛠️ Admin যোগ করা কমান্ড:")
        for name in sorted(custom):
            lines.append(f"/{name}")
    await update.effective_message.reply_text("\n".join(lines))


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(DEFAULT_COMMANDS["about"])


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(DEFAULT_COMMANDS["rules"])


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(DEFAULT_COMMANDS["contact"])


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update):
        return
    if not context.args or context.args[0].lower() not in {"on", "off"}:
        await update.effective_message.reply_text("ব্যবহার: /ai on অথবা /ai off")
        return
    DATA["ai_enabled"] = context.args[0].lower() == "on"
    save_data()
    state = "চালু ✅" if DATA["ai_enabled"] else "বন্ধ ⛔"
    await update.effective_message.reply_text(f"Gemini AI Auto Reply {state}")


async def addcommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update):
        return
    raw = update.effective_message.text.partition(" ")[2].strip()
    if "|" not in raw:
        await update.effective_message.reply_text(
            "ব্যবহার:\n/addcommand welcome | RS Team Bangladesh-এ স্বাগতম!"
        )
        return
    name, answer = [part.strip() for part in raw.split("|", 1)]
    name = name.lstrip("/").lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name):
        await update.effective_message.reply_text(
            "কমান্ডের নাম ইংরেজি অক্ষর দিয়ে শুরু করুন; শুধু a-z, 0-9 ও _ ব্যবহার করুন।"
        )
        return
    reserved = {"start", "help", "commands", "ai", "addcommand", "delcommand",
                "broadcast", "about", "rules", "contact"}
    if name in reserved:
        await update.effective_message.reply_text("এই নামটি আগে থেকেই সংরক্ষিত কমান্ডের জন্য ব্যবহৃত।")
        return
    if not answer:
        await update.effective_message.reply_text("কমান্ডের উত্তর খালি রাখা যাবে না।")
        return
    DATA.setdefault("custom_commands", {})[name] = answer[:3500]
    save_data()
    await update.effective_message.reply_text(
        f"✅ /{name} কমান্ড যোগ হয়েছে এবং JSON ফাইলে সংরক্ষিত হয়েছে।"
    )


async def delcommand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update):
        return
    if not context.args:
        await update.effective_message.reply_text("ব্যবহার: /delcommand welcome")
        return
    name = context.args[0].lstrip("/").lower()
    custom = DATA.setdefault("custom_commands", {})
    if name not in custom:
        await update.effective_message.reply_text("এই কাস্টম কমান্ডটি পাওয়া যায়নি।")
        return
    del custom[name]
    save_data()
    await update.effective_message.reply_text(f"🗑️ /{name} কমান্ড মুছে ফেলা হয়েছে।")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update):
        return
    message = update.effective_message.text.partition(" ")[2].strip()
    if not message:
        await update.effective_message.reply_text("ব্যবহার: /broadcast আপনার বার্তা")
        return
    # Safe starter behavior: broadcast only to the current chat, not a hidden user list.
    await update.effective_message.reply_text("📢 " + message[:4000])


async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return
    match = re.match(r"^/([a-zA-Z0-9_]+)(?:@\w+)?(?:\s|$)", message.text)
    if not match:
        return
    name = match.group(1).lower()
    answer = DATA.get("custom_commands", {}).get(name)
    if answer:
        await message.reply_text(str(answer)[:4000])


async def generate_ai_reply(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "⚠️ Gemini API Key সেট করা নেই। Render → Environment-এ GEMINI_API_KEY যোগ করুন।"

    def request_model() -> str:
        client = genai.Client(api_key=GEMINI_API_KEY)
        last_error = None
        for model in MODEL_CANDIDATES:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=700,
                    ),
                )
                answer = (response.text or "").strip()
                if answer:
                    return answer
                last_error = RuntimeError(f"{model} returned an empty response")
            except Exception as exc:
                last_error = exc
                logger.warning("Gemini model %s failed: %s", model, exc)
        raise RuntimeError(f"All Gemini models failed: {last_error}")

    try:
        return await asyncio.to_thread(request_model)
    except Exception:
        logger.exception("Gemini request failed")
        return (
            "দুঃখিত, এখন AI উত্তর দিতে পারছে না। Gemini API Key, API access, "
            "quota এবং GEMINI_MODEL সেটিংস পরীক্ষা করুন।"
        )


def describe_message(update: Update) -> str:
    message = update.effective_message
    if not message:
        return "ব্যবহারকারী একটি Telegram মেসেজ পাঠিয়েছেন।"
    if message.text:
        return message.text
    if message.caption:
        return f"ব্যবহারকারী মিডিয়া পাঠিয়েছেন। ক্যাপশন: {message.caption}"
    if message.photo:
        return "ব্যবহারকারী একটি ছবি পাঠিয়েছেন। ছবির ক্যাপশন নেই। ছবির বিষয়বস্তু না দেখে, বিনয়ের সঙ্গে কী সাহায্য দরকার তা জিজ্ঞেস করুন।"
    if message.voice:
        return "ব্যবহারকারী একটি voice message পাঠিয়েছেন। এই starter version অডিও ট্রান্সক্রাইব করে না; অডিওর বিষয়ে কী সাহায্য দরকার জিজ্ঞেস করুন।"
    if message.audio:
        return "ব্যবহারকারী একটি audio file পাঠিয়েছেন। এই starter version অডিও বিশ্লেষণ করে না; কী সাহায্য দরকার জিজ্ঞেস করুন।"
    if message.video:
        return "ব্যবহারকারী একটি video পাঠিয়েছেন। এই starter version ভিডিও বিশ্লেষণ করে না; কী সাহায্য দরকার জিজ্ঞেস করুন।"
    if message.sticker:
        emoji = message.sticker.emoji or "স্টিকার"
        return f"ব্যবহারকারী একটি Telegram sticker পাঠিয়েছেন ({emoji})। স্বাভাবিক ও সংক্ষিপ্ত উত্তর দিন।"
    if message.document:
        return f"ব্যবহারকারী একটি ফাইল পাঠিয়েছেন ({message.document.file_name or 'ফাইল'})। এই starter version ফাইলের বিষয়বস্তু পড়ে না; কী সাহায্য দরকার জিজ্ঞেস করুন।"
    if message.location:
        return "ব্যবহারকারী একটি লোকেশন পাঠিয়েছেন। ব্যক্তিগত ঠিকানা প্রকাশ না করে, কী সাহায্য দরকার জিজ্ঞেস করুন।"
    if message.contact:
        return "ব্যবহারকারী একটি contact card পাঠিয়েছেন। ব্যক্তিগত তথ্য পুনরাবৃত্তি না করে, কী সাহায্য দরকার জিজ্ঞেস করুন।"
    return "ব্যবহারকারী একটি Telegram মেসেজ পাঠিয়েছেন। সংক্ষিপ্তভাবে জিজ্ঞেস করুন কী সাহায্য দরকার।"


async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if not message or not user or user.is_bot:
        return
    if not DATA.get("ai_enabled", True):
        return

    # In groups, reply to ordinary messages too. Configure BotFather privacy mode off.
    prompt = describe_message(update)
    answer = await generate_ai_reply(prompt)
    # Telegram text messages have a 4096-character limit.
    await message.reply_text(answer[:4000])


async def post_init(application: Application) -> None:
    await refresh_command_menu(application)
    logger.info("Bot started. JSON file: %s", DATA_FILE.resolve())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled update error", exc_info=context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is missing; bot will start but AI replies will show setup warning.")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Known commands first; custom command handler catches other slash commands.
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("commands", commands_command))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("addcommand", addcommand))
    application.add_handler(CommandHandler("delcommand", delcommand))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("contact", contact_command))
    application.add_handler(MessageHandler(filters.COMMAND, custom_command))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, auto_reply))
    application.add_error_handler(error_handler)

    logger.info("Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
