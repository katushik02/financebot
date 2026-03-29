import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния для ConversationHandler
CHOOSING_ACTION, ADDING_INCOME, ADDING_MANDATORY, ADDING_OPTIONAL = range(4)

# Токен берем из переменных окружения Railway
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")

# --- Работа с базой данных ---
def init_db():
    """Создает таблицы в базе данных."""
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            description TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_transaction(user_id, trans_type, amount, description):
    """Добавляет транзакцию."""
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, description, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, trans_type, amount, description))
    conn.commit()
    conn.close()

def get_monthly_summary(user_id):
    """Возвращает сводку за месяц."""
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    current_month = datetime.now().strftime("%Y-%m")
    cursor.execute('''
        SELECT type, SUM(amount) FROM transactions
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        GROUP BY type
    ''', (user_id, current_month))
    rows = cursor.fetchall()
    conn.close()
    
    summary = {'income': 0, 'mandatory': 0, 'optional': 0}
    for row in rows:
        summary[row[0]] = row[1] if row[1] else 0
    return summary

# --- Клавиатуры ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Доход", callback_data='add_income')],
        [InlineKeyboardButton("💰 Обязательный расход", callback_data='add_mandatory')],
        [InlineKeyboardButton("🍕 Необязательный расход", callback_data='add_optional')],
        [InlineKeyboardButton("📊 Итоги за месяц", callback_data='show_summary')],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 Привет! Я бот для учёта расходов и доходов.\n"
        "Выбери действие:",
        reply_markup=main_menu_keyboard()
    )
    return CHOOSING_ACTION

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'add_income':
        await query.edit_message_text("Введите сумму дохода:")
        return ADDING_INCOME
    elif query.data == 'add_mandatory':
        await query.edit_message_text("Введите сумму обязательного расхода:")
        return ADDING_MANDATORY
    elif query.data == 'add_optional':
        await query.edit_message_text("Введите сумму необязательного расхода:")
        return ADDING_OPTIONAL
    elif query.data == 'show_summary':
        await show_summary(update, context)
        await query.message.reply_text("Выберите действие:", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION
    elif query.data == 'back_to_menu':
        await query.edit_message_text("Главное меню:", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION

async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(',', '.'))
        user_id = update.effective_user.id
        add_transaction(user_id, 'income', amount, "Доход")
        await update.message.reply_text(f"✅ Доход {amount} руб. добавлен!", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION
    except ValueError:
        await update.message.reply_text("❌ Введите число!", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION

async def add_mandatory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(',', '.'))
        user_id = update.effective_user.id
        add_transaction(user_id, 'mandatory', amount, "Обязательный расход")
        await update.message.reply_text(f"✅ Обязательный расход {amount} руб. добавлен!", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION
    except ValueError:
        await update.message.reply_text("❌ Введите число!", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION

async def add_optional(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(',', '.'))
        user_id = update.effective_user.id
        add_transaction(user_id, 'optional', amount, "Необязательный расход")
        await update.message.reply_text(f"✅ Необязательный расход {amount} руб. добавлен!", reply_markup=main_menu_keyboard())
        return CHOOSING_ACTION
    except ValueError:
        await update.message.reply_text("❌ Введите число!", reply_markup=main_menu_keyboard())

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    summary = get_monthly_summary(user_id)
    
    income = summary['income']
    mandatory = summary['mandatory']
    optional = summary['optional']
    total = mandatory + optional
    balance = income - total
    
    message = (
        f"📊 *Отчёт за месяц*\n\n"
        f"💰 Доходы: {income:.2f} руб.\n"
        f"🔴 Обязательные: {mandatory:.2f} руб.\n"
        f"🟡 Необязательные: {optional:.2f} руб.\n"
        f"💸 Всего расходов: {total:.2f} руб.\n"
        f"⚖️ Баланс: {balance:.2f} руб.\n"
    )
    
    if balance > 0:
        message += f"✅ Можно отложить {balance:.2f} руб."
    elif balance < 0:
        message += f"⚠️ Превышение бюджета на {abs(balance):.2f} руб."
    
    await query.edit_message_text(
        text=message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]
        ])
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard())
    return CHOOSING_ACTION

# --- Запуск бота ---
def main():
    init_db()
    
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_ACTION: [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, start),
            ],
            ADDING_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_income)],
            ADDING_MANDATORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_mandatory)],
            ADDING_OPTIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_optional)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', lambda u, c: u.message.reply_text(
        "/start - Главное меню\n/cancel - Отмена")))
    
    print("Бот запущен на Railway!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()