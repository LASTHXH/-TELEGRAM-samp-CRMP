import logging
import sys
import time
import random
import string
import asyncio
import hashlib

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import mysql.connector
from mysql.connector import Error

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

TOKEN = 'Токен своего бота' 

DB = {
    'host': 'localhost',# хост базы данных
    'database': 'database', # название базы данных
    'user': 'root',# пользователь от базы данных
    'password': 'password' # пароль от базы данных
}

code_time = 120  # скоко код будет работать


def dbconnect():
    """Создаёт соединение с базой данных."""
    try:
        conn = mysql.connector.connect(**DB)
        if conn.is_connected():
            log.info("Соединение с БД установлено")
            return conn
    except Error as err:
        log.error(f"Ошибка подключения к БД: {err}")
    return None


def codegenerate():
    """Генерирует шестизначный цифровой код."""
    return ''.join(random.choices(string.digits, k=6))


def temppass():
    """Генерирует временный пароль длиной 8-12 символов."""
    length = random.randint(8, 12)
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgid = update.effective_user.id
    log.info(f"Пользователь {tgid} запустил бота")

    conn = dbconnect()
    if conn is None:
        await update.message.reply_text("Не удалось соединиться с базой данных. Попробуйте позже.")
        return

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT tb.is_bound, a.name, a.id
            FROM telegram_bindings tb
            LEFT JOIN accounts a ON tb.user_id = a.id
            WHERE tb.telegram_id = %s
            """,
            (tgid,)
        )
        row = cur.fetchone()

        if row and row.get('is_bound') and row.get('name'):
            buttons = [
                [InlineKeyboardButton("Проверить привязку", callback_data='check')],
                [InlineKeyboardButton("Сбросить пароль", callback_data='reset')],
            ]
            await update.message.reply_text(
                f"Привет! Аккаунт {row['name']}[{row['id']}] уже привязан.\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            buttons = [
                [InlineKeyboardButton("Получить код", callback_data='code')],
                [InlineKeyboardButton("Проверить привязку", callback_data='check')],
            ]
            await update.message.reply_text(
                'Привет! Аккаунт ещё не привязан. Выберите действие:',
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    except Error as err:
        log.error(f"Ошибка при выполнении запроса: {err}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
    finally:
        if conn.is_connected():
            cur.close()
            conn.close()


async def getcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    tgid = update.effective_user.id

    log.info(f"Выдаю код для {tgid}")

    conn = dbconnect()
    if conn is None:
        await msg.reply_text("Не удалось соединиться с базой данных.")
        return

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT binding_code, code_expires, is_bound, user_id
            FROM telegram_bindings
            WHERE telegram_id = %s AND is_bound = 1
            """,
            (tgid,),
        )
        bind = cur.fetchone()
        if bind and bind['is_bound'] and bind['user_id']:
            await msg.reply_text("Этот Telegram уже привязан!")
            return

        cur.execute(
            """
            SELECT binding_code, code_expires
            FROM telegram_bindings
            WHERE telegram_id = %s AND is_bound = 0
            ORDER BY code_expires DESC LIMIT 1
            """,
            (tgid,),
        )
        active = cur.fetchone()

        now = int(time.time())
        if active and active['code_expires'] and active['code_expires'].timestamp() > now:
            left = int(active['code_expires'].timestamp() - now)
            await msg.reply_text(
                f"Ваш текущий код: {active['binding_code']}\nДействителен ещё {left} секунд"
            )
            return

        code = codegenerate()
        expires = now + code_time

        cur.execute("DELETE FROM telegram_bindings WHERE telegram_id = %s AND is_bound = 0", (tgid,))
        cur.execute(
            """
            INSERT INTO telegram_bindings (telegram_id, binding_code, code_expires, is_bound)
            VALUES (%s, %s, FROM_UNIXTIME(%s), 0)
            """,
            (tgid, code, expires),
        )
        conn.commit()

        await msg.reply_text(
            f"Ваш код: {code}\nОн действителен {code_time} секунд\nВведите его в игре для завершения привязки."
        )
    except Error as err:
        log.error(f"Ошибка при работе с базой: {err}")
        await msg.reply_text("Произошла ошибка. Попробуйте позже.")
    finally:
        if conn.is_connected():
            cur.close()
            conn.close()


