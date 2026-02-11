#!/usr/bin/env python3
import argparse
import requests
import sys

def send_telegram_message(token, chat_id, message, reply_to=None, message_thread_id=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram message sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        sys.exit(1)

def delete_telegram_message(token, chat_id, message_id):
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"Telegram message {message_id} deleted successfully.")
    except Exception as e:
        print(f"Failed to delete Telegram message: {e}")
        # Do not exit with error, as deletion is secondary

def main():
    parser = argparse.ArgumentParser(description="Send Telegram notification for new firmware.")
    parser.add_argument("--token", required=True, help="Telegram Bot Token")
    parser.add_argument("--chat-id", required=True, help="Telegram Chat ID")
    parser.add_argument("--device", required=True, help="Device Name")
    parser.add_argument("--variant", help="Device Variant (Optional)")
    parser.add_argument("--version", required=True, help="Firmware Version")
    parser.add_argument("--arb", required=True, help="ARB Index")
    parser.add_argument("--md5", help="MD5 Checksum")
    parser.add_argument("--url", help="Download URL")
    
    # New arguments for interactive bot
    parser.add_argument("--reply-to", help="Message ID to reply to")
    parser.add_argument("--user-mention", help="User name to mention (e.g. @username)")
    parser.add_argument("--delete-message-id", help="Message ID to delete after sending")

    # Extended metadata
    parser.add_argument("--product", help="Product Name")
    parser.add_argument("--security-patch", help="Security Patch Level")
    parser.add_argument("--build-id", help="Build ID")
    
    # Error handling
    parser.add_argument("--error", help="Error message to send instead of result")

    args = parser.parse_args()

    # Parse chat_id for thread_id
    chat_id = args.chat_id
    message_thread_id = None
    if "_" in chat_id:
        # Assuming format CHATID_THREADID. Note: Chat ID can be negative. 
        # So we should split by the LAST underscore if possible, or handle negative sign carefuly.
        # But usually formatted as "-100123123_12"
        try:
            parts = chat_id.rsplit("_", 1)
            if len(parts) == 2:
                chat_id = parts[0]
                message_thread_id = parts[1]
        except:
            pass

    # Construct the message
    message = ""
    if args.user_mention:
        message += f"Hello {args.user_mention}, "
    
    if args.error:
        message += f"an error occurred during the check:\n\n{args.error}"
        send_telegram_message(args.token, chat_id, message, args.reply_to, message_thread_id)
        # Verify if we should delete the status message even on error (probably yes)
        if args.delete_message_id:
            delete_telegram_message(args.token, chat_id, args.delete_message_id)
        return

    if args.user_mention:
        message += "here is your result:\n\n"

    message += (
        f"✨ *Firmware Analysis Result* ✨\n\n"
        f"📱 *Device:* {args.device}\n"
    )

    if args.product:
         message += f"📦 *Product:* {args.product}\n"

    if args.variant:
        message += f"🌍 *Variant:* {args.variant}\n"

    message += f"🚀 *Version:* {args.version}\n"

    if args.security_patch:
        message += f"🔒 *Security Patch:* {args.security_patch}\n"
    
    if args.build_id:
        # Format build ID as mono-space because it's long
        message += f"🏗️ *Build ID:* `{args.build_id}`\n"

    message += f"🛡️ *ARB Index:* {args.arb}\n"

    if args.md5:
        message += f"🔑 *MD5:* `{args.md5}`\n"
    
    if args.url:
        message += f"\n⬇️ [Download Link]({args.url})"

    send_telegram_message(args.token, chat_id, message, args.reply_to, message_thread_id)

    if args.delete_message_id:
        delete_telegram_message(args.token, chat_id, args.delete_message_id)

if __name__ == "__main__":
    main()
