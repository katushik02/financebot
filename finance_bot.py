# -*- coding: utf-8 -*-
import telebot
import time
from datetime import datetime

# ВСТАВЬТЕ СВОЙ ТОКЕН
TOKEN = "8772555387:AAHxQ6kzK7vR2mN9pL4sW8yT3fG5jH2dK1"  # ваш токен

print("🔄 Подключаюсь к Telegram...")

# Создаем бота с увеличенным таймаутом
bot = telebot.TeleBot(TOKEN)

# Проверка соединения
try:
    me = bot.get_me()
    print(f"✅ Бот @{me.username} успешно подключен!")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    print("\n🔧 ЧТО ДЕЛАТЬ:")
    print("1. Проверьте интернет (откройте сайт в браузере)")
    print("2. Отключите VPN/прокси если есть")
    print("3. Попробуйте перезагрузить роутер")
    print("4. Проверьте брандмауэр Windows")
    exit()

# Хранилище данных
user_data = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "💰 БОТ РАБОТАЕТ!\n\n"
        "Команды:\n"
        "/income 50000 зарплата\n"
        "/need 15000 аренда\n"
        "/want 2000 кино\n"
        "/stats - итоги")

@bot.message_handler(commands=['income'])
def add_income(message):
    try:
        parts = message.text.split()
        amount = float(parts[1])
        desc = ' '.join(parts[2:]) if len(parts) > 2 else "доход"
        
        user_id = message.from_user.id
        if user_id not in user_data:
            user_data[user_id] = {'income': 0, 'need': 0, 'want': 0}
        
        user_data[user_id]['income'] += amount
        bot.reply_to(message, f"✅ Доход {amount}₽")
    except:
        bot.reply_to(message, "❌ Пример: /income 50000 зарплата")

@bot.message_handler(commands=['need'])
def add_need(message):
    try:
        parts = message.text.split()
        amount = float(parts[1])
        
        user_id = message.from_user.id
        if user_id not in user_data:
            user_data[user_id] = {'income': 0, 'need': 0, 'want': 0}
        
        user_data[user_id]['need'] += amount
        bot.reply_to(message, f"✅ Обязательный {amount}₽")
    except:
        bot.reply_to(message, "❌ Пример: /need 15000 аренда")

@bot.message_handler(commands=['want'])
def add_want(message):
    try:
        parts = message.text.split()
        amount = float(parts[1])
        
        user_id = message.from_user.id
        if user_id not in user_data:
            user_data[user_id] = {'income': 0, 'need': 0, 'want': 0}
        
        user_data[user_id]['want'] += amount
        bot.reply_to(message, f"✅ Необязательный {amount}₽")
    except:
        bot.reply_to(message, "❌ Пример: /want 2000 кино")

@bot.message_handler(commands=['stats'])
def stats(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.reply_to(message, "Нет данных. Добавьте /income")
        return
    
    data = user_data[user_id]
    income = data['income']
    need = data['need']
    want = data['want']
    balance = income - (need + want)
    
    msg = f"""
📊 ИТОГИ:
💰 Доход: {income}₽
🔴 Обязательные: {need}₽
🟡 Необязательные: {want}₽
⚖️ Остаток: {balance}₽
"""
    bot.reply_to(message, msg)

print("\n✅ Бот запущен и ждет команды!")
print("📱 Идите в Telegram и напишите /start")
print("\n❌ Если бот не отвечает, проверьте интернет")
print("💡 Для остановки нажмите Ctrl+C")

try:
    bot.polling(none_stop=True, interval=0, timeout=20)
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    print("\n🔄 Пробуем переподключиться через 5 секунд...")
    time.sleep(5)
    bot.polling(none_stop=True, interval=0, timeout=20)