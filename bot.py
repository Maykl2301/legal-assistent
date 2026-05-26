from keep_alive import keep_alive
keep_alive()
import logging
import os
import asyncio
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from dotenv import load_dotenv
from responses import get_legal_response
from database import init_db, save_question, get_history

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSING_TOPIC, ASKING_QUESTION, SHOWING_ANSWER = range(3)

MAIN_MENU_KEYBOARD = [
    [KeyboardButton("⚖️ Цивільне право"), KeyboardButton("🏠 Житлові питання")],
    [KeyboardButton("👨‍👩‍👧 Сімейне право"), KeyboardButton("💼 Трудове право")],
    [KeyboardButton("🚗 ДТП та транспорт"), KeyboardButton("🏦 Кредити та борги")],
    [KeyboardButton("👮 Кримінальне право"), KeyboardButton("🏛️ Адміністративне")],
    [KeyboardButton("📋 Задати своє питання"), KeyboardButton("📜 Моя історія")],
    [KeyboardButton("ℹ️ Про бота")]
]

TOPICS = {
    "⚖️ Цивільне право": "civil",
    "🏠 Житлові питання": "housing",
    "👨‍👩‍👧 Сімейне право": "family",
    "💼 Трудове право": "labor",
    "🚗 ДТП та транспорт": "transport",
    "🏦 Кредити та борги": "credits",
    "👮 Кримінальне право": "criminal",
    "🏛️ Адміністративне": "admin",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    name = user.first_name or "Користувач"
    welcome_text = (
        f"👋 Вітаю, {name}!\n\n"
        "Я — бот-помічник юриста 🇺🇦\n\n"
        "Я можу допомогти вам:\n"
        "• Отримати базову юридичну консультацію\n"
        "• Дізнатись про свої права\n"
        "• Зрозуміти юридичні терміни\n"
        "• Знайти потрібні статті закону\n\n"
        "⚠️ <b>Увага:</b> Відповіді носять інформаційний характер і не замінюють консультацію з ліцензованим юристом.\n\n"
        "Оберіть тему або задайте своє питання 👇"
    )
    reply_markup = ReplyKeyboardMarkup(
        MAIN_MENU_KEYBOARD, resize_keyboard=True, one_time_keyboard=False
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=reply_markup)
    return CHOOSING_TOPIC


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    if text == "ℹ️ Про бота":
        await show_about(update, context)
        return CHOOSING_TOPIC

    if text == "📜 Моя історія":
        await show_history(update, context)
        return CHOOSING_TOPIC

    if text == "📋 Задати своє питання":
        await update.message.reply_text(
            "✍️ Напишіть своє юридичне питання, і я постараюсь допомогти:\n\n"
            "<i>(Наприклад: 'Що робити якщо роботодавець не виплачує зарплату?')</i>",
            parse_mode="HTML"
        )
        context.user_data["topic"] = "general"
        return ASKING_QUESTION

    if text in TOPICS:
        topic_key = TOPICS[text]
        context.user_data["topic"] = topic_key
        topic_questions = get_topic_questions(topic_key)
        keyboard = []
        for i, q in enumerate(topic_questions):
            keyboard.append([InlineKeyboardButton(q["text"], callback_data=f"q_{topic_key}_{i}")])
        keyboard.append([InlineKeyboardButton("✍️ Інше питання", callback_data=f"custom_{topic_key}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Ви обрали: <b>{text}</b>\n\nОберіть питання або напишіть своє:",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return CHOOSING_TOPIC

    context.user_data["topic"] = "general"
    await process_question(update, context, text)
    return CHOOSING_TOPIC


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back":
        reply_markup = ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)
        await query.message.reply_text("Головне меню:", reply_markup=reply_markup)
        return CHOOSING_TOPIC

    if data.startswith("custom_"):
        topic = data.split("_", 1)[1]
        context.user_data["topic"] = topic
        await query.message.reply_text("✍️ Напишіть своє питання:")
        return ASKING_QUESTION

    if data.startswith("q_"):
        parts = data.split("_")
        topic_key = parts[1]
        idx = int(parts[2])
        questions = get_topic_questions(topic_key)
        if idx < len(questions):
            question_text = questions[idx]["question"]
            answer = questions[idx]["answer"]
            user_id = query.from_user.id
            save_question(user_id, question_text, answer, topic_key)
            await send_answer(query.message, question_text, answer)
        return CHOOSING_TOPIC

    if data in ("feedback_good", "feedback_bad"):
        return CHOOSING_TOPIC

    return CHOOSING_TOPIC


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question = update.message.text
    topic = context.user_data.get("topic", "general")
    await process_question(update, context, question, topic)
    return CHOOSING_TOPIC


async def process_question(update, context, question, topic="general"):
    await update.message.reply_text("⏳ Шукаю відповідь...")
    user_id = update.effective_user.id
    answer = get_legal_response(question, topic)
    save_question(user_id, question, answer, topic)
    await send_answer(update.message, question, answer)


async def send_answer(message, question, answer):
    keyboard = [
        [
            InlineKeyboardButton("👍 Корисно", callback_data="feedback_good"),
            InlineKeyboardButton("👎 Не допомогло", callback_data="feedback_bad")
        ],
        [InlineKeyboardButton("🔙 Головне меню", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    response_text = (
        f"❓ <b>Питання:</b>\n{question}\n\n"
        f"⚖️ <b>Відповідь:</b>\n{answer}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <i>Це загальна інформація. Для вирішення конкретної ситуації "
        "зверніться до ліцензованого юриста.</i>"
    )
    if len(response_text) > 4096:
        response_text = response_text[:4090] + "..."
    await message.reply_text(response_text, parse_mode="HTML", reply_markup=reply_markup)


async def show_history(update, context):
    user_id = update.effective_user.id
    history = get_history(user_id, limit=5)
    if not history:
        await update.message.reply_text("📜 Ви ще не задавали питань.\n\nОберіть тему або напишіть питання!")
        return
    text = "📜 <b>Ваші останні питання:</b>\n\n"
    for i, (question, topic, timestamp) in enumerate(history, 1):
        text += f"{i}. {question}\n<i>({timestamp})</i>\n\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def show_about(update, context):
    about_text = (
        "ℹ️ <b>Бот-помічник юриста 🇺🇦</b>\n\n"
        "Цей бот створений для надання базової юридичної інформації громадянам України.\n\n"
        "📚 <b>Охоплені теми:</b>\n"
        "• Цивільне право\n• Сімейне право\n• Трудове право\n"
        "• Житлові питання\n• ДТП та транспорт\n"
        "• Кредити та борги\n• Кримінальне право\n• Адміністративне право\n\n"
        "📞 <b>Безкоштовна юридична допомога:</b>\n"
        "• 0 800 213 103\n"
        "• <a href='https://legalaid.gov.ua'>legalaid.gov.ua</a>\n\n"
        "⚠️ <i>Бот надає загальну інформацію і не замінює консультацію юриста.</i>"
    )
    await update.message.reply_text(about_text, parse_mode="HTML")


async def help_command(update, context):
    help_text = (
        "🆘 <b>Допомога</b>\n\n"
        "/start — Запустити бота\n"
        "/help — Ця довідка\n"
        "/menu — Головне меню\n"
        "/history — Моя історія питань\n\n"
        "Просто натисніть на тему або напишіть своє питання!"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def menu_command(update, context):
    reply_markup = ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)
    await update.message.reply_text("Головне меню:", reply_markup=reply_markup)
    return CHOOSING_TOPIC


def get_topic_questions(topic):
    questions_db = {
        "civil": [
            {"text": "Як повернути товар?", "question": "Як повернути товар неналежної якості?", "answer": "За Законом України 'Про захист прав споживачів' (ст. 8), ви маєте право повернути товар неналежної якості протягом гарантійного строку. Зверніться до продавця з чеком та паспортом. При відмові — Держпродспоживслужба або суд."},
            {"text": "Термін позовної давності", "question": "Які строки позовної давності?", "answer": "Загальна позовна давність — 3 роки (ст. 257 ЦКУ). Спеціальні: 1 рік — неустойка; 5 років — нікчемні угоди. Перебіг починається з дня порушення права."},
        ],
        "housing": [
            {"text": "Виселення з квартири", "question": "Чи можуть мене виселити?", "answer": "Виселення — лише за судовим рішенням (ст. 40 ЖКУ). Без суду ніхто не має права вас виселити. При загрозі — викличте поліцію та зверніться до юриста."},
            {"text": "Права орендаря", "question": "Які права має орендар?", "answer": "Орендар може користуватись житлом протягом строку договору. Господар не може виселити без попередження за 3 місяці. Рекомендується нотаріальний договір."},
        ],
        "family": [
            {"text": "Розлучення з дітьми", "question": "Як проходить розлучення з дітьми?", "answer": "З дітьми — через суд (ст. 109 СКУ). Суд визначає з ким діти, розмір аліментів, порядок спілкування. Аліменти: 1 дитина — 1/4 доходу, 2 — 1/3, 3+ — 1/2."},
            {"text": "Аліменти", "question": "Як стягнути аліменти?", "answer": "Через суд або нотаріальну угоду. Мінімум — 50% прожиткового мінімуму. Виконавчий лист до ДВС. При ухиленні — ст. 164 ККУ."},
        ],
        "labor": [
            {"text": "Незаконне звільнення", "question": "Що робити при незаконному звільненні?", "answer": "Протягом 1 місяця — позов до суду (ст. 233 КЗпП). Вимагайте поновлення та виплати за вимушений прогул. Також — скарга до Держпраці."},
            {"text": "Невиплата зарплати", "question": "Що робити якщо не платять зарплату?", "answer": "1) Письмова вимога керівнику. 2) Скарга до Держпраці. 3) Суд — видає наказ без розгляду. 4) Прокуратура. За ст. 175 ККУ — до 5 років. Компенсація 3% за кожен день."},
        ],
        "transport": [
            {"text": "ДТП — що робити?", "question": "Що робити після ДТП?", "answer": "1) Зупиніться, аварійка, знак. 2) Поліція 102, швидка 103. 3) Не переміщуйте авто. 4) Фото місця. 5) Страхова — 3 дні. Європротокол — якщо немає постраждалих і шкода до 80 000 грн."},
            {"text": "Позбавлення прав", "question": "Як оскаржити позбавлення прав?", "answer": "Протягом 10 днів до суду або вищого органу (ст. 291 КУпАП). Збережіть докази. При поданні скарги виконання зупиняється."},
        ],
        "credits": [
            {"text": "Борг колекторам", "question": "Що робити якщо телефонують колектори?", "answer": "Колекторам заборонено погрожувати та турбувати з 22:00 до 8:00. Скаржтесь до НБУ. Ви маєте право письмово відмовитись від контактів."},
            {"text": "Кредитна пастка", "question": "Як вирішити проблему з МФО?", "answer": "1) Реструктуризація. 2) Визнання договору недійсним (ставка понад 2,5% на день — незаконна). 3) Строк давності — 3 роки. 4) Банкрутство фізособи."},
        ],
        "criminal": [
            {"text": "Права при затриманні", "question": "Які права при затриманні поліцією?", "answer": "Право знати причину, телефонувати адвокату, мовчати, на перекладача. Максимум без санкції — 72 години. НІКОЛИ не підписуйте без адвоката!"},
            {"text": "Самозахист", "question": "Коли самооборона законна?", "answer": "Необхідна оборона (ст. 36 ККУ) — законна при реальній загрозі життю. Шкода має відповідати небезпеці. При будь-якому випадку — викличте поліцію."},
        ],
        "admin": [
            {"text": "Штраф поліції", "question": "Як оскаржити адмінштраф?", "answer": "Протягом 10 днів (ст. 288 КУпАП) до суду або вищого органу. При поданні скарги виконання зупиняється. Держмито не сплачується."},
            {"text": "Відмова держоргану", "question": "Що робити при відмові держоргану?", "answer": "1) Вимагайте письмову відмову. 2) Скарга керівнику. 3) Адмінпозов до суду — 6 місяців. 4) Омбудсмен: 0800 50 17 20."},
        ],
    }
    return questions_db.get(topic, [])


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN не знайдено!")

    init_db()

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic),
                CallbackQueryHandler(handle_callback),
            ],
            ASKING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("menu", menu_command),
        ],
        per_message=False,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("history", lambda u, c: show_history(u, c)))

    print("✅ Бот запущено!")
    logger.info("✅ Бот запущено!")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
