import os
import asyncio
import logging
import random

from google import genai
from google.genai import types

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")


# =========================================================
# GEMINI CLIENT
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# GEMINI MODELS
# =========================================================
#
# Primary model আগে চেষ্টা করবে।
# সমস্যা হলে fallback model-এ যাবে।
#
# =========================================================

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
]


# =========================================================
# REQUEST CONTROL
# =========================================================

GEMINI_SEMAPHORE = asyncio.Semaphore(3)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format=(
        "%(asctime)s - %(name)s - "
        "%(levelname)s - %(message)s"
    ),
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# BOT INFORMATION
# =========================================================

ABOUT_TEXT = """
🤖 About AI Assistant

আমি তোমার AI Assistant। ❤️

আমি RJ Team Bangladesh Hacker Community-এর পক্ষ থেকে
তোমার বন্ধু হিসেবে তোমার বিভিন্ন প্রশ্নের উত্তর দেওয়ার
চেষ্টা করি। 😊

💬 সাধারণ প্রশ্ন → সুন্দর উত্তর
😂 মজার SMS → মজার reply
❤️ Emotional SMS → emotional reply
🌐 Translation → যেকোনো ভাষার অনুবাদ

👑 Owner: @RJteam1
📢 Channel: @RJteam123890

🤝 RJ Team Bangladesh Hacker Community
"""


# =========================================================
# AI PERSONALITY
# =========================================================

SYSTEM_PROMPT = """
তুমি একটি বন্ধুসুলভ Telegram AI Assistant।

তুমি RJ Team Bangladesh Hacker Community-এর পক্ষ থেকে
ব্যবহারকারীর সাথে বন্ধুর মতো কথা বলবে।

সবচেয়ে গুরুত্বপূর্ণ নিয়ম:

ব্যবহারকারী যে ভাষাতেই SMS পাঠাক না কেন,
সাধারণ AI reply অবশ্যই বাংলায় দিতে হবে।

English SMS → বাংলায় উত্তর
Banglish SMS → বাংলায় উত্তর
বাংলা SMS → বাংলায় উত্তর
অন্য ভাষার SMS → বাংলায় উত্তর

RULES:

1. সাধারণ প্রশ্ন হলে সরাসরি, পরিষ্কার ও সুন্দর বাংলায় উত্তর দাও।

2. মজার SMS হলে বাংলায় মজার, playful এবং হাস্যকর reply দাও।
প্রয়োজনে 😂 😄 🤣 😆 ব্যবহার করতে পারো।

3. Emotional SMS হলে বাংলায় আন্তরিক, সুন্দর ও emotional reply দাও।
প্রয়োজনে ❤️ 🥺 😔 💔 ব্যবহার করতে পারো।

4. দুঃখের SMS হলে সহানুভূতিশীল বাংলায় উত্তর দাও।

5. ভালোবাসা বা romantic SMS হলে কোমল ও সুন্দর বাংলায় উত্তর দাও।

6. রাগের SMS হলে শান্ত ও ভদ্র বাংলায় উত্তর দাও।

7. সব SMS-কে emotional বানাবে না।
শুধু সত্যিই emotional SMS হলে emotional tone ব্যবহার করবে।

8. প্রশ্ন করলে প্রশ্নের উত্তর সরাসরি বাংলায় দাও।

9. ব্যবহারকারী English-এ প্রশ্ন করলেও উত্তর বাংলায় দাও।

10. ব্যবহারকারী Banglish-এ লিখলেও উত্তর বাংলা অক্ষরে দেওয়ার চেষ্টা করো।

11. উত্তর natural এবং মানুষের মতো হবে।

12. সাধারণ SMS-এর উত্তর খুব বড় করবে না।

13. প্রয়োজন অনুযায়ী 1-3টি emoji ব্যবহার করো।

14. একই reply বারবার হুবহু ব্যবহার করবে না।

15. গুরুতর বিষয়ে মজা করবে না।

16. ব্যবহারকারীর মূল বক্তব্য বুঝে reply করবে।

17. সাধারণ AI reply-এর মধ্যে অপ্রয়োজনীয় English ব্যবহার করবে না।

18. Translation command ব্যবহার করলে Translation-এর নির্দেশনা অনুসরণ করবে।

19. উত্তর সংক্ষিপ্ত, স্বাভাবিক এবং Telegram chat-এর উপযোগী রাখবে।

20. অপ্রয়োজনীয় heading বা দীর্ঘ explanation দেবে না,
যদি ব্যবহারকারী বিস্তারিত না চায়।
"""


