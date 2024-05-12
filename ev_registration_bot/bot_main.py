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
from google_calendar_helper.google_calendar_create import create_event
import pytz


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

moscow_tz = pytz.timezone("Europe/Moscow")

(
    CHOOSE_DATE,
    CHOOSE_TIME,
    REGISTER_NAME,
    REGISTER_AMOUNT,
    REGISTER_PHONE,
    MAKE_REGISTRATION,
) = range(6)


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
        "Выберете дату\n\nНажмите /cancel чтобы выйти",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    return CHOOSE_TIME


async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("User %s started free time.", update.message.from_user.first_name)
    user = update.message.from_user
    user_message = update.message.text
    logger.info("Free time for %s.", user.first_name)

    day = user_message.split(".")[0]
    month = user_message.split(".")[1]
    year = user_message.split(".")[2]

    global date
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
        return REGISTER_NAME


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    user_message = update.message.text

    chosen_start_time = user_message.split("-")[0]
    chosen_end_time = user_message.split("-")[1]

    global chosen_start_time_str
    chosen_start_time_str = (
        f"{date.year}-0{date.month}-{date.day}T{chosen_start_time}:00+03:00"
    )

    global chosen_end_time_str
    chosen_end_time_str = (
        f"{date.year}-0{date.month}-{date.day}T{chosen_end_time}:00+03:00"
    )

    await update.message.reply_text(
        "На какое имя зарегистрировать?",
        reply_markup=ReplyKeyboardRemove(),
    )

    return REGISTER_AMOUNT


async def register_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    user_message = update.message.text

    if user_message:
        global registration_name
        registration_name = user_message

        reply_keyboard = [
            ["1"],
            ["2"],
            ["3"],
            ["4"],
            ["5"],
        ]

        await update.message.reply_text(
            "Сколько еще человек будет с Вами?\n\nВыберите из списка:",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
            ),
        )
        return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    user_message = update.message.text

    if user_message:
        global registration_amount
        try:
            registration_amount = int(user_message)
            if int(user_message) > 5:
                await update.message.reply_text(
                    "Количество не должно превышать 5 человек\n\nПожалуйста выберите из списка:",
                )
                return REGISTER_PHONE
        except ValueError:
            await update.message.reply_text(
                "Количество должно быть числом\n\nПожалуйста выберите из списка:",
            )
            return REGISTER_PHONE

        await update.message.reply_text(
            "Напишите ваш номер телефона для связи",
            reply_markup=ReplyKeyboardRemove(),
        )
        return MAKE_REGISTRATION


async def make_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    user_message = update.message.text

    if user_message:
        registration_phone = user_message

        registration_result = create_event(
            summary=f"{registration_name}+{registration_amount}",
            start_time=chosen_start_time_str,
            end_time=chosen_end_time_str,
            phone=registration_phone,
        )
        if registration_result:
            await update.message.reply_text(
                "Вы успешно зарегистрированы!\nБудем Вас ждать!\n\nЧтобы записаться повторно нажмите /start",
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END
        await update.message.reply_text(
            "Что-то пошло не так...\n\nЧтобы записаться повторно нажмите /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""

    user = update.message.from_user

    logger.info("User %s canceled the conversation.", user.first_name)

    await update.message.reply_text(
        "Чтобы зарегистрироваться снова нажмите /start",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


if __name__ == "__main__":
    application = ApplicationBuilder().token(get_settings().telegram.bot_token).build()

    init_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
            CHOOSE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
            REGISTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)
            ],
            REGISTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_amount)
            ],
            REGISTER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_phone)
            ],
            MAKE_REGISTRATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, make_registration)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(init_conv_handler)

    application.run_polling(poll_interval=1.0)
