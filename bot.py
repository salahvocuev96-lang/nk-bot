import os
import csv
import tempfile
import psycopg
import requests
import datetime
from pytz import timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, JobQueue
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
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    
    try:
        c.execute('ALTER TABLE users ALTER COLUMN user_id TYPE BIGINT')
        c.execute('ALTER TABLE grades ALTER COLUMN user_id TYPE BIGINT')
        c.execute('ALTER TABLE questions ALTER COLUMN user_id TYPE BIGINT')
        c.execute('ALTER TABLE conspekts ALTER COLUMN user_id TYPE BIGINT')
        c.execute('ALTER TABLE anon_messages ALTER COLUMN user_id TYPE BIGINT')
        c.execute('ALTER TABLE poll_votes ALTER COLUMN user_id TYPE BIGINT')
        conn.commit()
    except:
        conn.rollback()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY, first_name TEXT, username TEXT, group_name TEXT, 
        full_name TEXT DEFAULT NULL, phone TEXT DEFAULT NULL, is_verified INTEGER DEFAULT 0, last_active TEXT DEFAULT NULL)''')
    c.execute('CREATE TABLE IF NOT EXISTS schedule (id SERIAL PRIMARY KEY, group_name TEXT, day TEXT, time TEXT, subject TEXT, teacher TEXT, room TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS homework (id SERIAL PRIMARY KEY, group_name TEXT, subject TEXT, task TEXT, deadline TEXT, created_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS grades (id SERIAL PRIMARY KEY, user_id BIGINT, subject TEXT, grade INTEGER, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS teachers (id SERIAL PRIMARY KEY, name TEXT, subject TEXT, cabinet TEXT, email TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS news (id SERIAL PRIMARY KEY, title TEXT, content TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS exams (id SERIAL PRIMARY KEY, group_name TEXT, subject TEXT, date TEXT, time TEXT, room TEXT)')
    c.execute("CREATE TABLE IF NOT EXISTS questions (id SERIAL PRIMARY KEY, user_id BIGINT, question TEXT, is_anon INTEGER, date TEXT, status TEXT DEFAULT 'new')")
    c.execute('CREATE TABLE IF NOT EXISTS conspekts (id SERIAL PRIMARY KEY, user_id BIGINT, subject TEXT, title TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS polls (id SERIAL PRIMARY KEY, question TEXT, options TEXT, creator_id BIGINT, created_at TEXT, is_active INTEGER DEFAULT 1)')
    c.execute('CREATE TABLE IF NOT EXISTS poll_votes (id SERIAL PRIMARY KEY, poll_id INTEGER, user_id BIGINT, option_index INTEGER)')
    c.execute("CREATE TABLE IF NOT EXISTS anon_messages (id SERIAL PRIMARY KEY, user_id BIGINT, first_name TEXT, username TEXT, group_name TEXT, message TEXT, recipient_type TEXT DEFAULT 'all', status TEXT DEFAULT 'pending', created_at TEXT, moderated_at TEXT, channel_message_id INTEGER)")
    c.execute('CREATE TABLE IF NOT EXISTS scheduled_messages (id SERIAL PRIMARY KEY, text TEXT, file_type TEXT, file_id TEXT, caption TEXT, send_at TEXT)')
    conn.commit()
    conn.close()

def get_user_group(user_id):
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT group_name FROM users WHERE user_id = %s ORDER BY user_id DESC LIMIT 1', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] else None

def get_day_name(day_num=None):
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    if day_num is None:
        day_num = datetime.datetime.now(TIMEZONE).weekday()
    return days[day_num]

def calculate_gpa(user_id):
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT AVG(grade) FROM grades WHERE user_id = %s', (user_id,))
    result = c.fetchone()
    conn.close()
    return float(result[0]) if result and result[0] else 0.0

def get_all_users():
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT user_id, first_name, group_name FROM users')
    users = c.fetchall()
    conn.close()
    return users

def get_users_by_group(group_name):
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT user_id, first_name FROM users WHERE group_name = %s', (group_name,))
    users = c.fetchall()
    conn.close()
    return users

# ==================== КЛАВИАТУРЫ ====================
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("👤 Мой профиль", callback_data='profile'), InlineKeyboardButton("🗓️ Расписание", callback_data='schedule')],
        [InlineKeyboardButton("📊 Оценки", callback_data='grades'), InlineKeyboardButton("🧮 GPA", callback_data='gpa')],
        [InlineKeyboardButton("👨‍🏫 Преподаватели", callback_data='teachers'), InlineKeyboardButton("🎓 Экзамены", callback_data='exams')],
        [InlineKeyboardButton("📰 Новости", callback_data='news'), InlineKeyboardButton("🌤️ Погода", callback_data='weather')],
        [InlineKeyboardButton("📈 Посещаемость", callback_data='attendance'), InlineKeyboardButton("🗺️ Аудитории", callback_data='rooms')],
        [InlineKeyboardButton("💬 Анонимный чат", callback_data='anon_chat'), InlineKeyboardButton("📢 Канал анонимок", url=ANON_CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Вопрос админу", callback_data='question'), InlineKeyboardButton("📍 Контакты", callback_data='contacts_info')],
        [InlineKeyboardButton("💼 Практика", callback_data='practice_info'), InlineKeyboardButton("🆘 Помощь", callback_data='help')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')]])

def groups_keyboard():
    keyboard = []
    row = []
    for group in GROUPS:
        row.append(InlineKeyboardButton(group, callback_data=f'setgroup_{group}'))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM anon_messages WHERE status = 'pending'")
    pending_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM questions WHERE status = 'new'")
    questions_count = c.fetchone()[0]
    conn.close()
    moderation_text = f"📥 Модерация ({pending_count})" if pending_count > 0 else "📥 Модерация"
    questions_text = f"❓ Вопросы ({questions_count})" if questions_count > 0 else "❓ Вопросы"
    keyboard = [
        [InlineKeyboardButton(moderation_text, callback_data='admin_moderation')],
        [InlineKeyboardButton(questions_text, callback_data='admin_questions')],
        [InlineKeyboardButton("📋 История модерации", callback_data='admin_moderation_history')],
        [InlineKeyboardButton("📊 Статистика бота", callback_data='admin_stats')],
        [InlineKeyboardButton("📖 Справка по командам", callback_data='admin_help')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
async def start(update: Update, context):
    user = update.effective_user
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT is_verified FROM users WHERE user_id = %s', (user.id,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] == 0:
        context.user_data['reg_step'] = 'waiting_full_name'
        text = f"👋 Привет, {user.first_name}!\n\nДля доступа к боту {COLLEGE_NAME} нужна быстрая регистрация.\n\nШаг 1: Напиши свои **ФИО** (полностью, как в журнале)."
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    text = f"👋 Привет, {user.first_name}!\n\nДобро пожаловать в бота {COLLEGE_NAME}!"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def admin_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Доступ запрещен!")
    await update.message.reply_text("👨‍💼 Админ-панель\n\nВыбери раздел:", reply_markup=admin_panel_keyboard())

async def profile_command(update: Update, context):
    user_id = update.effective_user.id
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT first_name, username, group_name, full_name, phone, is_verified, last_active FROM users WHERE user_id = %s', (user_id,))
    user = c.fetchone()
    conn.close()
    if not user:
        text = "⚠️ Ты не зарегистрирован в системе.\n\nНапиши /start, чтобы пройти регистрацию."
    else:
        first_name, username, group_name, full_name, phone, is_verified, last_active = user
        status = "✅ Подтвержден" if is_verified == 1 else "⏳ Ожидает подтверждения"
        text = (f"👤 **Твой профиль**\n\n"
                f"📛 **Имя:** {first_name}\n🔗 **Username:** @{username or 'не указан'}\n"
                f"👥 **Группа:** {group_name or 'не указана'}\n📝 **ФИО:** {full_name or 'не указано'}\n"
                f"📞 **Телефон:** {phone or 'не указан'}\n🔐 **Статус:** {status}\n"
                f"🕐 **Последняя активность:** {last_active or 'никогда'}\n\n"
                f"💡 Чтобы изменить данные, напиши администратору через команду /anon_chat.")
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode='Markdown')

# ==================== АДМИН: УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================
async def export_users_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    await update.message.reply_text("📥 Формирую файл с базой данных...")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT user_id, first_name, username, group_name, full_name, phone, is_verified, last_active FROM users ORDER BY group_name')
    users = c.fetchall()
    conn.close()
    if not users: return await update.message.reply_text("⚠️ База данных пуста.")

    file_path = '/tmp/students_export.csv'
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Telegram ID', 'Имя', 'Username', 'Группа', 'ФИО', 'Телефон', 'Верифицирован (1=Да)', 'Последняя активность'])
        for u in users: writer.writerow(u)
            
    with open(file_path, 'rb') as f:
        await update.message.reply_document(document=f, filename='База_студентов_NK_College.csv', caption=f"✅ Готово! Экспортировано {len(users)} студентов.")
    os.remove(file_path)

async def edit_user_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if len(context.args) < 3: return await update.message.reply_text("⚠️ Формат: /edit_user [ID] fio/group/phone [значение]\nПример: /edit_user 8688778044 fio Иванов Иван Иванович")
    try: user_id = int(context.args[0])
    except: return await update.message.reply_text("⚠️ ID должен быть числом!")
    
    field = context.args[1].lower()
    new_value = ' '.join(context.args[2:])
    valid_fields = {'fio': 'full_name', 'group': 'group_name', 'phone': 'phone'}
    if field not in valid_fields: return await update.message.reply_text("⚠️ Неверное поле! Доступные: fio, group, phone")
    
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT first_name, full_name, group_name, phone FROM users WHERE user_id = %s', (user_id,))
    user = c.fetchone()
    if not user: conn.close(); return await update.message.reply_text(f"❌ Пользователь с ID {user_id} не найден!")
    
    c.execute(f'UPDATE users SET {valid_fields[field]} = %s WHERE user_id = %s', (new_value, user_id))
    conn.commit(); conn.close()
    
    field_names = {'fio': 'ФИО', 'group': 'группу', 'phone': 'телефон'}
    await update.message.reply_text(f"✅ Данные обновлены!\n🆔 ID: {user_id}\n📝 Изменено: {field_names[field]}\n📄 Новое значение: {new_value}")

async def delete_user_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if not context.args: return await update.message.reply_text("⚠️ Формат: /delete_user [ID]")
    try: user_id = int(context.args[0])
    except: return await update.message.reply_text("⚠️ ID должен быть числом!")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT first_name, full_name, group_name FROM users WHERE user_id = %s', (user_id,))
    user = c.fetchone()
    if not user: conn.close(); return await update.message.reply_text(f"❌ Пользователь с ID {user_id} не найден!")
    c.execute('DELETE FROM users WHERE user_id = %s', (user_id,))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Пользователь удален!\n🆔 ID: {user_id}\n👤 Имя: {user[0]}")

async def active_users_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    days = 7
    if context.args:
        try: days = int(context.args[0])
        except: pass
    cutoff_date = (datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT user_id, first_name, full_name, group_name, last_active FROM users WHERE last_active >= %s ORDER BY last_active DESC LIMIT 50', (cutoff_date,))
    users = c.fetchall()
    conn.close()
    if not users: return await update.message.reply_text(f"📊 Нет активных пользователей за последние {days} дней.")
    text = f"📊 АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ (за {days} дней):\n\n"
    for uid, fname, full, grp, last in users:
        text += f"🆔 `{uid}` | {full or fname} | {grp}\n   🕐 Последняя активность: {last}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def inactive_users_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    days = 30
    if context.args:
        try: days = int(context.args[0])
        except: pass
    cutoff_date = (datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, full_name, group_name, last_active FROM users WHERE (last_active < %s OR last_active IS NULL) AND is_verified = 1 ORDER BY last_active ASC LIMIT 50", (cutoff_date,))
    users = c.fetchall()
    conn.close()
    if not users: return await update.message.reply_text(f"✅ Все пользователи активны за последние {days} дней!")
    text = f"😴 НЕАКТИВНЫЕ ПОЛЬЗОВАТЕЛИ (не заходили {days}+ дней):\n\n"
    for uid, fname, full, grp, last in users:
        text += f"🆔 `{uid}` | {full or fname} | {grp}\n   🕐 Последняя активность: {last or 'никогда'}\n\n"
    text += "💡 Чтобы удалить: /delete_user [ID]"
    await update.message.reply_text(text, parse_mode='Markdown')

# ==================== ЗАГРУЗКА РАСПИСАНИЯ ИЗ CSV ====================
async def upload_schedule_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Только для админа!")
    
    doc = update.message.document
    if not doc and update.message.reply_to_message:
        doc = update.message.reply_to_message.document

    if not doc:
        return await update.message.reply_text(
            "⚠️ Нужно прикрепить файл к команде или ответить на файл командой /upload_schedule.\n\n"
            "Файл должен быть в формате CSV со столбцами: Группа, День, Время, Предмет, Преподаватель, Аудитория"
        )
    
    await update.message.reply_text("📥 Читаю файл и очищаю старое расписание...")
    
    file = await context.bot.get_file(doc.file_id)
    file_path = '/tmp/schedule_upload.csv'
    await file.download_to_drive(file_path)
    
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('DELETE FROM schedule')
    conn.commit()
    
    count = 0
    errors = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row = {k.strip(): v for k, v in row.items()}
                try:
                    group = row.get('Группа', '').strip()
                    day = row.get('День', '').strip()
                    time = row.get('Время', '').strip()
                    subject = row.get('Предмет', '').strip()
                    teacher = row.get('Преподаватель', '').strip()
                    room = row.get('Аудитория', '').strip()
                    
                    if group and day and time and subject:
                        c.execute('''INSERT INTO schedule (group_name, day, time, subject, teacher, room) 
                                     VALUES (%s, %s, %s, %s, %s, %s)''',
                                  (group, day, time, subject, teacher, room))
                        count += 1
                except Exception as e:
                    errors += 1
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Расписание успешно загружено!\n📚 Добавлено пар: {count}\n❌ Ошибок: {errors}")
    except Exception as e:
        conn.close()
        await update.message.reply_text(f"❌ Ошибка при чтении файла: {e}")
    
    if os.path.exists(file_path): os.remove(file_path)

# ==================== АДМИН: РАСПИСАНИЕ И ДОМАШКА ====================
async def add_schedule_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if len(context.args) == 5:
        group_name, day_short, time, subject, teacher, room = "ОБЩЕЕ", context.args[0], context.args[1], context.args[2], context.args[3], context.args[4]
    elif len(context.args) == 6:
        group_name, day_short, time, subject, teacher, room = context.args[0], context.args[1], context.args[2], context.args[3], context.args[4], context.args[5]
    else: return await update.message.reply_text("⚠️ Формат: /add_schedule [ГРУППА] ДЕНЬ ВРЕМЯ ПРЕДМЕТ ПРЕПОД АУД")
    
    valid_days = {'ПН': 'Понедельник', 'ВТ': 'Вторник', 'СР': 'Среда', 'ЧТ': 'Четверг', 'ПТ': 'Пятница', 'СБ': 'Суббота', 'ВС': 'Воскресенье'}
    if day_short.upper() not in valid_days: return await update.message.reply_text(f"⚠️ Неверный день! Используй: {', '.join(valid_days.keys())}")
    if len(time) != 5 or time[2] != ':': return await update.message.reply_text("⚠️ Неверное время! Формат: 09:00")
    
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('INSERT INTO schedule (group_name, day, time, subject, teacher, room) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
              (group_name, valid_days[day_short.upper()], time, subject, teacher, room))
    sid = c.fetchone()[0]
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Пара добавлена! ID: {sid}\nДля удаления: /delete_schedule {sid}")

async def view_schedule_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute("SELECT id, group_name, day, time, subject, teacher, room FROM schedule ORDER BY group_name, CASE day WHEN 'Понедельник' THEN 1 WHEN 'Вторник' THEN 2 WHEN 'Среда' THEN 3 WHEN 'Четверг' THEN 4 WHEN 'Пятница' THEN 5 WHEN 'Суббота' THEN 6 WHEN 'Воскресенье' THEN 7 END, time")
    schedule = c.fetchall(); conn.close()
    if not schedule: return await update.message.reply_text("📅 Расписание пустое!")
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
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT group_name, day, time, subject FROM schedule WHERE id = %s', (sid,))
    res = c.fetchone()
    if not res: conn.close(); return await update.message.reply_text("⚠️ Не найдено!")
    c.execute('DELETE FROM schedule WHERE id = %s', (sid,))
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
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('INSERT INTO homework (group_name, subject, task, deadline, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id',
              (group_name, subject, task, deadline, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
    hid = c.fetchone()[0]
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Домашка добавлена! ID: {hid}\nУдалить: /delete_homework {hid}")

async def view_homework_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
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
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT group_name, subject, task FROM homework WHERE id = %s', (hid,))
    res = c.fetchone()
    if not res: conn.close(); return await update.message.reply_text("⚠️ Не найдено!")
    c.execute('DELETE FROM homework WHERE id = %s', (hid,))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Удалено: {res[0]} | {res[1]}: {res[2]}")

# ==================== РАССЫЛКИ ====================
async def broadcast_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if not update.message.reply_to_message: return await update.message.reply_text("⚠️ Ответь на сообщение командой /broadcast")
    reply_msg = update.message.reply_to_message
    users = get_all_users()
    if not users: return await update.message.reply_text("⚠️ В базе нет пользователей!")
    await update.message.reply_text(f"📨 Начинаю рассылку {len(users)} пользователям...")
    success, failed = 0, 0
    for user_data in users:
        try:
            if reply_msg.photo: await context.bot.send_photo(user_data[0], reply_msg.photo[-1].file_id, caption=reply_msg.caption or "")
            elif reply_msg.video: await context.bot.send_video(user_data[0], reply_msg.video.file_id, caption=reply_msg.caption or "")
            elif reply_msg.document: await context.bot.send_document(user_data[0], reply_msg.document.file_id, caption=reply_msg.caption or "")
            elif reply_msg.text: await context.bot.send_message(user_data[0], text=reply_msg.text)
            else: await context.bot.send_message(user_data[0], text="📢 Объявление от администрации")
            success += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await update.message.reply_text(f"✅ Рассылка завершена!\n📨 Отправлено: {success}\n❌ Ошибок: {failed}")

async def broadcast_cancel_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    users = get_all_users()
    if not users: return await update.message.reply_text("⚠️ В базе нет пользователей!")
    await update.message.reply_text(f"📨 Начинаю отмену рассылки {len(users)} пользователям...")
    success, failed = 0, 0
    cancel_text = "⚠️ **ПРЕДЫДУЩЕЕ ОБЪЯВЛЕНИЕ ОТМЕНЕНО**\n\nПросим игнорировать предыдущее сообщение.\nПриносим извинения за неудобства."
    for user_data in users:
        try:
            await context.bot.send_message(chat_id=user_data[0], text=cancel_text, parse_mode='Markdown')
            success += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await update.message.reply_text(f"✅ Отмена рассылки завершена!\n📨 Отправлено: {success}\n❌ Ошибок: {failed}")

async def good_morning_job(context):
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT user_id, first_name FROM users WHERE is_verified = 1')
    users = c.fetchall()
    conn.close()
    success, failed = 0, 0
    for user_id, first_name in users:
        try:
            text = f"☀️ Доброе утро, {first_name}!\n\nНе забудь проверить расписание и домашние задания!\n\n👇 Быстрые команды:"
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=main_menu_keyboard())
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
    try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Утренняя рассылка завершена!\n📨 Успешно: {success}\n❌ Ошибок: {failed}")
    except: pass

async def send_later_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if not update.message.reply_to_message: return await update.message.reply_text("⚠️ Сначала ответь на сообщение, а потом напиши команду.")
    if len(context.args) < 2: return await update.message.reply_text("⚠️ Укажи дату и время! Пример: /send_later 31.08.2026 14:05")
    
    date_str, time_str = context.args[0], context.args[1]
    try:
        target_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        target_dt = TIMEZONE.localize(target_dt)
    except ValueError: return await update.message.reply_text("⚠️ Неверный формат! Используй: /send_later ДД.ММ.ГГГГ ЧЧ:ММ")
    
    now = datetime.datetime.now(TIMEZONE)
    if target_dt <= now: return await update.message.reply_text("⚠️ Время должно быть в будущем!")
    
    delay_seconds = (target_dt - now).total_seconds()
    msg = update.message.reply_to_message
    text = msg.text or msg.caption or ""
    file_type, file_id = None, None
    if msg.photo: file_type, file_id = 'photo', msg.photo[-1].file_id
    elif msg.video: file_type, file_id = 'video', msg.video.file_id
    elif msg.document: file_type, file_id = 'document', msg.document.file_id

    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('INSERT INTO scheduled_messages (text, file_type, file_id, caption, send_at) VALUES (%s, %s, %s, %s, %s) RETURNING id', (text, file_type, file_id, msg.caption, target_dt.strftime('%d.%m.%Y %H:%M')))
    msg_id = c.fetchone()[0]
    conn.commit(); conn.close()

    context.job_queue.run_once(send_scheduled_job, delay_seconds, data={'msg_id': msg_id})
    await update.message.reply_text(f"✅ Сообщение запланировано на {target_dt.strftime('%d.%m.%Y в %H:%M')}! ID: {msg_id}")

async def cancel_send_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if not context.args: return await update.message.reply_text("⚠️ Формат: /cancel_send [ID]\nПример: /cancel_send 5")
    try: msg_id = int(context.args[0])
    except ValueError: return await update.message.reply_text("⚠️ ID должен быть числом!")

    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT text, send_at FROM scheduled_messages WHERE id = %s', (msg_id,))
    msg_data = c.fetchone()
    if not msg_data: conn.close(); return await update.message.reply_text(f"❌ Запланированное сообщение с ID {msg_id} не найдено или уже было отправлено!")

    c.execute('DELETE FROM scheduled_messages WHERE id = %s', (msg_id,))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Запланированная рассылка ID {msg_id} успешно отменена!")

async def send_scheduled_job(context):
    msg_id = context.job.data['msg_id']
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT text, file_type, file_id, caption FROM scheduled_messages WHERE id = %s', (msg_id,))
    msg_data = c.fetchone()
    c.execute('DELETE FROM scheduled_messages WHERE id = %s', (msg_id,))
    conn.commit(); conn.close()
    if not msg_data: return
    
    text, file_type, file_id, caption = msg_data
    users = get_all_users()
    for user_data in users:
        try:
            if file_type == 'photo': await context.bot.send_photo(user_data[0], file_id, caption=caption or text)
            elif file_type == 'video': await context.bot.send_video(user_data[0], file_id, caption=caption or text)
            elif file_type == 'document': await context.bot.send_document(user_data[0], file_id, caption=caption or text)
            else: await context.bot.send_message(user_data[0], text=text)
            await asyncio.sleep(0.05)
        except Exception as e: print(f"Ошибка отправки: {e}")
    await context.bot.send_message(ADMIN_ID, f"✅ Отложенная рассылка ID {msg_id} успешно отправлена!")

# ==================== ГОЛОСОВАНИЯ ====================
async def create_poll_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if len(context.args) < 3: return await update.message.reply_text("⚠️ Формат: /create_poll Вопрос Вариант1 Вариант2 ...")
    question, options = context.args[0], context.args[1:]
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('INSERT INTO polls (question, options, creator_id, created_at) VALUES (%s, %s, %s, %s) RETURNING id',
              (question, '|'.join(options), update.effective_user.id, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
    poll_id = c.fetchone()[0]
    conn.commit(); conn.close()
    
    keyboard = [[InlineKeyboardButton(f"🔹 {opt.replace('_', ' ')}", callback_data=f'vote_{poll_id}_{i}')] for i, opt in enumerate(options)]
    keyboard.append([InlineKeyboardButton("📊 Результаты", callback_data=f'results_{poll_id}')])
    keyboard.append([InlineKeyboardButton("📢 Отправить всем", callback_data=f'publish_poll_{poll_id}')])
    await update.message.reply_text(f"🗳️ Новое голосование!\n\n❓ {question.replace('_', ' ')}\n\nВыбери вариант:", reply_markup=InlineKeyboardMarkup(keyboard))

async def poll_results_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    if not context.args: return await update.message.reply_text("⚠️ Формат: /poll_results [ID]")
    try: poll_id = int(context.args[0])
    except: return await update.message.reply_text("⚠️ ID должен быть числом!")
    
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT question, options, created_at FROM polls WHERE id = %s', (poll_id,))
    poll = c.fetchone()
    if not poll: conn.close(); return await update.message.reply_text(f"❌ Голосование #{poll_id} не найдено!")
    
    question, options_str, created_at = poll
    options = options_str.split('|')
    c.execute('SELECT pv.option_index, u.first_name, u.username, u.group_name FROM poll_votes pv JOIN users u ON pv.user_id = u.user_id WHERE pv.poll_id = %s ORDER BY pv.option_index', (poll_id,))
    votes = c.fetchall()
    vote_counts = {i: 0 for i in range(len(options))}
    for vote in votes: vote_counts[vote[0]] = vote_counts.get(vote[0], 0) + 1
    total_votes = len(votes)
    conn.close()
    
    text = f"📊 РЕЗУЛЬТАТЫ ГОЛОСОВАНИЯ #{poll_id}\n\nВопрос: {question.replace('_', ' ')}\nСоздано: {created_at}\nВсего голосов: {total_votes}\n\n"
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

async def poll_history_command(update: Update, context):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("⛔ Только для админа!")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT id, question, options, created_at, is_active FROM polls ORDER BY created_at DESC LIMIT 20')
    polls = c.fetchall(); conn.close()
    if not polls: return await update.message.reply_text("🗳️ Нет голосований")
    
    text = "🗳️ ИСТОРИЯ ГОЛОСОВАНИЙ (последние 20)\n\n"
    for pid, q, opts, created, active in polls:
        options = opts.split('|')
        status = "✅ Активно" if active == 1 else "🔴 Завершено"
        conn2 = psycopg.connect(os.environ.get('DATABASE_URL'))
        c2 = conn2.cursor()
        c2.execute('SELECT COUNT(*) FROM poll_votes WHERE poll_id = %s', (pid,))
        vcount = c2.fetchone()[0]
        conn2.close()
        text += f"#{pid} ({status})\n{q.replace('_', ' ')}\n📅 {created} | 👥 {vcount} голосов\nВарианты: {', '.join([o.replace('_', ' ') for o in options[:3]])}\nДетали: /poll_results {pid}\n\n" + "-" * 40 + "\n\n"
    await update.message.reply_text(text)

# ==================== ФУНКЦИЯ ПУБЛИКАЦИИ В КАНАЛ ====================
async def publish_to_channel(context, anon_id):
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('SELECT group_name, message, recipient_type FROM anon_messages WHERE id = %s', (anon_id,))
    anon = c.fetchone()
    conn.close()
    if not anon: return False, "❌ Сообщение не найдено"
    group_name, message_text, recipient_type = anon
    channel_text = f"💬 Анонимное сообщение\n\n{message_text}\n\n🕐 {datetime.datetime.now(TIMEZONE).strftime('%H:%M %d.%m.%Y')}"
    try:
        msg = await context.bot.send_message(chat_id=ANON_CHANNEL_ID, text=channel_text)
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('UPDATE anon_messages SET channel_message_id = %s WHERE id = %s', (msg.message_id, anon_id))
        conn.commit(); conn.close()
        return True, f"✅ Опубликовано в канале!"
    except Exception as e:
        return False, f"❌ Ошибка публикации: {e}"

# ==================== ОБРАБОТЧИК КНОПОК ====================
async def button_handler(update: Update, context):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == 'back_to_menu':
        context.user_data.clear()
        await query.edit_message_text("👇 Выбери действие:", reply_markup=main_menu_keyboard())
        return

    if data.startswith('setgroup_'):
        group_name = data.replace('setgroup_', '')
        if context.user_data.get('reg_step') == 'waiting_group':
            context.user_data['reg_group'] = group_name
            context.user_data['reg_step'] = 'waiting_phone'
            keyboard = [[KeyboardButton("📱 Поделиться номером телефона", request_contact=True)]]
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("✅ Группа выбрана!\n\nШаг 3: Нажми на кнопку ниже, чтобы подтвердить номер телефона.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
            return
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('UPDATE users SET group_name = %s WHERE user_id = %s', (group_name, query.from_user.id))
        conn.commit(); conn.close()
        await query.edit_message_text(f"✅ Группа установлена: {group_name}", reply_markup=main_menu_keyboard())
        return

    elif data == 'schedule':
        group = get_user_group(query.from_user.id)
        if not group: text = "⚠️ Сначала укажи группу!"
        else:
            conn = psycopg.connect(os.environ.get('DATABASE_URL'))
            c = conn.cursor()
            c.execute("SELECT time, subject, teacher, room FROM schedule WHERE (group_name = %s OR group_name = 'ОБЩЕЕ') AND day = %s ORDER BY time", (group, get_day_name()))
            schedule = c.fetchall(); conn.close()
            if not schedule: text = f"📅 На сегодня ({get_day_name()}) пар нет! 🎉"
            else:
                text = f"🗓️ Расписание на {get_day_name()}\n👥 {group}\n\n"
                for i, (time, subj, teach, room) in enumerate(schedule, 1): text += f"{i}. {time} - {subj}\n   👨‍🏫 {teach} | 🚪 {room}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗓️ На неделю", callback_data='schedule_week')], [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]]))
        return

    elif data == 'schedule_week':
        group = get_user_group(query.from_user.id)
        if not group: text = "⚠️ Сначала укажи группу!"
        else:
            conn = psycopg.connect(os.environ.get('DATABASE_URL'))
            c = conn.cursor()
            c.execute("SELECT day, time, subject, teacher, room FROM schedule WHERE (group_name = %s OR group_name = 'ОБЩЕЕ') ORDER BY CASE day WHEN 'Понедельник' THEN 1 WHEN 'Вторник' THEN 2 WHEN 'Среда' THEN 3 WHEN 'Четверг' THEN 4 WHEN 'Пятница' THEN 5 WHEN 'Суббота' THEN 6 WHEN 'Воскресенье' THEN 7 END, time", (group,))
            schedule = c.fetchall(); conn.close()
            if not schedule: text = f"📅 Расписание для {group} пока не добавлено."
            else:
                text = f"📅 Расписание на неделю\n👥 {group}\n\n"
                cur_day = None
                for day, time, subj, teach, room in schedule:
                    if day != cur_day: text += f"\n📌 {day}:\n"; cur_day = day
                    text += f"  • {time} - {subj} ({teach}, ауд. {room})\n"
        await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data == 'homework':
        group = get_user_group(query.from_user.id)
        if not group: text = "⚠️ Сначала укажи группу!"
        else:
            conn = psycopg.connect(os.environ.get('DATABASE_URL'))
            c = conn.cursor()
            c.execute("SELECT subject, task, deadline FROM homework WHERE (group_name = %s OR group_name = 'ОБЩЕЕ') ORDER BY created_at DESC", (group,))
            hw = c.fetchall(); conn.close()
            if not hw: text = f"📝 Домашних заданий для {group} пока нет!"
            else:
                text = f"📝 Домашние задания\n👥 {group}\n\n"
                for subj, task, dead in hw: text += f"📚 {subj}\n   📝 {task}\n   ⏰ {dead}\n\n"
        await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data == 'anon_chat':
        group = get_user_group(query.from_user.id)
        if not group:
            await query.edit_message_text("⚠️ Сначала укажи свою группу в Настройках!", reply_markup=back_button())
        else:
            context.user_data['waiting_for_anon'] = True
            context.user_data['anon_recipient'] = 'all'
            await query.edit_message_text(f"💬 Анонимный чат\n\n📢 Канал: {ANON_CHANNEL_LINK}\n\n⚠️ ПРАВИЛА:\n• Только для учебы\n• Все сообщения проходят модерацию\n\nНапиши своё сообщение следующим текстом.", reply_markup=back_button())
        return

    elif data.startswith('approve_anon_'):
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Только для админа!", show_alert=True)
        anon_id = int(data.split('_')[2])
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute("UPDATE anon_messages SET status = 'approved', moderated_at = %s WHERE id = %s", (datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M'), anon_id))
        conn.commit(); conn.close()
        success, result_msg = await publish_to_channel(context, anon_id)
        await query.edit_message_text(f"{result_msg}\n\nID сообщения: {anon_id}", reply_markup=back_button())
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('SELECT user_id FROM anon_messages WHERE id = %s', (anon_id,))
        anon = c.fetchone(); conn.close()
        if anon:
            try: await context.bot.send_message(chat_id=anon[0], text="✅ Твоё анонимное сообщение одобрено и опубликовано!")
            except: pass
        return

    elif data.startswith('reject_anon_'):
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Только для админа!", show_alert=True)
        anon_id = int(data.split('_')[2])
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute("UPDATE anon_messages SET status = 'rejected', moderated_at = %s WHERE id = %s", (datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M'), anon_id))
        conn.commit(); conn.close()
        await query.edit_message_text(f"❌ Сообщение ID {anon_id} отклонено.", reply_markup=back_button())
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('SELECT user_id FROM anon_messages WHERE id = %s', (anon_id,))
        anon = c.fetchone(); conn.close()
        if anon:
            try: await context.bot.send_message(chat_id=anon[0], text="❌ Твоё анонимное сообщение отклонено администратором.")
            except: pass
        return

    elif data == 'admin':
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Доступ запрещен!", show_alert=True)
        await query.edit_message_text("👨‍💼 Админ-панель\n\nВыбери раздел:", reply_markup=admin_panel_keyboard())
        return

    elif data == 'admin_moderation':
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Доступ запрещен!", show_alert=True)
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute("SELECT id, first_name, username, group_name, message, recipient_type, created_at FROM anon_messages WHERE status = 'pending' ORDER BY created_at DESC")
        pending = c.fetchall(); conn.close()
        if not pending: return await query.edit_message_text("📥 Модерация\n\n✅ Нет сообщений на рассмотрении!", reply_markup=admin_panel_keyboard())
        
        text = f"📥 Модерация\n\n🔴 Сообщений на рассмотрении: {len(pending)}\n\n"
        keyboard = []
        for anon_id, first_name, username, group_name, message, recipient_type, created_at in pending:
            text += f"\n📌 ID {anon_id} ({created_at})\n👤 {first_name}"
            if username and username != "нет": text += f" (@{username})"
            text += f"\n📤 Кому: 🌍 Всем студентам\n💬 {message[:100]}{'...' if len(message) > 100 else ''}\n"
            keyboard.append([InlineKeyboardButton(f"✅ Одобрить #{anon_id}", callback_data=f'approve_anon_{anon_id}'), InlineKeyboardButton(f"❌ Отклонить #{anon_id}", callback_data=f'reject_anon_{anon_id}')])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data == 'admin_moderation_history':
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Доступ запрещен!", show_alert=True)
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute("SELECT id, first_name, group_name, message, recipient_type, status, created_at, moderated_at FROM anon_messages WHERE status != 'pending' ORDER BY moderated_at DESC LIMIT 20")
        history = c.fetchall(); conn.close()
        if not history: return await query.edit_message_text("📋 История модерации\n\nИстория пуста.", reply_markup=admin_panel_keyboard())
        
        text = "📋 История модерации (последние 20)\n\n"
        for anon_id, first_name, group_name, message, recipient_type, status, created_at, moderated_at in history:
            emoji = "✅" if status == "approved" else "❌"
            status_text = "одобрено" if status == "approved" else "отклонено"
            text += f"{emoji} ID {anon_id} | {first_name} | 🌍 Всем\n   💬 {message[:80]}{'...' if len(message) > 80 else ''}\n   📅 {created_at} → {status_text} {moderated_at}\n\n"
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data == 'admin_stats':
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Доступ запрещен!", show_alert=True)
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users'); total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM anon_messages WHERE status = 'pending'"); pending_anon = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM anon_messages WHERE status = 'approved'"); approved_anon = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM anon_messages WHERE status = 'rejected'"); rejected_anon = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM schedule'); total_schedule = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM homework'); total_homework = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM questions WHERE status = 'new'"); new_questions = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM questions'); total_questions = c.fetchone()[0]
        conn.close()
        text = (f"📊 Статистика бота\n\n👥 Пользователи:\n   Всего зарегистрировано: {total_users}\n\n💬 Анонимный чат:\n   ✅ Одобрено: {approved_anon}\n   ❌ Отклонено: {rejected_anon}\n   ⏳ На модерации: {pending_anon}\n\n📅 Расписание:\n   Всего пар: {total_schedule}\n\n📝 Домашние задания:\n   Всего домашек: {total_homework}\n\n❓ Вопросы:\n   Всего: {total_questions}\n   🆕 Новых: {new_questions}")
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data == 'admin_help':
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Доступ запрещен!", show_alert=True)
        text = ("📖 Справка по админ-командам\n\n"
                "📅 Расписание:\n• /upload_schedule (отправить CSV файл)\n• /add_schedule [ГРУППА] ДЕНЬ ВРЕМЯ ПРЕДМЕТ ПРЕПОД АУД\n• /view_schedule\n• /delete_schedule [ID]\n\n"
                "📝 Домашка:\n• /add_homework ГРУППА ПРЕДМЕТ ЗАДАНИЕ [До дедлайн]\n• /view_homework\n• /delete_homework [ID]\n\n"
                "📨 Рассылка:\n• Ответь на сообщение: /broadcast\n• /send_later ДД.ММ.ГГГГ ЧЧ:ММ\n• /cancel_send [ID]\n\n"
                "👥 Пользователи:\n• /export_users - выгрузить базу в Excel\n• /edit_user [ID] fio/group/phone [значение]\n• /delete_user [ID]\n• /active_users [дней]\n• /inactive_users [дней]\n\n"
                "🗳️ Голосование:\n• /create_poll Вопрос Вариант1 Вариант2 ...\n• /poll_history\n• /poll_results [ID]")
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data == 'admin_questions':
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Доступ запрещен!", show_alert=True)
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute("SELECT id, user_id, question, date FROM questions WHERE status = 'new' ORDER BY date DESC LIMIT 10")
        questions = c.fetchall(); conn.close()
        if not questions: return await query.edit_message_text("❓ Новых вопросов нет!", reply_markup=admin_panel_keyboard())
        
        text = "❓ Новые вопросы:\n\n"
        for q_id, user_id, question, date in questions:
            conn2 = psycopg.connect(os.environ.get('DATABASE_URL'))
            c2 = conn2.cursor()
            c2.execute('SELECT first_name, group_name FROM users WHERE user_id = %s', (user_id,))
            user = c2.fetchone(); conn2.close()
            user_name = user[0] if user else "Неизвестно"
            user_group = user[1] if user and user[1] else "Группа не указана"
            text += f"🔹 ID: {q_id}\n👤 {user_name} ({user_group})\n📅 {date}\n💬 {question}\n\n"
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())
        return

    elif data.startswith('vote_'):
        parts = data.split('_')
        poll_id, option_index = parts[1], int(parts[2])
        user_id = query.from_user.id
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('SELECT id FROM poll_votes WHERE poll_id = %s AND user_id = %s', (poll_id, user_id))
        if c.fetchone(): conn.close(); return await query.answer("⚠️ Ты уже голосовал!", show_alert=True)
        c.execute('INSERT INTO poll_votes (poll_id, user_id, option_index) VALUES (%s, %s, %s)', (poll_id, user_id, option_index))
        conn.commit(); conn.close()
        await query.answer("✅ Твой голос принят!", show_alert=True)
        return

    elif data.startswith('publish_poll_'):
        if query.from_user.id != ADMIN_ID: return await query.answer("⛔ Только для админа!", show_alert=True)
        poll_id = data.split('_')[2]
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('SELECT question, options FROM polls WHERE id = %s', (poll_id,))
        poll = c.fetchone(); conn.close()
        if not poll: return await query.answer("Опрос не найден", show_alert=True)
        
        question, options_str = poll
        options = options_str.split('|')
        keyboard = [[InlineKeyboardButton(f"🔹 {opt.replace('_', ' ')}", callback_data=f'vote_{poll_id}_{i}')] for i, opt in enumerate(options)]
        keyboard.append([InlineKeyboardButton("📊 Результаты", callback_data=f'results_{poll_id}')])
        text = f"🗳️ Голосование!\n\n❓ {question.replace('_', ' ')}\n\nВыбери вариант:"
        reply_markup = InlineKeyboardMarkup(keyboard)
        users = get_all_users()
        
        await query.edit_message_text(f"📨 Начинаю рассылку голосования {len(users)} студентам...")
        success = 0
        for user_data in users:
            try:
                await context.bot.send_message(chat_id=user_data[0], text=text, reply_markup=reply_markup)
                success += 1
                await asyncio.sleep(0.3)
            except: pass
        await query.edit_message_text(f"✅ Голосование успешно отправлено {success} студентам!")
        return

    elif data.startswith('results_'):
        poll_id = data.split('_')[1]
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('SELECT question, options FROM polls WHERE id = %s', (poll_id,))
        poll = c.fetchone()
        if not poll: conn.close(); return await query.answer("Опрос не найден", show_alert=True)
        
        question, options_str = poll
        options = options_str.split('|')
        c.execute('SELECT option_index, COUNT(*) FROM poll_votes WHERE poll_id = %s GROUP BY option_index', (poll_id,))
        votes = dict(c.fetchall()); total_votes = sum(votes.values())
        conn.close()
        
        text = f"📊 Результаты: {question.replace('_', ' ')}\n\n"
        for i, option in enumerate(options):
            count = votes.get(i, 0)
            percent = (count / total_votes * 100) if total_votes > 0 else 0
            text += f"🔹 {option.replace('_', ' ')}: {count} голосов ({percent:.1f}%)\n"
        text += f"\n👥 Всего проголосовало: {total_votes}"
        await query.edit_message_text(text, reply_markup=back_button())
        return

    elif data == 'profile':
        user_id = query.from_user.id
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('SELECT first_name, username, group_name, full_name, phone, is_verified, last_active FROM users WHERE user_id = %s', (user_id,))
        user = c.fetchone(); conn.close()
        if not user: text = "⚠️ Ты не зарегистрирован в системе.\n\nНапиши /start."
        else:
            first_name, username, group_name, full_name, phone, is_verified, last_active = user
            status = "✅ Подтвержден" if is_verified == 1 else "⏳ Ожидает подтверждения"
            text = (f"👤 **Твой профиль**\n\n"
                    f"📛 **Имя:** {first_name}\n🔗 **Username:** @{username or 'не указан'}\n"
                    f"👥 **Группа:** {group_name or 'не указана'}\n📝 **ФИО:** {full_name or 'не указано'}\n"
                    f"📞 **Телефон:** {phone or 'не указан'}\n🔐 **Статус:** {status}\n"
                    f"🕐 **Последняя активность:** {last_active or 'никогда'}")
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode='Markdown')
        return

    elif data == 'contacts_info':
        await query.edit_message_text("📍 Контакты НК\n👩‍💼 Директор: Кузьминская Ю.Б.\n🏢 г. Москва, ул. 3-я Хорошевская, д. 2, стр. 1\n📞 +7 (495) 568-07-07", reply_markup=back_button(), parse_mode='Markdown')
        return
    elif data == 'practice_info':
        await query.edit_message_text("💼 Партнеры по практике:\n🏛️ ФНС\n🏦 Сбербанк, МКБ, УРАЛСИБ\n⚖️ Департамент труда и соцзащиты г. Москвы", reply_markup=back_button(), parse_mode='Markdown')
        return
    elif data in ['grades', 'gpa', 'teachers', 'news', 'weather', 'exams', 'attendance', 'rooms', 'reminders', 'conspekts']:
        await query.edit_message_text("⚙️ Этот раздел в разработке или пуст.", reply_markup=back_button())
        return
    elif data == 'help':
        await query.edit_message_text("🆘 Помощь\n\n📱 /start - Главное меню\n📱 /setgroup [ГРУППА] - Выбрать группу\n❓ /anon_chat - Задать вопрос", reply_markup=back_button())
        return
    
    await query.edit_message_text("⚙️ В разработке.", reply_markup=back_button())

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================
async def handle_message(update: Update, context):
    if context.user_data.get('reg_step') == 'waiting_full_name':
        context.user_data['reg_full_name'] = update.message.text.strip()
        context.user_data['reg_step'] = 'waiting_group'
        await update.message.reply_text("✅ ФИО принято!\n\nШаг 2: Выбери свою группу:", reply_markup=groups_keyboard())
        return

    if update.message.contact and context.user_data.get('reg_step') == 'waiting_phone':
        phone = update.message.contact.phone_number
        group_name = context.user_data.get('reg_group')
        full_name = context.user_data.get('reg_full_name')
        if not group_name or not full_name:
            return await update.message.reply_text("⚠️ Ошибка. Начни с /start", reply_markup=ReplyKeyboardRemove())
        
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('''INSERT INTO users (user_id, first_name, username, full_name, phone, group_name, is_verified)
                     VALUES (%s, %s, %s, %s, %s, %s, 1)
                     ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name, phone=excluded.phone, group_name=excluded.group_name, is_verified=1''',
                  (update.effective_user.id, update.effective_user.first_name, update.effective_user.username, full_name, phone, group_name))
        conn.commit(); conn.close()
        context.user_data.clear()
        await update.message.reply_text(f"✅ Регистрация завершена!\n👤 {full_name}\n👥 {group_name}", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text("👇 Выбери действие:", reply_markup=main_menu_keyboard())
        
        log_text = f"🆕 **Новая регистрация!**\n🆔 ID: `{update.effective_user.id}`\n👤 ФИО: {full_name}\n📞 Телефон: {phone}\n👥 Группа: {group_name}"
        try: await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode='Markdown')
        except: pass
        return

    if context.user_data.get('waiting_for_anon'):
        context.user_data['waiting_for_anon'] = False
        group = get_user_group(update.effective_user.id)
        if not group: return await update.message.reply_text("⚠️ Сначала укажи группу!", reply_markup=main_menu_keyboard())
        
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute("INSERT INTO anon_messages (user_id, first_name, username, group_name, message, recipient_type, status, created_at) VALUES (%s, %s, %s, %s, %s, 'all', 'pending', %s) RETURNING id",
                  (update.effective_user.id, update.effective_user.first_name, update.effective_user.username or "нет", group, update.message.text, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
        anon_id = c.fetchone()[0]
        conn.commit(); conn.close()
        
        await update.message.reply_text(f"✅ Отправлено на модерацию! ID: {anon_id}", reply_markup=main_menu_keyboard())
        admin_msg = f"📥 НОВОЕ СООБЩЕНИЕ\n🆔 ID: {anon_id}\n👤 {update.effective_user.first_name}\n👥 {group}\n💬 {update.message.text}"
        keyboard = [[InlineKeyboardButton("✅ Одобрить", callback_data=f'approve_anon_{anon_id}')], [InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_anon_{anon_id}')]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if context.user_data.get('waiting_for_question'):
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('INSERT INTO questions (user_id, question, date) VALUES (%s, %s, %s)',
                  (update.effective_user.id, update.message.text, datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')))
        conn.commit(); conn.close()
        context.user_data['waiting_for_question'] = False
        
        user_link = f"tg://user?id={update.effective_user.id}"
        admin_msg = f"❓ **Новый вопрос**\n🆔 ID: `{update.effective_user.id}`\n👤 {update.effective_user.first_name}\n🔗 [{update.effective_user.username or 'нет'}]({user_link})\n👥 {get_user_group(update.effective_user.id) or 'не указана'}\n\n💬 **Вопрос:**\n{update.message.text}"
        try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode='Markdown')
        except: pass
        await update.message.reply_text("✅ Вопрос отправлен админу!", reply_markup=main_menu_keyboard())
        return

    if update.message.text.lower().startswith('/setgroup'):
        parts = update.message.text.split(' ', 1)
        if len(parts) < 2: return await update.message.reply_text("⚠️ Пример: /setgroup 1Ю1/925o")
        group_name = parts[1].strip()
        if group_name not in GROUPS: return await update.message.reply_text(f"⚠️ Группа '{group_name}' не найдена!")
        conn = psycopg.connect(os.environ.get('DATABASE_URL'))
        c = conn.cursor()
        c.execute('INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING', (update.effective_user.id, update.effective_user.first_name, update.effective_user.username))
        c.execute('UPDATE users SET group_name = %s WHERE user_id = %s', (group_name, update.effective_user.id))
        conn.commit(); conn.close()
        await update.message.reply_text(f"✅ Группа установлена: {group_name}", reply_markup=main_menu_keyboard())
        return

    text_lower = update.message.text.lower()
    if 'привет' in text_lower:
        await update.message.reply_text(f"👋 Привет, {update.effective_user.first_name}!", reply_markup=main_menu_keyboard())
    elif 'спасибо' in text_lower:
        await update.message.reply_text("😊 Пожалуйста!")
    else:
        await update.message.reply_text("Используй кнопки или /help", reply_markup=main_menu_keyboard())

# ==================== КОМАНДЫ МЕНЮ ====================
async def setgroup_command(update: Update, context):
    if not context.args: return await update.message.reply_text("⚠️ Пример: /setgroup 1Ю1/925o")
    group_name = context.args[0].strip()
    if group_name not in GROUPS: return await update.message.reply_text(f"⚠️ Группа '{group_name}' не найдена!")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute('INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING', (update.effective_user.id, update.effective_user.first_name, update.effective_user.username))
    c.execute('UPDATE users SET group_name = %s WHERE user_id = %s', (group_name, update.effective_user.id))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Отлично! Твоя группа теперь: {group_name}", reply_markup=main_menu_keyboard())

async def schedule_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group: return await update.message.reply_text("⚠️ Сначала выбери группу командой /setgroup")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute("SELECT time, subject, teacher, room FROM schedule WHERE (group_name = %s OR group_name = 'ОБЩЕЕ') AND day = %s ORDER BY time", (group, get_day_name()))
    schedule = c.fetchall(); conn.close()
    if not schedule: text = f"📅 На сегодня ({get_day_name()}) пар нет! 🎉"
    else:
        text = f"📅 Расписание на {get_day_name()}\n👥 {group}\n\n"
        for i, (time, subj, teach, room) in enumerate(schedule, 1): text += f"{i}. {time} - {subj}\n   👨‍🏫 {teach} | 🚪 {room}\n"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def schedule_week_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group: return await update.message.reply_text("⚠️ Сначала выбери группу командой /setgroup")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute("SELECT day, time, subject, teacher, room FROM schedule WHERE (group_name = %s OR group_name = 'ОБЩЕЕ') ORDER BY CASE day WHEN 'Понедельник' THEN 1 WHEN 'Вторник' THEN 2 WHEN 'Среда' THEN 3 WHEN 'Четверг' THEN 4 WHEN 'Пятница' THEN 5 WHEN 'Суббота' THEN 6 WHEN 'Воскресенье' THEN 7 END, time", (group,))
    schedule = c.fetchall(); conn.close()
    if not schedule: text = f"📅 Расписание для {group} пока не добавлено."
    else:
        text = f"📅 Расписание на неделю\n👥 {group}\n\n"
        cur_day = None
        for day, time, subj, teach, room in schedule:
            if day != cur_day: text += f"\n📌 {day}:\n"; cur_day = day
            text += f"  • {time} - {subj} ({teach}, ауд. {room})\n"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def homework_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group: return await update.message.reply_text("⚠️ Сначала выбери группу командой /setgroup")
    conn = psycopg.connect(os.environ.get('DATABASE_URL'))
    c = conn.cursor()
    c.execute("SELECT subject, task, deadline FROM homework WHERE (group_name = %s OR group_name = 'ОБЩЕЕ') ORDER BY created_at DESC", (group,))
    hw = c.fetchall(); conn.close()
    if not hw: text = f"📝 Домашних заданий для {group} пока нет!"
    else:
        text = f"📝 Домашние задания\n👥 {group}\n\n"
        for subj, task, dead in hw: text += f"📚 {subj}\n   📝 {task}\n   ⏰ {dead}\n\n"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def grades_command(update: Update, context): await update.message.reply_text("📊 Оценок пока нет.", reply_markup=main_menu_keyboard())
async def gpa_command(update: Update, context): await update.message.reply_text("🧮 Оценок пока нет.", reply_markup=main_menu_keyboard())
async def teachers_command(update: Update, context): await update.message.reply_text("👨‍🏫 Список преподавателей пока пуст.", reply_markup=main_menu_keyboard())
async def exams_command(update: Update, context): await update.message.reply_text("🎓 Экзаменов пока не запланировано.", reply_markup=main_menu_keyboard())
async def news_command(update: Update, context): await update.message.reply_text("📰 Новостей пока нет.", reply_markup=main_menu_keyboard())
async def weather_command(update: Update, context):
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast?latitude=55.75&longitude=37.61&current_weather=true")
        d = r.json()['current_weather']
        text = f"🌤️ Погода в Москве\n🌡️ {d['temperature']}°C\n💨 Ветер: {d['windspeed']} км/ч"
    except: text = "❌ Не удалось получить погоду."
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def contacts_command(update: Update, context):
    text = "📍 Контакты НК\n👩‍💼 Директор: Кузьминская Ю.Б.\n🏢 г. Москва, ул. 3-я Хорошевская, д. 2, стр. 1\n📞 +7 (495) 568-07-07"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def practice_command(update: Update, context):
    text = "💼 Партнеры по практике:\n🏛️ ФНС\n🏦 Сбербанк, МКБ, УРАЛСИБ\n⚖️ Департамент труда и соцзащиты г. Москвы"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def help_command(update: Update, context):
    text = ("🆘 Помощь\n\n📱 Основные команды:\n• /start - Главное меню\n• /setgroup [ГРУППА] - Выбрать группу\n• /schedule - Расписание на день\n• /schedule_week - Расписание на неделю\n• /homework - Домашние задания\n• /grades - Оценки\n• /gpa - Средний балл\n• /teachers - Преподаватели\n• /exams - Экзамены\n• /news - Новости\n• /weather - Погода\n• /contacts - Контакты колледжа\n• /practice - Практика\n• /anon_chat - Анонимный чат\n\n❓ Вопросы:\n• Напиши свой вопрос, и он уйдет администратору\n\n⚙️ Настройки:\n• /setgroup - выбрать или изменить группу")
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def anon_chat_command(update: Update, context):
    group = get_user_group(update.effective_user.id)
    if not group: return await update.message.reply_text("⚠️ Сначала выбери группу командой /setgroup\n\nБез группы анонимный чат не работает.", reply_markup=main_menu_keyboard())
    context.user_data['waiting_for_anon'] = True
    context.user_data['anon_recipient'] = 'all'
    text = f"💬 Анонимный чат\n\n📢 Канал: {ANON_CHANNEL_LINK}\n\n⚠️ ПРАВИЛА:\n• Только для учебы\n• Все сообщения проходят модерацию\n\nНапиши своё сообщение следующим текстом."
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

# ==================== FLASK СЕРВЕР (ДЛЯ RENDER) ====================
web_app = Flask('')
@web_app.route('/')
def home(): return "Бот работает!"
def run_flask(): web_app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==================== ЗАПУСК ====================
def main():
    init_db()
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).job_queue(JobQueue()).build()
    
    # Утренняя рассылка в 07:00 (Пн-Сб)
    app.job_queue.run_daily(good_morning_job, time=datetime.time(hour=7, minute=0, tzinfo=TIMEZONE), days=(0, 1, 2, 3, 4, 5))
    print("⏰ Утренняя рассылка запланирована на 07:00 (Пн-Сб)")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("export_users", export_users_command))
    app.add_handler(CommandHandler("edit_user", edit_user_command))
    app.add_handler(CommandHandler("delete_user", delete_user_command))
    app.add_handler(CommandHandler("active_users", active_users_command))
    app.add_handler(CommandHandler("inactive_users", inactive_users_command))
    app.add_handler(CommandHandler("upload_schedule", upload_schedule_command))
    app.add_handler(CommandHandler("add_schedule", add_schedule_command))
    app.add_handler(CommandHandler("view_schedule", view_schedule_command))
    app.add_handler(CommandHandler("delete_schedule", delete_schedule_command))
    app.add_handler(CommandHandler("add_homework", add_homework_command))
    app.add_handler(CommandHandler("view_homework", view_homework_command))
    app.add_handler(CommandHandler("delete_homework", delete_homework_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("broadcast_cancel", broadcast_cancel_command))
    app.add_handler(CommandHandler("send_later", send_later_command))
    app.add_handler(CommandHandler("cancel_send", cancel_send_command))
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
    
    app.add_handler(CallbackQueryHandler(button_handler))
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
