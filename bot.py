import logging
import os
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

# Стани розмови
CHOOSING_TOPIC, ASKING_QUESTION, SHOWING_ANSWER = range(3)

# Головне меню
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
    """Команда /start"""
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

    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    return CHOOSING_TOPIC


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору теми"""
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
        for i in range(0, len(topic_questions), 1):
            keyboard.append([InlineKeyboardButton(
                topic_questions[i]["text"],
                callback_data=f"q_{topic_key}_{i}"
            )])
        keyboard.append([InlineKeyboardButton(
            "✍️ Інше питання", callback_data=f"custom_{topic_key}"
        )])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Ви обрали: <b>{text}</b>\n\nОберіть питання або напишіть своє:",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return CHOOSING_TOPIC

    # Якщо введено довільний текст — вважаємо питанням
    context.user_data["topic"] = "general"
    context.user_data["question"] = text
    await process_question(update, context, text)
    return CHOOSING_TOPIC


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка inline кнопок"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back":
        reply_markup = ReplyKeyboardMarkup(
            MAIN_MENU_KEYBOARD, resize_keyboard=True
        )
        await query.message.reply_text(
            "Головне меню:", reply_markup=reply_markup
        )
        return CHOOSING_TOPIC

    if data.startswith("custom_"):
        topic = data.split("_", 1)[1]
        context.user_data["topic"] = topic
        await query.message.reply_text(
            "✍️ Напишіть своє питання:"
        )
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

    return CHOOSING_TOPIC


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка введеного питання"""
    question = update.message.text
    topic = context.user_data.get("topic", "general")
    await process_question(update, context, question, topic)
    return CHOOSING_TOPIC


async def process_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question: str,
    topic: str = "general"
):
    """Обробка та відповідь на питання"""
    await update.message.reply_text("⏳ Шукаю відповідь...")

    user_id = update.effective_user.id
    answer = get_legal_response(question, topic)
    save_question(user_id, question, answer, topic)
    await send_answer(update.message, question, answer)


