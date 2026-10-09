
import os
from collections import defaultdict

from telegram import (
    Update, InlineKeyboardButton,
    InlineKeyboardMarkup, ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN variable missing in Railway")

RULES = os.getenv(
    "GROUP_RULES",
    "1. Be respectful.\n2. No spam.\n3. No unauthorized links."
)

warnings = defaultdict(int)
recent_messages = defaultdict(list)
autopost_jobs = {}


async def is_admin(update, context):
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )
    return member.status in ("administrator", "creator")


async def admin_check(update, context):
    if not await is_admin(update, context):
        await update.effective_message.reply_text(
            "⛔ Admins only."
        )
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Group Rules", callback_data="rules")],
        [InlineKeyboardButton("🛡️ Help", callback_data="help")]
    ])
    await update.effective_message.reply_text(
        "🤖 Welcome to our group!\n\n"
        "🎉 Glad to have you here.\n"
        "📜 Please read the rules.\n"
        "❤️ Be kind. No spam.",
        reply_markup=keyboard
    )


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.effective_message.new_chat_members:
        if user.is_bot:
            continue
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 Rules", callback_data="rules"),
             InlineKeyboardButton("🛡️ Help", callback_data="help")]
        ])
        await update.effective_message.reply_text(
            f"🎉 Welcome {user.mention_html()}!\n\n"
            "💎 మా గ్రూప్‌కు స్వాగతం!\n"
            "✨ Be friendly • Follow rules.",
            parse_mode="HTML",
            reply_markup=keyboard
        )


async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "rules":
        await query.message.reply_text("📜 GROUP RULES\n\n" + RULES)
    elif query.data == "help":
        await query.message.reply_text(
            "🤖 Commands:\n/start\n/help\n/rules\n\n"
            "Admin commands:\n/warn (reply)\n/mute (reply)\n"
            "/unmute (reply)\n/ban (reply)\n"
            "/autopost MINUTES message\n/stopautopost"
        )


async def rules(update, context):
    await update.effective_message.reply_text("📜 GROUP RULES\n\n" + RULES)


async def help_command(update, context):
    await update.effective_message.reply_text(
        "/start - Welcome\n/rules - Rules\n/help - Help\n"
        "Reply to a member's message with /warn, /mute, /unmute or /ban.\n"
        "/autopost MINUTES message\n/stopautopost"
    )


async def warn(update, context):
    if not await admin_check(update, context):
        return
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a member's message with /warn.")
        return
    user = msg.reply_to_message.from_user
    key = (msg.chat_id, user.id)
    warnings[key] += 1
    await msg.reply_text(f"⚠️ Warning {warnings[key]}/3")
    if warnings[key] >= 3:
        try:
            await context.bot.ban_chat_member(msg.chat_id, user.id)
            await msg.reply_text("🚫 3 warnings: member banned.")
        except Exception:
            await msg.reply_text("Ban failed. Check bot admin permissions.")


async def mute(update, context):
    if not await admin_check(update, context):
        return
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a member's message with /mute.")
        return
    try:
        await context.bot.restrict_chat_member(
            msg.chat_id, msg.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=False)
        )
        await msg.reply_text("🔇 Member muted.")
    except Exception as e:
        await msg.reply_text(f"Mute failed: {e}")


async def unmute(update, context):
    if not await admin_check(update, context):
        return
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a member's message with /unmute.")
        return
    try:
        await context.bot.restrict_chat_member(
            msg.chat_id, msg.reply_to_message.from_user.id,
            ChatPermissions(
                can_send_messages=True, can_send_audios=True,
                can_send_documents=True, can_send_photos=True,
                can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_voice_notes=True
            )
        )
        await msg.reply_text("🔊 Member unmuted.")
    except Exception as e:
        await msg.reply_text(f"Unmute failed: {e}")


async def ban(update, context):
    if not await admin_check(update, context):
        return
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a member's message with /ban.")
        return
    try:
        await context.bot.ban_chat_member(
            msg.chat_id, msg.reply_to_message.from_user.id
        )
        await msg.reply_text("🚫 Member banned.")
    except Exception as e:
        await msg.reply_text(f"Ban failed: {e}")


async def moderate(update, context):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or user.is_bot:
        return
    try:
        member = await context.bot.get_chat_member(msg.chat_id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        return

    text = (msg.text or msg.caption or "").lower()
    if "http://" in text or "https://" in text or "t.me/" in text:
        try:
            await msg.delete()
            await context.bot.send_message(
                msg.chat_id, "🚫 Links are not allowed."
            )
        except Exception:
            pass
        return

    key = (msg.chat_id, user.id)
    recent_messages[key].append(text.strip())
    recent_messages[key] = recent_messages[key][-3:]
    if len(recent_messages[key]) == 3 and len(set(recent_messages[key])) == 1:
        try:
            await msg.delete()
            await context.bot.send_message(
                msg.chat_id, "⚠️ Please don't repeat messages."
            )
        except Exception:
            pass


async def post_job(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=context.job.data
    )


async def autopost(update, context):
    if not await admin_check(update, context):
        return
    msg = update.effective_message
    if len(context.args) < 2:
        await msg.reply_text(
            "Usage: /autopost MINUTES message\n"
            "Example: /autopost 60 Hello everyone!"
        )
        return
    try:
        minutes = int(context.args[0])
        if minutes < 1:
            raise ValueError
        old = autopost_jobs.pop(msg.chat_id, None)
        if old:
            old.schedule_removal()
        job = context.job_queue.run_repeating(
            post_job, interval=minutes * 60,
            first=minutes * 60, chat_id=msg.chat_id,
            data=" ".join(context.args[1:])
        )
        autopost_jobs[msg.chat_id] = job
        await msg.reply_text(f"✅ Auto-post every {minutes} minutes.")
    except ValueError:
        await msg.reply_text("Enter a valid number of minutes.")
    except Exception as e:
        await msg.reply_text(f"Auto-post error: {e}")


async def stop_autopost(update, context):
    if not await admin_check(update, context):
        return
    job = autopost_jobs.pop(update.effective_chat.id, None)
    if job:
        job.schedule_removal()
        await update.effective_message.reply_text("⏹️ Auto-post stopped.")
    else:
        await update.effective_message.reply_text("No scheduled post found.")


async def error_handler(update, context):
    print("Bot error:", repr(context.error))


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("autopost", autopost))
    app.add_handler(CommandHandler("stopautopost", stop_autopost))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
        moderate
    ))
    app.add_error_handler(error_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
