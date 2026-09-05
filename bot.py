import asyncio
import logging
import sqlite3
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = '8621625728:AAHt5hqaGopZ8U_YmWzONCYIltYf4W6LxPM'
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

DISTRICTS = ["Гетто", "Даунтаун", "Порт", "Вайнвуд"]

def init_db():
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            nickname TEXT UNIQUE,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 500,
            hp INTEGER DEFAULT 100,
            energy INTEGER DEFAULT 100,
            wanted INTEGER DEFAULT 0,
            location TEXT DEFAULT 'Гетто',
            faction TEXT DEFAULT 'Гражданский',
            is_taxi INTEGER DEFAULT 0,
            car TEXT DEFAULT 'Нет',
            weapon TEXT DEFAULT 'Нет',
            armor INTEGER DEFAULT 0,
            jail_time INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            passenger_id INTEGER,
            driver_id INTEGER,
            to_location TEXT,
            end_time TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            tg_id INTEGER,
            item_name TEXT,
            item_type TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gangs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            leader_id INTEGER,
            territory TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user(tg_id):
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE tg_id = ?', (tg_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_location(tg_id, new_location):
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET location = ? WHERE tg_id = ?', (new_location, tg_id))
    conn.commit()
    conn.close()

def update_user_balance(tg_id, amount):
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE tg_id = ?', (amount, tg_id))
    conn.commit()
    conn.close()

def create_user(tg_id, nickname):
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (tg_id, nickname) VALUES (?, ?)', (tg_id, nickname))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

class Registration(StatesGroup):
    waiting_for_nickname = State()

def get_main_menu(is_taxi_status=0):
    taxi_text = "🟢 Выключить такси" if is_taxi_status == 1 else "🚖 Работать таксистом"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
         InlineKeyboardButton(text="🗺 Карта / Город", callback_data="menu_map")],
        [InlineKeyboardButton(text="💼 Работа", callback_data="menu_work"),
         InlineKeyboardButton(text="🚨 Криминал", callback_data="menu_crime")],
        [InlineKeyboardButton(text="🚗 Гараж / Авто", callback_data="menu_garage"),
         InlineKeyboardButton(text="🔫 Амунация", callback_data="menu_shop")],
        [InlineKeyboardButton(text="💬 Чат района", callback_data="menu_chat"),
         InlineKeyboardButton(text="⚖️ Гос. службы", callback_data="menu_gov")],
        [InlineKeyboardButton(text=taxi_text, callback_data="toggle_taxi")]
    ])

def get_map_menu():
    keyboard = []
    for dist in DISTRICTS:
        keyboard.append([InlineKeyboardButton(text=f"📍 {dist}", callback_data=f"map_goto_{dist}")])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if user:
        await message.answer(
            f"С возвращением на улицы, <b>{user[1]}</b>!\nЧто планируешь делать сегодня?",
            reply_markup=get_main_menu(user[10]),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🌆 <b>Добро пожаловать в Los Santos!</b>\n\n"
            "Здесь решают деньги, связи и ствол за поясом. Чтобы стать частью города, тебе нужен паспорт.\n\n"
            "✏️ <b>Придумай свой игровой никнейм</b> (от 3 до 16 символов):",
            parse_mode="HTML"
        )
        await state.set_state(Registration.waiting_for_nickname)

@router.message(StateFilter(Registration.waiting_for_nickname))
async def process_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()
    if not re.match(r'^[A-Za-zА-Яа-я0-9_]{3,16}$', nickname):
        await message.answer("⚠️ Недопустимый никнейм!\nИспользуй от 3 до 16 букв или цифр. Попробуй еще раз:")
        return

    success = create_user(message.from_user.id, nickname)
    if success:
        await state.clear()
        await message.answer(
            f"🎉 <b>Отлично, {nickname}!</b> Твой профиль создан.\n\n"
            f"💰 В качестве подъемных город выдает тебе <b>$500</b>.",
            reply_markup=get_main_menu(0),
            parse_mode="HTML"
        )
    else:
        await message.answer("⚠️ Этот никнейм уже занят другим игроком! Придумай другой:")