async def checkbinding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    tgid = update.effective_user.id
    log.info(f"Проверка привязки для {tgid}")

    conn = dbconnect()
    if conn is None:
        await msg.reply_text("Не удалось соединиться с базой данных.")
        return

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT tb.is_bound, tb.user_id, a.name, a.id
            FROM telegram_bindings tb
            LEFT JOIN accounts a ON tb.user_id = a.id
            WHERE tb.telegram_id = %s
            """,
            (tgid,),
        )
        row = cur.fetchone()

        if row and row['is_bound'] and row['user_id'] and row['name']:
            buttons = [[InlineKeyboardButton("Сбросить пароль", callback_data='reset')]]
            await msg.reply_text(
                f"Аккаунт {row['name']}[{row['id']}] привязан.",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            buttons = [[InlineKeyboardButton("Получить код", callback_data='code')]]
            await msg.reply_text(
                "Аккаунт не привязан. Получите код:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    except Error as err:
        log.error(f"Ошибка при запросе: {err}")
        await msg.reply_text("Произошла ошибка. Попробуйте позже.")
    finally:
        if conn.is_connected():
            cur.close()
            conn.close()


async def resetpass(tgid: int):
    """Сбрасывает пароль и возвращает новый пароль или None."""
    log.info(f"Сброс пароля для {tgid}")
    conn = dbconnect()
    if conn is None:
        return None

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT user_id FROM telegram_bindings WHERE telegram_id = %s AND is_bound = 1",
            (tgid,),
        )
        row = cur.fetchone()
        if not row or row['user_id'] is None:
            return None

        uid = row['user_id']
        password = temppass()
        salt = ''.join(chr(random.randint(47, 125)) for _ in range(10))
        hashed = hashlib.sha256((password + salt).encode()).hexdigest().upper()

        cur.execute(
            "UPDATE accounts SET password = %s, salt = %s WHERE id = %s",
            (hashed, salt, uid),
        )
        conn.commit()
        return password
    except Error as err:
        log.error(f"Ошибка при сбросе пароля: {err}")
        return None
    finally:
        if conn.is_connected():
            cur.close()
            conn.close()


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'code':
        await getcode(update, context)
    elif data == 'check':
        await checkbinding(update, context)
    elif data == 'reset':
        tgid = query.from_user.id
        password = await resetpass(tgid)
        if password:
            await query.message.reply_text(
                f"Ваш новый пароль: {password}\nПожалуйста, смените его после входа."
            )
        else:
            await query.message.reply_text("Не удалось сбросить пароль.")


async def notify(context: ContextTypes.DEFAULT_TYPE):
    log.info("Проверка уведомлений")
    conn = dbconnect()
    if conn is None:
        return

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM telegram_notifications WHERE is_sent = 0")
        notes = cur.fetchall()

        for note in notes:
            try:
                await context.bot.send_message(chat_id=note['telegram_id'], text=note['message'])
                cur.execute(
                    "UPDATE telegram_notifications SET is_sent = 1 WHERE id = %s",
                    (note['id'],),
                )
                conn.commit()
            except Exception as err:
                log.error(f"Не удалось отправить уведомление: {err}")
    except Error as err:
        log.error(f"Ошибка при работе с уведомлениями: {err}")
    finally:
        if conn.is_connected():
            cur.close()
            conn.close()


async def startbot():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getcode", getcode))
    app.add_handler(CommandHandler("check", checkbinding))
    app.add_handler(CallbackQueryHandler(button))

    jobs = app.job_queue
    jobs.run_repeating(notify, interval=60)

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    return app


async def stopbot(app):
    await app.stop()
    await app.shutdown()


def main():
    loop = asyncio.get_event_loop()
    app = None
    try:
        log.info("Запуск бота")
        app = loop.run_until_complete(startbot())
        log.info(f"Бот запущен: {app.bot.username}")
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("Получен сигнал остановки, завершаю…")
    finally:
        if app:
            loop.run_until_complete(stopbot(app))
        loop.close()
        log.info("Бот остановлен")


if __name__ == "__main__":
    main()