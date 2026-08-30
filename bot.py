import sqlite3
import requests
import datetime
from pytz import timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import asyncio
from flask import Flask
from threading import Thread

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8951290780:AAEE1VDMjka29-WK1THxFjX_kvY1j-bkW4Y"
ADMIN_ID = 8688778044
COLLEGE_NAME = "NK College"
TIMEZONE = timezone('Europe/Moscow')
ANON_CHANNEL_ID = -1004489728672
ANON_CHANNEL_LINK = "https://t.me/+y8N08aQQpPhjZjcy"
LOG_CHANNEL_ID = -1004354073962

GROUPS = [
    "1Ю1/925o", "1Ю2/925o", "1Б1/925o", "1БД1/925o", "1Л1/925o", "1П1/925o",
    "2Н1/924o", "2Б1/924o", "1Б3/1125o", "2Ю2/924о", "1Ю3/1125о", "2Л1/924o",
    "1Л3/1125о", "2П1/924о", "2П2/924o", "1П3/1125o", "3П1/923o", "2П3/923o",
    "2П3/1124o", "3Н1/923o", "3Н2/923o", "2н3/1124o", "3Б1/923o", "2Б3/1124o",
    "3БД1/923o", "2БД3/1124o", "3Ю1/923o", "3Ю2/923o", "2Ю3/1124o", "3Л1/923o",
    "2Л3/1124o", "4Н1/922o", "3Н3/1123o"
]

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        first_name TEXT, 
        username TEXT, 
        group_name TEXT, 
        full_name TEXT DEFAULT NULL, 
        phone TEXT DEFAULT NULL, 
        is_verified INTEGER DEFAULT 0,
        last_active TEXT DEFAULT NULL
    )''')
    c.execute('CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, day TEXT, time TEXT, subject TEXT, teacher TEXT, room TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS homework (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, subject TEXT, task TEXT, deadline TEXT, created_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS grades (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, grade INTEGER, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS teachers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, subject TEXT, cabinet TEXT, email TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS exams (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, subject TEXT, date TEXT, time TEXT, room TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, question TEXT, is_anon INTEGER, date TEXT, status TEXT DEFAULT "new")')
    c.execute('CREATE TABLE IF NOT EXISTS conspekts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, title TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS polls (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, options TEXT, creator_id INTEGER, created_at TEXT, is_active INTEGER DEFAULT 1)')
    c.execute('CREATE TABLE IF NOT EXISTS poll_votes (id INTEGER PRIMARY KEY AUTOINCREMENT, poll_id INTEGER, user_id INTEGER, option_index INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS anon_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, first_name TEXT, username TEXT, group_name TEXT, message TEXT, recipient_type TEXT DEFAULT "all", status TEXT DEFAULT "pending", created_at TEXT, moderated_at TEXT, channel_message_id INTEGER)')
    conn.commit()
    conn.close()

def get_user_group(user_id):
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT group_name FROM users WHERE user_id = ? ORDER BY user_id DESC LIMIT 1', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] else None

def get_day_name(day_num=None):
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    if day_num is None:
        day_num = datetime.datetime.now(TIMEZONE).weekday()
    return days[day_num]

def calculate_gpa(user_id):
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT AVG(grade) FROM grades WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0

def get_all_users():
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT user_id, first_name, group_name FROM users')
    users = c.fetchall()
    conn.close()
    return users

def get_users_by_group(group_name):
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT user_id, first_name FROM users WHERE group_name = ?', (group_name,))
    users = c.fetchall()
    conn.close()
    return users

# ==================== КЛАВИАТУРЫ ====================
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Расписание на день", callback_data='schedule'),
         InlineKeyboardButton("📅 Расписание на неделю", callback_data='schedule_week')],
        [InlineKeyboardButton("📊 Оценки", callback_data='grades'),
         InlineKeyboardButton("🧮 GPA", callback_data='gpa')],
        [InlineKeyboardButton("👨‍🏫 Преподаватели", callback_data='teachers'),
         InlineKeyboardButton("🎓 Экзамены", callback_data='exams')],
        [InlineKeyboardButton(" Новости", callback_data='news'),
         InlineKeyboardButton("🌤️ Погода", callback_data='weather')],
        [InlineKeyboardButton("📈 Посещаемость", callback_data='attendance'),
         InlineKeyboardButton("🗺️ Аудитории", callback_data='rooms')],
        [InlineKeyboardButton("💬 Анонимный чат", callback_data='anon_chat'),
         InlineKeyboardButton("📢 Канал анонимок", url=ANON_CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Вопрос админу", callback_data='question'),
         InlineKeyboardButton("📍 Контакты", callback_data='contacts_info')],
        [InlineKeyboardButton("💼 Практика", callback_data='practice_info'),
         InlineKeyboardButton("🆘 Помощь", callback_data='help')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button():
    keyboard = [[InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]]
    return InlineKeyboardMarkup(keyboard)

def groups_keyboard():
    keyboard = []
    row = []
    for group in GROUPS:
        row.append(InlineKeyboardButton(group, callback_data=f'setgroup_{group}'))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM anon_messages WHERE status = "pending"')
    pending_count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM questions WHERE status = "new"')
    questions_count = c.fetchone()[0]
    conn.close()
    moderation_text = f"📥 Модерация ({pending_count})" if pending_count > 0 else " Модерация"
    questions_text = f"❓ Вопросы ({questions_count})" if questions_count > 0 else "❓ Вопросы"
    keyboard = [
        [InlineKeyboardButton(moderation_text, callback_data='admin_moderation')],
        [InlineKeyboardButton(questions_text, callback_data='admin_questions')],
        [InlineKeyboardButton(" История модерации", callback_data='admin_moderation_history')],
        [InlineKeyboardButton(" Статистика бота", callback_data='admin_stats')],
        [InlineKeyboardButton(" Справка по командам", callback_data='admin_help')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== КОМАНДА /start ====================
async def start(update: Update, context):
    user = update.effective_user
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT is_verified FROM users WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] == 0:
        context.user_data['reg_step'] = 'waiting_full_name'
        text = (
            f"👋 Привет, {user.first_name}!\n\n"
            f"Для доступа к боту {COLLEGE_NAME} нужна быстрая регистрация.\n\n"
            f"Шаг 1: Напиши свои **ФИО** (полностью, как в журнале)."
        )
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    text = f"👋 Привет, {user.first_name}!\n\nДобро пожаловать в бота {COLLEGE_NAME}!"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

# ==================== АДМИН-КОМАНДА ====================
async def admin_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен!")
        return
    text = "‍💼 Админ-панель\n\nВыбери раздел:"
    await update.message.reply_text(text, reply_markup=admin_panel_keyboard())

# ==================== BROADCAST ====================
async def broadcast_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(" Только для админа!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Формат: ответь на сообщение командой /broadcast")
        return
    reply_msg = update.message.reply_to_message
    users = get_all_users()
    if not users:
        await update.message.reply_text("⚠️ В базе нет пользователей!")
        return
    await update.message.reply_text(f"📨 Начинаю рассылку {len(users)} пользователям...")
    success = 0
    failed = 0
    for user_data in users:
        user_id = user_data[0]
        user_name = user_data[1]
        try:
            if reply_msg.photo:
                photo_file_id = reply_msg.photo[-1].file_id
                caption = reply_msg.caption if reply_msg.caption else ""
                await context.bot.send_photo(chat_id=user_id, photo=photo_file_id, caption=caption)
            elif reply_msg.video:
                video_file_id = reply_msg.video.file_id
                caption = reply_msg.caption if reply_msg.caption else ""
                await context.bot.send_video(chat_id=user_id, video=video_file_id, caption=caption)
            elif reply_msg.document:
                doc_file_id = reply_msg.document.file_id
                caption = reply_msg.caption if reply_msg.caption else ""
                await context.bot.send_document(chat_id=user_id, document=doc_file_id, caption=caption)
            elif reply_msg.audio:
                audio_file_id = reply_msg.audio.file_id
                caption = reply_msg.caption if reply_msg.caption else ""
                await context.bot.send_audio(chat_id=user_id, audio=audio_file_id, caption=caption)
            elif reply_msg.voice:
                voice_file_id = reply_msg.voice.file_id
                await context.bot.send_voice(chat_id=user_id, voice=voice_file_id)
            elif reply_msg.animation:
                animation_file_id = reply_msg.animation.file_id
                caption = reply_msg.caption if reply_msg.caption else ""
                await context.bot.send_animation(chat_id=user_id, animation=animation_file_id, caption=caption)
            elif reply_msg.text:
                await context.bot.send_message(chat_id=user_id, text=reply_msg.text)
            else:
                await context.bot.send_message(chat_id=user_id, text="📢 Объявление от администрации")
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            print(f"❌ Ошибка отправки пользователю {user_id} ({user_name}): {e}")
    await update.message.reply_text(f"✅ Рассылка завершена!\n\n📨 Отправлено: {success}\n Ошибок: {failed}\n👥 Всего пользователей: {len(users)}")

# ==================== ОТМЕНА BROADCAST ====================
async def broadcast_cancel_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("⚠️ В базе нет пользователей!")
        return
    await update.message.reply_text(f"📨 Начинаю отмену рассылки {len(users)} пользователям...")
    success = 0
    failed = 0
    cancel_text = "⚠️ **ПРЕДЫДУЩЕЕ ОБЪЯВЛЕНИЕ ОТМЕНЕНО**\n\nПросим игнорировать предыдущее сообщение.\nПриносим извинения за неудобства."
    for user_data in users:
        user_id = user_data[0]
        try:
            await context.bot.send_message(chat_id=user_id, text=cancel_text, parse_mode='Markdown')
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            print(f"❌ Ошибка отмены пользователю {user_id}: {e}")
    await update.message.reply_text(f"✅ Отмена рассылки завершена!\n\n📨 Отправлено: {success}\n❌ Ошибок: {failed}\n👥 Всего пользователей: {len(users)}")

# ==================== СОЗДАНИЕ ГОЛОСОВАНИЯ ====================
async def create_poll_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    if len(context.args) < 3:
        await update.message.reply_text("⚠️ Формат: /create_poll Вопрос Вариант1 Вариант2 ...")
        return
    question = context.args[0]
    options = context.args[1:]
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('INSERT INTO polls (question, options, creator_id, created_at) VALUES (?, ?, ?, ?)',
              (question, '|'.join(options), update.effective_user.id, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
    poll_id = c.lastrowid
    conn.commit()
    conn.close()
    keyboard = []
    for i, option in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"🔹 {option.replace('_', ' ')}", callback_data=f'vote_{poll_id}_{i}')])
    keyboard.append([InlineKeyboardButton("📊 Посмотреть результаты", callback_data=f'results_{poll_id}')])
    keyboard.append([InlineKeyboardButton("📢 Отправить всем студентам", callback_data=f'publish_poll_{poll_id}')])
    text = f"️ Новое голосование!\n\n❓ {question.replace('_', ' ')}\n\nВыбери вариант:"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== АДМИН-КОМАНДЫ (Расписание и Домашка) ====================
async def add_schedule_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    if len(context.args) == 5:
        group_name = "ОБЩЕЕ"
        day_short, time, subject, teacher, room = context.args
    elif len(context.args) == 6:
        group_name = context.args[0]
        day_short, time, subject, teacher, room = context.args[1], context.args[2], context.args[3], context.args[4], context.args[5]
    else:
        await update.message.reply_text("⚠️ Формат: /add_schedule [ГРУППА] ДЕНЬ ВРЕМЯ ПРЕДМЕТ ПРЕПОД АУД")
        return
    valid_days = {'ПН': 'Понедельник', 'ВТ': 'Вторник', 'СР': 'Среда', 'ЧТ': 'Четверг', 'ПТ': 'Пятница', 'СБ': 'Суббота', 'ВС': 'Воскресенье'}
    if day_short.upper() not in valid_days:
        await update.message.reply_text(f"⚠️ Неверный день! Используй: {', '.join(valid_days.keys())}")
        return
    if len(time) != 5 or time[2] != ':':
        await update.message.reply_text("⚠️ Неверное время! Формат: 09:00")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('INSERT INTO schedule (group_name, day, time, subject, teacher, room) VALUES (?, ?, ?, ?, ?, ?)',
              (group_name, valid_days[day_short.upper()], time, subject, teacher, room))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Пара добавлена! ID: {sid}\nДля удаления: /delete_schedule {sid}")

async def view_schedule_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT id, group_name, day, time, subject, teacher, room FROM schedule ORDER BY group_name, CASE day WHEN "Понедельник" THEN 1 WHEN "Вторник" THEN 2 WHEN "Среда" THEN 3 WHEN "Четверг" THEN 4 WHEN "Пятница" THEN 5 WHEN "Суббота" THEN 6 WHEN "Воскресенье" THEN 7 END, time')
    schedule = c.fetchall()
    conn.close()
    if not schedule:
        await update.message.reply_text("📅 Расписание пустое!")
        return
    text = "📅 ВСЕ РАСПИСАНИЕ:\n\n"
    cur_group, cur_day = None, None
    for sid, gn, day, time, subj, teach, room in schedule:
        if gn != cur_group: text += f"\n👥 Группа: {gn}\n"; cur_group = gn; cur_day = None
        if day != cur_day: text += f"\n📌 {day}:\n"; cur_day = day
        text += f"  ID {sid}: {time} - {subj} ({teach}, ауд. {room})\n"
    await update.message.reply_text(text + "\n💡 Удалить: /delete_schedule [ID]")

async def delete_schedule_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if not context.args: return await update.message.reply_text("⚠️ Укажи ID!")
    try: sid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ ID должен быть числом!")
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT group_name, day, time, subject FROM schedule WHERE id = ?', (sid,))
    res = c.fetchone()
    if not res: conn.close(); return await update.message.reply_text("⚠️ Не найдено!")
    c.execute('DELETE FROM schedule WHERE id = ?', (sid,))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Удалено: {res[0]} | {res[1]} {res[2]} - {res[3]}")

async def add_homework_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if len(context.args) < 3: return await update.message.reply_text("⚠️ Формат: /add_homework ГРУППА ПРЕДМЕТ ЗАДАНИЕ [До дедлайн]")
    group_name, subject = context.args[0], context.args[1]
    task = ' '.join(context.args[2:])
    deadline = "Не указан"
    parts = task.split()
    if len(parts) > 1 and parts[-2].lower() == 'до':
        deadline = parts[-1]
        task = ' '.join(parts[:-2])
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('INSERT INTO homework (group_name, subject, task, deadline, created_at) VALUES (?, ?, ?, ?, ?)',
              (group_name, subject, task, deadline, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
    hid = c.lastrowid
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Домашка добавлена! ID: {hid}\nУдалить: /delete_homework {hid}")

async def view_homework_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT id, group_name, subject, task, deadline FROM homework ORDER BY group_name, created_at DESC')
    hw = c.fetchall(); conn.close()
    if not hw: return await update.message.reply_text("📝 Домашек нет!")
    text = "📝 ВСЕ ДОМАШКИ:\n\n"
    cur_group = None
    for hid, gn, subj, task, dead in hw:
        if gn != cur_group: text += f"\n👥 {gn}\n"; cur_group = gn
        text += f"  ID {hid}: {subj} - {task} (⏰ {dead})\n"
    await update.message.reply_text(text + "\n💡 Удалить: /delete_homework [ID]")

async def delete_homework_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if not context.args: return await update.message.reply_text("⚠️ Укажи ID!")
    try: hid = int(context.args[0])
    except: return await update.message.reply_text("⚠️ ID должен быть числом!")
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT group_name, subject, task FROM homework WHERE id = ?', (hid,))
    res = c.fetchone()
    if not res: conn.close(); return await update.message.reply_text("️ Не найдено!")
    c.execute('DELETE FROM homework WHERE id = ?', (hid,))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Удалено: {res[0]} | {res[1]}: {res[2]}")

# ==================== ФУНКЦИЯ ПУБЛИКАЦИИ В КАНАЛ ====================
async def publish_to_channel(context, anon_id):
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT group_name, message, recipient_type FROM anon_messages WHERE id = ?', (anon_id,))
    anon = c.fetchone()
    conn.close()
    if not anon:
        return False, "❌ Сообщение не найдено"
    group_name, message_text, recipient_type = anon
    channel_text = f"💬 Анонимное сообщение\n\n{message_text}\n\n {datetime.datetime.now(TIMEZONE).strftime('%H:%M %d.%m.%Y')}"
    try:
        msg = await context.bot.send_message(chat_id=ANON_CHANNEL_ID, text=channel_text)
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('UPDATE anon_messages SET channel_message_id = ? WHERE id = ?', (msg.message_id, anon_id))
        conn.commit()
        conn.close()
        return True, f"✅ Опубликовано в канале!"
    except Exception as e:
        return False, f"❌ Ошибка публикации: {e}"

# ==================== ОБРАБОТЧИК КНОПОК ====================
async def button_handler(update: Update, context):
    query = update.callback_query
    data = query.data

    if data == 'back_to_menu':
        await query.answer()
        
        if context.user_data.get('reg_step'):
            context.user_data.clear()
            await query.edit_message_text(
                "❌ Регистрация отменена.\n\n"
                "Чтобы начать регистрацию заново, пожалуйста, напиши команду /start"
            )
            return
            
        await query.edit_message_text("👇 Выбери действие:", reply_markup=main_menu_keyboard())
        return

    if data.startswith('setgroup_'):
        await query.answer()
        group_name = data.replace('setgroup_', '')

        if context.user_data.get('reg_step') == 'waiting_group':
            context.user_data['reg_group'] = group_name
            context.user_data['reg_step'] = 'waiting_phone'

            keyboard = [[KeyboardButton("📱 Поделиться номером телефона", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "✅ Группа выбрана!\n\nШаг 3 (последний): Нажми на кнопку ниже, чтобы подтвердить свой номер телефона.",
                reply_markup=reply_markup
            )
            return

        user_id = query.from_user.id
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('UPDATE users SET group_name = ? WHERE user_id = ?', (group_name, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ Группа установлена: {group_name}", reply_markup=main_menu_keyboard())
        return

    elif data == 'schedule':
        await query.answer()
        group = get_user_group(query.from_user.id)
        if not group: text = "⚠️ Сначала укажи группу в Настройках!"
        else:
            conn = sqlite3.connect('college_bot.db')
            c = conn.cursor()
            c.execute('SELECT time, subject, teacher, room FROM schedule WHERE (group_name = ? OR group_name = "ОБЩЕЕ") AND day = ? ORDER BY time', (group, get_day_name()))
            schedule = c.fetchall(); conn.close()
            if not schedule: text = f"📅 На сегодня ({get_day_name()}) пар нет! 🎉"
            else:
                text = f"📅 Расписание на {get_day_name()}\n {group}\n\n"
                for i, (time, subj, teach, room) in enumerate(schedule, 1):
                    text += f"{i}. {time} - {subj}\n   👨🏫 {teach} | 🚪 {room}\n"
        await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data == 'schedule_week':
        await query.answer()
        group = get_user_group(query.from_user.id)
        if not group: text = "️ Сначала укажи группу в Настройках!"
        else:
            conn = sqlite3.connect('college_bot.db')
            c = conn.cursor()
            c.execute('SELECT day, time, subject, teacher, room FROM schedule WHERE (group_name = ? OR group_name = "ОБЩЕЕ") ORDER BY CASE day WHEN "Понедельник" THEN 1 WHEN "Вторник" THEN 2 WHEN "Среда" THEN 3 WHEN "Четверг" THEN 4 WHEN "Пятница" THEN 5 WHEN "Суббота" THEN 6 WHEN "Воскресенье" THEN 7 END, time', (group,))
            schedule = c.fetchall(); conn.close()
            if not schedule: text = f"📅 Расписание для {group} пока не добавлено."
            else:
                text = f"📅 Расписание на неделю\n {group}\n\n"
                cur_day = None
                for day, time, subj, teach, room in schedule:
                    if day != cur_day: text += f"\n📌 {day}:\n"; cur_day = day
                    text += f"  • {time} - {subj} ({teach}, ауд. {room})\n"
        await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data == 'homework':
        await query.answer()
        group = get_user_group(query.from_user.id)
        if not group: text = "⚠️ Сначала укажи группу в Настройках!"
        else:
            conn = sqlite3.connect('college_bot.db')
            c = conn.cursor()
            c.execute('SELECT subject, task, deadline FROM homework WHERE (group_name = ? OR group_name = "ОБЩЕЕ") ORDER BY created_at DESC', (group,))
            hw = c.fetchall(); conn.close()
            if not hw: text = f"📝 Домашних заданий для {group} пока нет!"
            else:
                text = f"📝 Домашние задания\n {group}\n\n"
                for subj, task, dead in hw:
                    text += f"📚 {subj}\n   📝 {task}\n   ⏰ {dead}\n\n"
        await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data == 'anon_chat':
        await query.answer()
        group = get_user_group(query.from_user.id)
        if not group:
            text = "⚠️ Сначала укажи свою группу в Настройках!\n\nБез группы анонимный чат не работает."
            await query.edit_message_text(text, reply_markup=back_button())
        else:
            context.user_data['waiting_for_anon'] = True
            context.user_data['anon_recipient'] = 'all'
            text = (
                f"💬 Анонимный чат\n\n"
                f" Хочешь почитать, что пишут другие? Заходи в наш канал:\n"
                f" {ANON_CHANNEL_LINK}\n\n"
                f"⚠️ ПРАВИЛА:\n"
                f"• Только для учебы и конструктивных вопросов\n"
                f"• За оскорбления, буллинг и спам — бан\n"
                f"• Все сообщения проходят модерацию администратором\n\n"
                f"Напиши своё сообщение следующим текстом.\n"
                f"После одобрения админом оно будет анонимно отправлено всем студентам колледжа.\n\n"
                f"◀️ Чтобы отменить, нажми 'Назад'."
            )
            await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data.startswith('approve_anon_'):
        if query.from_user.id != ADMIN_ID:
            await query.answer(" Только для админа!", show_alert=True)
            return
        await query.answer()
        anon_id = int(data.split('_')[2])
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('UPDATE anon_messages SET status = "approved", moderated_at = ? WHERE id = ?',
                  (datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M'), anon_id))
        conn.commit()
        conn.close()
        success, result_msg = await publish_to_channel(context, anon_id)
        await query.edit_message_text(f"{result_msg}\n\nID сообщения: {anon_id}", reply_markup=back_button())
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM anon_messages WHERE id = ?', (anon_id,))
        anon = c.fetchone()
        conn.close()
        if anon:
            try:
                await context.bot.send_message(chat_id=anon[0], text="✅ Твоё анонимное сообщение одобрено и опубликовано в канале!")
            except:
                pass
        return

    elif data.startswith('reject_anon_'):
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Только для админа!", show_alert=True)
            return
        await query.answer()
        anon_id = int(data.split('_')[2])
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('UPDATE anon_messages SET status = "rejected", moderated_at = ? WHERE id = ?',
                  (datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M'), anon_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"❌ Сообщение ID {anon_id} отклонено.", reply_markup=back_button())
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM anon_messages WHERE id = ?', (anon_id,))
        anon = c.fetchone()
        conn.close()
        if anon:
            try:
                await context.bot.send_message(chat_id=anon[0], text="❌ Твоё анонимное сообщение отклонено администратором.")
            except:
                pass
        return

    elif data == 'admin':
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Доступ запрещен!", show_alert=True)
            return
        await query.answer()
        text = "👨‍💼 Админ-панель\n\nВыбери раздел:"
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data == 'admin_moderation':
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Доступ запрещен!", show_alert=True)
            return
        await query.answer()
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT id, first_name, username, group_name, message, recipient_type, created_at FROM anon_messages WHERE status = "pending" ORDER BY created_at DESC')
        pending = c.fetchall()
        conn.close()
        if not pending:
            text = "📥 Модерация\n\n✅ Нет сообщений на рассмотрении!"
            await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
            return
        text = f" Модерация\n\n🔴 Сообщений на рассмотрении: {len(pending)}\n\n"
        keyboard = []
        for anon_id, first_name, username, group_name, message, recipient_type, created_at in pending:
            text += f"\n📌 ID {anon_id} ({created_at})\n"
            text += f"👤 {first_name}"
            if username and username != "нет": text += f" (@{username})"
            text += f"\n📤 Кому: 🌍 Всем студентам\n"
            text += f"💬 {message[:100]}{'...' if len(message) > 100 else ''}\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ Одобрить #{anon_id}", callback_data=f'approve_anon_{anon_id}'),
                InlineKeyboardButton(f"❌ Отклонить #{anon_id}", callback_data=f'reject_anon_{anon_id}')
            ])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data == 'admin_moderation_history':
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Доступ запрещен!", show_alert=True)
            return
        await query.answer()
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT id, first_name, group_name, message, recipient_type, status, created_at, moderated_at FROM anon_messages WHERE status != "pending" ORDER BY moderated_at DESC LIMIT 20')
        history = c.fetchall()
        conn.close()
        if not history:
            text = "📋 История модерации\n\nИстория пуста."
            await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
            return
        text = f"📋 История модерации (последние 20)\n\n"
        for anon_id, first_name, group_name, message, recipient_type, status, created_at, moderated_at in history:
            emoji = "✅" if status == "approved" else "❌"
            status_text = "одобрено" if status == "approved" else "отклонено"
            text += f"{emoji} ID {anon_id} | {first_name} | 🌍 Всем\n"
            text += f"   💬 {message[:80]}{'...' if len(message) > 80 else ''}\n"
            text += f"   📅 {created_at} → {status_text} {moderated_at}\n\n"
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data == 'admin_stats':
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Доступ запрещен!", show_alert=True)
            return
        await query.answer()
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM anon_messages WHERE status = "pending"')
        pending_anon = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM anon_messages WHERE status = "approved"')
        approved_anon = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM anon_messages WHERE status = "rejected"')
        rejected_anon = c.fetchone()[0]
        total_anon = pending_anon + approved_anon + rejected_anon
        c.execute('SELECT COUNT(*) FROM schedule')
        total_schedule = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM homework')
        total_homework = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM questions WHERE status = "new"')
        new_questions = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM questions')
        total_questions = c.fetchone()[0]
        conn.close()
        text = (
            f"📊 Статистика бота\n\n"
            f"👥 Пользователи:\n"
            f"   Всего зарегистрировано: {total_users}\n\n"
            f"💬 Анонимный чат:\n"
            f"   Всего сообщений: {total_anon}\n"
            f"   ✅ Одобрено: {approved_anon}\n"
            f"   ❌ Отклонено: {rejected_anon}\n"
            f"    На модерации: {pending_anon}\n\n"
            f"📅 Расписание:\n"
            f"   Всего пар добавлено: {total_schedule}\n\n"
            f" Домашние задания:\n"
            f"   Всего домашек: {total_homework}\n\n"
            f"❓ Вопросы:\n"
            f"   Всего вопросов: {total_questions}\n"
            f"   🆕 Новых (непрочитанных): {new_questions}"
        )
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data == 'admin_help':  
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Доступ запрещен!", show_alert=True)
            return
        await query.answer()
        text = (
            "📖 Справка по админ-командам\n\n"
            " Расписание:\n"
            "• /add_schedule [ГРУППА] ДЕНЬ ВРЕМЯ ПРЕДМЕТ ПРЕПОД АУД\n"
            "• /view_schedule - просмотр всего\n"
            "• /delete_schedule [ID] - удалить\n\n"
            "📝 Домашние задания:\n"
            "• /add_homework ГРУППА ПРЕДМЕТ ЗАДАНИЕ [До дедлайн]\n"
            "• /view_homework - просмотр всех\n"
            "• /delete_homework [ID] - удалить\n\n"
            "📨 Рассылка:\n"
            "• Ответь на сообщение (фото/текст/видео) командой /broadcast\n"
            "• /broadcast_cancel - отменить последнюю рассылку\n\n"
            "🗳️ Голосование:\n"
            "• /create_poll Вопрос Вариант1 Вариант2 ...\n"
            "• /poll_history - история всех голосований\n"
            "• /poll_results [ID] - узнать, кто именно проголосовал\n\n"
            "👥 Управление пользователями:\n"
            "• /delete_user [ID] - удалить пользователя из базы\n"
            "• /active_users [дней] - кто был активен (по умолч. 7 дней)\n"
            "• /inactive_users [дней] - кто не заходил (по умолч. 30 дней)\n\n"
            "💬 Модерация:\n"
            "• /admin - открыть админ-панель\n"
            "• Модерация анонимок через кнопки\n\n"
            " Примеры:\n"
            "/add_schedule ПН 09:00 Математика Иванов 301\n"
            "/active_users 3\n"
            "/delete_user 123456789"
        )
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return
    elif data == 'admin_questions':
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Доступ запрещен!", show_alert=True)
            return
        await query.answer()
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT id, user_id, question, date FROM questions WHERE status = "new" ORDER BY date DESC LIMIT 10')
        questions = c.fetchall()
        conn.close()
        if not questions:
            text = "❓ Новых вопросов нет!"
        else:
            text = "❓ Новые вопросы:\n\n"
            for q_id, user_id, question, date in questions:
                conn = sqlite3.connect('college_bot.db')
                c = conn.cursor()
                c.execute('SELECT first_name, group_name FROM users WHERE user_id = ?', (user_id,))
                user = c.fetchone()
                conn.close()
                user_name = user[0] if user else "Неизвестно"
                user_group = user[1] if user and user[1] else "Группа не указана"
                text += f"🔹 ID: {q_id}\n"
                text += f"👤 {user_name} ({user_group})\n"
                text += f"📅 {date}\n"
                text += f"💬 {question}\n\n"
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data.startswith('vote_'):
        parts = data.split('_')
        poll_id = parts[1]
        option_index = int(parts[2])
        user_id = query.from_user.id
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT id FROM poll_votes WHERE poll_id = ? AND user_id = ?', (poll_id, user_id))
        if c.fetchone():
            await query.answer("⚠️ Ты уже голосовал в этом опросе!", show_alert=True)
            conn.close()
            return
        c.execute('INSERT INTO poll_votes (poll_id, user_id, option_index) VALUES (?, ?, ?)', (poll_id, user_id, option_index))
        conn.commit()
        conn.close()
        await query.answer("✅ Твой голос принят!", show_alert=True)
        return

    elif data.startswith('publish_poll_'):
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ Только для админа!", show_alert=True)
            return
        poll_id = data.split('_')[2]
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT question, options FROM polls WHERE id = ?', (poll_id,))
        poll = c.fetchone()
        conn.close()
        if not poll:
            await query.answer("Опрос не найден", show_alert=True)
            return
        question, options_str = poll
        options = options_str.split('|')
        keyboard = []
        for i, option in enumerate(options):
            keyboard.append([InlineKeyboardButton(f"🔹 {option.replace('_', ' ')}", callback_data=f'vote_{poll_id}_{i}')])
        keyboard.append([InlineKeyboardButton("📊 Посмотреть результаты", callback_data=f'results_{poll_id}')])
        text = f"️ Голосование!\n\n❓ {question.replace('_', ' ')}\n\nВыбери вариант:"
        reply_markup = InlineKeyboardMarkup(keyboard)
        users = get_all_users()
        await query.answer()
        await query.edit_message_text(f" Начинаю рассылку голосования {len(users)} студентам...")
        success = 0
        for user_data in users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=text, reply_markup=reply_markup)
                success += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"Ошибка рассылки: {e}")
                pass
        await query.edit_message_text(f"✅ Голосование успешно отправлено {success} студентам!")
        return

    elif data.startswith('results_'):
        poll_id = data.split('_')[1]
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT question, options FROM polls WHERE id = ?', (poll_id,))
        poll = c.fetchone()
        if not poll:
            await query.answer("Опрос не найден", show_alert=True)
            conn.close()
            return
        question, options_str = poll
        options = options_str.split('|')
        c.execute('SELECT option_index, COUNT(*) FROM poll_votes WHERE poll_id = ? GROUP BY option_index', (poll_id,))
        votes = dict(c.fetchall())
        total_votes = sum(votes.values())
        conn.close()
        text = f"📊 Результаты: {question.replace('_', ' ')}\n\n"
        for i, option in enumerate(options):
            count = votes.get(i, 0)
            percent = (count / total_votes * 100) if total_votes > 0 else 0
            text += f"🔹 {option.replace('_', ' ')}: {count} голосов ({percent:.1f}%)\n"
        text += f"\n👥 Всего проголосовало: {total_votes}"
        await query.answer()
        await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data == 'contacts_info':
        await query.answer()
        text = (
            "📍 **Контакты Налогового колледжа**\n\n"
            "👩‍💼 **Директор:** Кузьминская Юлия Борисовна\n\n"
            "🏢 **Адрес:** г. Москва, ул. 3-я Хорошевская, д. 2, стр. 1\n"
            "(м. Хорошево, м. Полежаевская)\n\n"
            "🕒 **Режим работы:**\n"
            "Пн-Пт: 09:00 - 19:30\n"
            "Сб: 10:00 - 14:00\n"
            "Вс: выходной\n\n"
            " **Телефоны:**\n"
            "Приемная комиссия: +7 (495) 568-07-07\n"
            "Секретарь: +7 (499) 191-00-69\n\n"
            "🔗 **Полезные ссылки:**\n"
            "🌐 Официальный сайт: https://xn----7sbgdhfiukffarqbe1t.xn--p1ai/\n"
            "💻 Личный кабинет абитуриента: https://lk-nk.ru\n"
            " Дистанционное обучение: https://distant-nk.ru"
        )
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode='Markdown')
        return

    elif data == 'practice_info':
        await query.answer()
        text = (
            "💼 **Партнеры по практике**\n\n"
            "Наши студенты проходят практику в ведущих организациях:\n\n"
            "️ Федеральная налоговая служба (ФНС)\n"
            "🏦 ПАО «Сбербанк»\n"
            "🏦 ПАО «Московский кредитный банк»\n"
            "🏦 ПАО «Банк УРАЛСИБ»\n"
            "️ Департамент труда и соцзащиты г. Москвы\n"
            " Ассоциация налоговых консультантов\n"
            "🏢 ООО «Международная консалтинговая группа»\n\n"
            " *Полный список мест практики доступен в учебной части колледжа.*"
        )
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode='Markdown')
        return

    elif data == 'grades': text = "📊 Оценок пока нет."
    elif data == 'gpa': text = "🧮 Оценок пока нет."
    elif data == 'teachers': text = "👨‍🏫 Список преподавателей пока пуст."
    elif data == 'news': text = "📰 Новостей пока нет."
    elif data == 'weather':
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast?latitude=55.75&longitude=37.61&current_weather=true")
            d = r.json()['current_weather']
            text = f"🌤️ Погода в Москве\n🌡️ {d['temperature']}°C\n💨 Ветер: {d['windspeed']} км/ч"
        except: text = "❌ Не удалось получить погоду."
    elif data == 'exams': text = " Экзаменов пока не запланировано."
    elif data == 'question':
        context.user_data['waiting_for_question'] = True
        text = "❓ Задать вопрос админу\n\nНапиши свой вопрос. Он уйдет лично администратору."
    elif data == 'conspekts': text = "📚 Конспектов пока нет."
    elif data == 'attendance': text = "📈 Посещаемость в разработке."
    elif data == 'rooms': text = "🗺️ Карта аудиторий в разработке."
    elif data == 'reminders': text = "⏰ Напоминания в разработке."
    elif data == 'settings':
        group = get_user_group(query.from_user.id)
        text = f"👥 Выбор группы\n\n {query.from_user.first_name}\n Группа: {group or 'Не указана'}\n\n👇 Выбери свою группу:"
        await query.answer()
        await query.edit_message_text(text, reply_markup=groups_keyboard())
        return
    elif data == 'help':
        text = (
            "🆘 Помощь\n\n"
            "📱 Основные команды:\n"
            "• /start - Главное меню\n"
            "• /setgroup [ГРУППА] - Выбрать группу\n\n"
            "❓ Вопросы:\n"
            "• Нажми '❓ Вопрос админу'\n\n"
            "️ Настройки:\n"
            "• Нажми '👥 Выбрать группу' для выбора группы"
        )
        await query.answer()
        await query.edit_message_text(text, reply_markup=back_button())
        return
    else: text = "️ В разработке."

    if text:
        await query.answer()
        await query.edit_message_text(text, reply_markup=back_button())

# ==================== ОБРАБОТЧИК РЕГИСТРАЦИИ ====================
async def handle_registration_message(update: Update, context):
    user_id = update.effective_user.id

    if update.message.contact:
        if context.user_data.get('reg_step') == 'waiting_phone':
            phone = update.message.contact.phone_number
            group_name = context.user_data.get('reg_group')
            full_name = context.user_data.get('reg_full_name')

            conn = sqlite3.connect('college_bot.db')
            c = conn.cursor()
            c.execute('''INSERT INTO users (user_id, first_name, username, full_name, phone, group_name, is_verified)
                         VALUES (?, ?, ?, ?, ?, ?, 1)
                         ON CONFLICT(user_id) DO UPDATE SET
                            full_name=excluded.full_name, phone=excluded.phone,
                            group_name=excluded.group_name, is_verified=1''',
                      (user_id, update.effective_user.first_name, update.effective_user.username, full_name, phone, group_name))
            conn.commit()
            conn.close()
            context.user_data.clear()

            await update.message.reply_text(
                f"✅ Регистрация завершена!\n\n👤 {full_name}\n📞 {phone}\n👥 {group_name}\n\nТеперь тебе доступны все функции!",
                reply_markup=ReplyKeyboardRemove()
            )
            
            await update.message.reply_text(" Выбери действие:", reply_markup=main_menu_keyboard())

            log_text = (
                f" **Новая регистрация!**\n\n"
                f"🆔 ID пользователя: `{user_id}`\n"
                f"👤 ФИО: {full_name}\n"
                f"📞 Телефон: {phone}\n"
                f"👥 Группа: {group_name}\n"
            )
            if update.effective_user.username:
                log_text += f"🔗 Юзернейм: @{update.effective_user.username}\n"
            
            try:
                await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode='Markdown')
            except Exception as e:
                print(f"❌ Ошибка отправки в лог-канал: {e}")
            
            return

    if context.user_data.get('reg_step') == 'waiting_full_name':
        context.user_data['reg_full_name'] = update.message.text.strip()
        context.user_data['reg_step'] = 'waiting_group'
        await update.message.reply_text("✅ ФИО принято!\n\nШаг 2: Выбери свою группу из списка ниже:", reply_markup=groups_keyboard())
        return

    await handle_message(update, context)

# ==================== ОБРАБОТЧИК СООБЩЕНИЙ ====================
async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text

    # Обновляем время последней активности
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET last_active = ? WHERE user_id = ?', 
              (datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M'), user_id))
    conn.commit()
    conn.close()

    if context.user_data.get('reg_step') in ['waiting_full_name', 'waiting_group', 'waiting_phone']:
        return

    if context.user_data.get('waiting_for_anon'):
        context.user_data['waiting_for_anon'] = False
        context.user_data['anon_recipient'] = None
        group = get_user_group(user_id)
        if not group:
            await update.message.reply_text("⚠️ Ошибка: группа не найдена.", reply_markup=main_menu_keyboard())
            return
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('INSERT INTO anon_messages (user_id, first_name, username, group_name, message, recipient_type, status, created_at) VALUES (?, ?, ?, ?, ?, "all", "pending", ?)',
                  (user_id, update.effective_user.first_name, update.effective_user.username or "нет", group, text, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
        anon_id = c.lastrowid
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Твоё сообщение отправлено на модерацию!\n\n"
            f"📤 Получатели: 🌍 Все студенты колледжа\n"
            f" ID сообщения: {anon_id}\n\n"
            f"После одобрения администратором оно будет опубликовано в канале анонимок.\n\n"
            f"⚠️ Если сообщение нарушает правила — оно будет отклонено.",
            reply_markup=main_menu_keyboard()
        )
        sender_username = update.effective_user.username or "нет"
        admin_msg = (
            f"📥 НОВОЕ СООБЩЕНИЕ НА МОДЕРАЦИЮ\n\n"
            f"🆔 ID: {anon_id}\n"
            f"👤 От: {update.effective_user.first_name}\n"
            f" Username: @{sender_username}\n"
            f"👥 Группа: {group}\n"
            f"📤 Кому: 🌍 Всем студентам\n"
            f" Время: {datetime.datetime.now(TIMEZONE).strftime('%H:%M')}\n\n"
            f"💬 Сообщение:\n{text}\n\n"
            f"Выбери действие:"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Одобрить и опубликовать", callback_data=f'approve_anon_{anon_id}')],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_anon_{anon_id}')]
        ]
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=InlineKeyboardMarkup(keyboard))
            print(f"✅ Анонимка ID {anon_id} на модерации от {update.effective_user.first_name}")
        except Exception as e:
            print(f"❌ Не удалось отправить на модерацию: {e}")
        return

    if context.user_data.get('waiting_for_question'):
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('INSERT INTO questions (user_id, question, date) VALUES (?, ?, ?)',
                  (user_id, text, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
        conn.commit(); conn.close()
        context.user_data['waiting_for_question'] = False
        await update.message.reply_text("✅ Вопрос отправлен админу!", reply_markup=main_menu_keyboard())
        admin_msg = f"❓ Новый вопрос\n {update.effective_user.first_name}\n {text}"
        try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        except: pass
        return

    if text.lower().startswith('/setgroup'):
        parts = text.split(' ', 1)
        if len(parts) < 2: return await update.message.reply_text("️ Пример: /setgroup 1Ю1/925o")
        group_name = parts[1].strip()
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('UPDATE users SET group_name = ? WHERE user_id = ?', (group_name, user_id))
        conn.commit(); conn.close()
        await update.message.reply_text(f"✅ Группа установлена: {group_name}", reply_markup=main_menu_keyboard())
        return

    text_lower = text.lower()
    if 'привет' in text_lower:
        await update.message.reply_text(f"👋 Привет, {update.effective_user.first_name}!", reply_markup=main_menu_keyboard())
    elif 'спасибо' in text_lower:
        await update.message.reply_text("😊 Пожалуйста!")
    else:
        await update.message.reply_text(" Используй кнопки или /help", reply_markup=main_menu_keyboard())

# ==================== FLASK СЕРВЕР (ДЛЯ RENDER) ====================
web_app = Flask('')

@web_app.route('/')
def home():
    return "Бот работает!"

def run_flask():
    web_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==================== АДМИН: РЕЗУЛЬТАТЫ ГОЛОСОВАНИЯ ====================
async def poll_results_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Формат: /poll_results [ID]\nПример: /poll_results 1")
        return
    try:
        poll_id = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ ID должен быть числом!")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT question, options, created_at FROM polls WHERE id = ?', (poll_id,))
    poll = c.fetchone()
    if not poll:
        conn.close()
        await update.message.reply_text(f"❌ Голосование #{poll_id} не найдено!")
        return
    question, options_str, created_at = poll
    options = options_str.split('|')
    c.execute('SELECT pv.option_index, u.first_name, u.username, u.group_name FROM poll_votes pv JOIN users u ON pv.user_id = u.user_id WHERE pv.poll_id = ? ORDER BY pv.option_index', (poll_id,))
    votes = c.fetchall()
    vote_counts = {}
    for i in range(len(options)):
        vote_counts[i] = 0
    for vote in votes:
        vote_counts[vote[0]] = vote_counts.get(vote[0], 0) + 1
    total_votes = len(votes)
    conn.close()
    text = f"📊 РЕЗУЛЬТАТЫ ГОЛОСОВАНИЯ #{poll_id}\n\n"
    text += f"Вопрос: {question.replace('_', ' ')}\n"
    text += f"Создано: {created_at}\n"
    text += f"Всего голосов: {total_votes}\n\n"
    for i, option in enumerate(options):
        count = vote_counts.get(i, 0)
        percent = (count / total_votes * 100) if total_votes > 0 else 0
        text += f"🔹 {option.replace('_', ' ')}: {count} ({percent:.1f}%)\n"
    if votes:
        text += "\n👥 Кто голосовал:\n"
        for opt_idx, fname, uname, gname in votes:
            info = f"• {fname}"
            if gname: info += f" ({gname})"
            if uname and uname != "None": info += f" @{uname}"
            text += f"{info} → {options[opt_idx].replace('_', ' ')}\n"
    await update.message.reply_text(text)

# ==================== АДМИН: ИСТОРИЯ ГОЛОСОВАНИЙ ====================
async def poll_history_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(" Только для админа!")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT id, question, options, created_at, is_active FROM polls ORDER BY created_at DESC LIMIT 20')
    polls = c.fetchall()
    conn.close()
    if not polls:
        await update.message.reply_text("🗳️ Нет голосований")
        return
    text = "🗳️ ИСТОРИЯ ГОЛОСОВАНИЙ (последние 20)\n\n"
    for pid, q, opts, created, active in polls:
        options = opts.split('|')
        status = "✅ Активно" if active == 1 else "🔴 Завершено"
        conn = sqlite3.connect('college_bot.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM poll_votes WHERE poll_id = ?', (pid,))
        vcount = c.fetchone()[0]
        conn.close()
        text += f"#{pid} ({status})\n{q.replace('_', ' ')}\n"
        text += f"📅 {created} | 👥 {vcount} голосов\n"
        text += f"Варианты: {', '.join([o.replace('_', ' ') for o in options[:3]])}\n"
        text += f"Детали: /poll_results {pid}\n\n"
        text += "-" * 40 + "\n\n"
    await update.message.reply_text(text)

# ==================== КОМАНДА /setgroup ====================
async def setgroup_command(update: Update, context):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("️ Пример: /setgroup 1Ю1/925o")
        return
    group_name = context.args[0].strip()
    if group_name not in GROUPS:
        await update.message.reply_text(f"⚠️ Группа '{group_name}' не найдена!")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)',
              (user_id, update.effective_user.first_name, update.effective_user.username))
    c.execute('UPDATE users SET group_name = ? WHERE user_id = ?', (group_name, user_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Отлично! Твоя группа теперь: {group_name}", reply_markup=main_menu_keyboard())

# ==================== АДМИН: УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ ====================
async def delete_user_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Формат: /delete_user [ID]\nПример: /delete_user 123456789")
        return
    try:
        user_id = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ ID должен быть числом!")
        return
    
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT first_name, full_name, group_name FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        await update.message.reply_text(f"❌ Пользователь с ID {user_id} не найден в базе!")
        return
    
    c.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Пользователь удален из базы!\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {user[0]}\n"
        f" ФИО: {user[1]}\n"
        f"👥 Группа: {user[2]}\n\n"
        f"️ Если он напишет /start снова — регистрация пройдет заново."
    )

# ==================== АДМИН: АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ ====================
async def active_users_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
        except:
            pass
    
    cutoff_date = (datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
    
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT user_id, first_name, full_name, group_name, last_active FROM users WHERE last_active >= ? ORDER BY last_active DESC LIMIT 50', (cutoff_date,))
    users = c.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text(f"📊 Нет активных пользователей за последние {days} дней.")
        return
    
    text = f"📊 АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ (за {days} дней):\n\n"
    for uid, fname, full, grp, last in users:
        text += f" `{uid}` | {full or fname} | {grp}\n"
        text += f"   🕐 Последняя активность: {last}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ==================== АДМИН: НЕАКТИВНЫЕ ПОЛЬЗОВАТЕЛИ ====================
async def inactive_users_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только для админа!")
        return
    
    days = 30
    if context.args:
        try:
            days = int(context.args[0])
        except:
            pass
    
    cutoff_date = (datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
    
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT user_id, first_name, full_name, group_name, last_active FROM users WHERE (last_active < ? OR last_active IS NULL) AND is_verified = 1 ORDER BY last_active ASC LIMIT 50', (cutoff_date,))
    users = c.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text(f"✅ Все пользователи активны за последние {days} дней!")
        return
    
    text = f"😴 НЕАКТИВНЫЕ ПОЛЬЗОВАТЕЛИ (не заходили {days}+ дней):\n\n"
    for uid, fname, full, grp, last in users:
        text += f"🆔 `{uid}` | {full or fname} | {grp}\n"
        text += f"   🕐 Последняя активность: {last or 'никогда'}\n\n"
    
    text += f"💡 Чтобы удалить: /delete_user [ID]"
    await update.message.reply_text(text, parse_mode='Markdown')

# ==================== КОМАНДЫ ДЛЯ КНОПОК МЕНЮ ====================
async def schedule_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group:
        await update.message.reply_text("⚠️ Сначала выбери группу командой /setgroup")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT time, subject, teacher, room FROM schedule WHERE (group_name = ? OR group_name = "ОБЩЕЕ") AND day = ? ORDER BY time', (group, get_day_name()))
    schedule = c.fetchall()
    conn.close()
    if not schedule:
        text = f"📅 На сегодня ({get_day_name()}) пар нет! 🎉"
    else:
        text = f"📅 Расписание на {get_day_name()}\n👥 {group}\n\n"
        for i, (time, subj, teach, room) in enumerate(schedule, 1):
            text += f"{i}. {time} - {subj}\n   👨‍🏫 {teach} | 🚪 {room}\n"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def schedule_week_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group:
        await update.message.reply_text("️ Сначала выбери группу командой /setgroup")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT day, time, subject, teacher, room FROM schedule WHERE (group_name = ? OR group_name = "ОБЩЕЕ") ORDER BY CASE day WHEN "Понедельник" THEN 1 WHEN "Вторник" THEN 2 WHEN "Среда" THEN 3 WHEN "Четверг" THEN 4 WHEN "Пятница" THEN 5 WHEN "Суббота" THEN 6 WHEN "Воскресенье" THEN 7 END, time', (group,))
    schedule = c.fetchall()
    conn.close()
    if not schedule:
        text = f"📅 Расписание для {group} пока не добавлено."
    else:
        text = f"📅 Расписание на неделю\n👥 {group}\n\n"
        cur_day = None
        for day, time, subj, teach, room in schedule:
            if day != cur_day: text += f"\n📌 {day}:\n"; cur_day = day
            text += f"  • {time} - {subj} ({teach}, ауд. {room})\n"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def grades_command(update: Update, context):
    await update.message.reply_text(" Оценок пока нет.", reply_markup=main_menu_keyboard())

async def gpa_command(update: Update, context):
    await update.message.reply_text(" Оценок пока нет.", reply_markup=main_menu_keyboard())

async def teachers_command(update: Update, context):
    await update.message.reply_text("‍🏫 Список преподавателей пока пуст.", reply_markup=main_menu_keyboard())

async def exams_command(update: Update, context):
    await update.message.reply_text("🎓 Экзаменов пока не запланировано.", reply_markup=main_menu_keyboard())

async def news_command(update: Update, context):
    await update.message.reply_text("📰 Новостей пока нет.", reply_markup=main_menu_keyboard())

async def weather_command(update: Update, context):
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast?latitude=55.75&longitude=37.61&current_weather=true")
        d = r.json()['current_weather']
        text = f"🌤️ Погода в Москве\n🌡️ {d['temperature']}°C\n💨 Ветер: {d['windspeed']} км/ч"
    except:
        text = "❌ Не удалось получить погоду."
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def homework_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group:
        await update.message.reply_text("⚠️ Сначала выбери группу командой /setgroup")
        return
    conn = sqlite3.connect('college_bot.db')
    c = conn.cursor()
    c.execute('SELECT subject, task, deadline FROM homework WHERE (group_name = ? OR group_name = "ОБЩЕЕ") ORDER BY created_at DESC', (group,))
    hw = c.fetchall()
    conn.close()
    if not hw:
        text = f" Домашних заданий для {group} пока нет!"
    else:
        text = f" Домашние задания\n👥 {group}\n\n"
        for subj, task, dead in hw:
            text += f"📚 {subj}\n   📝 {task}\n   ⏰ {dead}\n\n"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def contacts_command(update: Update, context):
    text = (
        "📍 Контакты Налогового колледжа\n\n"
        "👩‍💼 Директор: Кузьминская Юлия Борисовна\n\n"
        "🏢 Адрес: г. Москва, ул. 3-я Хорошевская, д. 2, стр. 1\n"
        "(м. Хорошево, м. Полежаевская)\n\n"
        "🕒 Режим работы:\n"
        "Пн-Пт: 09:00 - 19:30\n"
        "Сб: 10:00 - 14:00\n"
        "Вс: выходной\n\n"
        "📞 Телефоны:\n"
        "Приемная комиссия: +7 (495) 568-07-07\n"
        "Секретарь: +7 (499) 191-00-69\n\n"
        "🔗 Полезные ссылки:\n"
        "🌐 Официальный сайт: https://xn----7sbgdhfiukffarqbe1t.xn--p1ai/\n"
        "💻 Личный кабинет абитуриента: https://lk-nk.ru\n"
        "🎓 Дистанционное обучение: https://distant-nk.ru"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def practice_command(update: Update, context):
    text = (
        "💼 Партнеры по практике\n\n"
        "Наши студенты проходят практику в ведущих организациях:\n\n"
        "🏛️ Федеральная налоговая служба (ФНС)\n"
        "🏦 ПАО «Сбербанк»\n"
        "🏦 ПАО «Московский кредитный банк»\n"
        " ПАО «Банк УРАЛСИБ»\n"
        "⚖️ Департамент труда и соцзащиты г. Москвы\n"
        "🤝 Ассоциация налоговых консультантов\n"
        " ООО «Международная консалтинговая группа»\n\n"
        "📌 Полный список мест практики доступен в учебной части колледжа."
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def help_command(update: Update, context):
    text = (
        "🆘 Помощь\n\n"
        "📱 Основные команды:\n"
        "• /start - Главное меню\n"
        "• /setgroup [ГРУППА] - Выбрать группу\n"
        "• /schedule - Расписание на день\n"
        "• /schedule_week - Расписание на неделю\n"
        "• /homework - Домашние задания\n"
        "• /grades - Оценки\n"
        "• /gpa - Средний балл\n"
        "• /teachers - Преподаватели\n"
        "• /exams - Экзамены\n"
        "• /news - Новости\n"
        "• /weather - Погода\n"
        "• /contacts - Контакты колледжа\n"
        "• /practice - Практика\n"
        "• /anon_chat - Анонимный чат\n\n"
        "❓ Вопросы:\n"
        "• Напиши свой вопрос, и он уйдет администратору\n\n"
        "⚙️ Настройки:\n"
        "• /setgroup - выбрать или изменить группу"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def anon_chat_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group:
        text = "⚠️ Сначала выбери группу командой /setgroup\n\nБез группы анонимный чат не работает."
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())
        return
    context.user_data['waiting_for_anon'] = True
    context.user_data['anon_recipient'] = 'all'
    text = (
        f"💬 Анонимный чат\n\n"
        f"📢 Хочешь почитать, что пишут другие? Заходи в наш канал:\n"
        f"👉 {ANON_CHANNEL_LINK}\n\n"
        f"⚠️ ПРАВИЛА:\n"
        f"• Только для учебы и конструктивных вопросов\n"
        f"• За оскорбления, буллинг и спам — бан\n"
        f"• Все сообщения проходят модерацию администратором\n\n"
        f"Напиши своё сообщение следующим текстом.\n"
        f"После одобрения админом оно будет анонимно отправлено всем студентам колледжа.\n\n"
        f"Чтобы отменить, нажми /start"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

# ==================== ЗАПУСК ====================
def main():
    init_db()
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("broadcast_cancel", broadcast_cancel_command))
    app.add_handler(CommandHandler("create_poll", create_poll_command))
    app.add_handler(CommandHandler("poll_results", poll_results_command))
    app.add_handler(CommandHandler("poll_history", poll_history_command))
    app.add_handler(CommandHandler("setgroup", setgroup_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("schedule_week", schedule_week_command))
    app.add_handler(CommandHandler("grades", grades_command))
    app.add_handler(CommandHandler("gpa", gpa_command))
    app.add_handler(CommandHandler("teachers", teachers_command))
    app.add_handler(CommandHandler("exams", exams_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("homework", homework_command))
    app.add_handler(CommandHandler("contacts", contacts_command))
    app.add_handler(CommandHandler("practice", practice_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("anon_chat", anon_chat_command))
    app.add_handler(CommandHandler("add_schedule", add_schedule_command))
    app.add_handler(CommandHandler("view_schedule", view_schedule_command))
    app.add_handler(CommandHandler("delete_schedule", delete_schedule_command))
    app.add_handler(CommandHandler("add_homework", add_homework_command))
    app.add_handler(CommandHandler("view_homework", view_homework_command))
    app.add_handler(CommandHandler("delete_homework", delete_homework_command))
    app.add_handler(CommandHandler("delete_user", delete_user_command))
    app.add_handler(CommandHandler("active_users", active_users_command))
    app.add_handler(CommandHandler("inactive_users", inactive_users_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, handle_registration_message))
    app.add_handler(MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен!")
    print(f"👥 Загружено групп: {len(GROUPS)}")
    print(f"🛡️ Модерация анонимок: ВКЛЮЧЕНА")
    print(f"📢 Канал анонимок: {ANON_CHANNEL_ID}")
    print(f"🔗 Ссылка на канал: {ANON_CHANNEL_LINK}")
    print(f"📊 Статистика бота: ВКЛЮЧЕНА")
    print(f"📨 Массовая рассылка (с медиа): ВКЛЮЧЕНА")
    print(f"🗳️ Голосование: ВКЛЮЧЕНО")
    print(f"📍 Контакты и практика: ВКЛЮЧЕНО")
    app.run_polling()

if __name__ == '__main__':
    main()