# =========================================================
# ERROR TYPE CHECK
# =========================================================

def get_error_type(error_text: str):

    text = error_text.lower()

    # -----------------------------------------------------
    # QUOTA / RATE LIMIT
    # -----------------------------------------------------

    quota_patterns = [
        "429",
        "resource_exhausted",
        "quota exceeded",
        "generate_content_free_tier_requests",
        "rate limit",
        "too many requests",
    ]

    if any(
        pattern in text
        for pattern in quota_patterns
    ):
        return "quota"

    # -----------------------------------------------------
    # TEMPORARY SERVER ERROR
    # -----------------------------------------------------

    transient_patterns = [
        "500",
        "502",
        "503",
        "504",
        "service unavailable",
        "internal server error",
        "bad gateway",
        "gateway timeout",
        "high demand",
        "temporarily unavailable",
        "timeout",
    ]

    if any(
        pattern in text
        for pattern in transient_patterns
    ):
        return "transient"

    # -----------------------------------------------------
    # MODEL NOT AVAILABLE
    # -----------------------------------------------------

    unavailable_patterns = [
        "404",
        "not_found",
        "not found",
        "model is not available",
        "model is unavailable",
        "no longer available",
    ]

    if any(
        pattern in text
        for pattern in unavailable_patterns
    ):
        return "unavailable"

    return "other"


# =========================================================
# GEMINI GENERATOR
# =========================================================

async def generate_gemini(
    prompt,
    system_instruction=None,
):

    async with GEMINI_SEMAPHORE:

        quota_failed_models = []
        temporary_failed_models = []

        # -------------------------------------------------
        # প্রতিটি model একবার করে চেষ্টা
        # -------------------------------------------------

        for model_index, model_name in enumerate(
            GEMINI_MODELS
        ):

            # -------------------------------------------------
            # প্রথম model-এ 1 attempt
            # fallback model-এও unnecessary retry কমানো হয়েছে
            # -------------------------------------------------

            max_attempts = 1

            for attempt in range(
                1,
                max_attempts + 1
            ):

                try:

                    logger.info(
                        "Gemini request | "
                        "model=%s | attempt=%s/%s",
                        model_name,
                        attempt,
                        max_attempts,
                    )

                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        max_output_tokens=500,
                        automatic_function_calling=(
                            types.AutomaticFunctionCallingConfig(
                                disable=True
                            )
                        ),
                    )

                    response = (
                        await client.aio.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=config,
                        )
                    )

                    answer = (
                        response.text or ""
                    ).strip()

                    # -------------------------------------------------
                    # SUCCESS
                    # -------------------------------------------------

                    if answer:

                        logger.info(
                            "Gemini success | model=%s",
                            model_name,
                        )

                        return answer

                    logger.warning(
                        "Gemini empty response | model=%s",
                        model_name,
                    )

                    break

                except Exception as e:

                    error_text = str(e)

                    error_type = get_error_type(
                        error_text
                    )

                    logger.error(
                        "Gemini error | "
                        "model=%s | "
                        "type=%s | "
                        "attempt=%s/%s | %s",
                        model_name,
                        error_type,
                        attempt,
                        max_attempts,
                        error_text,
                    )

                    # =================================================
                    # QUOTA ERROR
                    # =================================================

                    if error_type == "quota":

                        quota_failed_models.append(
                            model_name
                        )

                        logger.warning(
                            "Quota exhausted | "
                            "model=%s | "
                            "trying next model",
                            model_name,
                        )

                        # -------------------------------------------------
                        # QUOTA ERROR হলে অপেক্ষা না করে সরাসরি next model
                        # -------------------------------------------------

                        break

                    # =================================================
                    # TEMPORARY ERROR
                    # =================================================

                    if error_type == "transient":

                        temporary_failed_models.append(
                            model_name
                        )

                        logger.warning(
                            "Temporary Gemini error | "
                            "model=%s",
                            model_name,
                        )

                        # -------------------------------------------------
                        # শুধু temporary error হলে ছোট delay
                        # -------------------------------------------------

                        if model_index < len(
                            GEMINI_MODELS
                        ) - 1:

                            wait_time = (
                                random.uniform(
                                    1.0,
                                    2.5,
                                )
                            )

                            await asyncio.sleep(
                                wait_time
                            )

                        break

                    # =================================================
                    # MODEL UNAVAILABLE
                    # =================================================

                    if error_type == "unavailable":

                        logger.warning(
                            "Model unavailable | "
                            "model=%s | "
                            "trying next model",
                            model_name,
                        )

                        break

                    # =================================================
                    # OTHER ERROR
                    # =================================================

                    logger.warning(
                        "Unknown Gemini error | "
                        "model=%s | "
                        "trying next model",
                        model_name,
                    )

                    break

        # =========================================================
        # ALL MODELS FAILED
        # =========================================================

        logger.error(
            "ALL GEMINI MODELS FAILED | "
            "quota_models=%s | temporary_models=%s",
            quota_failed_models,
            temporary_failed_models,
        )

        # ---------------------------------------------------------
        # যদি সব model quota exhausted হয়
        # ---------------------------------------------------------

        if (
            len(quota_failed_models)
            == len(GEMINI_MODELS)
        ):

            return "__GEMINI_QUOTA_EXHAUSTED__"

        # ---------------------------------------------------------
        # অন্য কোনো সমস্যা
        # ---------------------------------------------------------

        return None


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "ℹ️ About",
                callback_data="about",
            ),
            InlineKeyboardButton(
                "🌐 Translate",
                callback_data="translate_help",
            ),
        ],
        [
            InlineKeyboardButton(
                "📢 Channel",
                url="https://t.me/RJteam123890",
            ),
            InlineKeyboardButton(
                "👑 Owner",
                url="https://t.me/RJteam1",
            ),
        ],
    ]

    await update.message.reply_text(
        "👋 হ্যালো বন্ধু! ❤️\n\n"
        "আমি তোমার AI Assistant। 🤖\n\n"
        "💬 যেকোনো SMS পাঠাও।\n"
        "😂 মজার হলে মজার reply\n"
        "❤️ Emotional হলে emotional reply\n"
        "🤔 প্রশ্ন হলে সুন্দর উত্তর\n"
        "🌐 Translation-ও করা যাবে।\n\n"
        "নিচের Button ব্যবহার করতে পারো 👇",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        "🤖 Bot Help\n\n"
        "💬 যেকোনো SMS পাঠাও।\n"
        "🇧🇩 AI reply সবসময় বাংলায় হবে।\n"
        "😂 মজার হলে মজার reply\n"
        "❤️ Emotional হলে emotional reply\n"
        "🤔 প্রশ্ন হলে বাংলায় উত্তর\n\n"
        "🌐 Translate:\n"
        "/translate Hello, how are you?\n\n"
        "ℹ️ About:\n"
        "/about"
    )


