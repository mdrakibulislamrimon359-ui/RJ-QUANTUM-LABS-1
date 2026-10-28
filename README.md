RS Team Bangladesh Premium Telegram AI Bot
A Python Telegram bot using python-telegram-bot and Google's Gemini API.
Features
AI replies to incoming non-command messages in private chats and groups.
Bengali, Banglish, and English responses based on the incoming message.
Admin-only /ai on and /ai off.
Admin can add/remove text commands using /addcommand and /delcommand.
Command data and AI enabled state are stored in bot_data.json.
Default commands can also be changed in DEFAULT_COMMANDS inside bot.py.
Requirements
A Telegram bot token from the official @BotFather.
A Gemini API key from Google AI Studio, with access to at least one configured model.
A GitHub repository.
A Render Background Worker.
Local run
Install Python 3.11 or newer.
In this folder run: pip install -r requirements.txt
Set environment variables BOT_TOKEN, GEMINI_API_KEY, and optionally ADMIN_USERNAME / ADMIN_USER_ID.
Run: python bot.py
Do not commit API keys or bot tokens to GitHub.
Render deployment
Push these files to a GitHub repository.
In Render create a Background Worker from that repository.
Build command: pip install -r requirements.txt
Start command: python bot.py
Add environment variables:
BOT_TOKEN = token from BotFather
GEMINI_API_KEY = your Gemini API key
ADMIN_USERNAME = RJteam1 (without @)
GEMINI_MODEL = gemini-3.8-flash (change to a model enabled for your API key if needed)
DATA_FILE = bot_data.json
Deploy and inspect Render Logs for startup errors.
The included render.yaml can also be used as a Blueprint.
Group messages
Telegram bots may not receive every ordinary group message while privacy mode is enabled. In @BotFather, use /setprivacy, select your bot, then choose Disable. Re-add the bot to the group if Telegram asks you to. Give it only the permissions it needs. Note: bots cannot read messages sent before they joined.
Admin identity
By default, the owner username is RJteam1. Usernames can change, so optionally set ADMIN_USER_ID to the owner's numeric Telegram ID for a more stable admin check. Keep this ID in Render environment variables, not in public code.
Custom commands
Add: /addcommand welcome | RS Team Bangladesh-এ স্বাগতম!
Use: /welcome
Delete: /delcommand welcome
List: /commands
To change the built-in /about, /rules, or /contact answers, edit DEFAULT_COMMANDS in bot.py and redeploy.
Important limitations
"All messages" means the bot responds to incoming non-command messages it receives. It ignores messages sent by bots and Telegram slash commands unless they are a built-in/custom command.
This starter version replies to photos, audio, video, stickers, and files based on their message type/caption; it does not yet inspect image/audio/video/file contents.
A very busy group can generate many Gemini requests. Use a smaller group or add rate limits before broad rollout.
Render's ordinary filesystem may be ephemeral. A JSON file alone is not guaranteed to survive redeploys or instance replacement. If you need reliable persistence, attach a persistent disk where supported by your Render service/plan, or use an external database. Back up bot_data.json regularly.
Do not use the bot for unsolicited spam or to message people who have not opted in.
