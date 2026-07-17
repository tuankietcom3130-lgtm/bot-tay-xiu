import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import random
import time
import os
import math
import re
from dotenv import load_dotenv

# ================= CẤU HÌNH CƠ BẢN =================
load_dotenv()

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(API_TOKEN)

LOAN_LIMIT = 100000000000      # 100 Tỷ
LOAN_DURATION = 600       
JAIL_DURATION = 3600      
BAIL_FEE_PER_MIN = 1000000 

# Biến toàn cục lưu lịch sử Tài Xỉu
tx_history = []

# ================= HÀM BỔ TRỢ =================
def format_vnd(amount):
    return f"{amount:,}"

def reply_msg(message, text, markup=None):
    thread_id = getattr(message, 'message_thread_id', None)
    bot.send_message(
        chat_id=message.chat.id,
        text=text,
        reply_to_message_id=message.message_id,
        message_thread_id=thread_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

def send_msg(message, text, markup=None):
    thread_id = getattr(message, 'message_thread_id', None)
    bot.send_message(
        chat_id=message.chat.id,
        text=text,
        message_thread_id=thread_id,
        parse_mode='Markdown',
        reply_markup=markup
    )

def is_valid_reply(message):
    if not message.reply_to_message:
        return False
    thread_id = getattr(message, 'message_thread_id', None)
    if thread_id and message.reply_to_message.message_id == thread_id:
        return False
    return True

def init_db():
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, first_name TEXT DEFAULT 'Người chơi', balance INTEGER DEFAULT 0, last_work REAL DEFAULT 0, loan INTEGER DEFAULT 0, loan_time REAL DEFAULT 0, jail_time REAL DEFAULT 0, last_cuop REAL DEFAULT 0, jail_count INTEGER DEFAULT 0, rob_count INTEGER DEFAULT 0, steal_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT, rarity TEXT, min_pay INTEGER, max_pay INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS market
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, icon TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS black_market
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, icon TEXT, target_action TEXT, success_rate INTEGER, immune_jail INTEGER, max_uses INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (inv_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_id INTEGER, insurance_expiry REAL DEFAULT 0, is_pawned INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS black_inventory
                 (inv_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_id INTEGER, uses_left INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS server_stats 
                 (date TEXT PRIMARY KEY, bank_pool INTEGER)''')
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM jobs")
    if c.fetchone()[0] == 0:
        default_jobs = [
            ("đi phụ hồ bốc gạch gãy cả lưng", "common", 50000, 150000),
            ("giao trà sữa giữa trưa nắng gặp khách bom hàng", "common", 50000, 150000),
            ("nhặt ve chai lượm được bí kíp võ công", "rare", 200000, 600000),
            ("viết code thuê cho sếp cả đêm được thưởng nóng", "rare", 200000, 600000),
            ("đào móng nhà trúng hũ vàng ròng phong kiến", "legendary", 1000000, 5000000)
        ]
        c.executemany("INSERT INTO jobs (description, rarity, min_pay, max_pay) VALUES (?, ?, ?, ?)", default_jobs)

    c.execute("SELECT COUNT(*) FROM market")
    if c.fetchone()[0] == 0:
        market_items = [("Đồng hồ Rolex", 100000000, "⌚"), ("Siêu xe Ferrari", 15000000000, "🏎️"), ("Biệt thự Vinpearl", 50000000000, "🏡"), ("Du thuyền hạng sang", 100000000000, "🛥️")]
        c.executemany("INSERT INTO market (name, price, icon) VALUES (?, ?, ?)", market_items)
        
    c.execute("SELECT COUNT(*) FROM black_market")
    if c.fetchone()[0] == 0:
        bm_items = [
            ("Kìm cộng lực", 25000000, "🔧", "trom", 55, 0, 2), 
            ("Súng AK-47", 250000000, "🔫", "cuop", 25, 0, 2), 
            ("Bom mù Ninja", 750000000, "💣", "trom", 40, 1, 1), 
            ("Vật tổ trường sinh", 2500000000, "🏺", "all", 50, 1, 1)
        ]
        c.executemany("INSERT INTO black_market (name, price, icon, target_action, success_rate, immune_jail, max_uses) VALUES (?, ?, ?, ?, ?, ?, ?)", bm_items)
        
    conn.commit()
    conn.close()

# Quản lý Hạn Mức Cướp Ngân Hàng (1000 Tỷ / Ngày)
def get_daily_bank_pool():
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    today = time.strftime('%Y-%m-%d')
    c.execute("SELECT bank_pool FROM server_stats WHERE date = ?", (today,))
    row = c.fetchone()
    if row:
        pool = row[0]
    else:
        pool = 1000000000000 # 1000 Tỷ
        c.execute("INSERT INTO server_stats (date, bank_pool) VALUES (?, ?)", (today, pool))
        conn.commit()
    conn.close()
    return pool

def deduct_bank_pool(amount):
    today = time.strftime('%Y-%m-%d')
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("UPDATE server_stats SET bank_pool = bank_pool - ? WHERE date = ?", (amount, today))
    conn.commit()
    conn.close()

def get_balance(user_id, first_name=None):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        if first_name:
            c.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (first_name, user_id))
            conn.commit()
        conn.close()
        return result[0]
    else:
        name_to_save = first_name if first_name else "Người chơi"
        c.execute("INSERT INTO users (user_id, first_name, balance, last_work, loan, loan_time, jail_time, last_cuop, jail_count, rob_count, steal_count) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)", (user_id, name_to_save))
        conn.commit()
        conn.close()
        return 0

def update_balance(user_id, amount):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def check_loan_overdue(user_id):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT loan, loan_time FROM users WHERE user_id = ?", (user_id,))
    data = c.fetchone()
    is_overdue = False
    if data and data[0] > 0:
        loan, loan_time = data[0], data[1]
        if loan_time > 0 and (time.time() - loan_time > LOAN_DURATION):
            new_loan = loan * 2
            c.execute("UPDATE users SET loan = ?, loan_time = -1 WHERE user_id = ?", (new_loan, user_id))
            conn.commit()
            is_overdue = True
        elif loan_time == -1:
            is_overdue = True
    conn.close()
    return is_overdue

def check_jail(user_id):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT jail_time FROM users WHERE user_id = ?", (user_id,))
    data = c.fetchone()
    conn.close()
    if data and data[0] > 0:
        time_passed = time.time() - data[0]
        if time_passed < JAIL_DURATION:
            return True, int(JAIL_DURATION - time_passed)
        else:
            conn = sqlite3.connect('economy_v10.db')
            c = conn.cursor()
            c.execute("UPDATE users SET jail_time = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
    return False, 0

# TỐI ƯU CƠ CHẾ ĐỌC TIỀN TỆ (Có thể dịch các từ viết tắt 2tỷ5, 2m5, 1/2all...)
def get_bet_amount(bet_str, balance):
    bet_str = str(bet_str).lower().replace(" ", "").replace(",", ".")
    if bet_str == 'all': return balance
    if bet_str in ['1/2all', 'half', '1/2']: return balance // 2
    
    # Dịch format: 2tỷ5 -> 2.5tỷ | 5m5 -> 5.5m
    bet_str = re.sub(r'(\d+)(tỷ|ty|tr|m|k|b)(\d+)', r'\1.\3\2', bet_str)
    
    multiplier = 1
    if bet_str.endswith('k'):
        multiplier = 10**3
        bet_str = bet_str[:-1]
    elif bet_str.endswith('m'):
        multiplier = 10**6
        bet_str = bet_str[:-1]
    elif bet_str.endswith('tr'):
        multiplier = 10**6
        bet_str = bet_str[:-2]
    elif bet_str.endswith('tỷ') or bet_str.endswith('ty'):
        multiplier = 10**9
        if bet_str.endswith('tỷ') or bet_str.endswith('ty'):
            bet_str = bet_str[:-2]
    elif bet_str.endswith('b'):
        multiplier = 10**9
        bet_str = bet_str[:-1]
        
    try: 
        amount = int(float(bet_str) * multiplier)
        return amount if amount > 0 else -1
    except: 
        return -1

def consume_best_illegal_item(user_id, action_type):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute('''SELECT bi.inv_id, bm.name, bm.icon, bm.success_rate, bm.immune_jail, bi.uses_left 
                 FROM black_inventory bi 
                 JOIN black_market bm ON bi.item_id = bm.id 
                 WHERE bi.user_id = ? AND bi.uses_left > 0 AND (bm.target_action = ? OR bm.target_action = 'all')
                 ORDER BY bm.immune_jail DESC, bm.success_rate DESC LIMIT 1''', (user_id, action_type))
    item = c.fetchone()
    if item:
        inv_id, name, icon, rate, immune, uses_left = item
        new_uses = uses_left - 1
        if new_uses > 0: c.execute("UPDATE black_inventory SET uses_left = ? WHERE inv_id = ?", (new_uses, inv_id))
        else: c.execute("DELETE FROM black_inventory WHERE inv_id = ?", (inv_id,))
        conn.commit()
        conn.close()
        return {"name": name, "icon": icon, "rate": rate, "immune": immune == 1, "remains": new_uses}
    conn.close()
    return None

# ================= HỆ THỐNG NAME TAG =================
@bot.message_handler(commands=['setnt'])
def handle_set_nametag(message):
    user_id = message.from_user.id
    if message.chat.type == 'private':
        return reply_msg(message, "⚠️ Lệnh này chỉ dùng được trong nhóm chat!")
        
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    available_tags = []
    
    c.execute("SELECT user_id FROM users ORDER BY balance DESC LIMIT 3")
    top_wealth = [row[0] for row in c.fetchall()]
    if user_id in top_wealth:
        rank = top_wealth.index(user_id) + 1
        if rank == 1: available_tags.append("👑 Trùm Tư Bản")
        elif rank == 2: available_tags.append("💰 Đại Phú Hào")
        else: available_tags.append("💎 Tài Phiệt")
        
    c.execute("SELECT user_id FROM users WHERE rob_count > 0 ORDER BY rob_count DESC LIMIT 1")
    top_rob = c.fetchone()
    if top_rob and top_rob[0] == user_id:
        available_tags.append("🔫 Bố Già")
        
    c.execute("SELECT user_id FROM users WHERE steal_count > 0 ORDER BY steal_count DESC LIMIT 1")
    top_steal = c.fetchone()
    if top_steal and top_steal[0] == user_id:
        available_tags.append("🥷 Siêu Đạo Chích")
        
    c.execute("SELECT user_id FROM users WHERE jail_count > 0 ORDER BY jail_count DESC LIMIT 1")
    top_jail = c.fetchone()
    if top_jail and top_jail[0] == user_id:
        available_tags.append("⛓️ Tù Trưởng")
        
    conn.close()
    
    if not available_tags:
        return reply_msg(message, "❌ Bạn chưa đủ đẳng cấp! Hãy leo lên TOP 1 các bảng xếp hạng tội phạm, hoặc TOP 3 đại gia để nhận Name Tag!")
        
    markup = InlineKeyboardMarkup(row_width=1)
    for tag in available_tags:
        markup.add(InlineKeyboardButton(f"Nhận tag: {tag}", callback_data=f"setnt_{tag}"))
        
    reply_msg(message, "🏷 **HỆ THỐNG DANH HIỆU**\nChúc mừng! Bạn đang đạt điều kiện cho các Name Tag sau. Hãy chọn 1 cái để trang bị:", markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('setnt_'))
def callback_set_nametag(call):
    tag_name = call.data.replace('setnt_', '')
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    name = call.from_user.first_name
    
    try:
        bot.set_chat_administrator_custom_title(chat_id, user_id, tag_name)
        bot.answer_callback_query(call.id, f"✅ Đã đổi Name Tag thành {tag_name}!", show_alert=True)
        send_msg(call.message, f"🎉 Kính thưa quý vị! **{name}** vừa chính thức khoác lên mình danh hiệu: **{tag_name}**!")
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Lỗi: Không thể đổi tag. Có thể bot thiếu quyền hoặc bạn là Creator!", show_alert=True)

# ================= LỆNH CHÀO HỎI & MENU =================
@bot.message_handler(commands=['start'])
def handle_start(message):
    txt = f"👋 Chào {message.from_user.first_name}! Chào mừng bạn đến với Tổ hợp Casino & Thế giới ngầm V10.\n\n👉 Gõ `/helps` hoặc `/menu` để xem luật chơi nhé!"
    reply_msg(message, txt)

@bot.message_handler(commands=['games', 'helps', 'menu', 'help'])
def show_games(message):
    help_text = """
🎮 **HỆ THỐNG LỆNH KINH TẾ BÓNG TỐI (V10)** 🎮

📊 **1. CÁ NHÂN & KINH TẾ**
👉 `/stat` : Xem hồ sơ (Tư pháp, Tiền, Nợ, Tài sản, Hàng cấm).
👉 `/bal` : Tra cứu nhanh số dư.
👉 `/work` : Đi làm kiếm tiền chân chính.
👉 `/khosai` : Lao động công ích giảm án tù.
👉 `/chuyen <số_tiền/all/1/2all>` : (Reply) Chuyển khoản.
👉 `/tops` : Bảng xếp hạng.
👉 `/setnt` : Đổi Name Tag nhóm (Nếu lọt TOP).

🛍️ **2. CHỢ HỢP PHÁP & CHỢ ĐEN (MUA QUA MENU)**
👉 `/cho` : Chợ Đồ Xa Xỉ (Bấm nút).
👉 `/choden` : Thế Giới Ngầm (Bấm nút).
👉 `/flex` : Khoe tài sản công khai.

🥷 **3. ĐẠO CHÍCH & CƯỚP**
👉 `/trom` : (Reply) Trộm đồ hết hạn BH.
👉 `/cuop` : Cướp ngân hàng (Quỹ Tối Đa: 1000 Tỷ/Ngày).

🏦 **4. CẦM ĐỒ & TÍN DỤNG ĐEN**
👉 `/vay <tiền>` | `/tra` : Vay nặng lãi (Max 100 Tỷ).
👉 `/cam <ID_chợ>` | `/chuocdo <ID_chợ>` : Cầm đồ lấy 75% gốc.
👉 `/chuoc` : (Reply) Đóng bảo lãnh ra tù.

🎲 **5. KHU VỰC CASINO**
*(Mẹo gõ tiền gộp: 2tỷ5, 1m5, 500k, all, 1/2all...)*
👉 `/tx <tai/xiu> <tiền>` | `/xu <sap/ngua> <tiền>`
👉 `/cau` : Xem lịch sử 20 ván Tài Xỉu để bắt cầu.
👉 `/spin <tiền>` | `/lo <00-99> <tiền>`
"""
    reply_msg(message, help_text)

# ================= HỒ SƠ TỔNG HỢP /STAT =================
@bot.message_handler(commands=['stat', 'stats', 'profile'])
def show_stat(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    bal = get_balance(user_id, name)
    is_overdue = check_loan_overdue(user_id)
    
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
    loan = c.fetchone()[0]
    
    c.execute('''SELECT m.icon, m.name, i.insurance_expiry, i.is_pawned, m.id 
                 FROM inventory i JOIN market m ON i.item_id = m.id WHERE i.user_id = ?''', (user_id,))
    items = c.fetchall()
    
    # [TỐI ƯU] Gộp nhóm số lần sử dụng hàng cấm
    c.execute('''SELECT bm.icon, bm.name, SUM(bi.uses_left) 
                 FROM black_inventory bi JOIN black_market bm ON bi.item_id = bm.id 
                 WHERE bi.user_id = ? GROUP BY bm.id''', (user_id,))
    black_items = c.fetchall()
    conn.close()
    
    is_jailed, time_left = check_jail(user_id)
    
    txt = f"👤 **HỒ SƠ CÁ NHÂN: {name.upper()}** 👤\n━━━━━━━━━━━━━━━\n"
    if is_jailed: txt += f"🚨 **Tư pháp:** Đang bóc lịch (Còn `{time_left // 60}`p `{time_left % 60}`s)\n"
    else: txt += f"🟢 **Tư pháp:** Công dân tự do\n"
        
    txt += f"💰 **Tiền mặt:** `{format_vnd(bal)} VND`\n"
    txt += f"🏦 **Nợ xấu:** `{format_vnd(loan)} VND` ({'⚠️ QUÁ HẠN x2' if is_overdue else '⏳ Trong hạn' if loan > 0 else 'Không có'})\n"
    txt += "━━━━━━━━━━━━━━━\n🎒 **Kho Tài Sản Hợp Pháp:**\n"
    
    if not items: txt += "*(Trống rỗng...)*\n"
    else:
        now = time.time()
        for item in items:
            icon, item_name, expiry, is_pawned, item_id = item[0], item[1], item[2], item[3], item[4]
            if is_pawned == 1: status = "🏦 [ĐANG CẮM]"
            elif expiry > now: status = f"🛡️ BH còn {int(expiry - now) // 3600}h"
            else: status = "⚠️ HẾT BẢO HIỂM"
            txt += f"➖ {icon} {item_name} (ID: `{item_id}`) -> {status}\n"
            
    txt += "\n🥷 **Kho Hàng Phi Pháp (Tự động dùng):**\n"
    if not black_items: txt += "*(Là công dân tốt, không tàng trữ hàng cấm)*"
    else:
        for b_item in black_items: txt += f"➖ {b_item[0]} {b_item[1]}: `{b_item[2]}` lượt dùng\n"
            
    reply_msg(message, txt)

# ================= BẢNG XẾP HẠNG TOÀN DIỆN (/TOPS) =================
@bot.message_handler(commands=['tops'])
def show_leaderboard(message):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    txt = "🏆 **HỆ THỐNG BẢNG XẾP HẠNG V10** 🏆\n\n"
    
    c.execute("SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 5")
    tops = c.fetchall()
    txt += "💰 **TOP 5 ĐẠI GIA:**\n"
    for i, u in enumerate(tops): txt += f"  {i+1}. {u[0]}: `{format_vnd(u[1])} VND`\n"
    
    c.execute("SELECT first_name, rob_count FROM users WHERE rob_count > 0 ORDER BY rob_count DESC LIMIT 3")
    tops = c.fetchall()
    txt += "\n🥷 **TOP 3 VUA CƯỚP NGÂN HÀNG:**\n"
    if tops:
        for i, u in enumerate(tops): txt += f"  {i+1}. {u[0]}: `{u[1]} phi vụ`\n"
    else: txt += "  *(Chưa có ai cướp thành công)*\n"
    
    c.execute("SELECT first_name, steal_count FROM users WHERE steal_count > 0 ORDER BY steal_count DESC LIMIT 3")
    tops = c.fetchall()
    txt += "\n🕵️ **TOP 3 SIÊU TRỘM:**\n"
    if tops:
        for i, u in enumerate(tops): txt += f"  {i+1}. {u[0]}: `{u[1]} lần trót lọt`\n"
    else: txt += "  *(Chưa có ai trộm thành công)*\n"

    c.execute("SELECT first_name, jail_count FROM users WHERE jail_count > 0 ORDER BY jail_count DESC LIMIT 3")
    tops = c.fetchall()
    txt += "\n🚓 **TOP 3 BÓC LỊCH NHIỀU NHẤT:**\n"
    if tops:
        for i, u in enumerate(tops): txt += f"  {i+1}. {u[0]}: `{u[1]} lần`\n"
    else: txt += "  *(Chưa có ai bị tóm)*\n"

    conn.close()
    reply_msg(message, txt)

# ================= MENU CHỢ HỢP PHÁP (NÚT BẤM) =================
@bot.message_handler(commands=['cho', 'chợ'])
def show_market(message):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT id, name, price, icon FROM market")
    items = c.fetchall()
    conn.close()
    
    markup = InlineKeyboardMarkup(row_width=2)
    txt = "🛒 **CHỢ ĐỒ XA XỈ V10** 🛒\nBấm vào các nút bên dưới để chốt đơn ngay lập tức:\n\n"
    
    for item in items:
        item_id, name, price, icon = item
        txt += f"**{item_id}.** {icon} {name} - Giá: `{format_vnd(price)} VND`\n"
        btn_no_ins = InlineKeyboardButton(f"Mua {icon} (0h BH)", callback_data=f"buy_legal_{item_id}_0")
        btn_ins = InlineKeyboardButton(f"Mua {icon} (+12h BH)", callback_data=f"buy_legal_{item_id}_12")
        markup.row(btn_no_ins, btn_ins)
        
    txt += "\n*(Phí bảo hiểm tính thêm 0.5% giá trị gốc mỗi giờ)*"
    reply_msg(message, txt, markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_legal_'))
def callback_buy_legal(call):
    user_id = call.from_user.id
    name = call.from_user.first_name
    is_jailed, _ = check_jail(user_id)
    if is_jailed:
        return bot.answer_callback_query(call.id, "🚓 Đang đi tù mà đòi mua sắm?", show_alert=True)
    
    data_parts = call.data.replace('buy_legal_', '').split('_')
    item_id, hours = int(data_parts[0]), int(data_parts[1])
    
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT name, price, icon FROM market WHERE id = ?", (item_id,))
    item = c.fetchone()
    if not item:
        conn.close()
        return bot.answer_callback_query(call.id, "❌ Lỗi: Vật phẩm không tồn tại!", show_alert=True)
        
    item_name, item_price, item_icon = item
    insurance_fee = int(item_price * 0.005 * hours)
    total_price = item_price + insurance_fee
    
    bal = get_balance(user_id, name)
    if bal < total_price:
        conn.close()
        return bot.answer_callback_query(call.id, f"❌ Thiếu tiền! Bạn cần {format_vnd(total_price)} VND.", show_alert=True)
        
    expiry = time.time() + (hours * 3600) if hours > 0 else 0
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_price, user_id))
    c.execute("INSERT INTO inventory (user_id, item_id, insurance_expiry, is_pawned) VALUES (?, ?, ?, 0)", (user_id, item_id, expiry))
    conn.commit()
    conn.close()
    
    ins_txt = f"🛡️ Đã bao gồm {hours}h Bảo hiểm!" if hours > 0 else "⚠️ KHÔNG BẢO HIỂM!"
    bot.answer_callback_query(call.id, f"✅ Đã mua {item_name} thành công!")
    send_msg(call.message, f"🛍️ **{name}** vừa chốt đơn **{item_icon} {item_name}** với giá `{format_vnd(total_price)} VND`. {ins_txt}")

# ================= MENU CHỢ ĐEN (NÚT BẤM) =================
@bot.message_handler(commands=['choden', 'chợđen'])
def show_black_market(message):
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT id, name, price, icon, target_action, success_rate, immune_jail, max_uses FROM black_market")
    items = c.fetchall()
    conn.close()
    
    markup = InlineKeyboardMarkup(row_width=1)
    txt = "🥷 **CHỢ ĐEN - THẾ GIỚI NGẦM V10** 🥷\nBấm nút để giao dịch bí mật:\n\n"
    
    for item in items:
        item_id, name, price, icon, action, rate, immune, uses = item
        action_name = "Cướp/Trộm" if action == 'all' else "Cướp NH" if action == 'cuop' else "Trộm Đồ"
        immune_txt = " | 🛡️ **CHỐNG ĐI TÙ**" if immune == 1 else ""
        
        txt += f"**{icon} {name}** - `{format_vnd(price)} VND`\n"
        txt += f"└ ⚡ Tác dụng: Tăng tỷ lệ {action_name} lên **{rate}%**{immune_txt} (Dùng {uses} lần)\n\n"
        
        btn = InlineKeyboardButton(f"Mua {icon} {name}", callback_data=f"buy_illegal_{item_id}")
        markup.add(btn)
        
    reply_msg(message, txt, markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_illegal_'))
def callback_buy_illegal(call):
    user_id = call.from_user.id
    name = call.from_user.first_name
    is_jailed, _ = check_jail(user_id)
    if is_jailed:
        return bot.answer_callback_query(call.id, "🚓 Đang đi tù cấm mua hàng cấm!", show_alert=True)
        
    item_id = int(call.data.replace('buy_illegal_', ''))
    
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT name, price, icon, max_uses FROM black_market WHERE id = ?", (item_id,))
    item = c.fetchone()
    if not item:
        conn.close()
        return bot.answer_callback_query(call.id, "❌ Lỗi: Không tồn tại!", show_alert=True)
        
    i_name, i_price, i_icon, i_uses = item
    bal = get_balance(user_id, name)
    if bal < i_price:
        conn.close()
        return bot.answer_callback_query(call.id, f"❌ Thiếu tiền! Cần {format_vnd(i_price)} VND.", show_alert=True)
        
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (i_price, user_id))
    c.execute("INSERT INTO black_inventory (user_id, item_id, uses_left) VALUES (?, ?, ?)", (user_id, item_id, i_uses))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, f"✅ Giao dịch ngầm {i_name} thành công!")
    send_msg(call.message, f"🥷 **{name}** vừa nhận mật hàng {i_icon} **{i_name}** từ thế giới ngầm.")

# ================= CÁC LỆNH TÀI CHÍNH & VAY MƯỢN =================
@bot.message_handler(commands=['balance', 'bal'])
def check_balance(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    bal = get_balance(user_id, name)
    is_overdue = check_loan_overdue(user_id)
    
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
    loan = c.fetchone()[0]
    conn.close()
    
    is_jailed, time_left = check_jail(user_id)
    jail_status = f"\n🚓 Đang ở tù (Còn {time_left // 60}p {time_left % 60}s)" if is_jailed else ""
    
    msg = f"💳 **{name}**, tài khoản có: `{format_vnd(bal)} VND`{jail_status}"
    if loan > 0: msg += f"\n🏦 Đang nợ: `{format_vnd(loan)} VND` ({'⚠️ QUÁ HẠN x2' if is_overdue else '⏳ Trong hạn'})"
    reply_msg(message, msg)

@bot.message_handler(commands=['chuyen', 'chotien', 'pay'])
def transfer_money(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, f"🚓 Đang đi tù thì không chuyển được tiền.")
    
    if not is_valid_reply(message): 
        return reply_msg(message, "⚠️ Vui lòng **Reply (Trả lời)** đúng tin nhắn của người bạn muốn chuyển tiền!")
        
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.first_name
    if target_id == user_id: return reply_msg(message, "❌ Không tự chuyển tiền cho mình!")
    if message.reply_to_message.from_user.is_bot: return reply_msg(message, "❌ Không chuyển cho Bot!")
        
    args = message.text.split()
    if len(args) < 2: return reply_msg(message, "⚠️ Cú pháp: `/chuyen <tiền>`")
    bal = get_balance(user_id, name)
    
    # Nối toàn bộ phần tiền (Cho phép /chuyen 2 tỷ 5)
    bet_str = "".join(args[1:])
    amount = get_bet_amount(bet_str, bal)
    
    if amount <= 0: return reply_msg(message, "❌ Số tiền không hợp lệ!")
    if amount > bal: return reply_msg(message, "❌ Bạn không đủ tiền trong ví để chuyển khoản!")
    
    get_balance(target_id, target_name)
    update_balance(user_id, -amount)
    update_balance(target_id, amount)
    reply_msg(message, f"💸 **GIAO DỊCH XONG!**\nĐã gửi `{format_vnd(amount)} VND` cho **{target_name}**.")

@bot.message_handler(commands=['vay'])
def borrow_money(message):
    user_id = message.from_user.id
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, f"🚓 Đang đi tù không được duyệt vay.")
    
    name = message.from_user.first_name
    get_balance(user_id, name)
    args = message.text.split()
    if len(args) < 2: return reply_msg(message, "⚠️ Cú pháp: `/vay <tiền>` (VD: /vay 5tr, /vay 2tỷ5)")
    
    bet_str = "".join(args[1:])
    amount = get_bet_amount(bet_str, LOAN_LIMIT)
    if amount <= 0 or amount > LOAN_LIMIT: return reply_msg(message, f"❌ Tiền vay không hợp lệ hoặc Vượt quá hạn mức tối đa `{format_vnd(LOAN_LIMIT)} VND`!")

    check_loan_overdue(user_id)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone()[0] > 0: return reply_msg(message, "❌ Đang có nợ chưa trả! Gõ `/tra`.")
    
    c.execute("UPDATE users SET balance = balance + ?, loan = ?, loan_time = ? WHERE user_id = ?", (amount, amount, time.time(), user_id))
    conn.commit()
    conn.close()
    reply_msg(message, f"🏦 Đã giải ngân khoản vay `{format_vnd(amount)} VND`.\n⏳ Hạn thanh toán: 10 phút.")

@bot.message_handler(commands=['tra'])
def repay_money(message):
    user_id = message.from_user.id
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Ở tù không thanh toán nợ được.")
    
    check_loan_overdue(user_id)
    bal = get_balance(user_id, message.from_user.first_name)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
    loan = c.fetchone()[0]
    
    if loan == 0: return reply_msg(message, "🤝 Bạn không nợ ai cả!")
    if bal < loan: return reply_msg(message, f"❌ Không đủ tiền! Bạn cần `{format_vnd(loan)} VND`.")
    
    c.execute("UPDATE users SET balance = balance - ?, loan = 0, loan_time = 0 WHERE user_id = ?", (loan, user_id))
    conn.commit()
    conn.close()
    reply_msg(message, f"✅ Đã thanh toán sòng phẳng nợ gốc và phạt: `{format_vnd(loan)} VND`.")

# ================= CÔNG VIỆC CHÂN CHÍNH =================
@bot.message_handler(commands=['work'])
def handle_work(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return reply_msg(message, f"🚓 Bạn đang ở tù! Gõ `/khosai` để lao động giảm án thay vì `/work`.")
    
    name = message.from_user.first_name
    get_balance(user_id, name)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    rate = random.randint(1, 100)
    if rate <= 70: rarity, tag = "common", "🟢 [THƯỜNG]"
    elif rate <= 95: rarity, tag = "rare", "🔵 [HIẾM]"
    else: rarity, tag = "legendary", "🟡 [HUYỀN THOẠI]"

    c.execute("SELECT description, min_pay, max_pay FROM jobs WHERE rarity = ?", (rarity,))
    jobs = c.fetchall()
    if not jobs:
        c.execute("SELECT description, min_pay, max_pay FROM jobs WHERE rarity = 'common'")
        jobs = c.fetchall()
        tag = "🟢 [THƯỜNG]"
    job = random.choice(jobs)
    earned = random.randint(job[1], job[2])
    
    is_overdue = check_loan_overdue(user_id)
    if is_overdue:
        c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
        current_loan = c.fetchone()[0]
        if earned >= current_loan:
            left_over = earned - current_loan
            c.execute("UPDATE users SET balance = balance + ?, loan = 0, loan_time = 0 WHERE user_id = ?", (left_over, user_id))
            reply_msg(message, f"🚨 **PHẠT NỢ x2!** Kiếm được `{format_vnd(earned)} VND`.\n⚠️ Đã bị siết để **TRẢ HẾT NỢ**, dư `{format_vnd(left_over)} VND` trả về ví.")
        else:
            c.execute("UPDATE users SET loan = loan - ? WHERE user_id = ?", (earned, user_id))
            reply_msg(message, f"🚨 **PHẠT NỢ x2!** Kiếm được `{format_vnd(earned)} VND`.\n⚠️ Bị tịch thu 100%! Nợ còn: `{format_vnd(current_loan - earned)} VND`.")
        conn.commit()
        conn.close()
        return

    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earned, user_id))
    conn.commit()
    conn.close()
    reply_msg(message, f"{tag} Bạn vừa **{job[0]}** và nhận được `{format_vnd(earned)} VND`!")

@bot.message_handler(commands=['khosai', 'khổsai'])
def prison_labor(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if not is_jailed: return reply_msg(message, "✅ Bạn đang tự do, không cần lao động khổ sai!")
        
    reduce_time = random.randint(1, 300)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    if time_left - reduce_time <= 0:
        c.execute("UPDATE users SET jail_time = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        reply_msg(message, f"⛏️ Bạn chà sạch bồn cầu và được giảm `{reduce_time}` giây!\n🎉 **CHÚC MỪNG!** Bạn đã hoàn thành án phạt và được trả tự do sớm!")
    else:
        c.execute("UPDATE users SET jail_time = jail_time - ? WHERE user_id = ?", (reduce_time, user_id))
        conn.commit()
        new_left = time_left - reduce_time
        reply_msg(message, f"⛏️ Đập đá mệt nhọc... Quản ngục giảm án cho `{reduce_time}` giây!\n🚓 Còn lại: `{new_left // 60}` phút `{new_left % 60}` giây.")
    conn.close()

# ================= CƯỚP, TRỘM & CHUỘC TÙ =================
@bot.message_handler(commands=['cuop'])
def rob_bank(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    get_balance(user_id, name)
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Đang trong phòng giam, cướp bằng niềm tin à?")
    
    current_time = time.time()
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT last_cuop FROM users WHERE user_id = ?", (user_id,))
    last_cuop = c.fetchone()[0]
    
    if current_time - last_cuop < 600:
        return reply_msg(message, f"🕵️ Cảnh sát đang lùng sục! Chờ thêm `{int(600 - (current_time - last_cuop))}` giây nữa.")
        
    win_amount = 100000000000 # 100 TỶ
    daily_pool = get_daily_bank_pool()
    if daily_pool < win_amount:
        return reply_msg(message, "🏦 **KÉT SẮT TRỐNG RỖNG!**\nNgân hàng thành phố hôm nay đã bị các băng đảng khác khoắng sạch (Hết hạn mức 1,000 Tỷ/ngày). Hãy quay lại vào ngày mai!")

    c.execute("UPDATE users SET last_cuop = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    success_rate = 5 
    immune_jail = False
    buff_msg = ""
    used_item = consume_best_illegal_item(user_id, 'cuop')
    if used_item:
        success_rate = used_item['rate']
        immune_jail = used_item['immune']
        rem_msg = f"Còn {used_item['remains']} lần" if used_item['remains'] > 0 else "Vật phẩm đã hỏng"
        buff_msg = f"\n{used_item['icon']} *Hệ thống tự động sử dụng {used_item['name']}! Tỉ lệ thắng: {success_rate}%. ({rem_msg})*\n"

    if random.randint(1, 100) <= success_rate:
        deduct_bank_pool(win_amount)
        c.execute("UPDATE users SET balance = balance + ?, rob_count = rob_count + 1 WHERE user_id = ?", (win_amount, user_id))
        conn.commit()
        reply_msg(message, f"{buff_msg}🥷 **CƯỚP NGÂN HÀNG THÀNH CÔNG!** Nhận được: `+{format_vnd(win_amount)} VND`! 💰🔥")
    else:
        if immune_jail:
            reply_msg(message, f"{buff_msg}🚓 **THẤT BẠI NHƯNG MAY MẮN!**\nNhờ sức mạnh của vật phẩm phi pháp, bạn tẩu thoát an toàn mà không bị bắt!")
        else:
            c.execute("UPDATE users SET jail_time = ?, jail_count = jail_count + 1 WHERE user_id = ?", (current_time, user_id))
            conn.commit()
            reply_msg(message, f"{buff_msg}🚓 **THẤT BẠI!** Bạn bị bế lên phường.\n⚖️ Hình phạt: Đi tù **1 Giờ**.")
    conn.close()

@bot.message_handler(commands=['trom', 'trộm'])
def steal_item(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, f"🚓 Đang đi tù thì ngồi im!")
    
    if not is_valid_reply(message): 
        return reply_msg(message, "⚠️ Phải **Reply (Trả lời)** tin nhắn của mục tiêu để trộm đồ!")
        
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.first_name
    if target_id == user_id: return reply_msg(message, "❌ Tự trộm đồ của mình?")
    if message.reply_to_message.from_user.is_bot: return reply_msg(message, "❌ Robot không có đồ hiệu!")
        
    get_balance(target_id, target_name)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    now = time.time()
    c.execute('''SELECT i.inv_id, m.name, m.icon, i.insurance_expiry 
                 FROM inventory i JOIN market m ON i.item_id = m.id 
                 WHERE i.user_id = ? AND i.is_pawned = 0''', (target_id,))
    all_items = c.fetchall()
    
    uninsured_items = [item for item in all_items if item[3] < now]
    if not uninsured_items:
        conn.close()
        return reply_msg(message, f"🔐 **SƠ HỞ BẰNG KHÔNG!** Nhà của **{target_name}** bảo mật quá gắt!")
        
    success_rate = 30 
    immune_jail = False
    buff_msg = ""
    used_item = consume_best_illegal_item(user_id, 'trom')
    if used_item:
        success_rate = used_item['rate']
        immune_jail = used_item['immune']
        rem_msg = f"Còn {used_item['remains']} lần" if used_item['remains'] > 0 else "Vật phẩm tiêu biến"
        buff_msg = f"\n{used_item['icon']} *Đã dùng {used_item['name']}! Tỉ lệ trộm: {success_rate}%. ({rem_msg})*\n"

    if random.randint(1, 100) <= success_rate:
        stolen = random.choice(uninsured_items)
        inv_id, item_name, item_icon = stolen[0], stolen[1], stolen[2]
        c.execute("UPDATE inventory SET user_id = ?, insurance_expiry = 0 WHERE inv_id = ?", (user_id, inv_id))
        c.execute("UPDATE users SET steal_count = steal_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        reply_msg(message, f"{buff_msg}🥷 **TRỘM TRÓT LỌT!**\nBạn đã cuỗm chiếc **{item_icon} {item_name}** của **{target_name}**!")
    else:
        if immune_jail:
            reply_msg(message, f"{buff_msg}🚓 **BÁO ĐỘNG NHƯNG KỊP TRỐN THOÁT!**\nChủ nhà thức giấc, nhờ vật phẩm phi pháp, bạn chạy thoát không để lại dấu vết!")
        else:
            c.execute("UPDATE users SET jail_time = ?, jail_count = jail_count + 1 WHERE user_id = ?", (time.time(), user_id))
            conn.commit()
            reply_msg(message, f"{buff_msg}🚓 **HỆ THỐNG BÁO ĐỘNG!**\nBạn bị tóm tại trận.\n⚖️ Hình phạt: Đi tù **1 Giờ đồng hồ**.")
    conn.close()

@bot.message_handler(commands=['chuoc', 'chuộc'])
def bail_prisoner(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 **BẠN ĐANG Ở TRONG TÙ!** Phạm nhân không thể nộp tiền bảo lãnh.")
    
    if not is_valid_reply(message): 
        return reply_msg(message, "⚠️ Bạn phải **Reply (Trả lời)** tin nhắn của phạm nhân đang ở trong tù!")
        
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.first_name
    target_jailed, time_left = check_jail(target_id)
    if not target_jailed: return reply_msg(message, f"❌ **{target_name}** hiện tại đang tự do ngoài xã hội!")
        
    minutes_left = math.ceil(time_left / 60)
    bail_cost = minutes_left * BAIL_FEE_PER_MIN
    bal = get_balance(user_id, name)
    if bal < bail_cost: return reply_msg(message, f"❌ Bạn cần `{format_vnd(bail_cost)} VND` để bảo lãnh **{target_name}**, ví chỉ có `{format_vnd(bal)} VND`.")
        
    update_balance(user_id, -bail_cost)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("UPDATE users SET jail_time = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    reply_msg(message, f"⚖️ **PHÓNG THÍCH!**\n**{name}** đã nộp khoản tiền bảo lãnh `{format_vnd(bail_cost)} VND`.\n🎉 Chúc mừng **{target_name}** được tự do!")

# ================= CẦM ĐỒ =================
@bot.message_handler(commands=['cam', 'cắm'])
def pawn_item(message):
    user_id = message.from_user.id
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Đang ở tù cấm cắm đồ.")
    args = message.text.split()
    if len(args) < 2: return reply_msg(message, "⚠️ Cú pháp: `/cam <ID_chợ>`")
    try: item_id = int(args[1])
    except: return
    
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT inv_id FROM inventory WHERE user_id = ? AND item_id = ? AND is_pawned = 0 LIMIT 1", (user_id, item_id))
    inv_data = c.fetchone()
    if not inv_data: return reply_msg(message, "❌ Bạn không sở hữu món này hoặc đồ đã bị cắm/trộm!")
        
    inv_id = inv_data[0]
    c.execute("SELECT name, price, icon FROM market WHERE id = ?", (item_id,))
    market_data = c.fetchone()
    item_name, item_price, item_icon = market_data[0], market_data[1], market_data[2]
    pawn_payout = int(item_price * 0.75)
    
    c.execute("UPDATE inventory SET is_pawned = 1 WHERE inv_id = ?", (inv_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (pawn_payout, user_id))
    conn.commit()
    conn.close()
    reply_msg(message, f"🏦 **TIỆM CẦM ĐỒ GIẢI NGÂN!**\nĐã cắm **{item_icon} {item_name}** lấy `+{format_vnd(pawn_payout)} VND`.\n💸 Chuộc lại tốn 200% gốc qua lệnh: `/chuocdo {item_id}`.")

@bot.message_handler(commands=['chuocdo', 'chuộcđồ'])
def redeem_item(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Đang bóc lịch không đi chuộc đồ được.")
    args = message.text.split()
    if len(args) < 2: return reply_msg(message, "⚠️ Cú pháp: `/chuocdo <ID_chợ>`")
    try: item_id = int(args[1])
    except: return
    
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("SELECT inv_id FROM inventory WHERE user_id = ? AND item_id = ? AND is_pawned = 1 LIMIT 1", (user_id, item_id))
    inv_data = c.fetchone()
    if not inv_data: return reply_msg(message, "❌ Bạn không có món đồ này ở tiệm cầm đồ!")
        
    inv_id = inv_data[0]
    c.execute("SELECT name, price, icon FROM market WHERE id = ?", (item_id,))
    market_data = c.fetchone()
    item_name, item_price, item_icon = market_data[0], market_data[1], market_data[2]
    redeem_cost = int(item_price * 2.0) 
    
    bal = get_balance(user_id, name)
    if bal < redeem_cost: return reply_msg(message, f"❌ Cần `{format_vnd(redeem_cost)} VND` để chuộc!")
        
    c.execute("UPDATE inventory SET is_pawned = 0, insurance_expiry = 0 WHERE inv_id = ?", (inv_id,))
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (redeem_cost, user_id))
    conn.commit()
    conn.close()
    reply_msg(message, f"✅ **CHUỘC THÀNH CÔNG!**\nTrích `{format_vnd(redeem_cost)} VND` lấy lại **{item_icon} {item_name}**.\n⚠️ Đồ chuộc về KHÔNG CÓ BẢO HIỂM!")

@bot.message_handler(commands=['flex'])
def flex_inventory(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    bal = get_balance(user_id, name)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute('''SELECT m.icon, m.name, i.insurance_expiry, COUNT(*) 
                 FROM inventory i JOIN market m ON i.item_id = m.id 
                 WHERE i.user_id = ? AND i.is_pawned = 0
                 GROUP BY m.id, i.insurance_expiry''', (user_id,))
    items = c.fetchall()
    conn.close()
    
    txt = f"😎 **SHOWROOM CỦA ĐẠI GIA {name.upper()}** 😎\n\n💳 **Tiền mặt:** `{format_vnd(bal)} VND`\n\n🎒 **Tài sản trưng bày:**\n"
    if not items: txt += "*(Trống rỗng...)*"
    else:
        now = time.time()
        for item in items:
            icon, item_name, expiry, count = item[0], item[1], item[2], item[3]
            if expiry > now:
                rem = int(expiry - now)
                ins_txt = f"🛡️ BH {rem // 3600}h {(rem % 3600) // 60}p"
            else: ins_txt = "⚠️ KHÔNG BẢO HIỂM"
            txt += f"➖ `{count}x` {icon} {item_name} ({ins_txt})\n"
    reply_msg(message, txt)

# ================= SOI CẦU TÀI XỈU =================
@bot.message_handler(commands=['cau', 'cầu'])
def show_cau_taixiu(message):
    global tx_history
    if not tx_history:
        return reply_msg(message, "🎲 Bàn Tài Xỉu mới mở, chưa có ván nào được lắc. Cầu đang trắng!")
        
    cau_str = " - ".join(tx_history)
    tai_count = tx_history.count("🔴 TÀI")
    xiu_count = tx_history.count("⚫ XỈU")
    
    txt = f"📊 **BẢNG SOI CẦU TÀI XỈU (20 Ván Gần Nhất)** 📊\n\n"
    txt += f"👉 KẾT QUẢ: {cau_str}\n\n"
    txt += f"📈 **Thống kê:** TÀI (`{tai_count}`) | XỈU (`{xiu_count}`)\n"
    txt += "*(Bí quyết: Đỏ đánh Tài, Đen đánh Xỉu, không biết đánh gì thì All-in)*"
    
    reply_msg(message, txt)

# ================= CASINO CÓ ĐẦY ĐỦ HIỆU ỨNG =================
@bot.message_handler(commands=['tx'])
def play_taixiu(message):
    global tx_history
    user_id = message.from_user.id
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Đang đi tù cấm đánh bạc!")
    is_overdue = check_loan_overdue(user_id)
    if is_overdue: return reply_msg(message, "⛔ Tài khoản đóng băng do trốn nợ!")

    args = message.text.split()
    if len(args) < 3 or args[1].lower() not in ['tai', 'tài', 'xiu', 'xỉu']: return reply_msg(message, "⚠️ Dùng: `/tx <tai/xiu> <tiền>`")
    bal = get_balance(user_id, message.from_user.first_name)
    
    bet_str = "".join(args[2:])
    bet = get_bet_amount(bet_str, bal)
    if bet <= 0: return reply_msg(message, "❌ Số tiền cược không hợp lệ!")
    if bet > bal: return reply_msg(message, "❌ Bạn không đủ tiền trong ví để cược!")
    
    update_balance(user_id, -bet)
    d1, d2, d3 = random.randint(1,6), random.randint(1,6), random.randint(1,6)
    total = d1 + d2 + d3
    res_str = "tai" if total >= 11 else "xiu"
    
    tx_history.append("🔴 TÀI" if res_str == 'tai' else "⚫ XỈU")
    if len(tx_history) > 20: tx_history.pop(0)
    
    send_msg(message, f"🎲 Đang lắc xúc xắc...\nCạch cạch cạch... Kết quả: **{d1} - {d2} - {d3}**\n👉 Tổng điểm: **{total} ({'TÀI' if res_str=='tai' else 'XỈU'})**\n*(Tiền cược: {format_vnd(bet)} VND)*")
    if (args[1].lower() in ['tai', 'tài'] and res_str == "tai") or (args[1].lower() in ['xiu', 'xỉu'] and res_str == "xiu"):
        update_balance(user_id, bet * 2)
        reply_msg(message, f"🎉 Thắng `+{format_vnd(bet*2)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`")
    else:
        reply_msg(message, f"💸 Thua mất `{format_vnd(bet)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`")

@bot.message_handler(commands=['xu'])
def play_coin(message):
    user_id = message.from_user.id
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Đang ở tù cấm chơi xu!")
    is_overdue = check_loan_overdue(user_id)
    if is_overdue: return reply_msg(message, "⛔ Trốn nợ bị phong tỏa tài sản!")

    args = message.text.split()
    if len(args) < 3 or args[1].lower() not in ['sap', 'sấp', 'ngua', 'ngửa']: return reply_msg(message, "⚠️ Cú pháp: `/xu <sap/ngua> <tiền>`")
    bal = get_balance(user_id, message.from_user.first_name)
    
    bet_str = "".join(args[2:])
    bet = get_bet_amount(bet_str, bal)
    if bet <= 0: return reply_msg(message, "❌ Số tiền cược không hợp lệ!")
    if bet > bal: return reply_msg(message, "❌ Bạn không đủ tiền trong ví để cược!")
    
    update_balance(user_id, -bet)
    coin_result = random.choice(['sap', 'ngua'])
    result_display = "SẤP 🪙" if coin_result == 'sap' else "NGỬA 🪙"
    
    send_msg(message, f"🪙 Đồng xu đang xoay tròn trên không trung...\nLeng keng... Kết quả: **{result_display}**\n*(Tiền cược: {format_vnd(bet)} VND)*")
    player_choice = 'sap' if args[1].lower() in ['sap', 'sấp'] else 'ngua'
    if player_choice == coin_result:
        update_balance(user_id, bet * 2)
        reply_msg(message, f"🎉 Thắng trúng tủ! `+{format_vnd(bet*2)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`")
    else:
        reply_msg(message, f"💸 Đoán sai mất trắng! Số dư: `{format_vnd(get_balance(user_id))} VND`")

@bot.message_handler(commands=['spin'])
def play_spin(message):
    user_id = message.from_user.id
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Trong tù không được quay thưởng.")
    is_overdue = check_loan_overdue(user_id)
    if is_overdue: return reply_msg(message, "⛔ Hãy gõ /tra nợ trước!")

    args = message.text.split()
    if len(args) < 2: return reply_msg(message, "⚠️ Cú pháp: `/spin <tiền>`")
    bal = get_balance(user_id, message.from_user.first_name)
    
    bet_str = "".join(args[1:])
    bet = get_bet_amount(bet_str, bal)
    if bet <= 0: return reply_msg(message, "❌ Số tiền cược không hợp lệ!")
    if bet > bal: return reply_msg(message, "❌ Bạn không đủ tiền trong ví để quay!")
    
    update_balance(user_id, -bet)
    wheel_options = [(0, "Mất Trắng ❌"), (0, "Mất Trắng ❌"), (0.5, "Hoàn 50% 🌗"), (1, "Hòa Vốn 🟡"), (1.5, "Thắng Nhẹ 📈"), (2, "Nhân Đôi 🔥"), (5, "🚨 JACKPOT (5x) 💎")]
    multiplier, text_result = random.choice(wheel_options)
    win_money = int(bet * multiplier)
    update_balance(user_id, win_money)
    
    announcement = f"🎡 **VÒNG QUAY MAY MẮN ĐANG XOAY...** \n*(Cược: {format_vnd(bet)} VND)*\n\n🎯 Kết quả: Ô **{text_result}**\n"
    if multiplier > 1: announcement += f"🎉 Được cộng: `+{format_vnd(win_money)} VND`!"
    elif multiplier == 1: announcement += f"🟡 Nhận lại đủ tiền cược!"
    elif multiplier == 0.5: announcement += f"🌗 Vớt vát lại: `+{format_vnd(win_money)} VND`."
    else: announcement += f"💸 Mất trắng!"
    reply_msg(message, announcement + f"\n💳 Số dư: `{format_vnd(get_balance(user_id))} VND`")

@bot.message_handler(commands=['lo', 'lô'])
def play_lo(message):
    user_id = message.from_user.id
    is_jailed, _ = check_jail(user_id)
    if is_jailed: return reply_msg(message, "🚓 Đi tù cấm ôm bảng lô!")
    is_overdue = check_loan_overdue(user_id)
    if is_overdue: return reply_msg(message, "⛔ Bị khóa cờ bạc!")

    args = message.text.split()
    if len(args) < 3 or not args[1].isdigit() or len(args[1]) != 2: return reply_msg(message, "⚠️ Dùng: `/lo <00-99> <tiền>`")
    bal = get_balance(user_id, message.from_user.first_name)
    
    bet_str = "".join(args[2:])
    bet = get_bet_amount(bet_str, bal)
    if bet <= 0: return reply_msg(message, "❌ Số tiền cược không hợp lệ!")
    if bet > bal: return reply_msg(message, "❌ Bạn không đủ tiền trong ví để ghi lô!")
    
    update_balance(user_id, -bet)
    winning_num = str(random.randint(0, 99)).zfill(2)
    send_msg(message, f"🎰 Nhà đài đang quay thưởng giải độc đắc...\nLồng cầu dừng lại ở con số: **{winning_num}**\n*(Cược: {format_vnd(bet)} VND)*")
    if args[1] == winning_num:
        update_balance(user_id, bet * 70)
        reply_msg(message, f"🏆 TRÚNG LÔ x70: `+{format_vnd(bet*70)} VND`! Số dư: `{format_vnd(get_balance(user_id))} VND`")
    else:
        reply_msg(message, f"💸 Tạch lô, ra đê mà ở nhé! Số dư: `{format_vnd(get_balance(user_id))} VND`")

# ================= LỆNH ADMIN =================
@bot.message_handler(commands=['admin'])
def show_admin_commands(message):
    if message.from_user.id != ADMIN_ID: return
    admin_text = "👑 **LỆNH QUẢN TRỊ VIÊN** 👑\n👉 `/addjob <common/rare/legendary> <min> <max> <mô_tả>`\n👉 `/addmoney <tiền>` | `/takemoney <tiền>` | `/setmoney <tiền>` (Reply)\n👉 `/globalwipe` : Reset server."
    reply_msg(message, admin_text)

@bot.message_handler(commands=['addjob'])
def admin_add_job(message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=4)
    if len(parts) < 5 or parts[1].lower() not in ['common', 'rare', 'legendary']: return
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("INSERT INTO jobs (description, rarity, min_pay, max_pay) VALUES (?, ?, ?, ?)", (parts[4], parts[1].lower(), int(parts[2]), int(parts[3])))
    conn.commit()
    conn.close()
    reply_msg(message, "✅ Đã thêm việc làm thành công!")

@bot.message_handler(commands=['addmoney'])
def cheat_add(message):
    if message.from_user.id != ADMIN_ID: return
    if not is_valid_reply(message): return reply_msg(message, "⚠️ Vui lòng reply đúng tin nhắn người nhận!")
    try: amount = int(message.text.split()[1])
    except: return reply_msg(message, "⚠️ Cú pháp: `/addmoney <số_tiền>`")
    t_id, t_name = message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name
    get_balance(t_id, t_name)
    update_balance(t_id, amount)
    reply_msg(message, f"👑 Đã bơm `+{format_vnd(amount)} VND` cho **{t_name}**")

@bot.message_handler(commands=['takemoney'])
def cheat_take(message):
    if message.from_user.id != ADMIN_ID: return
    if not is_valid_reply(message): return reply_msg(message, "⚠️ Vui lòng reply đúng tin nhắn đối tượng!")
    try: amount = int(message.text.split()[1])
    except: return reply_msg(message, "⚠️ Cú pháp: `/takemoney <số_tiền>`")
    t_id, t_name = message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name
    get_balance(t_id, t_name)
    update_balance(t_id, -amount)
    reply_msg(message, f"⚡ Đã thu `-{format_vnd(amount)} VND` của **{t_name}**")

@bot.message_handler(commands=['setmoney'])
def cheat_set(message):
    if message.from_user.id != ADMIN_ID: return
    if not is_valid_reply(message): return reply_msg(message, "⚠️ Vui lòng reply đúng tin nhắn đối tượng!")
    try: amount = int(message.text.split()[1])
    except: return reply_msg(message, "⚠️ Cú pháp: `/setmoney <số_tiền>`")
    t_id, t_name = message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name
    get_balance(t_id, t_name)
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, t_id))
    conn.commit()
    conn.close()
    reply_msg(message, f"🔧 Set số dư của **{t_name}** thành `{format_vnd(amount)} VND`")

@bot.message_handler(commands=['globalwipe'])
def cheat_wipe(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('economy_v10.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = 0, loan = 0, loan_time = 0, jail_time = 0, last_cuop = 0, jail_count = 0, rob_count = 0, steal_count = 0")
    c.execute("DELETE FROM inventory")
    c.execute("DELETE FROM black_inventory")
    c.execute("DELETE FROM server_stats")
    global tx_history
    tx_history = []
    conn.commit()
    conn.close()
    reply_msg(message, "🚨 Server đã bị reset hoàn toàn dữ liệu về vạch xuất phát!")

if __name__ == "__main__":
    init_db()
    print("Bot đang chạy bản V10 Cực Đỉnh! Đã thêm giới hạn cướp ngân hàng, đọc tắt tiền tệ 2tỷ5 và gộp đồ phi pháp.")
    bot.polling(none_stop=True)