# =========================================================
# ABOUT
# =========================================================

async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "👑 Owner",
                url="https://t.me/RJteam1",
            ),
            InlineKeyboardButton(
                "📢 Channel",
                url="https://t.me/RJteam123890",
            ),
        ]
    ]

    await update.message.reply_text(
        ABOUT_TEXT,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        disable_web_page_preview=True,
    )


# =========================================================
# AI REPLY
# =========================================================

async def ai_reply(
    text,
):

    answer = await generate_gemini(
        prompt=text,
        system_instruction=SYSTEM_PROMPT,
    )

    # -----------------------------------------------------
    # QUOTA EXHAUSTED
    # -----------------------------------------------------

    if answer == "__GEMINI_QUOTA_EXHAUSTED__":

        return (
            "⚠️ এই মুহূর্তে AI-এর দৈনিক API quota শেষ হয়ে গেছে।\n\n"
            "কিছু সময় পরে আবার চেষ্টা করুন। ❤️"
        )

    # -----------------------------------------------------
    # OTHER ERROR
    # -----------------------------------------------------

    if not answer:

        return (
            "😅 এই মুহূর্তে AI সার্ভার ব্যস্ত আছে।\n\n"
            "একটু পরে আবার SMS পাঠাও। ❤️"
        )

    return answer


# =========================================================
# TRANSLATE
# =========================================================

async def translate_text(
    text,
):

    prompt = f"""
Translate the following text naturally.

Automatically detect the source language.

If the user explicitly specifies a target language,
translate into that target language.

If no target language is specified,
translate into Bangla.

Return ONLY the translated text.

Do not explain.
Do not add quotation marks.

Text:
{text}
"""

    result = await generate_gemini(
        prompt=prompt,
        system_instruction=(
            "You are a professional translation assistant. "
            "Return only the requested translation."
        ),
    )

    if result == "__GEMINI_QUOTA_EXHAUSTED__":

        return (
            "⚠️ Gemini API quota শেষ হয়ে গেছে।\n"
            "কিছু সময় পরে আবার চেষ্টা করুন।"
        )

    if not result:

        return (
            "❌ Translation সার্ভার এই মুহূর্তে ব্যস্ত।\n"
            "কিছুক্ষণ পরে আবার চেষ্টা করুন।"
        )

    return result


