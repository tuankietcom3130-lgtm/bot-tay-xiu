import telebot
import sqlite3
import random
import time
import os
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(API_TOKEN)

# ================= HÀM BỔ TRỢ =================
def format_vnd(amount):
    return f"{amount:,}"

def init_db():
    conn = sqlite3.connect('economy_final.db')
    c = conn.cursor()
    
    # Bảng người dùng
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, last_work REAL DEFAULT 0)''')
                 
    # Bảng công việc
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT, rarity TEXT, min_pay INTEGER, max_pay INTEGER)''')
    conn.commit()
    
    # Nạp 15 việc mẫu nếu bảng jobs trống
    c.execute("SELECT COUNT(*) FROM jobs")
    if c.fetchone()[0] == 0:
        default_jobs = [
            ("đi phụ hồ bốc gạch gãy cả lưng", "common", 50000, 150000),
            ("giao trà sữa giữa trưa nắng 40 độ gặp ngay bom hàng", "common", 50000, 150000),
            ("bán vé số dạo dạo quanh hồ Gươm", "common", 50000, 150000),
            ("làm content creator trên TikTok được hẳn 3 view", "common", 50000, 150000),
            ("đi rải tờ rơi ngã tư bị chó đuổi suýt quăng cả xe", "common", 50000, 150000),
            ("làm phục vụ quán cà phê bị khách đổ thừa làm vỡ ly", "common", 50000, 150000),
            ("thức đêm trực nét ngồi gục cằm xuống bàn ngủ quên", "common", 50000, 150000),
            ("nhặt ve chai vô tình lượm được bí kíp võ công mang bán", "rare", 200000, 600000),
            ("viết code thuê cho sếp cả đêm may mắn được thưởng nóng", "rare", 200000, 600000),
            ("đi lau kính tòa nhà Landmark 81 được sếp khen quả cảm", "rare", 200000, 600000),
            ("livestream bán quần áo chốt được hẳn 50 đơn hàng thật", "rare", 200000, 600000),
            ("làm gia sư dạy học sinh tiểu học được phụ huynh bồi dưỡng thêm", "rare", 200000, 600000),
            ("vô tình đào móng nhà trúng hũ vàng ròng từ thời phong kiến", "legendary", 1000000, 5000000),
            ("được một vị đại gia bí ẩn bao nuôi, cấp cho thẻ đen vô hạn", "legendary", 1000000, 5000000),
            ("mua bừa tờ vé số kiến thiết ai dè trúng ngay giải độc đắc", "legendary", 1000000, 5000000)
        ]
        c.executemany("INSERT INTO jobs (description, rarity, min_pay, max_pay) VALUES (?, ?, ?, ?)", default_jobs)
        conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect('economy_final.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        conn.close()
        return result[0]
    else:
        c.execute("INSERT INTO users (user_id, balance, last_work) VALUES (?, 0, 0)", (user_id,))
        conn.commit()
        conn.close()
        return 0

def update_balance(user_id, amount):
    get_balance(user_id) # Khởi tạo nếu chưa có
    conn = sqlite3.connect('economy_final.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# ================= MENU HƯỚNG DẪN =================
@bot.message_handler(commands=['games', 'help', 'menu'])
def show_games(message):
    help_text = """
🎮 **DANH SÁCH LỆNH & TRÒ CHƠI** 🎮

💰 **Hệ thống Kinh tế:**
👉 `/work` : Làm việc kiếm tiền ngẫu nhiên theo độ hiếm (Hồi chiêu 30s).
👉 `/bal` hoặc `/balance` : Xem số dư tài khoản hiện tại.

🎲 **Khu vực Casino:**
👉 `/taixiu <tai/xiu> <số_tiền>` : Đổ xúc xắc Tài Xỉu.
*(Ví dụ: `/taixiu tai 50000`)*
👉 `/lo <00-99> <số_tiền>` : Đánh lô 2 số cuối, tỷ lệ 1 ăn 70.
*(Ví dụ: `/lo 68 10000`)*

Chúc bạn chơi game vui vẻ và sớm trở thành đại gia! 💸
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['admin'])
def show_admin_commands(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ Bạn không có quyền truy cập hệ thống quản trị.")
        
    admin_text = """
👑 **DANH SÁCH LỆNH QUẢN TRỊ VIÊN** 👑

💼 **Quản lý Việc làm:**
👉 `/addjob <common/rare/legendary> <min> <max> <mô_tả>`

💸 **Cheat (Phải Reply tin nhắn mục tiêu):**
👉 `/addmoney <tiền>` : Bơm tiền.
👉 `/takemoney <tiền>` : Thu tiền.
👉 `/setmoney <tiền>` : Set số dư.

🚨 **Tối Cao:**
👉 `/globalwipe` : Reset tiền cả server về 0.
    """
    bot.reply_to(message, admin_text, parse_mode='Markdown')

# ================= LỆNH NGƯỜI CHƠI =================
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ Chỉ Admin mới có quyền khởi động Bot!")
    bot.reply_to(message, "✅ Bot Mini-Game VND đã được kích hoạt!")

@bot.message_handler(commands=['balance', 'bal'])
def check_balance(message):
    user_id = message.from_user.id
    bal = get_balance(user_id)
    bot.reply_to(message, f"💳 **{message.from_user.first_name}**, tài khoản của bạn có: `{format_vnd(bal)} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['work'])
def handle_work(message):
    user_id = message.from_user.id
    current_time = time.time()
    
    conn = sqlite3.connect('economy_final.db')
    c = conn.cursor()
    c.execute("SELECT last_work FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    last_work = user_data[0] if user_data else 0
    
    # Cooldown 30s
    if current_time - last_work < 30:
        bot.reply_to(message, f"⏳ Đang mệt! Chờ `{int(30 - (current_time - last_work))}` giây nữa.", parse_mode='Markdown')
        conn.close()
        return

    # Tỷ lệ hiếm
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
    
    c.execute("UPDATE users SET balance = balance + ?, last_work = ? WHERE user_id = ?", (earned, current_time, user_id))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"{tag} Bạn vừa **{job[0]}** và nhận được `{format_vnd(earned)} VND`!", parse_mode='Markdown')

@bot.message_handler(commands=['taixiu'])
def play_taixiu(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) < 3 or args[1].lower() not in ['tai', 'tài', 'xiu', 'xỉu']:
        return bot.reply_to(message, "⚠️ Dùng: `/taixiu <tai/xiu> <tiền>`", parse_mode='Markdown')
    try: bet = int(args[2])
    except: return bot.reply_to(message, "⚠️ Tiền cược phải là số nguyên!")
    
    if bet <= 0 or bet > get_balance(user_id):
        return bot.reply_to(message, "❌ Không đủ tiền hoặc sai mức cược!")

    update_balance(user_id, -bet)
    d1, d2, d3 = random.randint(1,6), random.randint(1,6), random.randint(1,6)
    total = d1 + d2 + d3
    res_str = "tai" if total >= 11 else "xiu"
    
    bot.send_message(message.chat.id, f"🎲 Đang lắc: {d1} - {d2} - {d3} -> **{total} điểm ({"TÀI" if res_str=='tai' else "XỈU"})**", parse_mode='Markdown')
    
    if (args[1].lower() in ['tai', 'tài'] and res_str == "tai") or (args[1].lower() in ['xiu', 'xỉu'] and res_str == "xiu"):
        update_balance(user_id, bet * 2)
        bot.reply_to(message, f"🎉 Thắng `+{format_vnd(bet*2)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"💸 Thua sạch `{format_vnd(bet)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['lo', 'lô'])
def play_lo(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) < 3 or not args[1].isdigit() or len(args[1]) != 2:
        return bot.reply_to(message, "⚠️ Dùng: `/lo <00-99> <tiền>`", parse_mode='Markdown')
    try: bet = int(args[2])
    except: return bot.reply_to(message, "⚠️ Tiền cược phải là số nguyên!")
    
    if bet <= 0 or bet > get_balance(user_id):
        return bot.reply_to(message, "❌ Không đủ tiền!")

    update_balance(user_id, -bet)
    winning_num = str(random.randint(0, 99)).zfill(2)
    bot.send_message(message.chat.id, f"🎰 Số độc đắc: **{winning_num}**", parse_mode='Markdown')
    
    if args[1] == winning_num:
        update_balance(user_id, bet * 70)
        bot.reply_to(message, f"🏆 TRÚNG LÔ! Trúng x70: `+{format_vnd(bet*70)} VND`!", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"💸 Trượt rồi. Mất `{format_vnd(bet)} VND`.", parse_mode='Markdown')

# ================= LỆNH ADMIN =================
@bot.message_handler(commands=['addjob'])
def admin_add_job(message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=4)
    if len(parts) < 5 or parts[1].lower() not in ['common', 'rare', 'legendary']:
        return bot.reply_to(message, "⚠️ `/addjob <common/rare/legendary> <min> <max> <mô tả>`", parse_mode='Markdown')
    
    conn = sqlite3.connect('economy_final.db')
    c = conn.cursor()
    c.execute("INSERT INTO jobs (description, rarity, min_pay, max_pay) VALUES (?, ?, ?, ?)", (parts[4], parts[1].lower(), int(parts[2]), int(parts[3])))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ Đã thêm việc làm thành công!")

@bot.message_handler(commands=['addmoney'])
def cheat_add(message):
    if message.from_user.id != ADMIN_ID or not message.reply_to_message: return
    amount = int(message.text.split()[1])
    update_balance(message.reply_to_message.from_user.id, amount)
    bot.reply_to(message, f"👑 Đã bơm `+{format_vnd(amount)} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['takemoney'])
def cheat_take(message):
    if message.from_user.id != ADMIN_ID or not message.reply_to_message: return
    amount = int(message.text.split()[1])
    update_balance(message.reply_to_message.from_user.id, -amount)
    bot.reply_to(message, f"⚡ Đã thu `-{format_vnd(amount)} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['setmoney'])
def cheat_set(message):
    if message.from_user.id != ADMIN_ID or not message.reply_to_message: return
    amount = int(message.text.split()[1])
    conn = sqlite3.connect('economy_final.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, message.reply_to_message.from_user.id))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"🔧 Set số dư thành `{format_vnd(amount)} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['globalwipe'])
def cheat_wipe(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('economy_final.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = 0")
    conn.commit()
    conn.close()
    bot.reply_to(message, "🚨 Server đã bị reset tiền về 0!")

# ================= CHẠY BOT =================
if __name__ == "__main__":
    init_db()
    print("Bot đang hoạt động...")
    bot.polling(none_stop=True)
