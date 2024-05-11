import datetime
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
from google_calendar_helper.google_calendar_get import (
    OutOfTimeException,
    get_free_slots_for_a_day,
    Slot,
)
import pytz


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

moscow_tz = pytz.timezone("Europe/Moscow")

CHOOSE_DATE, CHOOSE_TIME, REGISTER = range(3)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    reply_keyboard = [["Зарегистрироваться"]]
    await update.message.reply_text(
        "Здесь можно зарегистрироваться на посещение",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    return CHOOSE_DATE


def get_reply_keyboard():
    now = datetime.datetime.now(moscow_tz)
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    two_days_after_tomorrow = today + datetime.timedelta(days=3)

    if now.hour < 21:

        reply_keyboard = [
            [f"{today.day}.0{today.month}.{today.year}"],
            [f"{tomorrow.day}.0{tomorrow.month}.{tomorrow.year}"],
            [
                f"{day_after_tomorrow.day}.0{day_after_tomorrow.month}.{day_after_tomorrow.year}"
            ],
        ]
    else:
        reply_keyboard = [
            [f"{tomorrow.day}.0{tomorrow.month}.{tomorrow.year}"],
            [
                f"{day_after_tomorrow.day}.0{day_after_tomorrow.month}.{day_after_tomorrow.year}"
            ],
            [
                f"{two_days_after_tomorrow.day}.0{two_days_after_tomorrow.month}.{two_days_after_tomorrow.year}"
            ],
        ]

    return reply_keyboard


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = get_reply_keyboard()

    await update.message.reply_text(
        "Выберете дату",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    return CHOOSE_TIME


async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("User %s started free time.", update.message.from_user.first_name)
    user = update.message.from_user
    message = update.message.text
    logger.info("Free time for %s.", user.first_name)

    day = message.split(".")[0]
    month = message.split(".")[1]
    year = message.split(".")[2]

    date = moscow_tz.localize(datetime.datetime(int(year), int(month), int(day))).date()

    try:
        free_slots_for_a_day = get_free_slots_for_a_day(date)
    except OutOfTimeException:
        await update.message.reply_text(
            "Все занято. Выберите другую дату",
            reply_markup=ReplyKeyboardMarkup(
                get_reply_keyboard(),
            ),
        )
        return CHOOSE_DATE

    if free_slots_for_a_day:

        slots_time = [
            f"{':'.join(slot.start.split('T')[1].split('+')[0].split(':')[:2])}-{':'.join(slot.end.split('T')[1].split('+')[0].split(':')[:2])}"
            for slot in free_slots_for_a_day
        ]

        reply_keyboard = [slots_time]

        await update.message.reply_text(
            "Выберете время",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
            ),
        )
        return REGISTER


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User %s started registration.", user.first_name)


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

    init_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
            CHOOSE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
            REGISTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(init_conv_handler)

    application.run_polling(poll_interval=1.0)
