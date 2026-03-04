import logging
import os
import json
import time
import aiohttp
import html
from collections import defaultdict
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_PAT")
GITHUB_REPO = "Bartixxx32/OnePlus-antirollchecker"
WORKFLOW_ID = "telegram_check.yml"
ADMIN_USER_ID = 277390840  # Bartixxx32's Telegram user ID
BOT_VERSION = "1.1.0"
BOT_START_TIME = time.time()

# Paths
STATS_FILE = os.environ.get("STATS_FILE", "/data/stats.json")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Stats Management ---
def load_stats():
    """Load stats from JSON file."""
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "total_checks": 0,
            "total_errors": 0,
            "users": {},
            "daily": {},
            "first_check": None
        }

def save_stats(stats):
    """Save stats to JSON file."""
    try:
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save stats: {e}")

def record_check(user_id, username):
    """Record a check in stats."""
    stats = load_stats()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    stats["total_checks"] += 1
    
    uid = str(user_id)
    if uid not in stats["users"]:
        stats["users"][uid] = {"name": username, "count": 0}
    stats["users"][uid]["count"] += 1
    stats["users"][uid]["name"] = username  # Update name in case it changed
    
    if today not in stats["daily"]:
        stats["daily"][today] = 0
    stats["daily"][today] += 1

    if not stats["first_check"]:
        stats["first_check"] = today
    
    save_stats(stats)

def record_error():
    """Record an error in stats."""
    stats = load_stats()
    stats["total_errors"] += 1
    save_stats(stats)

# --- Rate Limiting ---
user_requests = defaultdict(list)
RATE_LIMIT_COUNT = 2
RATE_LIMIT_WINDOW = 60  # seconds

