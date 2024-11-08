import datetime
import enum
import logging
import re
from typing import List

import pytz
from ev_registration_bot.config import get_settings
from ev_registration_bot.google_calendar_helper.utils import (
    VisitType,
    get_commune_guest_limit,
)
from ev_registration_bot.google_calendar_helper.google_calendar_create import (
    create_event,
)
from ev_registration_bot.google_calendar_helper.google_calendar_get import (
    Commune,
    OutOfTimeException,
    get_free_slots_for_a_day,
    get_lecture_free_slots_for_a_day,
    get_lecture_free_half_an_hour_slots_for_a_day,
)
from telegram import (
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import google

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

moscow_tz = pytz.timezone("Europe/Moscow")


communes = [
    "Север-американские",
    "Северо-Германские",
]

visit_type = [
    ["Терапия (индивидуально, 1 час)"],
    ["Лекция (с другими гостями, 30 мин. или 1 час)"],
]

user_id: int | None = None

registration_amount_done: bool = False
user_children_amount: int | None = None
user_chosen_commune: str | None = None
user_visit_type: str | None = None
total_guests: int | None = None
visit_duration: str | None = None

(
    CHOOSE_COMMUNE,
    CHOOSE_VISIT_TYPE,
    CHOOSE_DATE,
    CHOOSE_TIME,
    CHOOSE_VISIT_DURATION,
    CHOOSE_TIME_FOR_LECTURE,
    ARE_CHILDREN,
    CHILDREN_AMOUNT,
    REGISTER_NAME,
    REGISTER_AMOUNT,
    REGISTER_PHONE,
    MAKE_REGISTRATION,
) = range(12)


async def delete_previous_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete all stored messages for the current chat."""
    if not context.user_data.get("message_ids"):
        return

    chat_id = context.user_data.get("chat_id")
    if not chat_id:
        return

    message_ids = context.user_data["message_ids"]
    if message_ids:
        try:
            await context.bot.delete_messages(chat_id, message_ids)
            context.user_data["message_ids"] = []
        except Exception as e:
            logger.error(f"Failed to delete messages: {e}")


async def store_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, message_id: int
) -> None:
    """Store message ID for later deletion."""
    if "message_ids" not in context.user_data:
        context.user_data["message_ids"] = []
    context.user_data["message_ids"].append(message_id)
    context.user_data["chat_id"] = update.message.chat_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""

    await delete_previous_messages(context)

    global user_id
    user_id = update.message.from_user.id
    global registration_amount_done
    registration_amount_done = False
    global user_children_amount
    user_children_amount = None
    global user_chosen_commune
    user_chosen_commune = None
    global user_visit_type
    user_visit_type = None
    global visit_duration
    visit_duration = None

    # Clear previous message IDs
    context.user_data["message_ids"] = []
    context.user_data["chat_id"] = update.message.chat_id

    reply_keyboard = [["Зарегистрироваться"]]
    message = await update.message.reply_text(
        "Здесь можно зарегистрироваться на посещение",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    await store_message(update, context, update.message.message_id)
    await store_message(update, context, message.message_id)

    return CHOOSE_COMMUNE


def get_reply_keyboard():
    now = datetime.datetime.now(moscow_tz)
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    two_days_after_tomorrow = today + datetime.timedelta(days=3)

    def format_date(date):
        return f"{date.day}.{date.month:02d}.{date.year}"

    if now.hour < 21:
        reply_keyboard = [
            [format_date(today)],
            [format_date(tomorrow)],
            [format_date(day_after_tomorrow)],
        ]
    else:
        reply_keyboard = [
            [format_date(tomorrow)],
            [format_date(day_after_tomorrow)],
            [format_date(two_days_after_tomorrow)],
        ]

    return reply_keyboard


async def choose_commune(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    reply_keyboard = [communes]
    message = await update.message.reply_text(
        "Выберите коммуну\n\nЗдесь будет описание каждой коммуны\n\nНажмите /cancel чтобы выйти",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    await store_message(update, context, update.message.message_id)
    await store_message(update, context, message.message_id)

    return CHOOSE_VISIT_TYPE


async def choose_visit_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    reply_keyboard = visit_type
    user_message = update.message.text

    global user_chosen_commune
    if user_message == "Север-американские":
        user_chosen_commune = Commune.AMERICAN
    elif user_message == "Северо-Германские":
        user_chosen_commune = Commune.GERMAN
    else:
        message = await update.message.reply_text(
            "Пожалуйста выберите из списка\n\nНажмите /cancel чтобы выйти"
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return CHOOSE_VISIT_TYPE

    message = await update.message.reply_text(
        "Выберите тип посещения\n\nНажмите /cancel чтобы выйти",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    await store_message(update, context, update.message.message_id)
    await store_message(update, context, message.message_id)

    return CHOOSE_DATE


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    user_message = update.message.text

    global user_visit_type
    if user_message == "Терапия (индивидуально, 1 час)":
        user_visit_type = VisitType.THERAPY
    elif user_message == "Лекция (с другими гостями, 30 мин. или 1 час)":
        user_visit_type = VisitType.LECTURE
    else:
        message = await update.message.reply_text(
            "Пожалуйста выберите из списка\n\nНажмите /cancel чтобы выйти"
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return CHOOSE_DATE

    reply_keyboard = get_reply_keyboard()

    message = await update.message.reply_text(
        "Выберете дату\n\nНажмите /cancel чтобы выйти",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    await store_message(update, context, update.message.message_id)
    await store_message(update, context, message.message_id)

    if user_visit_type == VisitType.THERAPY:
        return CHOOSE_TIME
    return CHOOSE_VISIT_DURATION


async def choose_visit_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    user_message = update.message.text
    global user_chosen_commune
    day = user_message.split(".")[0]
    month = user_message.split(".")[1]
    year = user_message.split(".")[2]

    global date
    date = moscow_tz.localize(datetime.datetime(int(year), int(month), int(day))).date()

    reply_keyboard = [["30 минут"], ["1 час"]]
    message = await update.message.reply_text(
        "Выберете длительность посещения\n\nНажмите /cancel чтобы выйти",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    await store_message(update, context, update.message.message_id)
    await store_message(update, context, message.message_id)

    return CHOOSE_TIME_FOR_LECTURE


async def choose_time_for_lecture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    user_message = update.message.text
    global date
    global user_chosen_commune
    global visit_duration
    visit_duration = user_message

    try:
        if user_message == "30 минут":
            free_slots_for_a_day = get_lecture_free_half_an_hour_slots_for_a_day(
                date, user_chosen_commune
            )
        elif user_message == "1 час":
            free_slots_for_a_day = get_lecture_free_slots_for_a_day(
                date, user_chosen_commune
            )
        else:
            message = await update.message.reply_text(
                "Пожалуйста выберите из списка\n\nНажмите /cancel чтобы выйти"
            )
            await store_message(update, context, update.message.message_id)
            await store_message(update, context, message.message_id)
            return CHOOSE_TIME_FOR_LECTURE

    except OutOfTimeException:
        message = await update.message.reply_text(
            "На выбранный день все занято. Пожалуйста, выберите другую дату\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardMarkup(
                get_reply_keyboard(),
            ),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return CHOOSE_DATE
    except google.auth.exceptions.RefreshError:
        message = await update.message.reply_text(
            "Что-то пошло не так...\n\nЧтобы записаться повторно нажмите /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        logger.error("Google auth error")
        return ConversationHandler.END
    except Exception as e:
        logger.error(e)
        message = await update.message.reply_text(
            "Что-то пошло не так...\n\nЧтобы записаться повторно нажмите /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return ConversationHandler.END

    if free_slots_for_a_day:
        guest_limit = get_commune_guest_limit(user_chosen_commune)
        reply_keyboard = [
            [
                InlineKeyboardButton(
                    f"{':'.join(slot.start.split('T')[1].split('+')[0].split(':')[:2])}-{':'.join(slot.end.split('T')[1].split('+')[0].split(':')[:2])} ({guest_limit - slot.total_guests} мест)"
                )
            ]
            for slot in free_slots_for_a_day
            if slot.total_guests < guest_limit
        ]

        if not reply_keyboard:
            message = await update.message.reply_text(
                "На выбранный день все места заняты. Пожалуйста, выберите другую дату\n\nНажмите /cancel чтобы выйти",
                reply_markup=ReplyKeyboardMarkup(
                    get_reply_keyboard(),
                ),
            )
            await store_message(update, context, update.message.message_id)
            await store_message(update, context, message.message_id)
            return CHOOSE_DATE

        message = await update.message.reply_text(
            "Выберете время\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
            ),
        )

        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)

        return ARE_CHILDREN


async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    logger.info("User %s started free time.", update.message.from_user.first_name)
    user = update.message.from_user
    user_message = update.message.text
    logger.info("Free time for %s.", user.first_name)

    global user_chosen_commune

    day = user_message.split(".")[0]
    month = user_message.split(".")[1]
    year = user_message.split(".")[2]

    global date
    date = moscow_tz.localize(datetime.datetime(int(year), int(month), int(day))).date()

    try:
        free_slots_for_a_day = get_free_slots_for_a_day(date, user_chosen_commune)
    except OutOfTimeException:
        message = await update.message.reply_text(
            "На выбранный день все занято. Пожалуйста, выберите другую дату\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardMarkup(
                get_reply_keyboard(),
            ),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return CHOOSE_DATE
    except google.auth.exceptions.RefreshError:
        message = await update.message.reply_text(
            "Что-то пошло не так...\n\nЧтобы записаться повторно нажмите /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        logger.error("Google auth error")
        return ConversationHandler.END
    except ValueError as e:
        logger.error(e)
        message = await update.message.reply_text(
            "Что-то пошло не так...\n\nЧтобы записаться повторно нажмите /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return ConversationHandler.END

    if free_slots_for_a_day:
        reply_keyboard = [
            [
                InlineKeyboardButton(
                    f"{':'.join(slot.start.split('T')[1].split('+')[0].split(':')[:2])}-{':'.join(slot.end.split('T')[1].split('+')[0].split(':')[:2])}"
                )
            ]
            for slot in free_slots_for_a_day
        ]

        message = await update.message.reply_text(
            "Выберете время\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
            ),
        )

        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)

        return ARE_CHILDREN


async def are_children(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    user_message = update.message.text
    global user_visit_type
    try:
        chosen_start_time = user_message.split("-")[0]
        if user_visit_type == VisitType.THERAPY:
            chosen_end_time = user_message.split("-")[1]
        else:
            chosen_end_time = user_message.split("-")[1].split(" ")[0]
            # Store the available places from the message
            global available_places
            available_places = int(user_message.split("(")[1].split(" ")[0])
        print(chosen_start_time, chosen_end_time)
    except IndexError:
        message = await update.message.reply_text(
            "Пожалуйста выберите из списка\n\nНажмите /cancel чтобы выйти",
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return ARE_CHILDREN

    global chosen_start_time_str
    chosen_start_time_str = (
        f"{date.year}-{date.month:02d}-{date.day}T{chosen_start_time}:00+03:00"
    )

    global chosen_end_time_str
    chosen_end_time_str = (
        f"{date.year}-{date.month:02d}-{date.day}T{chosen_end_time}:00+03:00"
    )

    reply_keyboard = [["Да", "Нет"]]

    message = await update.message.reply_text(
        "Будут ли с Вами дети?\n\nНажмите /cancel чтобы выйти",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
        ),
    )

    await store_message(update, context, update.message.message_id)
    await store_message(update, context, message.message_id)

    return CHILDREN_AMOUNT


async def children_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(context)

    global user_children_amount
    user_message = update.message.text
    if user_message == "Нет":
        # Set the user_children_amount to 0 when "Нет" is selected
        user_children_amount = 0
        message = await update.message.reply_text(
            "На какое имя зарегистрировать?\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardRemove(),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return REGISTER_AMOUNT
    elif user_message == "Да":
        reply_keyboard = [["1"], ["2"], ["3"], ["4"], ["5"]]
        message = await update.message.reply_text(
            "Укажите какое количество детей будет с Вами\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
            ),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return REGISTER_NAME
    else:
        message = await update.message.reply_text(
            "Пожалуйста, выберите из списка\n\nНажмите /cancel чтобы выйти",
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return CHILDREN_AMOUNT


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await delete_previous_messages(context)

    user_message = update.message.text
    global user_children_amount
    if user_children_amount is None or user_children_amount != 0:
        try:
            # This is to ensure if the previous state was CHILDREN_AMOUNT
            user_children_amount = int(user_message)
            if user_children_amount > 5:
                message = await update.message.reply_text(
                    "Пожалуйста, выберите из списка\n\nНажмите /cancel чтобы выйти"
                )
                await store_message(update, context, update.message.message_id)
                await store_message(update, context, message.message_id)
                user_children_amount = None
                return CHILDREN_AMOUNT
        except ValueError:
            message = await update.message.reply_text(
                "Пожалуйста, выберите из списка\n\nНажмите /cancel чтобы выйти"
            )
            await store_message(update, context, update.message.message_id)
            await store_message(update, context, message.message_id)
            user_children_amount = None
            return CHILDREN_AMOUNT

        message = await update.message.reply_text(
            "На какое имя зарегистрировать?\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardRemove(),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)

    return REGISTER_AMOUNT


async def register_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await delete_previous_messages(context)

    user = update.message.from_user
    user_message = update.message.text

    if user_message:
        global registration_name
        registration_name = user_message

        # For lecture visits, show only the available number of places
        if user_visit_type == VisitType.LECTURE:
            reply_keyboard = [[str(i)] for i in range(1, min(6, available_places + 1))]
            if not reply_keyboard:
                message = await update.message.reply_text(
                    "К сожалению, на выбранное время не осталось свободных мест.\n\nЧтобы записаться повторно нажмите /start",
                    reply_markup=ReplyKeyboardRemove(),
                )
                await store_message(update, context, update.message.message_id)
                await store_message(update, context, message.message_id)
                return ConversationHandler.END
        else:
            reply_keyboard = [
                ["1"],
                ["2"],
                ["3"],
                ["4"],
                ["5"],
            ]

        message = await update.message.reply_text(
            "Сколько всего человек придет на посещение, включая Вас? Выберите из списка\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
            ),
        )

        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)

        return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await delete_previous_messages(context)

    global registration_amount_done
    user = update.message.from_user
    user_message = update.message.text

    logger.info(f"line 279 {registration_amount_done=}")

    if user_message:
        if not registration_amount_done:
            global registration_amount
            try:
                registration_amount = int(user_message)
                logger.info(
                    f"кол-во человек зарегистрировано -- {registration_amount} чел"
                )
                registration_amount_done = True
                if int(user_message) > 5:
                    message = await update.message.reply_text(
                        "Количество не должно превышать 5 человек\n\nПожалуйста выберите из списка\n\nНажмите /cancel чтобы выйти",
                    )
                    await store_message(update, context, update.message.message_id)
                    await store_message(update, context, message.message_id)
                    return REGISTER_PHONE

                # For lecture visits, check if the requested number of guests exceeds available places
                if (
                    user_visit_type == VisitType.LECTURE
                    and registration_amount > available_places
                ):
                    message = await update.message.reply_text(
                        f"К сожалению, на выбранное время осталось только {available_places} мест.\n\nПожалуйста выберите меньшее количество человек\n\nНажмите /cancel чтобы выйти",
                        reply_markup=ReplyKeyboardMarkup(
                            [[str(i)] for i in range(1, available_places + 1)]
                        ),
                    )
                    await store_message(update, context, update.message.message_id)
                    await store_message(update, context, message.message_id)
                    registration_amount_done = False
                    return REGISTER_PHONE
            except ValueError:
                message = await update.message.reply_text(
                    "Количество должно быть числом\n\nПожалуйста выберите из списка\n\nНажмите /cancel чтобы выйти",
                )
                await store_message(update, context, update.message.message_id)
                await store_message(update, context, message.message_id)
                return REGISTER_PHONE

        message = await update.message.reply_text(
            "Напишите ваш номер телефона для связи\n\nНажмите /cancel чтобы выйти",
            reply_markup=ReplyKeyboardRemove(),
        )

        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)

        logger.info(f"line 306 {registration_amount_done=}")
        return MAKE_REGISTRATION


async def make_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await delete_previous_messages(context)

    user = update.message.from_user
    user_message = update.message.text
    phone_regex = re.compile(
        r'^(\+7|8)(\s|-)?(\()?[0-9]{3}(\))?(\s|-)?([0-9]{3})(\s|-)?([0-9]{2})(\s|-)?([0-9]{2})$'
    )

    if user_message:
        # / check regexp
        if not phone_regex.match(user_message):
            message = await update.message.reply_text(
                "Номер телефона не соответствует формату. Попробуйте снова.\n\nНажмите /cancel чтобы выйти",
            )
            await store_message(update, context, update.message.message_id)
            await store_message(update, context, message.message_id)
            return MAKE_REGISTRATION

        registration_phone = user_message

        try:
            assert isinstance(
                user_children_amount, int
            ), "children_amount must be an integer"
            assert isinstance(
                user_chosen_commune, Commune
            ), "commune must be of type Commune"
            assert isinstance(
                user_visit_type, VisitType
            ), "visit_type must be of type VisitType"

            registration_result = create_event(
                summary=f"{registration_name}+{registration_amount}",
                start_time=chosen_start_time_str,
                end_time=chosen_end_time_str,
                children_amount=user_children_amount,
                phone=registration_phone,
                commune=user_chosen_commune,
                visit_type=user_visit_type,
                total_guests=registration_amount,
            )
        except (ValueError, AssertionError) as e:
            logger.error(f"An error occurred: {e}")
            message = await update.message.reply_text(
                "Что-то пошло не так...\n\nЧтобы записаться повторно нажмите /start",
                reply_markup=ReplyKeyboardRemove(),
            )
            await store_message(update, context, update.message.message_id)
            await store_message(update, context, message.message_id)
            return ConversationHandler.END

        if registration_result:
            # Delete all previous messages before showing success
            await delete_previous_messages(context)
            await update.message.reply_text(
                "Вы успешно зарегистрированы!\nБудем Вас ждать!\n\nЧтобы записаться повторно нажмите /start",
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END

        message = await update.message.reply_text(
            "Что-то пошло не так...\n\nЧтобы записаться повторно нажмите /start",
            reply_markup=ReplyKeyboardRemove(),
        )
        await store_message(update, context, update.message.message_id)
        await store_message(update, context, message.message_id)
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await delete_previous_messages(context)

    user = update.message.from_user

    logger.info("User %s canceled the conversation.", user.first_name)

    message = await update.message.reply_text(
        "Чтобы зарегистрироваться снова нажмите /start",
        reply_markup=ReplyKeyboardRemove(),
    )

    await store_message(update, context, update.message.message_id)
    await store_message(update, context, message.message_id)

    return ConversationHandler.END


if __name__ == "__main__":
    application = ApplicationBuilder().token(get_settings().telegram.bot_token).build()

    init_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_COMMUNE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_commune)
            ],
            CHOOSE_VISIT_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_visit_type)
            ],
            CHOOSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
            CHOOSE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
            CHOOSE_VISIT_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_visit_duration)
            ],
            CHOOSE_TIME_FOR_LECTURE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time_for_lecture)
            ],
            ARE_CHILDREN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, are_children)
            ],
            CHILDREN_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, children_amount)
            ],
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
