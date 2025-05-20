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
        price=10000, 
        description="Пожизненный доступ к каналу + все обновления + персональная консультация", 
        duration_days=0  # 0 означает бессрочно
    ),
}

# Настройки канала и бота
CHANNEL_ID = -1002556601836  # Замените на ID вашего канала
BOT_TOKEN = 7678032381:AAG7gs3yTU8bfOrxx3ItNNbZEX-IruSaEGI  # Получите у @BotFather
ADMIN_ID = 7281866890  # Замените на ваш Telegram ID

# Файл для хранения данных о пользователях и платежах
USERS_DB_FILE = "users_db.json"

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
    import time
    return f"tx_{user_id}_{int(time.time())}"

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
*5555 5555 5555 5555*
Держатель: Ваше Имя

⚠️ *ВАЖНО!* В комментарии к платежу укажите код: `{tx_id}`

После оплаты нажмите кнопку "Я оплатил" ниже.
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
    
    # Уведомляем пользователя о проверке платежа
    await query.edit_message_text(
        f"Спасибо за оплату! Мы проверяем ваш платеж на сумму {tariff.price} ₽.\n"
        "Это может занять некоторое время (обычно до 15 минут).\n"
        "Вы получите уведомление, когда проверка будет завершена."
    )
    
    # Уведомляем администратора о новом платеже
    admin_message = f"""
Новый платеж!
От: {query.from_user.first_name} {query.from_user.last_name or ''} (@{query.from_user.username or 'нет юзернейма'})
ID пользователя: {query.from_user.id}
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
        keyboard.append([InlineKeyboardButton("Включить доступ", callback_data=f"grant_{user_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(user_info, reply_markup=reply_markup, parse_mode="Markdown")

# Обработчик для действий с пользователем (включение/отключение доступа)
async def user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("У вас нет прав для выполнения этого действия.")
        return
    
    action, user_id = query.data.split("_", 1)
    db = load_users_db()
    
    if user_id not in db.get("users", {}):
        await query.edit_message_text(f"Пользователь с ID {user_id} не найден в базе данных.")
        return
    
    if action == "revoke":
        # Отключаем доступ
        db["users"][user_id]["has_access"] = False
        save_users_db(db)
        
        await query.edit_message_text(f"Доступ для пользователя с ID {user_id} отключен.")
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="Ваш доступ к закрытому каналу был отключен администратором."
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
    
    elif action == "grant":
        # Включаем доступ
        db["users"][user_id]["has_access"] = True
        save_users_db(db)
        
        # Создаем ссылку-приглашение
        invite_link = await add_user_to_channel(int(user_id), context)
        
        if invite_link:
            await query.edit_message_text(f"Доступ для пользователя с ID {user_id} включен.")
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"""
Ассаляму алейкум! 🎉

Ваш доступ к закрытому каналу был активирован администратором.

Для входа используйте эту ссылку:
{invite_link}

Джазакуму Ллаху хайран за доверие!
"""
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
        else:
            await query.edit_message_text(
                f"Доступ для пользователя с ID {user_id} включен, но возникла ошибка при создании ссылки-приглашения."
            )

# Обработчик для проверки истечения срока подписок (запускается периодически)
async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE):
    db = load_users_db()
    current_time = int(asyncio.get_event_loop().time())
    
    for user_id, user_data in list(db.get("users", {}).items()):
        # Проверяем, есть ли у пользователя активный доступ и срок его действия
        if user_data.get("has_access", False) and user_data.get("access_expiry"):
            # Если срок действия истек
            if user_data["access_expiry"] < current_time:
                # Отключаем доступ
                db["users"][user_id]["has_access"] = False
                
                # Уведомляем пользователя
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text="""
Ассаляму алейкум!

Срок действия вашей подписки на закрытый канал истек.

Для продления доступа, пожалуйста, выберите новый тариф через команду /start.

Джазакуму Ллаху хайран!
"""
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
    
    # Сохраняем обновленную базу данных
    save_users_db(db)

# Основная функция для запуска бота
def main():
    # Создаем экземпляр приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем ConversationHandler для обработки процесса оплаты
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START: [
                CallbackQueryHandler(tariff_selection, pattern=r"^tariff_")
            ],
            AWAITING_PAYMENT: [
                CallbackQueryHandler(payment_notification, pattern=r"^paid_|^cancel$")
            ],
            PAYMENT_PROCESSING: [
                # Пустое состояние, т.к. дальнейшая обработка идет через админа
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Добавляем обработчики команд и callback-запросов
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(admin_payment_processing, pattern=r"^confirm_|^reject_"))
    application.add_handler(CallbackQueryHandler(user_management, pattern=r"^revoke_|^grant_"))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("find_user", find_user))
    
    # Добавляем задачу для периодической проверки подписок (каждые 12 часов)
    application.job_queue.run_repeating(check_subscriptions, interval=43200)
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()
