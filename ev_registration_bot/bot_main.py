from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from config import get_settings
import logging
from google_calendar_helper.google_calendar_get import get_next_regs


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


FREE_TIME, REGISTER = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    reply_keyboard = [["/get_free_time", "/register"]]
    await update.message.reply_text(
        "Че ннннада?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )


async def get_free_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("User %s started free time.", update.message.from_user.first_name)
    user = update.message.from_user
    logger.info("Free time for %s.", user.first_name)

    events = get_next_regs()

    if not events:
        await update.message.reply_text("Все слоты свободны....")
        return

    text = f""

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        # parse_mode="MarkdownV2",
    )


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User %s started registration.", user.first_name)

    await update.message.reply_text("Допустим зарегалсяюю")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""

    user = update.message.from_user

    logger.info("User %s canceled the conversation.", user.first_name)

    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


if __name__ == "__main__":
    application = ApplicationBuilder().token(get_settings().telegram.bot_token).build()

    # Start conversation
    init_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FREE_TIME: [MessageHandler(filters.COMMAND, get_free_time)],
            REGISTER: [MessageHandler(filters.COMMAND, register)],
            # ACCOUNT_AMOUNT: [
            #     MessageHandler(
            #         filters.TEXT & ~filters.COMMAND, create_init_account_amount
            #     )
            # ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    free_time_command = CommandHandler("get_free_time", get_free_time)
    register_command = CommandHandler("register", register)

    application.add_handler(init_conv_handler)
    application.add_handler(free_time_command)
    application.add_handler(register_command)

    application.run_polling(poll_interval=1.0)