@router.callback_query(F.data == "toggle_taxi")
async def toggle_taxi(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        return
    current_status = user[10]
    new_status = 0 if current_status == 1 else 1
    
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_taxi = ? WHERE tg_id = ?', (new_status, callback.from_user.id))
    conn.commit()
    conn.close()
    
    status_text = "🟢 Ты вышел на смену таксистом!" if new_status == 1 else "🔴 Ты закончил работу таксистом."
    await callback.answer(status_text, show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=get_main_menu(new_status))

@router.callback_query(F.data.startswith("menu_"))
async def handle_menu_buttons(callback: CallbackQuery):
    action = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка! Вы не зарегистрированы. Напишите /start", show_alert=True)
        return

    tg_id, nickname, level, exp, balance, hp, energy, wanted, location, faction, is_taxi, car, weapon, armor, jail_time = user

    if action == "profile":
        stars = "⭐" * wanted if wanted > 0 else "Нет розыска"
        profile_text = (
            f"👤 <b>Профиль: {nickname}</b>\n"
            f"──────────────\n"
            f"📊 <b>Уровень:</b> {level} ({exp} EXP)\n"
            f"💵 <b>Баланс:</b> ${balance}\n"
            f"──────────────\n"
            f"❤️ <b>Здоровье:</b> {hp}/100\n"
            f"⚡ <b>Энергия:</b> {energy}%\n"
            f"🛡 <b>Броня:</b> {armor}%\n"
            f"🚗 <b>Авто:</b> {car}\n"
            f"🔫 <b>Оружие:</b> {weapon}\n"
            f"──────────────\n"
            f"📍 <b>Район:</b> {location}\n"
            f"🏢 <b>Фракция:</b> {faction}\n"
            f"🚓 <b>Розыск:</b> {stars}"
        )
        await callback.message.edit_text(profile_text, reply_markup=get_main_menu(is_taxi), parse_mode="HTML")
        
    elif action == "map":
        await callback.message.edit_text(
            f"🗺 <b>Карта Los Santos</b>\nТекущий район: <b>{location}</b>\n\nКуда хочешь отправиться?",
            reply_markup=get_map_menu(),
            parse_mode="HTML"
        )
    elif action == "work":
        work_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Курьер (+$50, ⚡-10%)", callback_data="work_courier")],
            [InlineKeyboardButton(text="🚖 Таксист (+$150, ⚡-15%)", callback_data="work_taxi")],
            [InlineKeyboardButton(text="🚛 Дальнобойщик (+$400, ⚡-25%)", callback_data="work_truck")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
        await callback.message.edit_text("💼 <b>Легальная работа:</b>\nВыберите занятие:", reply_markup=work_kb, parse_mode="HTML")
        
    elif action == "crime":
        crime_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚗 Угон авто (риск звезды)", callback_data="crime_steal")],
            [InlineKeyboardButton(text="🔫 Ограбление магазина (нужен ствол)", callback_data="crime_shop")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
        await callback.message.edit_text("🚨 <b>Криминальный мир:</b>\nВыбирай дело с умом:", reply_markup=crime_kb, parse_mode="HTML")

    elif action == "garage":
        garage_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Автосалон / Б/У рынок", callback_data="shop_cars")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
        await callback.message.edit_text(f"🚗 <b>Ваш гараж:</b>\nТекущая машина: <b>{car}</b>", reply_markup=garage_kb, parse_mode="HTML")

    elif action == "shop":
        shop_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔫 Купить Пистолет ($300)", callback_data="buy_gun_pistol")],
            [InlineKeyboardButton(text="🛡 Купить Бронежилет ($200)", callback_data="buy_armor")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
        await callback.message.edit_text("🔫 <b>Магазин Ammu-Nation:</b>", reply_markup=shop_kb, parse_mode="HTML")

    elif action == "chat":
        await callback.message.edit_text(
            f"💬 <b>Локальный чат ({location})</b>\n"
            f"Все игроки в этом районе видят ваши сообщения.\n\n"
            f"<i>(Функция чата активна в текущей локации)</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]]),
            parse_mode="HTML"
        )

    elif action == "gov":
        gov_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚑 Устроиться во Врачи (EMS)", callback_data="gov_ems")],
            [InlineKeyboardButton(text="🚔 Устроиться в Полицию (LSPD)", callback_data="gov_lspd")],
            [InlineKeyboardButton(text="🕵️‍♂️ Устроиться в ФБР (FBI)", callback_data="gov_fbi")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
        ])
        await callback.message.edit_text("⚖️ <b>Государственные структуры:</b>\nВыберите фракцию:", reply_markup=gov_kb, parse_mode="HTML")

    elif action == "back":
        await callback.message.edit_text("Главное меню:", reply_markup=get_main_menu(is_taxi), parse_mode="HTML")
    else:
        await callback.answer("Раздел в разработке!", show_alert=False)

@router.callback_query(F.data.startswith("work_"))
async def process_work(callback: CallbackQuery):
    w_type = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    energy = user[6]
    
    if energy < 15:
        await callback.answer("❌ Слишком мало энергии! Отдохните.", show_alert=True)
        return
        
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    
    if w_type == "courier":
        cursor.execute('UPDATE users SET balance = balance + 50, energy = energy - 10, exp = exp + 10 WHERE tg_id = ?', (callback.from_user.id,))
        conn.commit()
        conn.close()
        await callback.answer("📦 Вы успешно разнесли посылки и заработали $50!", show_alert=True)
    elif w_type == "taxi":
        cursor.execute('UPDATE users SET balance = balance + 150, energy = energy - 15, exp = exp + 20 WHERE tg_id = ?', (callback.from_user.id,))
        conn.commit()
        conn.close()
        await callback.answer("🚖 Вы подвезли пассажиров и заработали $150!", show_alert=True)
    elif w_type == "truck":
        cursor.execute('UPDATE users SET balance = balance + 400, energy = energy - 25, exp = exp + 50 WHERE tg_id = ?', (callback.from_user.id,))
        conn.commit()
        conn.close()
        await callback.answer("🚛 Доставили крупный груз и заработали $400!", show_alert=True)
        
    conn.close()

@router.callback_query(F.data.startswith("crime_"))
async def process_crime(callback: CallbackQuery):
    c_type = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    weapon = user[12]
    
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    
    if c_type == "steal":
        cursor.execute('UPDATE users SET balance = balance + 300, wanted = wanted + 1, exp = exp + 30 WHERE tg_id = ?', (callback.from_user.id,))
        conn.commit()
        await callback.answer("🚗 Вы угнали машину! Получена 1 звезда розыска ⭐", show_alert=True)
    elif c_type == "shop":
        if weapon == "Нет":
            await callback.answer("❌ Для ограбления магазина нужен пистолет из Ammu-Nation!", show_alert=True)
            conn.close()
            return
        cursor.execute('UPDATE users SET balance = balance + 900, wanted = wanted + 2, exp = exp + 70 WHERE tg_id = ?', (callback.from_user.id,))
        conn.commit()
        await callback.answer("🔫 Магазин ограблен! Получено 2 звезды розыска ⭐⭐", show_alert=True)
        
    conn.close()

@router.callback_query(F.data.startswith("buy_"))
async def process_shop(callback: CallbackQuery):
    item = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    balance = user[4]
    
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    
    if item == "gun":
        if balance < 300:
            await callback.answer("❌ Недостаточно средств ($300)", show_alert=True)
        else:
            cursor.execute('UPDATE users SET balance = balance - 300, weapon = "Pistol" WHERE tg_id = ?', (callback.from_user.id,))
            conn.commit()
            await callback.answer("🔫 Вы купили пистолет!", show_alert=True)
    elif item == "armor":
        if balance < 200:
            await callback.answer("❌ Недостаточно средств ($200)", show_alert=True)
        else:
            cursor.execute('UPDATE users SET balance = balance - 200, armor = 100 WHERE tg_id = ?', (callback.from_user.id,))
            conn.commit()
            await callback.answer("🛡 Вы купили бронежилет!", show_alert=True)
            
    conn.close()

@router.callback_query(F.data.startswith("gov_"))
async def process_gov(callback: CallbackQuery):
    faction_type = callback.data.split("_")[1]
    f_names = {"ems": "Больница (EMS)", "lspd": "Полиция (LSPD)", "fbi": "ФБР (FBI)"}
    
    conn = sqlite3.connect('gta_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET faction = ? WHERE tg_id = ?', (f_names[faction_type], callback.from_user.id))
    conn.commit()
    conn.close()
    
    await callback.answer(f"✅ Вы успешно устроились в {f_names[faction_type]}!", show_alert=True)

@router.callback_query(F.data.startswith("map_goto_"))
async def map_goto(callback: CallbackQuery):
    target_loc = callback.data.split("_")[2]
    user = get_user(callback.from_user.id)
    current_loc = user[8]
    
    if current_loc == target_loc:
        await callback.answer(f"Ты уже находишься в районе {target_loc}!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Пешком (Бесплатно, ⚡-10%)", callback_data=f"travel_walk_{target_loc}")],
        [InlineKeyboardButton(text="🚖 Вызвать такси ($100, 3 мин)", callback_data=f"travel_taxi_{target_loc}")],
        [InlineKeyboardButton(text="◀️ На карту", callback_data="menu_map")]
    ])
    
    await callback.message.edit_text(
        f"📍 Пункт назначения: <b>{target_loc}</b>\nВыберите способ передвижения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("travel_"))
async def process_travel(callback: CallbackQuery):
    data_parts = callback.data.split("_")
    method = data_parts[1]
    target_loc = data_parts[2]
    
    user = get_user(callback.from_user.id)
    balance = user[4]
    
    if method == "walk":
        update_user_location(callback.from_user.id, target_loc)
        await callback.message.edit_text(
            f"🚶 Ты дошел пешком до района <b>{target_loc}</b>.",
            reply_markup=get_main_menu(user[10]),
            parse_mode="HTML"
        )
        
    elif method == "taxi":
        if balance < 100:
            await callback.answer("❌ У тебя недостаточно денег на такси ($100)!", show_alert=True)
            return
        
        update_user_balance(callback.from_user.id, -100)
        
        conn = sqlite3.connect('gta_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT tg_id, nickname FROM users WHERE is_taxi = 1 AND tg_id != ? LIMIT 1', (callback.from_user.id,))
        driver = cursor.fetchone()
        
        end_time = datetime.now() + timedelta(minutes=3)
        
        if driver:
            driver_id, driver_name = driver
            cursor.execute('INSERT INTO rides (passenger_id, driver_id, to_location, end_time) VALUES (?, ?, ?, ?)',
                           (callback.from_user.id, driver_id, target_loc, end_time))
            conn.commit()
            conn.close()
            
            update_user_balance(driver_id, 100)
            
            try:
                await bot.send_message(
                    driver_id,
                    f"🚖 <b>Внимание, заказ!</b> Игрок <b>{user[1]}</b> вызвал вас в такси.\n"
                    f"Направление: <b>{target_loc}</b>. Поездка продлится 3 минуты.",
                    parse_mode="HTML"
                )
            except:
                pass
                
            await callback.message.edit_text(
                f"🚖 Живой таксист <b>{driver_name}</b> принял твой заказ!\n"
                f"Вы едете в район <b>{target_loc}</b>. Поездка займет 3 минуты...",
                reply_markup=get_main_menu(user[10]),
                parse_mode="HTML"
            )
        else:
            cursor.execute('INSERT INTO rides (passenger_id, driver_id, to_location, end_time) VALUES (?, NULL, ?, ?)',
                           (callback.from_user.id, target_loc, end_time))
            conn.commit()
            conn.close()
            
            await callback.message.edit_text(
                f"🤖 Свободных таксистов не найдено. К тебе приехал автопилот (NPC-таксомотор).\n"
                f"Путь в район <b>{target_loc}</b> займет 3 минуты...",
                reply_markup=get_main_menu(user[10]),
                parse_mode="HTML"
            )

async def check_rides_loop():
    while True:
        await asyncio.sleep(5)
        now = datetime.now()
        
        conn = sqlite3.connect('gta_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, passenger_id, to_location FROM rides WHERE end_time <= ?', (now,))
        finished_rides = cursor.fetchall()
        
        for ride in finished_rides:
            ride_id, passenger_id, to_location = ride
            update_user_location(passenger_id, to_location)
            cursor.execute('DELETE FROM rides WHERE id = ?', (ride_id,))
            conn.commit()
            
            user = get_user(passenger_id)
            if user:
                try:
                    await bot.send_message(
                        passenger_id,
                        f"🏁 <b>Поездка завершена!</b>\nТы успешно прибыл в район <b>{to_location}</b>.",
                        reply_markup=get_main_menu(user[10]),
                        parse_mode="HTML"
                    )
                except:
                    pass
                
        conn.close()

async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    asyncio.create_task(check_rides_loop())
    print("GTA Telegram Bot запущен полностью!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