async def send_answer(message, question: str, answer: str):
    """Відправка відповіді з кнопками"""
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

    # Telegram обмеження — 4096 символів
    if len(response_text) > 4096:
        response_text = response_text[:4090] + "..."

    await message.reply_text(
        response_text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати історію питань"""
    user_id = update.effective_user.id
    history = get_history(user_id, limit=5)

    if not history:
        await update.message.reply_text(
            "📜 Ви ще не задавали питань.\n\nОберіть тему або напишіть питання!"
        )
        return

    text = "📜 <b>Ваші останні питання:</b>\n\n"
    for i, (question, topic, timestamp) in enumerate(history, 1):
        text += f"{i}. {question}\n<i>({timestamp})</i>\n\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Про бота"""
    about_text = (
        "ℹ️ <b>Бот-помічник юриста 🇺🇦</b>\n\n"
        "Цей бот створений для надання базової юридичної інформації "
        "громадянам України.\n\n"
        "📚 <b>Охоплені теми:</b>\n"
        "• Цивільне право\n"
        "• Сімейне право\n"
        "• Трудове право\n"
        "• Житлові питання\n"
        "• ДТП та транспорт\n"
        "• Кредити та борги\n"
        "• Кримінальне право\n"
        "• Адміністративне право\n\n"
        "📞 <b>Безкоштовна юридична допомога в Україні:</b>\n"
        "• Безоплатна правова допомога: 0 800 213 103\n"
        "• Сайт: <a href='https://legalaid.gov.ua'>legalaid.gov.ua</a>\n\n"
        "⚠️ <i>Бот надає загальну інформацію і не замінює консультацію юриста.</i>"
    )
    await update.message.reply_text(about_text, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "🆘 <b>Допомога</b>\n\n"
        "Команди:\n"
        "/start — Запустити бота\n"
        "/help — Ця довідка\n"
        "/menu — Головне меню\n"
        "/history — Моя історія питань\n\n"
        "Просто натисніть на тему або напишіть своє питання!"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /menu"""
    reply_markup = ReplyKeyboardMarkup(
        MAIN_MENU_KEYBOARD, resize_keyboard=True
    )
    await update.message.reply_text(
        "Головне меню:", reply_markup=reply_markup
    )
    return CHOOSING_TOPIC


def get_topic_questions(topic: str) -> list:
    """Популярні питання по темі"""
    questions_db = {
        "civil": [
            {"text": "Як повернути товар?", "question": "Як повернути товар неналежної якості?",
             "answer": "За Законом України 'Про захист прав споживачів' (ст. 8), ви маєте право повернути товар неналежної якості протягом гарантійного строку. Зверніться до продавця з чеком та паспортом. Продавець зобов'язаний прийняти товар і провести експертизу (до 14 днів). Якщо недолік підтверджено — вам повернуть гроші, замінять товар або відремонтують безкоштовно. При відмові — звертайтесь до Держпродспоживслужби або суду."},
            {"text": "Термін позовної давності", "question": "Які строки позовної давності в Україні?",
             "answer": "Згідно зі ст. 257 ЦКУ, загальна позовна давність — 3 роки. Спеціальні строки: 1 рік — для позовів про стягнення неустойки, оспорювання угод; 5 років — для позовів про визнання угоди недійсною (нікчемної); 10 років — для позовів щодо застосування наслідків нікчемного правочину. Перебіг починається з дня, коли особа дізналась або мала дізнатись про порушення свого права."},
        ],
        "housing": [
            {"text": "Виселення з квартири", "question": "Чи можуть мене виселити з квартири?",
             "answer": "Виселення можливе лише в судовому порядку (ст. 40 ЖКУ). Підстави: несплата комунальних послуг понад 6 місяців, систематичне порушення прав сусідів, використання житла не за призначенням, знесення будинку. Без судового рішення ніхто не може примусово вас виселити. Власника квартири можна виселити лише у виняткових випадках, передбачених законом. При загрозі виселення негайно зверніться до юриста."},
            {"text": "Права орендаря", "question": "Які права має орендар квартири?",
             "answer": "Орендар має право: користуватись житлом протягом строку договору; здавати в суборенду (якщо дозволено договором); вимагати усунення недоліків; розірвати договір при неналежному стані житла. Господар не може виселити без попередження за 3 місяці (якщо інше не передбачено договором) або підвищувати плату частіше ніж раз на рік. Рекомендую укладати договір нотаріально та реєструвати у ДПС."},
        ],
        "family": [
            {"text": "Розлучення з дітьми", "question": "Як проходить розлучення якщо є неповнолітні діти?",
             "answer": "При розлученні з дітьми до 18 років справа розглядається в суді (ст. 109 СКУ). Суд визначає: з ким залишаються діти; розмір аліментів (мінімум 50% прожиткового мінімуму на дитину); порядок спілкування другого з батьків з дітьми. Аліменти стягуються з доходу батька/матері: 1 дитина — 1/4, 2 дітей — 1/3, 3 і більше — 1/2. Подайте позов до суду за місцем проживання."},
            {"text": "Аліменти", "question": "Як стягнути аліменти на дитину?",
             "answer": "Аліменти можна отримати: добровільно (нотаріальна угода); через суд (позов до суду за місцем проживання позивача). Розмір: мінімум 50% прожиткового мінімуму на дитину. Суд може призначити в частці від доходу або фіксованою сумою. Виконавчий лист передайте до державної виконавчої служби. При ухиленні від сплати — кримінальна відповідальність за ст. 164 ККУ."},
        ],
        "labor": [
            {"text": "Незаконне звільнення", "question": "Що робити при незаконному звільненні з роботи?",
             "answer": "Якщо вас звільнили незаконно, протягом 1 місяця подайте позов до суду (ст. 233 КЗпП). Вимагайте: поновлення на роботі; виплати середнього заробітку за час вимушеного прогулу; відшкодування моральної шкоди. Також можна звернутись до Держпраці (Державна служба з питань праці) або прокуратури. Зберігайте всі документи: наказ про звільнення, трудову книжку, копії заяв."},
            {"text": "Невиплата зарплати", "question": "Що робити якщо роботодавець не виплачує зарплату?",
             "answer": "При затримці зарплати: 1) Зверніться письмово до керівника. 2) Подайте скаргу до Державної служби з питань праці (Держпраці). 3) Зверніться до суду — за несплату зарплати понад 1 місяць суд видає судовий наказ без розгляду справи. 4) Повідомте прокуратуру при систематичних затримках. За ст. 175 ККУ — кримінальна відповідальність до 5 років. Роботодавець також платить компенсацію 3% за кожен день прострочення."},
        ],
        "transport": [
            {"text": "ДТП — що робити?", "question": "Що робити після ДТП?",
             "answer": "Після ДТП: 1) Зупиніться, увімкніть аварійку, виставте знак (20м у місті, 40м на трасі). 2) Викличте поліцію (102) та швидку (103) якщо є постраждалі. 3) Не переміщуйте автомобілі до приїзду поліції. 4) Зафіксуйте місце ДТП фото/відео. 5) Обміняйтесь даними з іншим учасником. 6) Зверніться до страхової компанії протягом 3 робочих днів. Якщо шкода до 50 000 грн і немає постраждалих — можна оформити Європротокол без поліції."},
            {"text": "Позбавлення прав", "question": "Як оскаржити позбавлення водійських прав?",
             "answer": "Постанову про позбавлення прав можна оскаржити: протягом 10 днів до суду або вищого органу поліції (ст. 291 КУпАП). Підстави: процесуальні порушення при складанні протоколу; відсутність або ненадійність доказів; порушення ваших прав при розгляді справи. Зберіть докази (відео з реєстратора, свідки). Зупинення виконання постанови можливе при поданні скарги. Рекомендується допомога адвоката."},
        ],
        "credits": [
            {"text": "Борг колекторам", "question": "Що робити якщо телефонують колектори?",
             "answer": "Колектори в Україні мають право: повідомляти про борг, пропонувати реструктуризацію. Заборонено: погрожувати, турбувати з 22:00 до 8:00, контактувати частіше 2 разів на добу, розголошувати інформацію третім особам. При порушеннях скаржтесь до НБУ (банківський борг) або Нацкомфінпослуг. Ви маєте право письмово відмовитись від контактів. Борг не зникає — суд може стягнути примусово. Зверніться до юриста щодо реструктуризації чи банкрутства."},
            {"text": "Кредитна пастка", "question": "Як законно не платити кредит МФО?",
             "answer": "Законні способи вирішення: 1) Реструктуризація — зверніться до МФО з проханням змінити умови. 2) Визнання договору недійсним — якщо порушено закон при укладанні (відсоток понад 2,5% на день — незаконно за Законом про споживче кредитування). 3) Строк позовної давності — 3 роки. Після спливу МФО не може стягнути через суд. 4) Банкрутство фізособи (з 2019 року). Зверніть увагу: прострочення псує кредитну історію. Не ігноруйте — судове рішення виконавці виконують примусово."},
        ],
        "criminal": [
            {"text": "Права при затриманні", "question": "Які мої права якщо мене затримала поліція?",
             "answer": "При затриманні ви маєте право (ст. 29 КУ, КПК): знати причину затримання; негайно зателефонувати адвокату або родичам; мовчати — все сказане може бути використано проти вас; відмовитись давати показання без адвоката; на перекладача. Поліція зобов'язана: представитись; пояснити підставу затримання; скласти протокол. Максимальний строк без санкції прокурора — 72 години. Запам'ятайте: НІКОЛИ не підписуйте документи без адвоката!"},
            {"text": "Самозахист та зброя", "question": "Коли самооборона є законною в Україні?",
             "answer": "Необхідна оборона (ст. 36 ККУ) є законною якщо: є реальна загроза для вашого життя або здоров'я; дії спрямовані проти нападника; шкода відповідає небезпеці нападу. Перевищення меж необхідної оборони — кримінально карається. Зброя самооборони в Україні: балончики з газом — без дозволу; травматична та вогнестрільна — з дозволом поліції. При будь-якому випадку самооборони: викличте поліцію, не торкайтесь нічого, чекайте на адвоката."},
        ],
        "admin": [
            {"text": "Штраф поліції", "question": "Як оскаржити адміністративний штраф?",
             "answer": "Штраф можна оскаржити протягом 10 днів (ст. 288 КУпАП) до: вищого органу або посадової особи; суду за місцем розгляду справи. Підстави: протокол складено з порушеннями; вина не доведена; порушено ваші права при розгляді. Подайте скаргу письмово з копіями документів. При поданні скарги — виконання постанови зупиняється. Держмито не сплачується. Рекомендується зафіксувати всі порушення одразу."},
            {"text": "Відмова держоргану", "question": "Що робити якщо держорган відмовляє у послузі?",
             "answer": "При незаконній відмові держоргану: 1) Вимагайте письмову мотивовану відмову. 2) Оскаржте керівнику органу або вищому органу. 3) Зверніться до суду (адміністративний позов) — строк 6 місяців з дня відмови. 4) Подайте скаргу до омбудсмена (Уповноважений ВРУ з прав людини): 0800 50 17 20. 5) Для корупційних дій — до НАЗК або НАБУ. Держоргани зобов'язані відповідати на звернення протягом 30 днів (Закон про звернення громадян)."},
        ],
    }
    return questions_db.get(topic, [])


def main():
    """Запуск бота"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN не знайдено в .env файлі!")

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
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("history", lambda u, c: show_history(u, c)))

    logger.info("✅ Бот запущено!")
    print("✅ Бот запущено! Натисніть Ctrl+C для зупинки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
