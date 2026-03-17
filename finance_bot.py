import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для разговоров (ConversationHandler)
(
    CHOOSING_ACTION,
    ADDING_INCOME,
    ADDING_MANDATORY,
    ADDING_OPTIONAL,
    AWAITING_CONFIRMATION,
) = range(5)

# Токен вашего бота (получите у @BotFather)
TOKEN = "8772555387:AAGY9e_slmhwfd--eSnuiAN6JuDrrBvtPHg"

# --- Работа с базой данных ---
def init_db():
    """Создаёт таблицы в базе данных, если их нет."""
    conn = sqlite3.connect('finance_bot.db')
    cursor = conn.cursor()
    # Таблица для транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,  -- 'income', 'mandatory', 'optional'
            amount REAL,
            description TEXT,
            date TEXT
        )
    ''')
    # Таблица для месячного бюджета/лимитов (опционально)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_budget (
            user_id INTEGER PRIMARY KEY,
            month TEXT,
            mandatory_limit REAL DEFAULT 0,
            optional_limit REAL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def add_transaction(user_id, trans_type, amount, description):
    """Добавляет запись о транзакции в БД."""
    conn = sqlite3.connect('finance_bot.db')
    cursor = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, description, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, trans_type, amount, description, date))
    conn.commit()
    conn.close()

def get_monthly_summary(user_id):
    """Возвращает сводку за текущий месяц."""
    conn = sqlite3.connect('finance_bot.db')
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
        summary[row[0]] = row[1]
    return summary

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Приветственное сообщение и главное меню."""
    await update.message.reply_text(
        "👋 Привет! Я бот для учёта расходов и доходов.\n"
        "Я помогу тебе разделять обязательные и необязательные траты.\n"
        "Выбери действие:",
        reply_markup=main_menu_keyboard()
    )
    return CHOOSING_ACTION

def main_menu_keyboard():
    """Клавиатура главного меню."""
    keyboard = [
        [InlineKeyboardButton("➕ Доход", callback_data='add_income')],
        [InlineKeyboardButton("💰 Обязательный расход", callback_data='add_mandatory')],
        [InlineKeyboardButton("🍕 Необязательный расход", callback_data='add_optional')],
        [InlineKeyboardButton("📊 Итоги за месяц", callback_data='show_summary')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает нажатия на кнопки меню."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'add_income':
        await query.edit_message_text(
            text="Введите сумму дохода (можно добавить комментарий через пробел):"
        )
        return ADDING_INCOME
        
    elif query.data == 'add_mandatory':
        await query.edit_message_text(
            text="Введите сумму обязательного расхода (например: 15000 аренда):"
        )
        return ADDING_MANDATORY
        
    elif query.data == 'add_optional':
        await query.edit_message_text(
            text="Введите сумму необязательного расхода (например: 1000 кино):"
        )
        return ADDING_OPTIONAL
        
    elif query.data == 'show_summary':
        await show_summary(update, context)
        # Возвращаемся в главное меню
        await query.message.reply_text(
            "Выберите следующее действие:",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION
        
    elif query.data == 'back_to_menu':
        await query.edit_message_text(
            text="Главное меню:",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION

async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод дохода."""
    text = update.message.text
    try:
        parts = text.split(maxsplit=1)
        amount = float(parts[0].replace(',', '.'))
        description = parts[1] if len(parts) > 1 else "Без описания"
        
        user_id = update.effective_user.id
        add_transaction(user_id, 'income', amount, description)
        
        await update.message.reply_text(
            f"✅ Доход {amount} руб. добавлен!\n"
            f"Описание: {description}",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Введите число (сумму) и, если хотите, комментарий.\n"
            "Пример: 50000 зарплата",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION

async def add_mandatory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод обязательного расхода."""
    text = update.message.text
    try:
        parts = text.split(maxsplit=1)
        amount = float(parts[0].replace(',', '.'))
        description = parts[1] if len(parts) > 1 else "Без описания"
        
        user_id = update.effective_user.id
        add_transaction(user_id, 'mandatory', amount, description)
        
        await update.message.reply_text(
            f"✅ Обязательный расход {amount} руб. добавлен!\n"
            f"Описание: {description}",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Введите число и комментарий.\n"
            "Пример: 15000 аренда",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION

async def add_optional(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод необязательного расхода."""
    text = update.message.text
    try:
        parts = text.split(maxsplit=1)
        amount = float(parts[0].replace(',', '.'))
        description = parts[1] if len(parts) > 1 else "Без описания"
        
        user_id = update.effective_user.id
        add_transaction(user_id, 'optional', amount, description)
        
        await update.message.reply_text(
            f"✅ Необязательный расход {amount} руб. добавлен!\n"
            f"Описание: {description}",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION
    except ValueError:
        await update.message.reply_text(
            "❌ Ошибка! Введите число и комментарий.\n"
            "Пример: 1000 кино",
            reply_markup=main_menu_keyboard()
        )
        return CHOOSING_ACTION

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает сводку за текущий месяц."""
    query = update.callback_query
    user_id = update.effective_user.id
    summary = get_monthly_summary(user_id)
    
    income = summary['income']
    mandatory = summary['mandatory']
    optional = summary['optional']
    total_expenses = mandatory + optional
    balance = income - total_expenses
    
    message = (
        f"📊 *Финансовый отчёт за текущий месяц*\n\n"
        f"💰 *Доходы:* {income:.2f} руб.\n"
        f"🔴 *Обязательные расходы:* {mandatory:.2f} руб.\n"
        f"🟡 *Необязательные расходы:* {optional:.2f} руб.\n"
        f"💸 *Всего расходов:* {total_expenses:.2f} руб.\n"
        f"⚖️ *Баланс:* {balance:.2f} руб.\n"
    )
    
    if balance > 0:
        message += f"✅ Можно отложить {balance:.2f} руб. или потратить на развлечения!"
    elif balance < 0:
        message += f"⚠️ Превышение бюджета на {abs(balance):.2f} руб. Пора экономить!"
    else:
        message += "⚖️ Идеальный баланс: доходы равны расходам."
    
    await query.edit_message_text(
        text=message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]
        ])
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена и возврат в меню."""
    await update.message.reply_text(
        "Действие отменено. Возвращаюсь в меню.",
        reply_markup=main_menu_keyboard()
    )
    return CHOOSING_ACTION

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам."""
    await update.message.reply_text(
        "📚 *Команды бота:*\n\n"
        "/start - Запустить бота и открыть меню\n"
        "/help - Показать эту справку\n"
        "/cancel - Отменить текущее действие\n\n"
        "*Как пользоваться:*\n"
        "1️⃣ Добавляйте доходы и расходы через меню\n"
        "2️⃣ Расходы делятся на обязательные (кварплата, кредиты) и необязательные (развлечения)\n"
        "3️⃣ Смотрите статистику за месяц, чтобы планировать бюджет",
        parse_mode='Markdown'
    )

def main():
    """Запуск бота."""
    # Инициализация БД
    init_db()
    
    # Создание приложения
    application = Application.builder().token(TOKEN).build()
    
    # Обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_ACTION: [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, start),  # На случай текста
            ],
            ADDING_INCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_income),
                CommandHandler('cancel', cancel),
            ],
            ADDING_MANDATORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_mandatory),
                CommandHandler('cancel', cancel),
            ],
            ADDING_OPTIONAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_optional),
                CommandHandler('cancel', cancel),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    
    # Запуск бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()