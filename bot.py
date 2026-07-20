from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import db
import os
import re
import sqlite3
import datetime
from dotenv import load_dotenv
from tzlocal import get_localzone

# Завантаження конфігурації
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DEFAULT_INFO_TEXT = (
    "👋 <b>Вітаємо в нашому медичному чат-боті!</b>\n\n"
    "Шановні вихователі, цей бот створений для того, щоб зробити координацію медичних процедур зручною та ефективною.\n\n"
    "📋 <b>Ваші основні завдання як відповідальних за медичний корпус:</b>\n"
    "1. <b>Ознайомлення з графіком:</b> Тут ви зможете щодня перевіряти актуальний розклад медичних процедур для своїх груп протягом усієї табірної зміни.\n"
    "2. <b>Своєчасність:</b> Ваша головна задача — вчасно приводити необхідну кількість відпочиваючих на відповідні процедури.\n"
    "3. <b>Реакція на завдання:</b> Будь ласка, оперативно та чітко реагуйте на всі сповіщення та вказівки.\n\n"
    "⚠️ <b>Важливі правила:</b>\n"
    "• 📅 <b>Графік може змінюватися!</b> У зв'язку з екскурсіями, заходами та іншими активностями розклад процедур може коригуватися.\n"
    "• 📱 <b>Будьте завжди на зв'язку!</b> Найголовніше правило — тримати телефон увімкненим, бути в режимі <b>ONLINE</b> та оперативно реагувати на повідомлення.\n\n"
    "👑 <b>Контроль процесу:</b>\n"
    "Весь процес курує та контролює закріплений адміністратор медпункту, який завжди готовий допомогти та скоригувати дії.\n\n"
    "Дякуємо за вашу відповідальність та турботу про здоров'я дітей! ❤️✨"
)