# --- Helpers ---
def format_uptime():
    """Format bot uptime as human-readable string."""
    elapsed = int(time.time() - BOT_START_TIME)
    days, remainder = divmod(elapsed, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

DB_URL = "https://oneplusantiroll.netlify.app/database.json"

async def fetch_database():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DB_URL, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        logging.error(f"Failed to fetch database.json: {e}")
    return None

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 Device Status", callback_data="cmd_status"), InlineKeyboardButton("🔥 Latest Firmwares", callback_data="cmd_latest")],
        [InlineKeyboardButton("📥 Download Links", callback_data="cmd_download")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Handlers ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error, notify user, and DM admin with details."""
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    record_error()
    
    if isinstance(update, Update) and update.effective_message:
         await update.effective_message.reply_text("❌ An internal error occurred. Please try again later.")
    
    # DM admin with error details
    try:
        error_text = str(context.error) if context.error else "Unknown error"
        chat_info = ""
        user_info = ""
        if isinstance(update, Update):
            if update.effective_chat:
                chat_info = f"\n📍 Chat: <code>{update.effective_chat.id}</code>"
            if update.effective_user:
                name = update.effective_user.first_name
                name = html.escape(str(name)) if name else "Unknown"
                user_info = f"\n👤 User: {name} (<code>{update.effective_user.id}</code>)"
        
        error_text_esc = html.escape(error_text[:500])
        admin_msg = (
            f"🚨 <b>Bot Error Alert</b>\n\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"{chat_info}{user_info}\n\n"
            f"❌ <code>{error_text_esc}</code>"
        )
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=admin_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to notify admin: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text(
            "❌ This bot operates in the OnePlus ARB Checker group only.\n"
            "👉 Join here: https://t.me/oneplusarbchecker"
        )
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello! Send /check https://example.com/firmware.zip to analyze a firmware file.",
        reply_markup=get_main_keyboard()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available commands and usage."""
    msg = (
        "🤖 *OnePlus ARB Checker Bot*\n\n"
        "*Available Commands:*\n\n"
        "🔍 /check `https://...` — Analyze a firmware file\n"
        "   _Send a direct download link to a OnePlus firmware .zip_\n\n"
        "ℹ️ /about — Bot info, version & uptime\n"
        "❓ /help — Show this message\n\n"
        "*How it works:*\n"
        "1. Send /check with a firmware URL\n"
        "2. Bot triggers analysis via GitHub Actions\n"
        "3. Status updates appear in real-time\n"
        "4. Results are posted as a reply\n\n"
        "📋 _Rate limit: 2 checks per minute_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cmd_status":
        await query.message.reply_text("📱 Usage: /devicestatus <device_name_or_model>\nExample: /devicestatus OnePlus 12")
    elif query.data == "cmd_latest":
        await latest(update, context, is_callback=True)
    elif query.data == "cmd_download":
        await download_cmd(update, context, is_callback=True)

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot info, version, and uptime."""
    data = load_stats()
    uptime = format_uptime()
    
    msg = (
        f"ℹ️ *OnePlus ARB Checker Bot*\n\n"
        f"📦 *Version:* `{BOT_VERSION}`\n"
        f"⏱️ *Uptime:* {uptime}\n"
        f"🔢 *Total checks:* {data.get('total_checks', 0)}\n\n"
        f"🔗 [GitHub Repository](https://github.com/{GITHUB_REPO})\n"
        f"💬 [Support Group](https://t.me/oneplusarbchecker)\n\n"
        f"_Made with ❤️ by @Bartixxx32_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics (admin only)."""
    user = update.effective_user
    
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ This command is restricted to the bot admin.")
        return
    
    data = load_stats()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = data.get("daily", {}).get(today, 0)
    
    # Top 5 users
    sorted_users = sorted(data.get("users", {}).items(), key=lambda x: x[1]["count"], reverse=True)[:5]
    
    top_users_text = "\n".join(
        [f"  {i+1}. {html.escape(str(u[1]['name']))} — {u[1]['count']}" for i, u in enumerate(sorted_users)]
    ) or "  No data yet"
    
    msg = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"🔢 Total checks: <b>{data.get('total_checks', 0)}</b>\n"
        f"❌ Total errors: <b>{data.get('total_errors', 0)}</b>\n"
        f"📅 Today: <b>{today_count}</b>\n"
        f"📆 Since: {data.get('first_check', 'N/A')}\n\n"
        f"👥 <b>Top Users:</b>\n{top_users_text}"
    )
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        return
    
    if not context.args:
        await update.message.reply_text("📱 Usage: /devicestatus <device_name_or_model>\nExample: /devicestatus OnePlus 12")
        return
        
    query = " ".join(context.args).lower().strip()
    data = await fetch_database()
    if not data:
        await update.message.reply_text("❌ Failed to fetch database. Try again later.")
        return
        
    found_models = []
    for model, details in data.items():
        if query in model.lower() or query in details.get("device_name", "").lower():
            found_models.append((model, details))
            
    if not found_models:
        await update.message.reply_text(f"❌ No data found for '{query}'.")
        return
        
    text = f"📱 **Search results for '{query}':**\n\n"
    for model, details in found_models[:3]:
        device_name = details.get("device_name", model)
        text += f"*{device_name}* (`{model}`)\n"
        versions = details.get("versions", {})
        if not versions:
            text += "  No firmwares known.\n"
        else:
            current_versions = [v for v, v_det in versions.items() if v_det.get('status') == 'current']
            if not current_versions:
                current_versions = list(versions.keys())[-3:]
            for v in current_versions:
                v_det = versions[v]
                arb = v_det.get('arb', '?')
                regions = ", ".join(v_det.get('regions', []))
                status_icon = "🟢" if arb == 0 else "🔴"
                text += f"  • `{v}` ({regions}) - ARB: {arb} {status_icon}\n"
        text += "\n"
        
    if len(found_models) > 3:
        text += f"_...and {len(found_models)-3} more models._\n"
        
    await update.message.reply_text(text, parse_mode="Markdown")

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    data = await fetch_database()
    if not data:
        msg = "❌ Failed to fetch database."
        if is_callback:
            await update.callback_query.message.reply_text(msg)
        else:
            await update.message.reply_text(msg)
        return
        
    all_fw = []
    for model, details in data.items():
        dev_name = details.get('device_name', model)
        for v_name, v_det in details.get('versions', {}).items():
            if v_det.get('status') == 'current':
                # Use a default old date if first_seen is missing to push it to the bottom
                first_seen = v_det.get('first_seen') or '2000-01-01'
                all_fw.append((first_seen, dev_name, v_name, v_det))
                
    # Sort by first_seen (descending), then by version name (descending) as tie breaker
    all_fw.sort(key=lambda x: (x[0], x[2]), reverse=True)
    
    text = "🔥 **Latest Discovered Firmwares:**\n\n"
    for first_seen, dev_name, v_name, v_det in all_fw[:5]:
        arb = v_det.get('arb', '?')
        regions = ", ".join(v_det.get('regions', []))
        status_icon = "🟢" if arb == 0 else "🔴"
        
        date_str = ""
        if first_seen != '2000-01-01':
            date_str = f" 📅 `{first_seen}`"
            
        text += f"📱 *{dev_name}*\n  • `{v_name}` ({regions}) - ARB: {arb} {status_icon}{date_str}\n\n"
        
    if is_callback:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def download_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    text = (
        "📥 **Download OnePlus Firmwares**\n\n"
        "To find direct download links for your device, check our main website index:\n"
        "👉 [OnePlus ARB Checker](https://oneplusantiroll.netlify.app/)"
    )
    if is_callback:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        return
        
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast <message>")
        return
        
    message = " ".join(context.args)
    ALLOWED_GROUP_ID = -1003662409203
    try:
        await context.bot.send_message(
            chat_id=ALLOWED_GROUP_ID,
            text=f"📢 **Announcement**\n\n{message}",
            parse_mode="Markdown"
        )
        if update.effective_chat.id != ALLOWED_GROUP_ID:
            await update.message.reply_text("✅ Broadcast sent successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send broadcast: {e}")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Configuration
    ALLOWED_GROUP_ID = -1003662409203

    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id
    user_mention = f"@{user.username}" if user.username else user.first_name

    # 0. Rate Limiting
    now = time.time()
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < RATE_LIMIT_WINDOW]
    
    if len(user_requests[user_id]) >= RATE_LIMIT_COUNT:
        wait_time = int(RATE_LIMIT_WINDOW - (now - user_requests[user_id][0]))
        await update.message.reply_text(f"⚠️ Rate limit exceeded. Please wait {wait_time} seconds before making another request.")
        return
    
    user_requests[user_id].append(now)

    # 1. Restrict DMs
    if update.effective_chat.type == 'private':
        await update.message.reply_text(f"❌ DM checks are not allowed.\nPlease use the group: https://t.me/oneplusarbchecker")
        return

    # 2. Strict Group Check
    if chat_id != ALLOWED_GROUP_ID:
        await update.message.reply_text(f"❌ This bot is only authorized for the OnePlus ARB Checker group.")
        return

    if not context.args:
        try:
            await update.message.delete()
        except Exception as e:
            logging.error(f"Failed to delete message: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{user_mention}, ❌ Usage: /check https://..."
        )
        return

    firmware_url = context.args[0].strip('<>')
    
    # URL Validation
    if not firmware_url.startswith(("http://", "https://")) or " " in firmware_url:
        try:
            await update.message.delete()
        except Exception as e:
            logging.error(f"Failed to delete message: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{user_mention}, ❌ Invalid URL format.\nUsage: /check https://example.com/firmware.zip"
        )
        return

    # Record stats
    record_check(user_id, user_mention)

    message_id = update.message.message_id
    message_thread_id = update.effective_message.message_thread_id

    # Dynamic Thread Handling
    request_chat_id = str(chat_id)
    if message_thread_id:
        request_chat_id = f"{chat_id}_{message_thread_id}"

    # Reply immediately
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🚀 Initiating check...",
        message_thread_id=message_thread_id,
        reply_to_message_id=message_id
    )

    # Trigger GitHub Action
    success = await trigger_github_workflow(firmware_url, request_chat_id, message_id, user_mention, status_msg.message_id)

    if success:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✅ Check started! Waiting for GitHub Actions runner..."
        )
    else:
        record_error()
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ Failed to trigger GitHub Action. Check logs/credentials."
        )

