import os
import logging
from datetime import datetime
from collections import defaultdict
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен из переменных окружения Railway
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")

# --- Хранилище в памяти (все данные здесь!) ---
# Структура:
# user_data[user_id] = {
#     'income': [(amount, desc, date), ...],
#     'mandatory': [(amount, desc, date), ...],
#     'optional': [(amount, desc, date), ...]
# }
user_data = defaultdict(lambda: {
    'income': [],
    'mandatory': [],
    'optional': []
})

# --- Состояния FSM ---
class FinanceStates(StatesGroup):
    waiting_for_income = State()
    waiting_for_mandatory = State()
    waiting_for_optional = State()
    waiting_for_delete = State()

# --- Клавиатуры ---
def get_main_keyboard():
    """Главная инлайн-клавиатура."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Доход", callback_data="add_income")],
        [InlineKeyboardButton(text="💰 Обязательный расход", callback_data="add_mandatory")],
        [InlineKeyboardButton(text="🍕 Необязательный расход", callback_data="add_optional")],
        [InlineKeyboardButton(text="📊 Итоги за месяц", callback_data="show_summary")],
        [InlineKeyboardButton(text="📜 История операций", callback_data="show_history")],
        [InlineKeyboardButton(text="🗑 Очистить все данные", callback_data="clear_data")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

def get_cancel_keyboard():
    """Клавиатура с кнопкой отмены."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_clear_keyboard():
    """Клавиатура подтверждения очистки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, очистить всё", callback_data="confirm_clear")],
        [InlineKeyboardButton(text="❌ Нет, отменить", callback_data="back_to_menu")]
    ])

# --- Вспомогательные функции ---
def format_date(date):
    """Форматирует дату."""
    return date.strftime("%d.%m %H:%M")

def get_monthly_data(user_id):
    """Получает данные только за текущий месяц."""
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    result = {'income': 0, 'mandatory': 0, 'optional': 0}
    
    for trans_type in ['income', 'mandatory', 'optional']:
        for amount, desc, date in user_data[user_id][trans_type]:
            if date.year == current_year and date.month == current_month:
                result[trans_type] += amount
    
    return result

def get_all_time_data(user_id):
    """Получает все данные за всё время."""
    result = {'income': 0, 'mandatory': 0, 'optional': 0}
    
    for trans_type in ['income', 'mandatory', 'optional']:
        for amount, desc, date in user_data[user_id][trans_type]:
            result[trans_type] += amount
    
    return result

# --- Обработчики команд ---
async def start_command(message: types.Message, state: FSMContext):
    """Команда /start."""
    await state.clear()
    await message.answer(
        "💰 *Бот учёта финансов*\n\n"
        "Я помогу отслеживать доходы и расходы.\n"
        "Разделяю траты на обязательные и необязательные.\n\n"
        "⚠️ *Важно:* Данные хранятся только в памяти!\n"
        "При перезапуске бота все данные будут потеряны.\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def help_command(message: types.Message):
    """Команда /help."""
    await message.answer(
        "📚 *Помощь*\n\n"
        "*/start* - Главное меню\n"
        "*/stats* - Итоги за месяц\n"
        "*/allstats* - Итоги за всё время\n"
        "*/history* - История операций\n"
        "*/clear* - Очистить все данные\n"
        "*/cancel* - Отмена\n\n"
        "*Типы расходов:*\n"
        "🔴 *Обязательные* - аренда, коммуналка, кредиты, связь\n"
        "🟡 *Необязательные* - кафе, кино, развлечения, покупки\n\n"
        "💡 *Совет:* Старайтесь, чтобы необязательные расходы не превышали 30% от доходов!\n\n"
        "⚠️ *Внимание:* При перезапуске бота все данные удаляются!",
        parse_mode="Markdown"
    )

async def stats_command(message: types.Message):
    """Команда /stats - статистика за месяц."""
    user_id = message.from_user.id
    data = get_monthly_data(user_id)
    
    income = data['income']
    mandatory = data['mandatory']
    optional = data['optional']
    total = mandatory + optional
    balance = income - total
    
    # Проценты
    mandatory_pct = (mandatory / income * 100) if income > 0 else 0
    optional_pct = (optional / income * 100) if income > 0 else 0
    balance_pct = (balance / income * 100) if income > 0 else 0
    
    msg = (
        f"📊 *Статистика за текущий месяц*\n\n"
        f"💰 *Доходы:* {income:.2f} руб.\n"
        f"🔴 *Обязательные:* {mandatory:.2f} руб. ({mandatory_pct:.1f}%)\n"
        f"🟡 *Необязательные:* {optional:.2f} руб. ({optional_pct:.1f}%)\n"
        f"💸 *Всего расходов:* {total:.2f} руб. ({total/income*100 if income>0 else 0:.1f}%)\n"
        f"⚖️ *Баланс:* {balance:.2f} руб. ({balance_pct:.1f}%)\n\n"
    )
    
    if income == 0:
        msg += "⚠️ *Нет данных о доходах!*\nДобавьте доход через меню."
    elif balance > 0:
        if balance_pct >= 20:
            msg += "✅ *Отлично!* Вы откладываете более 20% доходов! 🎉"
        elif balance_pct >= 10:
            msg += f"✅ *Хорошо!* Можно отложить {balance:.2f} руб. 💪"
        else:
            msg += f"✅ У вас остаётся {balance:.2f} руб. 💰"
    elif balance < 0:
        msg += f"⚠️ *Внимание!* Превышение бюджета на {abs(balance):.2f} руб.\nСократите необязательные расходы! 📉"
    else:
        msg += "⚖️ Доходы равны расходам."
    
    await message.answer(msg, parse_mode="Markdown")

async def allstats_command(message: types.Message):
    """Команда /allstats - статистика за всё время."""
    user_id = message.from_user.id
    data = get_all_time_data(user_id)
    
    income = data['income']
    mandatory = data['mandatory']
    optional = data['optional']
    total = mandatory + optional
    balance = income - total
    
    msg = (
        f"📊 *Статистика за всё время*\n\n"
        f"💰 *Всего доходов:* {income:.2f} руб.\n"
        f"🔴 *Обязательные расходы:* {mandatory:.2f} руб.\n"
        f"🟡 *Необязательные расходы:* {optional:.2f} руб.\n"
        f"💸 *Всего расходов:* {total:.2f} руб.\n"
        f"⚖️ *Итоговый баланс:* {balance:.2f} руб.\n\n"
    )
    
    if income == 0:
        msg += "📭 *Нет данных* — добавьте первый доход!"
    elif balance > 0:
        msg += f"🎉 *Поздравляю!* Вы накопили {balance:.2f} руб.!"
    elif balance < 0:
        msg += f"⚠️ *Задолженность:* {abs(balance):.2f} руб."
    
    await message.answer(msg, parse_mode="Markdown")

async def history_command(message: types.Message):
    """Команда /history - история операций."""
    user_id = message.from_user.id
    
    # Собираем все операции
    all_transactions = []
    for trans_type, emoji, name in [
        ('income', '💰', 'Доход'),
        ('mandatory', '🔴', 'Обязат.'),
        ('optional', '🟡', 'Необяз.')
    ]:
        for amount, desc, date in user_data[user_id][trans_type]:
            all_transactions.append({
                'type': trans_type,
                'emoji': emoji,
                'name': name,
                'amount': amount,
                'desc': desc,
                'date': date
            })
    
    # Сортируем по дате (новые сверху)
    all_transactions.sort(key=lambda x: x['date'], reverse=True)
    
    if not all_transactions:
        await message.answer(
            "📭 *История пуста*\n\nДобавьте доходы и расходы через меню.",
            parse_mode="Markdown"
        )
        return
    
    # Показываем последние 10 операций
    msg = "📜 *Последние операции:*\n\n"
    for t in all_transactions[:10]:
        date_str = format_date(t['date'])
        msg += f"{t['emoji']} *{t['name']}*: {t['amount']:.2f} руб.\n"
        if t['desc'] and t['desc'] != "Без описания":
            msg += f"   📝 {t['desc'][:50]}\n"
        msg += f"   🕐 {date_str}\n\n"
    
    total_count = len(all_transactions)
    if total_count > 10:
        msg += f"\n📌 *Показано 10 из {total_count} операций*"
    
    await message.answer(msg, parse_mode="Markdown")

async def clear_command(message: types.Message):
    """Команда /clear - очистка всех данных."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Очистить всё", callback_data="confirm_clear")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")]
    ])
    await message.answer(
        "⚠️ *Внимание!*\n\n"
        "Вы уверены, что хотите удалить ВСЕ данные?\n"
        "Это действие нельзя отменить!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def cancel_command(message: types.Message, state: FSMContext):
    """Команда /cancel."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "❌ Действие отменено.",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "Нет активных действий для отмены.",
            reply_markup=get_main_keyboard()
        )

# --- Callback обработчики ---
async def handle_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка инлайн-кнопок."""
    await callback.answer()
    
    if callback.data == "add_income":
        await callback.message.edit_text(
            "💰 *Добавление дохода*\n\n"
            "Введите сумму и комментарий через пробел:\n"
            "`50000 зарплата за март`\n\n"
            "Или просто сумму: `50000`\n\n"
            "Нажмите /cancel для отмены",
            parse_mode="Markdown"
        )
        await state.set_state(FinanceStates.waiting_for_income)
        
    elif callback.data == "add_mandatory":
        await callback.message.edit_text(
            "🔴 *Добавление обязательного расхода*\n\n"
            "Введите сумму и комментарий через пробел:\n"
            "`15000 аренда квартиры`\n\n"
            "Нажмите /cancel для отмены",
            parse_mode="Markdown"
        )
        await state.set_state(FinanceStates.waiting_for_mandatory)
        
    elif callback.data == "add_optional":
        await callback.message.edit_text(
            "🟡 *Добавление необязательного расхода*\n\n"
            "Введите сумму и комментарий через пробел:\n"
            "`1000 кино с друзьями`\n\n"
            "Нажмите /cancel для отмены",
            parse_mode="Markdown"
        )
        await state.set_state(FinanceStates.waiting_for_optional)
        
    elif callback.data == "show_summary":
        user_id = callback.from_user.id
        data = get_monthly_data(user_id)
        
        income = data['income']
        mandatory = data['mandatory']
        optional = data['optional']
        balance = income - (mandatory + optional)
        
        mandatory_pct = (mandatory / income * 100) if income > 0 else 0
        optional_pct = (optional / income * 100) if income > 0 else 0
        
        msg = (
            f"📊 *Отчёт за месяц*\n\n"
            f"💰 *Доходы:* {income:.2f} руб.\n"
            f"🔴 *Обязательные:* {mandatory:.2f} руб. ({mandatory_pct:.1f}%)\n"
            f"🟡 *Необязательные:* {optional:.2f} руб. ({optional_pct:.1f}%)\n"
            f"⚖️ *Баланс:* {balance:.2f} руб.\n"
        )
        
        if balance > 0:
            msg += f"\n✅ Остаток: {balance:.2f} руб."
        elif balance < 0:
            msg += f"\n⚠️ Перерасход: {abs(balance):.2f} руб."
        
        await callback.message.edit_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ])
        )
        
    elif callback.data == "show_history":
        user_id = callback.from_user.id
        
        all_transactions = []
        for trans_type, emoji, name in [
            ('income', '💰', 'Доход'),
            ('mandatory', '🔴', 'Обязат.'),
            ('optional', '🟡', 'Необяз.')
        ]:
            for amount, desc, date in user_data[user_id][trans_type]:
                all_transactions.append({
                    'emoji': emoji,
                    'name': name,
                    'amount': amount,
                    'desc': desc,
                    'date': date
                })
        
        all_transactions.sort(key=lambda x: x['date'], reverse=True)
        
        if not all_transactions:
            await callback.message.edit_text(
                "📭 *История пуста*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
                ])
            )
            return
        
        msg = "📜 *Последние операции:*\n\n"
        for t in all_transactions[:5]:
            date_str = format_date(t['date'])
            msg += f"{t['emoji']} *{t['name']}*: {t['amount']:.2f} руб.\n"
            if t['desc'] and t['desc'] != "Без описания":
                msg += f"   📝 {t['desc'][:40]}\n"
            msg += f"   🕐 {date_str}\n\n"
        
        await callback.message.edit_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📜 Все операции", callback_data="show_full_history")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ])
        )
        
    elif callback.data == "show_full_history":
        user_id = callback.from_user.id
        
        all_transactions = []
        for trans_type, emoji, name in [
            ('income', '💰', 'Доход'),
            ('mandatory', '🔴', 'Обязат.'),
            ('optional', '🟡', 'Необяз.')
        ]:
            for amount, desc, date in user_data[user_id][trans_type]:
                all_transactions.append({
                    'emoji': emoji,
                    'name': name,
                    'amount': amount,
                    'desc': desc,
                    'date': date
                })
        
        all_transactions.sort(key=lambda x: x['date'], reverse=True)
        
        if not all_transactions:
            await callback.message.edit_text(
                "📭 История пуста",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
                ])
            )
            return
        
        msg = "📜 *Все операции:*\n\n"
        for t in all_transactions[:20]:
            date_str = format_date(t['date'])
            msg += f"{t['emoji']} {t['amount']:.0f} руб. — {date_str}\n"
            if t['desc'] and t['desc'] != "Без описания":
                msg += f"   📝 {t['desc'][:30]}\n"
        
        if len(all_transactions) > 20:
            msg += f"\n📌 *Показано 20 из {len(all_transactions)} операций*"
        
        await callback.message.edit_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="show_history")]
            ])
        )
        
    elif callback.data == "clear_data":
        await callback.message.edit_text(
            "⚠️ *Удалить все данные?*\n\n"
            "Это действие нельзя отменить!",
            parse_mode="Markdown",
            reply_markup=get_clear_keyboard()
        )
        
    elif callback.data == "confirm_clear":
        user_id = callback.from_user.id
        user_data[user_id] = {'income': [], 'mandatory': [], 'optional': []}
        await callback.message.edit_text(
            "🗑 *Все данные успешно удалены!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
            ])
        )
        
    elif callback.data == "help":
        await callback.message.edit_text(
            "📚 *Справка*\n\n"
            "💰 *Доходы* — деньги, которые вы получили\n"
            "🔴 *Обязательные расходы* — то, без чего нельзя обойтись:\n"
            "   • Аренда жилья\n"
            "   • Коммунальные платежи\n"
            "   • Кредиты\n"
            "   • Связь, интернет\n"
            "🟡 *Необязательные расходы* — развлечения и удовольствия:\n"
            "   • Кафе и рестораны\n"
            "   • Кино, концерты\n"
            "   • Покупки (кроме необходимых)\n\n"
            "💡 *Правило 50/30/20:*\n"
            "50% — обязательные траты\n"
            "30% — необязательные\n"
            "20% — накопления\n\n"
            "⚠️ *Данные хранятся в памяти!*\n"
            "При перезапуске бота всё удалится.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ])
        )
        
    elif callback.data == "back_to_menu":
        await callback.message.edit_text(
            "👋 *Главное меню*\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        await state.clear()

# --- Обработчики ввода ---
async def process_income(message: types.Message, state: FSMContext):
    """Обработка ввода дохода."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        parts = message.text.split(maxsplit=1)
        amount = float(parts[0].replace(',', '.'))
        description = parts[1] if len(parts) > 1 else "Без описания"
        
        user_id = message.from_user.id
        user_data[user_id]['income'].append((amount, description, datetime.now()))
        
        await message.answer(
            f"✅ *Доход добавлен!*\n\n"
            f"💰 Сумма: {amount:.2f} руб.\n"
            f"📝 {description}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ *Ошибка!*\n\n"
            "Введите сумму числом.\n"
            "Пример: `50000 зарплата`",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )

async def process_mandatory(message: types.Message, state: FSMContext):
    """Обработка ввода обязательного расхода."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        parts = message.text.split(maxsplit=1)
        amount = float(parts[0].replace(',', '.'))
        description = parts[1] if len(parts) > 1 else "Без описания"
        
        user_id = message.from_user.id
        user_data[user_id]['mandatory'].append((amount, description, datetime.now()))
        
        await message.answer(
            f"✅ *Обязательный расход добавлен!*\n\n"
            f"🔴 Сумма: {amount:.2f} руб.\n"
            f"📝 {description}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ *Ошибка!*\n\n"
            "Введите сумму числом.\n"
            "Пример: `15000 аренда`",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )

async def process_optional(message: types.Message, state: FSMContext):
    """Обработка ввода необязательного расхода."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        parts = message.text.split(maxsplit=1)
        amount = float(parts[0].replace(',', '.'))
        description = parts[1] if len(parts) > 1 else "Без описания"
        
        user_id = message.from_user.id
        user_data[user_id]['optional'].append((amount, description, datetime.now()))
        
        await message.answer(
            f"✅ *Необязательный расход добавлен!*\n\n"
            f"🟡 Сумма: {amount:.2f} руб.\n"
            f"📝 {description}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ *Ошибка!*\n\n"
            "Введите сумму числом.\n"
            "Пример: `1000 кино`",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )

# --- Запуск бота ---
async def main():
    """Главная функция."""
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация команд
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(stats_command, Command("stats"))
    dp.message.register(allstats_command, Command("allstats"))
    dp.message.register(history_command, Command("history"))
    dp.message.register(clear_command, Command("clear"))
    dp.message.register(cancel_command, Command("cancel"))
    
    # Регистрация callback
    dp.callback_query.register(handle_callback)
    
    # Регистрация состояний
    dp.message.register(process_income, FinanceStates.waiting_for_income)
    dp.message.register(process_mandatory, FinanceStates.waiting_for_mandatory)
    dp.message.register(process_optional, FinanceStates.waiting_for_optional)
    
    logger.info("🚀 Бот запущен! Данные хранятся в памяти.")
    logger.info("⚠️ При перезапуске все данные будут потеряны!")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())