# Ініціалізація бази даних
db.init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id == ADMIN_ID:
        keyboard = [
            ["📅 Графік", "📅 Актуальний графік на сьогодні"],
            ["📢 Виклик групи", "📊 Статус груп"],
            ["ℹ️ Інформація", "⚙️ Адмін-панель"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🏥 Вітаємо в панелі адміністратора!",
            reply_markup=reply_markup
        )
    else:
        # Перевіряємо, чи зареєстрований користувач
        user = db.get_user(user_id)
        if user:
            keyboard = [
                ["📅 Графік", "ℹ️ Інформація"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "🏥 Ласкаво просимо до медпункту!",
                reply_markup=reply_markup
            )
        else:
            # Якщо користувач новий, показуємо вибір групи
            keyboard = [
                ["Група 1", "Група 2"],
                ["Група 3", "Група 4"],
                ["Група 5", "Група 6"],
                ["Група 7", "Група 8"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Вітаємо! Будь ласка, оберіть вашу групу для реєстрації:",
                reply_markup=reply_markup
            )
async def send_call_to_educators(context, group_num: int, proc: str, count: str):
    users_by_group = db.get_all_users_grouped()
    group_users = users_by_group.get(group_num, [])
    
    proc_display = proc.replace("_", "/")
    
    keyboard = [
        [
            InlineKeyboardButton("🚶 Ведемо", callback_data=f"edu_resp:{group_num}:{proc}:{count}:yes"),
            InlineKeyboardButton("⏱️ Будемо за пару хв", callback_data=f"edu_resp:{group_num}:{proc}:{count}:soon")
        ],
        [
            InlineKeyboardButton("❌ Не ведемо", callback_data=f"edu_resp:{group_num}:{proc}:{count}:no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent_count = 0
    for u in group_users:
        try:
            await context.bot.send_message(
                chat_id=u['user_id'],
                text=(
                    f"🚨 <b>УВАГА! Терміновий виклик на процедуру!</b> 🚨\n\n"
                    f"💆 <b>Процедура:</b> {proc_display}\n"
                    f"👥 <b>Необхідна кількість відпочиваючих:</b> {count}\n\n"
                    f"Будь ласка, оберіть варіант відповіді нижче 👇"
                ),
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception as e:
            print(f"Error sending message to {u['user_id']}: {e}")
            
    return sent_count

async def notify_group_educators(context, group_num: int, message_text: str):
    """Надіслати текстове сповіщення всім вихователям вказаної групи."""
    users_by_group = db.get_all_users_grouped()
    group_users = users_by_group.get(group_num, [])
    sent_count = 0
    for u in group_users:
        try:
            await context.bot.send_message(
                chat_id=u['user_id'],
                text=message_text,
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception as e:
            print(f"Error sending message to {u['user_id']}: {e}")
    return sent_count

async def notify_group_about_schedule(context, group_num: int):
    """Надіслати оновлений графік усім вихователям групи."""
    sched_entries = db.get_schedule_for_group(group_num)
    if not sched_entries:
        return
        
    msg = f"📅 <b>Оновлено графік процедур на сьогодні (Група {group_num}):</b>\n\n"
    for item in sched_entries:
        msg += f"🔹 <b>{item['procedure_name']}:</b> {item['time_slot']}\n"
    
    await notify_group_educators(context, group_num, msg)

async def execute_group_call(update, context, group_num: int, proc: str, count: str):
    sent_count = await send_call_to_educators(context, group_num, proc, count)
    proc_display = proc.replace("_", "/")
    
    if sent_count == 0:
        msg = (
            f"⚠️ <b>Увага!</b> Виклик для <b>Групи {group_num}</b> на процедуру <b>{proc_display}</b> (кількість: {count}) "
            f"не був надісланий, оскільки у цій групі ще немає жодного зареєстрованого вихователя."
        )
    else:
        msg = (
            f"✅ <b>Виклик успішно надіслано!</b>\n\n"
            f"👥 <b>Група:</b> Група {group_num}\n"
            f"💆 <b>Процедура:</b> {proc_display}\n"
            f"📊 <b>Кількість:</b> {count}\n"
            f"📱 <b>Отримали сповіщення:</b> {sent_count} вих.\n\n"
            f"Очікуємо відповіді від вихователів..."
        )
    await update.message.reply_text(msg, parse_mode="HTML")

async def execute_group_call_callback(query, context, group_num: int, proc: str, count: str):
    sent_count = await send_call_to_educators(context, group_num, proc, count)
    proc_display = proc.replace("_", "/")
    
    if sent_count == 0:
        msg = (
            f"⚠️ <b>Увага!</b> Виклик для <b>Групи {group_num}</b> на процедуру <b>{proc_display}</b> (кількість: {count}) "
            f"не був надісланий, оскільки у цій групі ще немає жодного зареєстрованого вихователя."
        )
    else:
        msg = (
            f"✅ <b>Виклик успішно надіслано!</b>\n\n"
            f"👥 <b>Група:</b> Група {group_num}\n"
            f"💆 <b>Процедура:</b> {proc_display}\n"
            f"📊 <b>Кількість:</b> {count}\n"
            f"📱 <b>Отримали сповіщення:</b> {sent_count} вих.\n\n"
            f"Очікуємо відповіді від вихователів..."
        )
    keyboard = [[InlineKeyboardButton("« Новий виклик", callback_data="admin_call_menu")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Перевірка реєстрації
    user = db.get_user(user_id)
    valid_groups = [f"Група {i}" for i in range(1, 9)]

    # Редагування інформаційного тексту адміністратором
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_info_text'):
        db.set_setting("info_text", text)
        context.user_data['waiting_for_info_text'] = False
        await update.message.reply_text("✅ <b>Інформаційний текст успішно оновлено!</b>", parse_mode="HTML")
        return

    # Очікування введення кількості відпочиваючих вручну
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_call_custom_count'):
        group_num, proc = context.user_data['waiting_for_call_custom_count']
        del context.user_data['waiting_for_call_custom_count']
        await execute_group_call(update, context, group_num, proc, text)
        return

    # Очікування завантаження графіка адміністратором
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_schedule'):
        context.user_data['waiting_for_schedule'] = False
        lines = text.split("\n")
        current_procedure = None
        parsed_entries = []
        entry_re = re.compile(r"(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\s*-\s*(\d+)\s*груп")
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            
            if line_str.endswith(":"):
                candidate = line_str[:-1].strip()
                candidate = re.sub(r'^[^\w\s/_-]+', '', candidate).strip()
                if candidate:
                    current_procedure = candidate
                continue
            
            if current_procedure:
                entry_match = entry_re.search(line_str)
                if entry_match:
                    time_slot = entry_match.group(1).strip()
                    group_num = int(entry_match.group(2))
                    parsed_entries.append({
                        "procedure": current_procedure,
                        "group": group_num,
                        "time": time_slot
                    })
        
        if not parsed_entries:
            await update.message.reply_text(
                "❌ <b>Помилка:</b> не вдалося розпізнати жодного запису графіка. Перевірте формат та спробуйте ще раз.",
                parse_mode="HTML"
            )
            return
        
        db.clear_schedules()
        for entry in parsed_entries:
            db.add_schedule_entry(entry["procedure"], entry["group"], entry["time"])
            
        # Надсилаємо сповіщення групам
        active_groups = set(entry["group"] for entry in parsed_entries)
        for g in active_groups:
            await notify_group_about_schedule(context, g)
            
        report = "✅ <b>Графік успішно оновлено!</b>\n\nРозпізнані процедури:\n"
        grouped = {}
        for entry in parsed_entries:
            grouped.setdefault(entry["procedure"], []).append(f"Гр. {entry['group']} ({entry['time']})")
            
        for proc, slots in grouped.items():
            report += f"\n💆 <b>{proc}:</b>\n  " + "\n  ".join(slots)
            
        await update.message.reply_text(report, parse_mode="HTML")
        return

    # Очікування завантаження шаблону адміністратором
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_template'):
        day_type = context.user_data['waiting_for_template']
        context.user_data['waiting_for_template'] = None
        lines = text.split("\n")
        current_procedure = None
        parsed_entries = []
        entry_re = re.compile(r"(\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\s*-\s*(\d+)\s*груп")
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.endswith(":"):
                candidate = line_str[:-1].strip()
                candidate = re.sub(r'^[^\w\s/_-]+', '', candidate).strip()
                if candidate:
                    current_procedure = candidate
                continue
            if current_procedure:
                entry_match = entry_re.search(line_str)
                if entry_match:
                    time_slot = entry_match.group(1).strip()
                    group_num = int(entry_match.group(2))
                    parsed_entries.append({
                        "procedure": current_procedure,
                        "group": group_num,
                        "time": time_slot
                    })
                    
        if not parsed_entries:
            await update.message.reply_text(
                "❌ <b>Помилка:</b> не вдалося розпізнати жодного запису. Спробуйте ще раз.",
                parse_mode="HTML"
            )
            return
            
        db.save_template(day_type, parsed_entries)
        day_name = "ПАРНИХ" if day_type == "even" else "НЕПАРНИХ"
        report = f"✅ <b>Шаблон для {day_name} днів успішно збережено!</b>\n\nРозпізнані процедури:\n"
        grouped = {}
        for entry in parsed_entries:
            grouped.setdefault(entry["procedure"], []).append(f"Гр. {entry['group']} ({entry['time']})")
        for proc, slots in grouped.items():
            report += f"\n💆 <b>{proc}:</b>\n  " + "\n  ".join(slots)
            
        await update.message.reply_text(report, parse_mode="HTML")
        return

    # Очікування введення нового часу для активного запису
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_entry_field'):
        entry_id, field = context.user_data['waiting_for_entry_field']
        context.user_data['waiting_for_entry_field'] = None
        entry = db.get_active_entry(entry_id)
        if not entry:
            await update.message.reply_text("Запис не знайдено.")
            return
            
        if field == "time":
            old_time = entry['time_slot']
            new_time = text.strip()
            db.update_active_time(entry_id, new_time)
            
            # Надсилаємо сповіщення
            notification_text = (
                f"🔔 <b>Увага! Зміна в графіку процедур!</b>\n\n"
                f"💆 <b>{entry['procedure_name']}:</b> змінено час для <b>Групи {entry['group_number']}</b>.\n"
                f"⏱️ <b>Новий час:</b> <code>{new_time}</code> (було {old_time})"
            )
            await notify_group_educators(context, entry['group_number'], notification_text)
            
            keyboard = [[InlineKeyboardButton("« До процедури", callback_data=f"admin_edit_sched_proc:{entry['procedure_name']}")]]
            await update.message.reply_text(
                f"✅ Час для <b>Групи {entry['group_number']}</b> (процедура <b>{entry['procedure_name']}</b>) змінено на <code>{new_time}</code>!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return

    # Очікування додавання нового запису вручну
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_add_entry'):
        proc = context.user_data['waiting_for_add_entry']
        context.user_data['waiting_for_add_entry'] = None
        parts = text.split("-")
        if len(parts) == 2:
            try:
                g_num = int(parts[0].strip())
                t_slot = parts[1].strip()
                if 1 <= g_num <= 8:
                    db.add_schedule_entry(proc, g_num, t_slot)
                    
                    # Надсилаємо сповіщення
                    notification_text = (
                        f"🔔 <b>Увага! Нова процедура в графіку!</b>\n\n"
                        f"💆 <b>{proc}:</b> додано для вашої групи.\n"
                        f"⏱️ <b>Час:</b> <code>{t_slot}</code>"
                    )
                    await notify_group_educators(context, g_num, notification_text)
                    
                    keyboard = [[InlineKeyboardButton("« До процедури", callback_data=f"admin_edit_sched_proc:{proc}")]]
                    await update.message.reply_text(
                        f"✅ Додано запис: <b>Група {g_num}</b> на процедуру <b>{proc}</b> о <b>{t_slot}</b>!",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
                    return
            except ValueError:
                pass
        
        keyboard = [[InlineKeyboardButton("« До процедури", callback_data=f"admin_edit_sched_proc:{proc}")]]
        await update.message.reply_text(
            "❌ Неправильний формат. Спробуйте ще раз через меню процедури.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if not user and text in valid_groups:
        try:
            group_number = int(text.split(" ")[1])
        except (IndexError, ValueError):
            group_number = 1

        user_data = update.effective_user
        db.register_user(
            user_id=user_id,
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            group_number=group_number
        )

        keyboard = [
            ["📅 Графік", "ℹ️ Інформація"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"Реєстрація успішна! Ви обрали: {text}.\nТепер ви можете користуватися ботом.",
            reply_markup=reply_markup
        )
        return

    if text == "ℹ️ Інформація":
        if user_id == ADMIN_ID or user:
            info_text = db.get_setting("info_text", DEFAULT_INFO_TEXT)
            await update.message.reply_text(info_text, parse_mode="HTML")
            return

    if text in ["📅 Графік", "📅 Актуальний графік на сьогодні"]:
        if user_id == ADMIN_ID or user:
            group_num = None if user_id == ADMIN_ID else user["group_number"]
            if group_num:
                sched_entries = db.get_schedule_for_group(group_num)
                if not sched_entries:
                    await update.message.reply_text(
                        f"📅 <b>Ваш графік процедур на сьогодні:</b>\n\n"
                        f"Процедур для <b>Групи {group_num}</b> на сьогодні не заплановано. 🌴",
                        parse_mode="HTML"
                    )
                else:
                    msg = f"📅 <b>Ваш графік процедур на сьогодні (Група {group_num}):</b>\n\n"
                    for item in sched_entries:
                        msg += f"🔹 <b>{item['procedure_name']}:</b> {item['time_slot']}\n"
                    await update.message.reply_text(msg, parse_mode="HTML")
            else:
                all_sched = db.get_all_schedules()
                
                if not all_sched:
                    await update.message.reply_text("📅 Графік процедур порожній.", parse_mode="HTML")
                else:
                    by_group = {}
                    for row in all_sched:
                        by_group.setdefault(row[1], []).append(f"  • <b>{row[0]}:</b> {row[2]}")
                    
                    msg = "📅 <b>Загальний графік процедур на сьогодні:</b>\n\n"
                    for g_num in sorted(by_group.keys()):
                        msg += f"👥 <b>Група {g_num}:</b>\n" + "\n".join(by_group[g_num]) + "\n\n"
                    await update.message.reply_text(msg, parse_mode="HTML")
            return

    if user_id == ADMIN_ID:
        if text == "📊 Статус груп":
            users_by_group = db.get_all_users_grouped()
            response_text = "📊 <b>Статус груп та список учасників:</b>\n\n"
            for grp_num in range(1, 9):
                users_list = users_by_group[grp_num]
                response_text += f"👥 <b>Група {grp_num}:</b>\n"
                if not users_list:
                    response_text += "  <i>Немає учасників</i>\n"
                else:
                    for u in users_list:
                        first_name = (u['first_name'] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        last_name = (u['last_name'] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        name_str = f"{first_name} {last_name}".strip()
                        if u['username']:
                            user_ref = f"@{u['username'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}"
                        else:
                            user_ref = f"ID: {u['user_id']}"
                        response_text += f"  • {name_str} ({user_ref})\n"
                response_text += "\n"
            await update.message.reply_text(response_text, parse_mode="HTML")
        elif text == "⚙️ Адмін-панель":
            keyboard = [
                [InlineKeyboardButton("✏️ Змінити групу", callback_data="admin_change_grp")],
                [InlineKeyboardButton("❌ Видалити учасника", callback_data="admin_del_usr")],
                [InlineKeyboardButton("📝 Редагувати інформацію", callback_data="admin_edit_info")],
                [InlineKeyboardButton("📅 Керування графіками", callback_data="admin_sched_mgmt")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("⚙️ <b>Панель керування:</b>", reply_markup=reply_markup, parse_mode="HTML")
        elif text == "📢 Виклик групи":
            keyboard = []
            for i in range(1, 9, 2):
                keyboard.append([
                    InlineKeyboardButton(f"👥 Група {i}", callback_data=f"call_grp:{i}"),
                    InlineKeyboardButton(f"👥 Група {i+1}", callback_data=f"call_grp:{i+1}")
                ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📢 <b>Виберіть групу, яку хочете викликати:</b>", reply_markup=reply_markup, parse_mode="HTML")
            return
        else:
            await update.message.reply_text(f"Ви обрали: {text}")
        return
    if user:
        await update.message.reply_text(f"Ви обрали: {text}")
        return

    # Якщо користувач не зареєстрований і ввів щось інше
    keyboard = [
        ["Група 1", "Група 2"],
        ["Група 3", "Група 4"],
        ["Група 5", "Група 6"],
        ["Група 7", "Група 8"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Будь ласка, оберіть вашу групу за допомогою кнопок нижче, щоб завершити реєстрацію:",
        reply_markup=reply_markup
    )
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("edu_resp:"):
        parts = data.split(":")
        group_num = int(parts[1])
        proc = parts[2]
        count = parts[3]
        status = parts[4]
        
        status_map = {
            "yes": ("🚶 Ведемо", "Ведемо"),
            "soon": ("⏱️ Будемо за пару хв", "Будемо за кілька хвилин"),
            "no": ("❌ Не ведемо", "Не ведемо")
        }
        
        btn_text, full_status = status_map.get(status, ("Невідомо", "Невідомо"))
        proc_display = proc.replace("_", "/")
        
        user_info = query.from_user
        name_str = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
        if not name_str:
            name_str = f"ID: {user_info.id}"
        username_part = f" (@{user_info.username})" if user_info.username else ""
        
        await query.edit_message_text(
            f"🚨 <b>Терміновий виклик на процедуру</b>\n\n"
            f"💆 <b>Процедура:</b> {proc_display}\n"
            f"👥 <b>Кількість відпочиваючих:</b> {count}\n\n"
            f"Ваша відповідь: <b>{btn_text}</b>",
            parse_mode="HTML"
        )
        
        admin_msg = (
            f"🔔 <b>[Група {group_num}] Відповідь на виклик!</b>\n\n"
            f"👤 <b>Вихователь:</b> {name_str}{username_part}\n"
            f"💆 <b>Процедура:</b> {proc_display}\n"
            f"👥 <b>Кількість:</b> {count}\n"
            f"📝 <b>Рішення:</b> <b>{btn_text}</b>"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error notifying admin: {e}")
            
        return

    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("У вас немає прав доступу.")
        return

    if data == "admin_call_menu":
        keyboard = []
        for i in range(1, 9, 2):
            keyboard.append([
                InlineKeyboardButton(f"👥 Група {i}", callback_data=f"call_grp:{i}"),
                InlineKeyboardButton(f"👥 Група {i+1}", callback_data=f"call_grp:{i+1}")
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📢 <b>Виберіть групу, яку хочете викликати:</b>", reply_markup=reply_markup, parse_mode="HTML")
        return

    elif data.startswith("call_grp:"):
        group_num = int(data.split(":")[1])
        keyboard = [
            [InlineKeyboardButton("💆 Масаж", callback_data=f"call_proc:{group_num}:Масаж")],
            [InlineKeyboardButton("🛁 Ванни", callback_data=f"call_proc:{group_num}:Ванни")],
            [InlineKeyboardButton("⚡ Дарсонваль", callback_data=f"call_proc:{group_num}:Дарсонваль")],
            [InlineKeyboardButton("🛏️ Вібромасаж/Нугабест", callback_data=f"call_proc:{group_num}:Вібромасаж_Нугабест")],
            [InlineKeyboardButton("« Назад до вибору груп", callback_data="admin_call_menu")]
        ]
        await query.edit_message_text(
            f"👥 <b>Виклик для Групи {group_num}</b>\n\nОберіть медичну процедуру:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("call_proc:"):
        parts = data.split(":")
        group_num = int(parts[1])
        proc = parts[2]
        
        keyboard = []
        for i in range(1, 11, 2):
            keyboard.append([
                InlineKeyboardButton(str(i), callback_data=f"call_cnt:{group_num}:{proc}:{i}"),
                InlineKeyboardButton(str(i+1), callback_data=f"call_cnt:{group_num}:{proc}:{i+1}")
            ])
        keyboard.append([
            InlineKeyboardButton("👥 Усіх", callback_data=f"call_cnt:{group_num}:{proc}:Усіх"),
            InlineKeyboardButton("✍️ Свій варіант", callback_data=f"call_custom:{group_num}:{proc}")
        ])
        keyboard.append([InlineKeyboardButton("« Назад до процедур", callback_data=f"call_grp:{group_num}")])
        
        proc_display = proc.replace("_", "/")
        await query.edit_message_text(
            f"👥 <b>Група {group_num}</b> → {proc_display}\n\n"
            f"Оберіть кількість відпочиваючих, яких потрібно привести:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("call_custom:"):
        parts = data.split(":")
        group_num = int(parts[1])
        proc = parts[2]
        
        context.user_data['waiting_for_call_custom_count'] = (group_num, proc)
        keyboard = [[InlineKeyboardButton("« Скасувати", callback_data=f"call_proc:{group_num}:{proc}")]]
        
        proc_display = proc.replace("_", "/")
        await query.edit_message_text(
            f"✍️ <b>Введіть кількість відпочиваючих вручну</b>\n\n"
            f"Група: {group_num}\n"
            f"Процедура: {proc_display}\n\n"
            f"Надішліть число або текст у відповідь на це повідомлення (наприклад, <code>15</code> або <code>5 дівчат</code>):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("call_cnt:"):
        parts = data.split(":")
        group_num = int(parts[1])
        proc = parts[2]
        count = parts[3]
        await execute_group_call_callback(query, context, group_num, proc, count)
        return

    elif data == "admin_menu":
        context.user_data['waiting_for_info_text'] = False
        context.user_data['waiting_for_schedule'] = False
        context.user_data['waiting_for_template'] = None
        context.user_data['waiting_for_entry_field'] = None
        context.user_data['waiting_for_add_entry'] = None
        keyboard = [
            [InlineKeyboardButton("✏️ Змінити групу", callback_data="admin_change_grp")],
            [InlineKeyboardButton("❌ Видалити учасника", callback_data="admin_del_usr")],
            [InlineKeyboardButton("📝 Редагувати інформацію", callback_data="admin_edit_info")],
            [InlineKeyboardButton("📅 Керування графіками", callback_data="admin_sched_mgmt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("⚙️ <b>Панель керування:</b>", reply_markup=reply_markup, parse_mode="HTML")
        return

    elif data == "admin_sched_mgmt":
        keyboard = [
            [InlineKeyboardButton("📥 Шаблон (Парні)", callback_data="admin_upl_tpl:even"),
             InlineKeyboardButton("📥 Шаблон (Непарні)", callback_data="admin_upl_tpl:odd")],
            [InlineKeyboardButton("🔄 Запустити Парний день", callback_data="admin_run_tpl:even")],
            [InlineKeyboardButton("🔄 Запустити Непарний день", callback_data="admin_run_tpl:odd")],
            [InlineKeyboardButton("✏️ Редагувати сьогоднішній графік", callback_data="admin_edit_sched_list")],
            [InlineKeyboardButton("❌ Очистити сьогоднішній графік", callback_data="admin_clear_sched_confirm")],
            [InlineKeyboardButton("❌ Видалити шаблон (Парні)", callback_data="admin_clear_tpl_confirm:even"),
             InlineKeyboardButton("❌ Видалити шаблон (Непарні)", callback_data="admin_clear_tpl_confirm:odd")],
            [InlineKeyboardButton("« Назад", callback_data="admin_menu")]
        ]
        await query.edit_message_text(
            "📅 <b>Керування графіками процедур</b>\n\n"
            "Тут ви можете завантажити шаблони для парних та непарних днів, застосувати їх до сьогоднішнього активного графіка або точково змінити окремі записи.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data == "admin_clear_sched_confirm":
        keyboard = [
            [
                InlineKeyboardButton("Так, очистити графік", callback_data="admin_clear_sched_execute"),
                InlineKeyboardButton("Скасувати", callback_data="admin_sched_mgmt")
            ]
        ]
        await query.edit_message_text(
            "⚠️ <b>Попередження!</b>\n\nВи впевнені, що хочете повністю очистити сьогоднішній активний графік? "
            "Цю дію не можна буде скасувати.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data == "admin_clear_sched_execute":
        db.clear_schedules()
        keyboard = [[InlineKeyboardButton("« Назад до керування", callback_data="admin_sched_mgmt")]]
        await query.edit_message_text(
            "❌ <b>Сьогоднішній графік успішно очищено!</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("admin_clear_tpl_confirm:"):
        day_type = data.split(":")[1]
        day_name = "ПАРНИХ" if day_type == "even" else "НЕПАРНИХ"
        keyboard = [
            [
                InlineKeyboardButton("Так, видалити", callback_data=f"admin_clear_tpl_execute:{day_type}"),
                InlineKeyboardButton("Скасувати", callback_data="admin_sched_mgmt")
            ]
        ]
        await query.edit_message_text(
            f"⚠️ <b>Попередження!</b>\n\nВи впевнені, що хочете видалити шаблон для <b>{day_name}</b> днів? "
            f"Всі збережені записи для цього шаблону будуть стерті.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("admin_clear_tpl_execute:"):
        day_type = data.split(":")[1]
        db.clear_template(day_type)
        day_name = "ПАРНИХ" if day_type == "even" else "НЕПАРНИХ"
        keyboard = [[InlineKeyboardButton("« Назад до керування", callback_data="admin_sched_mgmt")]]
        await query.edit_message_text(
            f"❌ <b>Шаблон для {day_name} днів успішно видалено!</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("admin_upl_tpl:"):
        day_type = data.split(":")[1]
        context.user_data['waiting_for_template'] = day_type
        context.user_data['waiting_for_info_text'] = False
        keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_sched_mgmt")]]
        day_name = "ПАРНИХ" if day_type == "even" else "НЕПАРНИХ"
        await query.edit_message_text(
            f"📥 <b>Завантаження шаблону для {day_name} днів</b>\n\n"
            f"Надішліть повідомлення з графіком. Формат має бути стандартним, наприклад:\n\n"
            f"<code>МАСАЖІ:\n"
            f"🔹10:00-4група\n"
            f"🔹11:40- 5 група\n\n"
            f"ВАННИ:\n"
            f"🔹10:00-3 група</code>\n\n"
            f"Поточний шаблон для {day_name} днів буде повністю перезаписано.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("admin_run_tpl:"):
        day_type = data.split(":")[1]
        db.apply_template_to_active(day_type)
        
        # Надсилаємо графіки усім групам
        active_groups = db.get_template_groups(day_type)
        for g in active_groups:
            await notify_group_about_schedule(context, g)
            
        day_name = "ПАРНОГО" if day_type == "even" else "НЕПАРНОГО"
        keyboard = [[InlineKeyboardButton("« До керування графіками", callback_data="admin_sched_mgmt")]]
        await query.edit_message_text(
            f"✅ <b>Шаблон {day_name} дня успішно застосовано!</b>\n\n"
            f"Активний графік на сьогодні оновлено та надіслано вихователям відповідних груп. "
            f"Тепер вихователі бачать цей розклад, а ви можете точково відредагувати його за потреби.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data == "admin_edit_sched_list":
        procedures = db.get_all_active_procedures()
        if not procedures:
            keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_sched_mgmt")]]
            await query.edit_message_text(
                "📅 <b>Сьогоднішній графік порожній.</b>\n\n"
                "Будь ласка, застосуйте один з шаблонів або завантажте графік, перш ніж редагувати.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        keyboard = []
        for proc in procedures:
            keyboard.append([InlineKeyboardButton(f"💆 {proc}", callback_data=f"admin_edit_sched_proc:{proc}")])
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin_sched_mgmt")])
        await query.edit_message_text(
            "✏️ <b>Оберіть процедуру для редагування:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data.startswith("admin_edit_sched_proc:"):
        proc = data.split(":", 1)[1]
        entries = db.get_active_entries_by_procedure(proc)
        keyboard = []
        for e in entries:
            keyboard.append([InlineKeyboardButton(
                f"Гр. {e['group_number']} ({e['time_slot']})",
                callback_data=f"admin_edit_entry:{e['id']}"
            )])
        keyboard.append([InlineKeyboardButton("➕ Додати запис", callback_data=f"admin_add_entry_proc:{proc}")])
        keyboard.append([InlineKeyboardButton("« До списку процедур", callback_data="admin_edit_sched_list")])
        await query.edit_message_text(
            f"💆 <b>Редагування процедури: {proc}</b>\n\nОберіть запис для редагування або видалення:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("admin_edit_entry:"):
        entry_id = int(data.split(":")[1])
        entry = db.get_active_entry(entry_id)
        if not entry:
            keyboard = [[InlineKeyboardButton("« Назад до списку", callback_data="admin_edit_sched_list")]]
            await query.edit_message_text("Помилка: запис не знайдено.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        keyboard = [
            [InlineKeyboardButton("⏱️ Змінити час", callback_data=f"admin_edit_field:{entry_id}:time"),
             InlineKeyboardButton("👥 Змінити групу", callback_data=f"admin_edit_field:{entry_id}:group")],
            [InlineKeyboardButton("❌ Видалити запис", callback_data=f"admin_delete_entry_act:{entry_id}")],
            [InlineKeyboardButton("« Назад до процедури", callback_data=f"admin_edit_sched_proc:{entry['procedure_name']}")]
        ]
        await query.edit_message_text(
            f"📝 <b>Параметри запису:</b>\n\n"
            f"💆 <b>Процедура:</b> {entry['procedure_name']}\n"
            f"👥 <b>Група:</b> Група {entry['group_number']}\n"
            f"⏱️ <b>Час:</b> {entry['time_slot']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("admin_edit_field:"):
        parts = data.split(":")
        entry_id = int(parts[1])
        field = parts[2]
        
        entry = db.get_active_entry(entry_id)
        if not entry:
            keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_edit_sched_list")]]
            await query.edit_message_text("Запис не знайдено.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        if field == "time":
            context.user_data['waiting_for_entry_field'] = (entry_id, 'time')
            keyboard = [[InlineKeyboardButton("« Скасувати", callback_data=f"admin_edit_entry:{entry_id}")]]
            await query.edit_message_text(
                f"⏱️ <b>Зміна часу</b>\n\nПоточний час: <code>{entry['time_slot']}</code>\n\n"
                f"Введіть новий час або часовий проміжок (наприклад, <code>12:30</code> або <code>12:30-13:00</code>) у відповідь на це повідомлення:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        elif field == "group":
            keyboard = []
            for i in range(1, 9, 2):
                keyboard.append([
                    InlineKeyboardButton(f"Група {i}", callback_data=f"admin_set_entry_group:{entry_id}:{i}"),
                    InlineKeyboardButton(f"Група {i+1}", callback_data=f"admin_set_entry_group:{entry_id}:{i+1}")
                ])
            keyboard.append([InlineKeyboardButton("« Скасувати", callback_data=f"admin_edit_entry:{entry_id}")])
            await query.edit_message_text(
                f"👥 <b>Зміна групи</b>\n\nПоточна група: <b>Група {entry['group_number']}</b>\n\nОберіть нову групу зі списку нижче:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        return

    elif data.startswith("admin_set_entry_group:"):
        parts = data.split(":")
        entry_id = int(parts[1])
        new_grp = int(parts[2])
        
        entry = db.get_active_entry(entry_id)
        if entry:
            old_grp = entry['group_number']
            db.update_active_group(entry_id, new_grp)
            
            # Сповіщення старої групи
            old_notification = (
                f"🔔 <b>Увага! Зміна в графіку процедур!</b>\n\n"
                f"💆 <b>{entry['procedure_name']}</b> о <b>{entry['time_slot']}</b> скасовано або перенесено для вашої групи."
            )
            await notify_group_educators(context, old_grp, old_notification)
            
            # Сповіщення нової групи
            new_notification = (
                f"🔔 <b>Увага! Нова процедура в графіку!</b>\n\n"
                f"💆 <b>{entry['procedure_name']}</b> о <b>{entry['time_slot']}</b> додано для вашої групи."
            )
            await notify_group_educators(context, new_grp, new_notification)
            
            msg = f"✅ Групу для запису <b>{entry['procedure_name']}</b> успішно змінено з Групи {old_grp} на <b>Групу {new_grp}</b>! 🎉"
            keyboard = [[InlineKeyboardButton("« До процедури", callback_data=f"admin_edit_sched_proc:{entry['procedure_name']}")]]
        else:
            msg = "Помилка: запис не знайдено."
            keyboard = [[InlineKeyboardButton("« До списку", callback_data="admin_edit_sched_list")]]
            
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    elif data.startswith("admin_delete_entry_act:"):
        entry_id = int(data.split(":")[1])
        entry = db.get_active_entry(entry_id)
        if entry:
            db.delete_active_entry(entry_id)
            
            # Сповіщення
            notification_text = (
                f"🔔 <b>Увага! Процедуру скасовано!</b>\n\n"
                f"💆 <b>{entry['procedure_name']}</b> о <b>{entry['time_slot']}</b> скасовано для вашої групи."
            )
            await notify_group_educators(context, entry['group_number'], notification_text)
            
            msg = f"❌ Запис для <b>Групи {entry['group_number']}</b> на процедуру <b>{entry['procedure_name']}</b> ({entry['time_slot']}) видалено!"
            keyboard = [[InlineKeyboardButton("« До процедури", callback_data=f"admin_edit_sched_proc:{entry['procedure_name']}")]]
        else:
            msg = "Помилка: запис не знайдено."
            keyboard = [[InlineKeyboardButton("« До списку", callback_data="admin_edit_sched_list")]]
            
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    elif data.startswith("admin_add_entry_proc:"):
        proc = data.split(":", 1)[1]
        context.user_data['waiting_for_add_entry'] = proc
        keyboard = [[InlineKeyboardButton("« Скасувати", callback_data=f"admin_edit_sched_proc:{proc}")]]
        await query.edit_message_text(
            f"➕ <b>Додавання запису до процедури {proc}</b>\n\n"
            f"Надішліть групу та час у форматі <code>група - час</code> (наприклад, <code>4 - 10:30</code> або <code>2 - 14:15-14:45</code>) у відповідь на це повідомлення:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data == "admin_edit_info":
        context.user_data['waiting_for_info_text'] = True
        keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_menu")]]
        await query.edit_message_text(
            "📝 <b>Редагування інформаційного повідомлення</b>\n\n"
            "Будь ласка, надішліть новий текст у відповідь на це повідомлення. "
            "Ви можете використовувати HTML-теги для форматування (наприклад, <b>жирний</b>, <i>курсив</i>) та емодзі.\n\n"
            "Поточний текст буде замінено повністю.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data == "admin_change_grp":
        users = db.get_all_users()
        if not users:
            keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_menu")]]
            await query.edit_message_text("Немає зареєстрованих учасників.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        keyboard = []
        for u in users:
            name_str = f"{u['first_name'] or ''} {u['last_name'] or ''}".strip() or f"ID: {u['user_id']}"
            keyboard.append([InlineKeyboardButton(f"{name_str} (Гр. {u['group_number']})", callback_data=f"change_usr_id:{u['user_id']}")])
        
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin_menu")])
        await query.edit_message_text("Оберіть учасника, групу якого ви хочете змінити:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data.startswith("change_usr_id:"):
        target_id = int(data.split(":")[1])
        target_user = db.get_user(target_id)
        if not target_user:
            keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_change_grp")]]
            await query.edit_message_text("Користувача не знайдено.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        name_str = f"{target_user['first_name'] or ''} {target_user['last_name'] or ''}".strip() or f"ID: {target_user['user_id']}"
        
        # Grid of groups 1 to 8 (2 columns)
        keyboard = []
        for i in range(1, 9, 2):
            keyboard.append([
                InlineKeyboardButton(f"Група {i}", callback_data=f"set_grp:{target_id}:{i}"),
                InlineKeyboardButton(f"Група {i+1}", callback_data=f"set_grp:{target_id}:{i+1}")
            ])
        keyboard.append([InlineKeyboardButton("« Назад до списку", callback_data="admin_change_grp")])
        
        await query.edit_message_text(
            f"Оберіть нову групу для учасника <b>{name_str}</b> (поточна: Група {target_user['group_number']}):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("set_grp:"):
        parts = data.split(":")
        target_id = int(parts[1])
        new_grp = int(parts[2])
        
        target_user = db.get_user(target_id)
        if target_user:
            db.update_user_group(target_id, new_grp)
            name_str = f"{target_user['first_name'] or ''} {target_user['last_name'] or ''}".strip() or f"ID: {target_user['user_id']}"
            msg = f"Групу для <b>{name_str}</b> успішно змінено на <b>Групу {new_grp}</b>! 🎉"
        else:
            msg = "Помилка: користувача не знайдено."

        keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_change_grp")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    elif data == "admin_del_usr":
        users = db.get_all_users()
        if not users:
            keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_menu")]]
            await query.edit_message_text("Немає зареєстрованих учасників.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        keyboard = []
        for u in users:
            name_str = f"{u['first_name'] or ''} {u['last_name'] or ''}".strip() or f"ID: {u['user_id']}"
            keyboard.append([InlineKeyboardButton(f"❌ {name_str} (Гр. {u['group_number']})", callback_data=f"confirm_del:{u['user_id']}")])
        
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin_menu")])
        await query.edit_message_text("Оберіть учасника для видалення:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data.startswith("confirm_del:"):
        target_id = int(data.split(":")[1])
        target_user = db.get_user(target_id)
        if not target_user:
            keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_del_usr")]]
            await query.edit_message_text("Користувача не знайдено.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        name_str = f"{target_user['first_name'] or ''} {target_user['last_name'] or ''}".strip() or f"ID: {target_user['user_id']}"
        
        keyboard = [
            [
                InlineKeyboardButton("Так, видалити", callback_data=f"delete_usr:{target_id}"),
                InlineKeyboardButton("Скасувати", callback_data="admin_del_usr")
            ]
        ]
        await query.edit_message_text(
            f"⚠️ Ви впевнені, що хочете видалити учасника <b>{name_str}</b> (Група {target_user['group_number']})?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    elif data.startswith("delete_usr:"):
        target_id = int(data.split(":")[1])
        target_user = db.get_user(target_id)
        if target_user:
            db.delete_user(target_id)
            name_str = f"{target_user['first_name'] or ''} {target_user['last_name'] or ''}".strip() or f"ID: {target_user['user_id']}"
            msg = f"Учасника <b>{name_str}</b> успішно видалено з бази даних! ❌"
        else:
            msg = "Помилка: користувача не знайдено."

        keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_del_usr")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

async def daily_check_job(context: ContextTypes.DEFAULT_TYPE):
    """Щоденна перевірка о 8:10 наявності графіка на сьогодні."""
    today = datetime.date.today()
    day_type = "even" if today.day % 2 == 0 else "odd"
    day_name = "ПАРНИЙ" if day_type == "even" else "НЕПАРНИЙ"
    
    if not db.has_template_entries(day_type):
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"⚠️ <b>Увага!</b> Шаблон для <b>{day_name}</b> дня порожній або відсутній.\n\n"
                    f"Графік на сьогодні не буде надіслано групам о 8:15. Будь ласка, завантажте графік або шаблон!"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error sending warning to admin: {e}")

async def daily_schedule_job(context: ContextTypes.DEFAULT_TYPE):
    """Щоденний запуск о 8:15 для оновлення графіка та сповіщення груп."""
    today = datetime.date.today()
    day_type = "even" if today.day % 2 == 0 else "odd"
    
    if db.has_template_entries(day_type):
        # Застосувати шаблон до активного графіка
        db.apply_template_to_active(day_type)
        
        # Надіслати індивідуальні графіки вихователям кожної групи
        for group_num in range(1, 9):
            await notify_group_about_schedule(context, group_num)

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(admin_callback))

# Додати щоденні завдання
local_tz = get_localzone()

app.job_queue.run_daily(
    daily_check_job,
    time=datetime.time(hour=8, minute=10, tzinfo=local_tz)
)

app.job_queue.run_daily(
    daily_schedule_job,
    time=datetime.time(hour=8, minute=15, tzinfo=local_tz)
)

print("Бот запущений...")
app.run_polling()