async def trigger_github_workflow(url, chat_id, message_id, user_mention, status_message_id):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}",
    }
    data = {
        "ref": "main",
        "inputs": {
            "firmware_url": url,
            "request_chat_id": str(chat_id),
            "request_message_id": str(message_id),
            "request_user_name": user_mention,
            "request_status_message_id": str(status_message_id)
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{WORKFLOW_ID}/dispatches",
                headers=headers,
                json=data,
                timeout=30
            ) as response:
                
                if response.status == 204:
                    logging.info("Workflow triggered successfully.")
                    return True
                else:
                    text = await response.text()
                    logging.error(f"Failed to trigger workflow: {response.status} {text}")
                    return False
            
    except Exception as e:
        logging.error(f"Network error triggering workflow: {e}")
        return False


if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN or not GITHUB_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN and GITHUB_PAT environment variables must be set.")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('check', check))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('help', help_cmd))
    application.add_handler(CommandHandler('about', about))
    
    # New commands
    application.add_handler(CommandHandler('devicestatus', status_cmd))
    application.add_handler(CommandHandler('latest', latest))
    application.add_handler(CommandHandler('download', download_cmd))
    application.add_handler(CommandHandler('broadcast', broadcast))
    
    # Callback Query Handler for Inline Keyboards
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_error_handler(error_handler)
    
    print(f"Bot v{BOT_VERSION} is running...")
    application.run_polling(poll_interval=1.0, timeout=30)
