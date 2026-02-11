import logging
import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_PAT")
GITHUB_REPO = "Bartixxx32/OnePlus-antirollchecker" # Replace with your repo
WORKFLOW_ID = "telegram_check.yml"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text(
            "❌ This bot operates in the OnePlusOTA group only.\n"
            "👉 Join here: https://t.me/oneplusarbchecker"
        )
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello! Send /check <firmware_url> to analyze a firmware file."
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Configuration
    ALLOWED_GROUP_ID = -1003662409203

    chat_id = update.effective_chat.id
    user = update.effective_user
    user_mention = f"@{user.username}" if user.username else user.first_name

    # 1. Restrict DMs
    if update.effective_chat.type == 'private':
        await update.message.reply_text(f"❌ DM checks are not allowed.\nPlease use the group: https://t.me/oneplusarbchecker")
        return

    # 2. Strict Group Check (Optional, but requested "na grupce")
    if chat_id != ALLOWED_GROUP_ID:
        await update.message.reply_text(f"❌ This bot is only authorized for the OnePlusOTA group.")
        return

    firmware_url = context.args[0]
    
    # URL Validation
    if not firmware_url.startswith(("http://", "https://")) or " " in firmware_url:
        await update.message.reply_text("❌ Invalid URL. Please provide a valid Direct Download Link starting with http:// or https://")
        return

    message_id = update.message.message_id
    message_thread_id = update.effective_message.message_thread_id

    # Dynamic Thread Handling: If in a topic, reply in that topic; otherwise main group
    request_chat_id = str(chat_id)
    if message_thread_id:
        request_chat_id = f"{chat_id}_{message_thread_id}"

    # Reply immediately
    status_msg = await update.message.reply_text(f"🚀 Initiating check for {firmware_url}...", reply_to_message_id=message_id)

    # Trigger GitHub Action
    # Restore passing message_id to reply to the user's command
    success = trigger_github_workflow(firmware_url, request_chat_id, message_id, user_mention, status_msg.message_id)

    if success:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✅ Check started! I will reply to your original message when results are ready."
        )
    else:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ Failed to trigger GitHub Action. Check logs/credentials."
        )

def trigger_github_workflow(url, chat_id, message_id, user_mention, status_message_id):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}",
    }
    data = {
        "ref": "main", # Target the main branch
        "inputs": {
            "firmware_url": url,
            "request_chat_id": str(chat_id),
            "request_message_id": str(message_id),
            "request_user_name": user_mention,
            "request_status_message_id": str(status_message_id)
        }
    }
    
    response = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{WORKFLOW_ID}/dispatches",
        headers=headers,
        json=data
    )
    
    if response.status_code == 204:
        logging.info("Workflow triggered successfully.")
        return True
    else:
        logging.error(f"Failed to trigger workflow: {response.status_code} {response.text}")
        return False

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN or not GITHUB_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN and GITHUB_PAT environment variables must be set.")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    check_handler = CommandHandler('check', check)
    
    application.add_handler(start_handler)
    application.add_handler(check_handler)
    
    print("Bot is running...")
    application.run_polling()
