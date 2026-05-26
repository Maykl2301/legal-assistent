# ⚖️ Бот-юрист для Telegram

Telegram бот, який надає базові юридичні консультації громадянам України.

## 📁 Структура проекту

```
lawyer_bot/
├── bot.py           # Головний файл бота
├── responses.py     # База юридичних відповідей
├── database.py      # SQLite база даних
├── requirements.txt # Залежності
├── render.yaml      # Конфіг для Render.com
├── .env.example     # Шаблон для змінних середовища
└── .gitignore
```

---

## 🚀 Крок 1: Створення бота в Telegram

1. Відкрийте Telegram, знайдіть `@BotFather`
2. Надішліть `/newbot`
3. Введіть назву бота (наприклад: `Юрист-помічник`)
4. Введіть username (наприклад: `my_lawyer_ua_bot`)
5. Скопіюйте токен — він виглядає так: `1234567890:AABBccDDeEffGG...`

---

## 📱 Крок 2: Запуск на Termux (Android)

### Встановлення Termux:
1. Завантажте **Termux** з F-Droid (не з Play Store!)
   - F-Droid: https://f-droid.org
   - Або: https://github.com/termux/termux-app/releases

### Налаштування:
```bash
# Оновлення пакетів
pkg update && pkg upgrade -y

# Встановлення Python і Git
pkg install python git -y

# Перехід в домашню директорію
cd ~

# Клонування репозиторію (після завантаження на GitHub)
# git clone https://github.com/ВАШЕ_ІМ'Я/lawyer_bot.git
# cd lawyer_bot

# АБО просто скопіюйте файли через файловий менеджер
# і перейдіть в папку:
cd lawyer_bot

# Встановлення залежностей
pip install -r requirements.txt

# Створення .env файлу
cp .env.example .env

# Редагування токену
nano .env
# Замініть "ВАШ_ТОКЕН_ТУТ" на реальний токен від BotFather
# Збережіть: Ctrl+X, Y, Enter
```

### Запуск:
```bash
python bot.py
```

### Запуск у фоні (щоб бот працював при згорнутому Termux):
```bash
# Встановіть termux-services або просто використовуйте:
nohup python bot.py > bot.log 2>&1 &

# Перегляд логів:
tail -f bot.log

# Зупинка:
pkill -f "python bot.py"
```

---

## 🐱 Крок 3: Завантаження на GitHub

### Перший раз:
```bash
# Встановіть Git (якщо ще не встановлений)
pkg install git -y   # Termux
# або
sudo apt install git # Linux/Ubuntu

# Налаштування Git
git config --global user.name "Ваше Ім'я"
git config --global user.email "ваш@email.com"

# Ініціалізація репозиторію
cd lawyer_bot
git init
git add .
git commit -m "Initial commit: lawyer telegram bot"

# Створіть репозиторій на github.com (назва: lawyer_bot)
# Потім:
git remote add origin https://github.com/ВАШЕ_ІМ'Я/lawyer_bot.git
git branch -M main
git push -u origin main
```

### При оновленнях:
```bash
git add .
git commit -m "Оновлення бази відповідей"
git push
```

---

## 🌐 Крок 4: Деплой на Render.com

1. Зайдіть на **render.com** та зареєструйтесь (безкоштовно)

2. Натисніть **"New +"** → **"Web Service"**
   > ⚠️ Обирайте **"Background Worker"** або **"Web Service"** з типом Worker

3. Підключіть GitHub репозиторій

4. Налаштування:
   - **Name**: `lawyer-telegram-bot`
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`

5. Додайте змінну середовища:
   - Перейдіть в **Environment**
   - Додайте: `TELEGRAM_BOT_TOKEN` = `ваш_токен_тут`

6. Натисніть **"Create Web Service"**

### ✅ Render автоматично:
- Встановить залежності
- Запустить бота
- Перезапустить при падінні
- Оновить при push на GitHub

---

## 🔄 Workflow: оновлення бота

```bash
# 1. Редагуєте файли
# 2. Завантажуєте на GitHub:
git add .
git commit -m "Додав нові відповіді"
git push

# 3. Render автоматично підтягне зміни і перезапустить бота
```

---

## ➕ Додавання нових відповідей

Відкрийте `responses.py` і додайте в `KNOWLEDGE_BASE`:

```python
(
    ["ключове слово", "інше слово", "ще одне"],
    "⚖️ <b>Заголовок</b>\n\n"
    "Текст відповіді...\n\n"
    "📌 Підказка"
),
```

---

## 📊 Можливості бота

- ✅ 8 тематичних категорій права
- ✅ База з 15+ детальних відповідей
- ✅ Пошук по ключових словах
- ✅ Довільні питання від користувача
- ✅ Збереження історії питань (SQLite)
- ✅ Inline кнопки та зручне меню
- ✅ Посилання на безоплатну правову допомогу

---

## 📞 Корисні контакти (вшиті в бота)

- Безоплатна правова допомога: **0 800 213 103**
- НБУ (кредитні питання): **0 800 505 240**
- Сайт: legalaid.gov.ua