# =========================================================
# TRANSLATE COMMAND
# =========================================================

async def translate_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not context.args:

        await update.message.reply_text(
            "🌐 Translate ব্যবহার করার নিয়ম:\n\n"
            "/translate Hello, how are you?\n\n"
            "ডিফল্টভাবে বাংলা translation দেওয়া হবে। ❤️"
        )

        return

    text = " ".join(
        context.args
    )

    try:

        await update.message.chat.send_action(
            "typing"
        )

    except Exception:
        pass

    result = await translate_text(
        text
    )

    await update.message.reply_text(
        "🌐 Translation:\n\n" + result,
        disable_web_page_preview=True,
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    # =====================================================
    # ABOUT
    # =====================================================

    if query.data == "about":

        keyboard = [
            [
                InlineKeyboardButton(
                    "👑 Owner",
                    url="https://t.me/RJteam1",
                ),
                InlineKeyboardButton(
                    "📢 Channel",
                    url="https://t.me/RJteam123890",
                ),
            ]
        ]

        await query.message.reply_text(
            ABOUT_TEXT,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            disable_web_page_preview=True,
        )

        return

    # =====================================================
    # TRANSLATE HELP
    # =====================================================

    if query.data == "translate_help":

        await query.message.reply_text(
            "🌐 Translate\n\n"
            "যেকোনো ভাষার লেখা translate করতে পারো।\n\n"
            "উদাহরণ:\n"
            "/translate Hello, how are you?\n\n"
            "ডিফল্টভাবে বাংলা translation দেওয়া হবে। ❤️"
        )

        return


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = update.message.text.strip()

    if not text:
        return

    try:

        await update.message.chat.send_action(
            "typing"
        )

    except Exception:
        pass

    # -----------------------------------------------------
    # AI
    # -----------------------------------------------------

    answer = await ai_reply(
        text
    )

    # -----------------------------------------------------
    # Save last reply
    # -----------------------------------------------------

    context.user_data[
        "last_ai_reply"
    ] = answer

    # -----------------------------------------------------
    # Translate button
    # -----------------------------------------------------

    keyboard = [
        [
            InlineKeyboardButton(
                "🌐 Translate",
                callback_data="translate_last",
            )
        ]
    ]

    await update.message.reply_text(
        answer,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        disable_web_page_preview=True,
    )


# =========================================================
# TRANSLATE LAST AI REPLY
# =========================================================

async def translate_last(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    text = context.user_data.get(
        "last_ai_reply"
    )

    if not text:

        await query.message.reply_text(
            "❌ আগের reply পাওয়া যাচ্ছে না।"
        )

        return

    try:

        await query.message.chat.send_action(
            "typing"
        )

    except Exception:
        pass

    result = await translate_text(
        text
    )

    await query.message.reply_text(
        "🌐 Translation:\n\n" + result,
        disable_web_page_preview=True,
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.error(
        "Telegram error: %s",
        context.error,
        exc_info=True,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # =====================================================
    # COMMANDS
    # =====================================================

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "about",
            about_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "translate",
            translate_command,
        )
    )

    # =====================================================
    # BUTTONS
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            translate_last,
            pattern=r"^translate_last$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(about|translate_help)$",
        )
    )

    # =====================================================
    # TEXT MESSAGES
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    # =====================================================
    # ERROR
    # =====================================================

    application.add_error_handler(
        error_handler
    )

    # =====================================================
    # RENDER
    # =====================================================

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    render_url = os.getenv(
        "RENDER_EXTERNAL_URL"
    )

    # =====================================================
    # WEBHOOK
    # =====================================================

    if render_url:

        webhook_url = (
            render_url.rstrip("/")
            + "/telegram/"
            + BOT_TOKEN
        )

        logger.info(
            "Starting Render webhook..."
        )

        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="telegram/" + BOT_TOKEN,
            webhook_url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

    # =====================================================
    # POLLING
    # =====================================================

    else:

        logger.info(
            "RENDER_EXTERNAL_URL not found."
        )

        logger.info(
            "Starting Telegram polling..."
        )

        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
