

На основе проведенного анализа, предлагаю усовершенствовать ваш Telegram-бот для автоматизации процесса приема платежей и доступа к закрытому каналу. Я реализую автоматическую проверку платежей с использованием платежной системы.

## Выбор решения для автоматизации платежей

Для вашего бота необходимо добавить автоматический прием и проверку платежей. Существует несколько вариантов:

1. **Telegram Stars** - встроенная система платежей Telegram (подходит для цифровых товаров)
2. **Платежные шлюзы** - такие как QIWI, ЮMoney (Яндекс.Деньги) или другие популярные в России системы
3. **Система проверки платежей по комментариям к переводам** - более простой способ, который можно реализовать с минимальными изменениями

Исходя из вашего кода и требований, я предлагаю реализовать третий вариант - автоматическую проверку платежей по уникальным идентификаторам в комментариях. Это позволит сохранить вашу текущую структуру с минимальными изменениями.

## Изменения в коде

Вот усовершенствованная версия вашего кода с автоматической проверкой платежей:

```python
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from dataclasses import dataclass
from typing import Dict, List
import os
import json
import asyncio
import re
import hashlib
import time
import requests

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определение состояний для ConversationHandler
START, AWAITING_PAYMENT, PAYMENT_PROCESSING = range(3)

# Информация о вашем канале
CHANNEL_INFO = """
Ассаляму алейкум! 🕌

Добро пожаловать в мой закрытый канал!

Здесь я делюсь глубокими знаниями об исламе, саморазвитии и построении бизнеса в соответствии с мусульманскими принципами.

Вы найдете:
• Разборы аятов Корана
• Практические советы по жизни в соответствии с Сунной
• Бизнес-стратегии халяльного заработка
• Духовные практики для укрепления имана

Выберите подходящий вам тариф для доступа 👇
"""

# Структура тарифов
@dataclass
class Tariff:
    name: str
    price: int
    description: str
    duration_days: int

TARIFFS = {
    "month_1": Tariff(
        name="1 месяц", 
        price=500, 
        description="Доступ к закрытому каналу на 1 месяц", 
        duration_days=30
    ),
    "month_3": Tariff(
        name="3 месяца", 
        price=1500, 
        description="Доступ к закрытому каналу на 3 месяца + бонусные материалы", 
        duration_days=90
    ),
    "lifetime": Tariff(
        name="Навсегда", 
        price=5000, 
        description="Пожизненный доступ к каналу + все обновления + персональная консультация", 
        duration_days=0  # 0 означает бессрочно
    ),
}

# Настройки канала и бота
CHANNEL_ID = -1002556601836  # Замените на ID вашего канала
BOT_TOKEN = "7678032381:AAG7gs3yTU8bfOrxx3ItNNbZEX-IruSaEGI"  # Получите у @BotFather
ADMIN_ID = 7281866890  # Замените на ваш Telegram ID

# Реквизиты для оплаты
PAYMENT_CARD = "5555 5555 5555 5555"
PAYMENT_HOLDER = "Ваше Имя"

# Файл для хранения данных о пользователях и платежах
USERS_DB_FILE = "users_db.json"

# Интервал проверки платежей (в секундах)
PAYMENT_CHECK_INTERVAL = 60

# Загрузка базы данных пользователей
def load_users_db():
    if os.path.exists(USERS_DB_FILE):
        with open(USERS_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "payments": {}}

# Сохранение базы данных пользователей
def save_users_db(db):
    with open(USERS_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

# Генерация ID транзакции
def generate_transaction_id(user_id):
    # Создаем уникальный ID на основе user_id и текущего времени
    seed = f"{user_id}_{int(time.time())}"
    # Используем первые 8 символов хеша для создания короткого кода
    return f"TX{hashlib.md5(seed.encode()).hexdigest()[:8].upper()}"

# Функция эмуляции проверки платежа (в реальной системе здесь будет API вашей платежной системы)
async def check_payment_status(tx_id):
    """
    Симуляция проверки статуса платежа
    В реальной системе здесь будет взаимодействие с платежным API
    
    В данном примере, создается файл с именем транзакции для эмуляции оплаты.
    Если такой файл существует, значит платеж считается выполненным.
    """
    payment_file = f"payments/{tx_id}.txt"
    
    # Проверяем наличие директории для файлов платежей
    os.makedirs("payments", exist_ok=True)
    
    # Проверяем наличие файла с ID транзакции
    if os.path.exists(payment_file):
        # Если файл существует, считаем что платеж выполнен
        os.remove(payment_file)  # Удаляем файл после проверки
        return True
    
    return False

# Автоматическая проверка статуса платежей
async def check_pending_payments(context):
    """
    Периодически проверяет статус всех ожидающих платежей
    """
    db = load_users_db()
    payments_updated = False
    
    # Проходим по всем платежам со статусом "pending"
    for tx_id, payment_info in list(db["payments"].items()):
        if payment_info["status"] == "pending":
            # Проверяем статус платежа
            is_paid = await check_payment_status(tx_id)
            
            if is_paid:
                # Обновляем статус платежа на "confirmed"
                db["payments"][tx_id]["status"] = "confirmed"
                payments_updated = True
                
                # Получаем информацию о пользователе и тарифе
                user_id = payment_info["user_id"]
                tariff_id = payment_info["tariff_id"]
                tariff = TARIFFS[tariff_id]
                
                # Обновляем информацию о пользователе
                if str(user_id) not in db["users"]:
                    db["users"][str(user_id)] = {}
                
                db["users"][str(user_id)]["has_access"] = True
                db["users"][str(user_id)]["tariff_id"] = tariff_id
                
                # Устанавливаем дату истечения доступа, если это не пожизненный доступ
                if tariff.duration_days > 0:
                    expiry_time = int(time.time()) + (tariff.duration_days * 24 * 60 * 60)
                    db["users"][str(user_id)]["access_expiry"] = expiry_time
                else:
                    # Для пожизненного доступа устанавливаем null
                    db["users"][str(user_id)]["access_expiry"] = None
                
                # Создаем ссылку-приглашение для пользователя
                try:
                    invite_link = await context.bot.create_chat_invite_link(
                        chat_id=CHANNEL_ID,
                        member_limit=1,
                        expire_date=None
                    )
                    
                    # Уведомляем пользователя об успешной оплате и отправляем ссылку
                    success_message = f"""
Ассаляму алейкум! 🎉

Ваша оплата успешно подтверждена!

✅ Тариф: {tariff.name}
✅ Доступ: {"Навсегда" if tariff.duration_days == 0 else f"На {tariff.duration_days} дней"}

Для входа в закрытый канал используйте эту ссылку:
{invite_link.invite_link}

Джазакуму Ллаху хайран за доверие!
"""
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=success_message
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
                        
                    # Уведомляем администратора об успешном платеже
                    admin_message = f"""
✅ Платеж автоматически подтвержден!
От: ID {user_id}
Тариф: {tariff.name}
Сумма: {tariff.price} ₽
Код транзакции: {tx_id}
                    """
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=admin_message
                    )
                    
                except Exception as e:
                    logger.error(f"Ошибка при создании ссылки-приглашения: {e}")
    
    # Если были изменения в базе данных, сохраняем их
    if payments_updated:
        save_users_db(db)

# Генерация клавиатуры с тарифами
def get_tariffs_keyboard():
    keyboard = []
    for tariff_id, tariff in TARIFFS.items():
        button_text = f"{tariff.name} - {tariff.price} ₽"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"tariff_{tariff_id}")])
    return InlineKeyboardMarkup(keyboard)

# Функция для добавления пользователя в канал
async def add_user_to_channel(user_id, context):
    try:
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            expire_date=None
        )
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя в канал: {e}")
        return None

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = load_users_db()
    
    # Проверяем, есть ли пользователь уже в базе и имеет ли доступ
    user_id_str = str(user.id)
    if user_id_str in db["users"] and db["users"][user_id_str].get("has_access", False):
        await update.message.reply_text(
            "У вас уже есть доступ к каналу. Если возникли проблемы, обратитесь к администратору."
        )
        return ConversationHandler.END
    
    # Отправка приветственного сообщения с информацией о канале
    await update.message.reply_text(
        CHANNEL_INFO,
        reply_markup=get_tariffs_keyboard()
    )
    
    return START

# Обработчик выбора тарифа
async def tariff_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Получаем ID выбранного тарифа
    tariff_id = query.data.split("_")[1]
    tariff = TARIFFS[tariff_id]
    
    # Сохраняем выбранный тариф в контексте пользователя
    context.user_data["selected_tariff"] = tariff_id
    
    # Генерируем ID транзакции
    tx_id = generate_transaction_id(query.from_user.id)
    context.user_data["transaction_id"] = tx_id
    
    # Сохраняем информацию о платеже в базе данных
    db = load_users_db()
    if "payments" not in db:
        db["payments"] = {}
    
    db["payments"][tx_id] = {
        "user_id": query.from_user.id,
        "tariff_id": tariff_id,
        "amount": tariff.price,
        "status": "pending",
        "timestamp": int(asyncio.get_event_loop().time())
    }
    save_users_db(db)
    
    # Отправляем инструкции по оплате
    payment_message = f"""
*Выбран тариф: {tariff.name}*
💰 Стоимость: {tariff.price} ₽
📋 Описание: {tariff.description}

Для оплаты переведите указанную сумму на карту:
*{PAYMENT_CARD}*
Держатель: {PAYMENT_HOLDER}

⚠️ *ВАЖНО!* В комментарии к платежу укажите код: `{tx_id}`

После оплаты нажмите кнопку "Я оплатил" ниже, либо просто подождите - система автоматически проверит ваш платеж в течение нескольких минут.
"""
    
    keyboard = [
        [InlineKeyboardButton("Я оплатил", callback_data=f"paid_{tx_id}")],
        [InlineKeyboardButton("Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=payment_message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return AWAITING_PAYMENT

# Обработчик сообщения об оплате
async def payment_notification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, tx_id = query.data.split("_", 1)
    
    if action == "cancel":
        await query.edit_message_text("Оплата отменена. Для возврата в главное меню нажмите /start")
        return ConversationHandler.END
    
    # Проверяем существование транзакции
    db = load_users_db()
    if tx_id not in db["payments"]:
        await query.edit_message_text("Ошибка: транзакция не найдена. Пожалуйста, начните заново с /start")
        return ConversationHandler.END
    
    payment_info = db["payments"][tx_id]
    tariff = TARIFFS[payment_info["tariff_id"]]
    
    # Начинаем проверку платежа
    await query.edit_message_text(
        f"Спасибо за оплату! Мы проверяем ваш платеж на сумму {tariff.price} ₽.\n"
        "Это может занять некоторое время (обычно до 5 минут).\n"
        "Вы получите уведомление, когда проверка будет завершена."
    )
    
    # Немедленно запускаем проверку платежа
    is_paid = await check_payment_status(tx_id)
    
    if is_paid:
        # Платеж найден, обновляем статус
        db["payments"][tx_id]["status"] = "confirmed"
        
        # Обновляем информацию о пользователе
        user_id = query.from_user.id
        if str(user_id) not in db["users"]:
            db["users"][str(user_id)] = {}
        
        db["users"][str(user_id)]["has_access"] = True
        db["users"][str(user_id)]["tariff_id"] = payment_info["tariff_id"]
        
        # Устанавливаем дату истечения доступа
        if tariff.duration_days > 0:
            expiry_time = int(time.time()) + (tariff.duration_days * 24 * 60 * 60)
            db["users"][str(user_id)]["access_expiry"] = expiry_time
        else:
            db["users"][str(user_id)]["access_expiry"] = None
        
        save_users_db(db)
        
        # Создаем ссылку-приглашение
        invite_link = await add_user_to_channel(user_id, context)
        
        if invite_link:
            # Отправляем сообщение об успешной оплате
            success_message = f"""
Ассаляму алейкум! 🎉

Ваша оплата успешно подтверждена!

✅ Тариф: {tariff.name}
✅ Доступ: {"Навсегда" if tariff.duration_days == 0 else f"На {tariff.duration_days} дней"}

Для входа в закрытый канал используйте эту ссылку:
{invite_link}

Джазакуму Ллаху хайран за доверие!
"""
            await context.bot.send_message(
                chat_id=user_id,
                text=success_message
            )
            
            # Уведомляем администратора
            admin_message = f"""
✅ Платеж подтвержден!
От: ID {user_id} (@{query.from_user.username or 'нет юзернейма'})
Тариф: {tariff.name}
Сумма: {tariff.price} ₽
Код транзакции: {tx_id}
"""
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message
            )
            
            return ConversationHandler.END
    else:
        # Платеж не найден, оставляем статус "pending"
        # Уведомляем администратора о запросе на проверку платежа
        admin_message = f"""
⏳ Запрос на проверку платежа!
От: ID {query.from_user.id} (@{query.from_user.username or 'нет юзернейма'})
Тариф: {tariff.name}
Сумма: {tariff.price} ₽
Код транзакции: {tx_id}

Проверьте поступление средств и подтвердите платеж.
"""
        keyboard = [
            [
                InlineKeyboardButton("Подтвердить", callback_data=f"confirm_{tx_id}"),
                InlineKeyboardButton("Отклонить", callback_data=f"reject_{tx_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору: {e}")
    
    return PAYMENT_PROCESSING

# Обработчик подтверждения платежа администратором
async def admin_payment_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Проверяем, что это администратор
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("У вас нет прав для выполнения этого действия.")
        return
    
    action, tx_id = query.data.split("_", 1)
    
    # Загружаем данные о платеже
    db = load_users_db()
    if tx_id not in db["payments"]:
        await query.edit_message_text("Ошибка: транзакция не найдена.")
        return
    
    payment_info = db["payments"][tx_id]
    user_id = payment_info["user_id"]
    tariff_id = payment_info["tariff_id"]
    tariff = TARIFFS[tariff_id]
    
    if action == "confirm":
        # Подтверждаем платеж
        db["payments"][tx_id]["status"] = "confirmed"
        
        # Добавляем или обновляем информацию о пользователе
        if str(user_id) not in db["users"]:
            db["users"][str(user_id)] = {}
        
        db["users"][str(user_id)]["has_access"] = True
        db["users"][str(user_id)]["tariff_id"] = tariff_id
        
        # Устанавливаем дату истечения доступа, если это не пожизненный доступ
        if tariff.duration_days > 0:
            import time
            expiry_time = int(time.time()) + (tariff.duration_days * 24 * 60 * 60)
            db["users"][str(user_id)]["access_expiry"] = expiry_time
        else:
            # Для пожизненного доступа устанавливаем очень далекую дату или null
            db["users"][str(user_id)]["access_expiry"] = None
        
        save_users_db(db)
        
        # Создаем ссылку-приглашение для пользователя
        invite_link = await add_user_to_channel(user_id, context)
        
        if invite_link:
            # Уведомляем пользователя об успешной оплате и отправляем ссылку
            success_message = f"""
Ассаляму алейкум! 🎉

Ваша оплата успешно подтверждена!

✅ Тариф: {tariff.name}
✅ Доступ: {"Навсегда" if tariff.duration_days == 0 else f"На {tariff.duration_days} дней"}

Для входа в закрытый канал используйте эту ссылку:
{invite_link}

Джазакуму Ллаху хайран за доверие!
"""
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=success_message
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
            
            await query.edit_message_text(f"Платеж подтвержден. Пользователь получил доступ к каналу.")
        else:
            await query.edit_message_text(
                "Платеж подтвержден, но возникла ошибка при создании ссылки-приглашения. "
                "Пожалуйста, добавьте пользователя вручную."
            )
    
    elif action == "reject":
        # Отклоняем платеж
        db["payments"][tx_id]["status"] = "rejected"
        save_users_db(db)
        
        # Уведомляем пользователя об отклонении платежа
        reject_message = """
К сожалению, ваш платеж не был подтвержден.

Возможные причины:
- Неверная сумма перевода
- Отсутствие кода транзакции в комментарии
- Технические проблемы с платежной системой

Пожалуйста, свяжитесь с администратором для уточнения деталей или попробуйте снова.
"""
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=reject_message
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
        
        await query.edit_message_text("Платеж отклонен. Пользователь уведомлен.")

# Функция для проверки прав администратора
def is_admin_filter(update: Update):
    return update.effective_user.id == ADMIN_ID

# Обработчик для команды администратора /stats
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_filter(update):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    
    db = load_users_db()
    
    # Подсчет статистики
    total_users = len(db.get("users", {}))
    active_users = sum(1 for user_data in db.get("users", {}).values() if user_data.get("has_access", False))
    
    # Подсчет пользователей по тарифам
    tariffs_stats = {}
    for tariff_id in TARIFFS:
        tariffs_stats[tariff_id] = sum(
            1 for user_data in db.get("users", {}).values() 
            if user_data.get("tariff_id") == tariff_id and user_data.get("has_access", False)
        )
    
    # Статистика платежей
    total_payments = len(db.get("payments", {}))
    confirmed_payments = sum(1 for payment in db.get("payments", {}).values() if payment.get("status") == "confirmed")
    pending_payments = sum(1 for payment in db.get("payments", {}).values() if payment.get("status") == "pending")
    rejected_payments = sum(1 for payment in db.get("payments", {}).values() if payment.get("status") == "rejected")
    
    # Расчет общей суммы подтвержденных платежей
    total_revenue = sum(
        payment.get("amount", 0) 
        for payment in db.get("payments", {}).values() 
        if payment.get("status") == "confirmed"
    )
    
    stats_message = f"""
📊 *Статистика канала*

👥 *Пользователи:*
- Всего пользователей: {total_users}
- Активных подписчиков: {active_users}

💰 *Тарифы:*
{chr(10).join(f"- {TARIFFS[tariff_id].name}: {count} подписчиков" for tariff_id, count in tariffs_stats.items())}

💳 *Платежи:*
- Всего платежей: {total_payments}
- Подтверждено: {confirmed_payments}
- В ожидании: {pending_payments}
- Отклонено: {rejected_payments}

📈 *Доход:*
- Общая сумма: {total_revenue} ₽
"""
    
    await update.message.reply_text(stats_message, parse_mode="Markdown")

# Обработчик для команды администратора /find_user
async def find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_filter(update):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите ID пользователя после команды. Например: /find_user 123456789")
        return
    
    user_id = context.args[0]
    db = load_users_db()
    
    if user_id not in db.get("users", {}):
        await update.message.reply_text(f"Пользователь с ID {user_id} не найден в базе данных.")
        return
    
    user_data = db["users"][user_id]
    tariff_id = user_data.get("tariff_id")
    tariff_name = TARIFFS[tariff_id].name if tariff_id in TARIFFS else "Неизвестный тариф"
    
    has_access = user_data.get("has_access", False)
    access_status = "Активен" if has_access else "Неактивен"
    
    expiry = user_data.get("access_expiry")
    if expiry:
        import datetime
        expiry_date = datetime.datetime.fromtimestamp(expiry).strftime("%d.%m.%Y %H:%M")
    else:
        expiry_date = "Бессрочно" if has_access else "Нет доступа"
    
    user_info = f"""
📋 *Информация о пользователе*

🆔 ID: {user_id}
📅 Тариф: {tariff_name}
🔑 Статус доступа: {access_status}
⏱ Срок действия: {expiry_date}
"""
    
    # Создаем клавиатуру для управления пользователем
    keyboard = []
    if has_access:
        keyboard.append([InlineKeyboardButton("Отключить доступ", callback_data=f"revoke_{user_id}")])
    else:
        keyboard.append([InlineKeyboardButton("Включить доступ",
