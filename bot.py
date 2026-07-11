import telebot
import sqlite3
import random
import time
import os
from dotenv import load_dotenv

# ================= CẤU HÌNH CƠ BẢN =================
load_dotenv()

API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(API_TOKEN)

LOAN_LIMIT = 5000000      # Hạn mức vay: 5 triệu VND
LOAN_DURATION = 600       # Thời hạn vay: 10 phút (600 giây)
# [ĐÃ SỬA] Tăng thời gian đi tù lên 1 giờ (3600 giây)
JAIL_DURATION = 3600       

# ================= HÀM BỔ TRỢ =================
def format_vnd(amount):
    return f"{amount:,}"

def init_db():
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    
    # Bảng người dùng
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  first_name TEXT DEFAULT 'Người chơi',
                  balance INTEGER DEFAULT 0, 
                  last_work REAL DEFAULT 0,
                  loan INTEGER DEFAULT 0,
                  loan_time REAL DEFAULT 0,
                  jail_time REAL DEFAULT 0,
                  last_cuop REAL DEFAULT 0)''')
                 
    # Bảng công việc
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT, rarity TEXT, min_pay INTEGER, max_pay INTEGER)''')
    conn.commit()
    
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

def get_balance(user_id, first_name="Người chơi"):
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        c.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (first_name, user_id))
        conn.commit()
        conn.close()
        return result[0]
    else:
        c.execute("INSERT INTO users (user_id, first_name, balance, last_work, loan, loan_time, jail_time, last_cuop) VALUES (?, ?, 0, 0, 0, 0, 0, 0)", (user_id, first_name))
        conn.commit()
        conn.close()
        return 0

def update_balance(user_id, amount):
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def check_loan_overdue(user_id):
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT loan, loan_time FROM users WHERE user_id = ?", (user_id,))
    data = c.fetchone()
    conn.close()
    if data and data[0] > 0:
        if time.time() - data[1] > LOAN_DURATION:
            return True, data[0]
    return False, 0

def check_jail(user_id):
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT jail_time FROM users WHERE user_id = ?", (user_id,))
    data = c.fetchone()
    conn.close()
    if data and data[0] > 0:
        time_passed = time.time() - data[0]
        if time_passed < JAIL_DURATION:
            return True, int(JAIL_DURATION - time_passed)
        else:
            conn = sqlite3.connect('economy_v5.db')
            c = conn.cursor()
            c.execute("UPDATE users SET jail_time = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
    return False, 0

def get_bet_amount(bet_str, balance):
    if bet_str.lower() == 'all':
        return balance
    try:
        return int(bet_str)
    except:
        return -1

# ================= MENU HƯỚNG DẪN =================
@bot.message_handler(commands=['games', 'helps', 'menu'])
def show_games(message):
    help_text = """
    🎮 **DANH SÁCH LỆNH & TRÒ CHƠI** 🎮

💰 **Hệ thống Kinh tế:**
👉 `/work` : Làm việc kiếm tiền ngẫu nhiên.
👉 `/cuop` : Cướp ngân hàng (Ăn 10 Tỷ hoặc đi tù 1 tiếng).
👉 `/bal` : Xem số dư tài khoản.
👉 `/tops` : Bảng xếp hạng đại gia.

🏦 **Hệ thống Tín dụng đen:**
👉 `/vay <số_tiền>` : Vay tiền mặt (Tối đa 5 triệu, hạn 10 phút).
👉 `/tra` : Thanh toán khoản nợ.

🎲 **Khu vực Casino (Có thể dùng chữ 'all' để tất tay):**
👉 `/tx <tai/xiu> <số_tiền/all>` : Đổ Tài Xỉu.
👉 `/xu <sap/ngua> <số_tiền/all>` : Tung Đồng Xu.
👉 `/spin <số_tiền/all>` : Vòng quay may mắn (0x - 5x).
👉 `/lo <00-99> <số_tiền/all>` : Đánh lô (x70).
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['admin'])
def show_admin_commands(message):
    if message.from_user.id != ADMIN_ID: return
    admin_text = "👑 **LỆNH QUẢN TRỊ VIÊN** 👑\n👉 `/addjob <common/rare/legendary> <min> <max> <mô_tả>`\n👉 `/addmoney <tiền>` | `/takemoney <tiền>` | `/setmoney <tiền>` (Reply)\n👉 `/globalwipe` : Reset server."
    bot.reply_to(message, admin_text, parse_mode='Markdown')

# ================= LỆNH CHỨC NĂNG =================
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "✅ Bot Mini-Game VND đã được kích hoạt!")

@bot.message_handler(commands=['balance', 'bal'])
def check_balance(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    bal = get_balance(user_id, name)
    
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
    loan = c.fetchone()[0]
    conn.close()
    
    is_jailed, time_left = check_jail(user_id)
    
    # Định dạng lại thời gian hiển thị trong tù cho đẹp mắt (Giờ:Phút:Giây)
    if is_jailed:
        jail_status = f"\nBC 🚓 Đang ở tù (Còn {time_left // 60} phút {time_left % 60} giây)"
    else:
        jail_status = ""
    
    msg = f"💳 **{name}**, tài khoản có: `{format_vnd(bal)} VND`{jail_status}"
    if loan > 0:
        is_overdue, _ = check_loan_overdue(user_id)
        msg += f"\n🏦 Đang nợ: `{format_vnd(loan)} VND` ({'⚠️ QUÁ HẠN' if is_overdue else '⏳ Trong hạn'})"
        
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['tops'])
def show_leaderboard(message):
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 10")
    top_users = c.fetchall()
    conn.close()
    
    if not top_users: return bot.reply_to(message, "Chưa có bảng xếp hạng!")
        
    txt = "🏆 **BẢNG XẾP HẠNG ĐẠI GIA** 🏆\n\n"
    medal = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
    for i, u in enumerate(top_users): txt += f"{medal[i]} **{u[0]}**: `{format_vnd(u[1])} VND`\n"
    bot.reply_to(message, txt, parse_mode='Markdown')

@bot.message_handler(commands=['vay'])
def borrow_money(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, f"🚓 **ĐANG TRONG TÙ!** Bạn không thể vay tiền khi đang chấp hành án phạt.")
    
    name = message.from_user.first_name
    get_balance(user_id, name)
    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "⚠️ Cú pháp: `/vay <số_tiền>`", parse_mode='Markdown')
        
    try: amount = int(args[1])
    except: return bot.reply_to(message, "⚠️ Số tiền vay phải là số nguyên!")
    
    if amount <= 0 or amount > LOAN_LIMIT: return bot.reply_to(message, f"❌ Tiền vay không hợp lệ (Tối đa `{format_vnd(LOAN_LIMIT)} VND`)!")

    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone()[0] > 0:
        conn.close()
        return bot.reply_to(message, "❌ Đang có nợ chưa trả! Gõ `/tra` trước khi vay tiếp.")

    c.execute("UPDATE users SET balance = balance + ?, loan = ?, loan_time = ? WHERE user_id = ?", (amount, amount, time.time(), user_id))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"🏦 Đã vay `{format_vnd(amount)} VND`.\n⏳ Thời hạn: **10 phút**.")

@bot.message_handler(commands=['tra'])
def repay_money(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, "🚓 **ĐANG TRONG TÙ!** Bạn không thể thực hiện giao dịch trả nợ lúc này.")
    
    bal = get_balance(user_id, message.from_user.first_name)
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
    loan = c.fetchone()[0]
    
    if loan == 0:
        conn.close()
        return bot.reply_to(message, "🤝 Không có nợ!")
    if bal < loan:
        conn.close()
        return bot.reply_to(message, f"❌ Không đủ tiền! Cần `{format_vnd(loan)} VND`.")

    c.execute("UPDATE users SET balance = balance - ?, loan = 0, loan_time = 0 WHERE user_id = ?", (loan, user_id))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ Đã trả sạch nợ `{format_vnd(loan)} VND`.")

# --- CƯỚP NGÂN HÀNG (TỶ LỆ 5%, ĐI TÙ 1 TIẾNG) ---
@bot.message_handler(commands=['cuop'])
def rob_bank(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    get_balance(user_id, name)
    
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, "🚓 **ĐANG TRONG TÙ!** Bạn đang ở trong phòng giam biệt giam, không thể đi cướp.")
    
    current_time = time.time()
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("SELECT last_cuop FROM users WHERE user_id = ?", (user_id,))
    last_cuop = c.fetchone()[0]
    
    if current_time - last_cuop < 600:
        conn.close()
        return bot.reply_to(message, f"🕵️ Cảnh sát đang tuần tra gắt gao! Hãy ẩn náu thêm `{int(600 - (current_time - last_cuop))}` giây nữa mới được hành động.")

    c.execute("UPDATE users SET last_cuop = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    # [ĐÃ SỬA] Hạ tỷ lệ thành công xuống 5% (từ 1 đến 5)
    if random.randint(1, 100) <= 5:
        win_amount = 10000000000
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win_amount, user_id))
        conn.commit()
        bot.reply_to(message, f"🥷 **PHI VỤ THẾ KỶ THÀNH CÔNG RỰC RỠ!**\nBạn đã lách qua hệ thống la-ze, ôm trọn bao tải tiền 10 Tỷ. Nhận được: `+{format_vnd(win_amount)} VND`! 💰🔥", parse_mode='Markdown')
    else:
        c.execute("UPDATE users SET jail_time = ? WHERE user_id = ?", (current_time, user_id))
        conn.commit()
        bot.reply_to(message, f"🚓 **BÁO ĐỘNG ĐỎ! HỆ THỐNG AN NINH ĐÃ KÍCH HOẠT!**\nPhi vụ thất bại hoàn toàn, đặc nhiệm SWAT đã khống chế bạn.\n⚖️ Hình phạt: Bóc lịch biệt giam **1 Giờ đồng hồ** (Không thể tương tác bot).", parse_mode='Markdown')
    conn.close()

@bot.message_handler(commands=['work'])
def handle_work(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, f"🚓 **ĐANG TRONG TÙ!** Bạn đang bị còng tay bóc lịch. Phải ở trong tù thêm `{time_left // 60}` phút nữa.")
    
    name = message.from_user.first_name
    get_balance(user_id, name)
    conn = sqlite3.connect('economy_v5.db')
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
    
    is_overdue, loan_amount = check_loan_overdue(user_id)
    if is_overdue:
        c.execute("SELECT loan FROM users WHERE user_id = ?", (user_id,))
        current_loan = c.fetchone()[0]
        if earned >= current_loan:
            left_over = earned - current_loan
            c.execute("UPDATE users SET balance = balance + ?, loan = 0, loan_time = 0 WHERE user_id = ?", (left_over, user_id))
            bot.reply_to(message, f"🚨 **PHẠT QUÁ HẠN!** Bạn vừa {job[0]} kiếm được `{format_vnd(earned)} VND`.\n⚠️ Trừ sạch vào nợ! Đã **TRẢ HẾT NỢ**, dư `{format_vnd(left_over)} VND`.", parse_mode='Markdown')
        else:
            c.execute("UPDATE users SET loan = loan - ? WHERE user_id = ?", (earned, user_id))
            bot.reply_to(message, f"🚨 **PHẠT QUÁ HẠN!** Bạn vừa {job[0]} kiếm được `{format_vnd(earned)} VND`.\n⚠️ Tịch thu siết nợ! Nợ còn: `{format_vnd(current_loan - earned)} VND`.", parse_mode='Markdown')
        conn.commit()
        conn.close()
        return

    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earned, user_id))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"{tag} Bạn vừa **{job[0]}** và nhận được `{format_vnd(earned)} VND`!", parse_mode='Markdown')

# ================= KHU VỰC CASINO =================
@bot.message_handler(commands=['tx'])
def play_taixiu(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, f"🚓 **ĐANG TRONG TÙ!** Hãy tập trung cải tạo nốt `{time_left // 60}` phút.")
    is_overdue, loan = check_loan_overdue(user_id)
    if is_overdue: return bot.reply_to(message, f"⛔ **BỊ PHONG TỎA!** Đang trốn nợ. Gõ `/tra` đi!")

    args = message.text.split()
    if len(args) < 3 or args[1].lower() not in ['tai', 'tài', 'xiu', 'xỉu']:
        return bot.reply_to(message, "⚠️ Dùng: `/tx <tai/xiu> <số_tiền/all>`", parse_mode='Markdown')
        
    bal = get_balance(user_id, message.from_user.first_name)
    bet = get_bet_amount(args[2], bal)
    
    if bet <= 0 or bet > bal:
        return bot.reply_to(message, "❌ Không đủ tiền hoặc sai mức cược!")

    update_balance(user_id, -bet)
    d1, d2, d3 = random.randint(1,6), random.randint(1,6), random.randint(1,6)
    total = d1 + d2 + d3
    res_str = "tai" if total >= 11 else "xiu"
    
    bot.send_message(message.chat.id, f"🎲 Đang lắc: {d1} - {d2} - {d3} -> **{total} điểm ({'TÀI' if res_str=='tai' else 'XỈU'})**\n*(Tiền cược: {format_vnd(bet)} VND)*", parse_mode='Markdown')
    if (args[1].lower() in ['tai', 'tài'] and res_str == "tai") or (args[1].lower() in ['xiu', 'xỉu'] and res_str == "xiu"):
        update_balance(user_id, bet * 2)
        bot.reply_to(message, f"🎉 Thắng `+{format_vnd(bet*2)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"💸 Thua sạch `{format_vnd(bet)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['xu'])
def play_coin(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, f"🚓 **ĐANG TRONG TÙ!** Hãy cải tạo tốt nốt `{time_left // 60}` phút.")
    is_overdue, loan = check_loan_overdue(user_id)
    if is_overdue: return bot.reply_to(message, f"⛔ **BỊ PHONG TỎA!** Đang trốn nợ. Gõ `/tra` đi!")

    args = message.text.split()
    if len(args) < 3 or args[1].lower() not in ['sap', 'sấp', 'ngua', 'ngửa']:
        return bot.reply_to(message, "⚠️ Cú pháp: `/xu <sap/ngua> <số_tiền/all>`", parse_mode='Markdown')
        
    bal = get_balance(user_id, message.from_user.first_name)
    bet = get_bet_amount(args[2], bal)
    
    if bet <= 0 or bet > bal:
        return bot.reply_to(message, "❌ Bạn không đủ tiền hoặc nhập sai mức cược!")

    update_balance(user_id, -bet)
    coin_result = random.choice(['sap', 'ngua'])
    result_display = "SẤP 🪙" if coin_result == 'sap' else "NGỬA 🪙"
    
    bot.send_message(message.chat.id, f"🪙 Đồng xu đang xoay... Kết quả: **{result_display}**\n*(Tiền cược: {format_vnd(bet)} VND)*", parse_mode='Markdown')
    player_choice = 'sap' if args[1].lower() in ['sap', 'sấp'] else 'ngua'
    
    if player_choice == coin_result:
        win_money = bet * 2
        update_balance(user_id, win_money)
        bot.reply_to(message, f"🎉 Đoán đúng! `+{format_vnd(win_money)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"💸 Sai rồi! Mất `{format_vnd(bet)} VND`. Số dư: `{format_vnd(get_balance(user_id))} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['spin'])
def play_spin(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, f"🚓 **ĐANG TRONG TÙ!** Chờ ra tù rồi quay tiếp.")
    is_overdue, loan = check_loan_overdue(user_id)
    if is_overdue: return bot.reply_to(message, f"⛔ **BỊ PHONG TỎA!** Đang trốn nợ. Gõ `/tra` đi!")

    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "⚠️ Cú pháp: `/spin <số_tiền_cược/all>`", parse_mode='Markdown')
    
    bal = get_balance(user_id, message.from_user.first_name)
    bet = get_bet_amount(args[1], bal)

    if bet <= 0 or bet > bal:
        return bot.reply_to(message, "❌ Bạn không đủ tiền!")

    update_balance(user_id, -bet)
    wheel_options = [(0, "Mất Trắng (0x) ❌"), (0, "Mất Trắng (0x) ❌"), (0.5, "Hoàn Tiền 50% (0.5x) 🌗"), (1, "Hòa Vốn (1x) 🟡"), (1.5, "Thắng Nhẹ (1.5x) 📈"), (2, "Nhân Đôi Tài Sản (2x) 🔥"), (5, "🚨 JACKPOT NỔ HŨ (5x) 💎🏆")]

    multiplier, text_result = random.choice(wheel_options)
    win_money = int(bet * multiplier)
    update_balance(user_id, win_money)

    announcement = f"🎡 **VÒNG QUAY MAY MẮN ĐANG XOAY...** 🎡\n*(Tiền cược: {format_vnd(bet)} VND)*\n\n🎯 Kết quả: Bạn đã quay trúng ô **{text_result}**\n"
    if multiplier > 1: announcement += f"🎉 Bạn được cộng: `+{format_vnd(win_money)} VND`!"
    elif multiplier == 1: announcement += f"🟡 Bạn nhận lại đủ tiền cược!"
    elif multiplier == 0.5: announcement += f"🌗 Bạn được vớt vát lại: `+{format_vnd(win_money)} VND`."
    else: announcement += f"💸 Bạn mất trắng số tiền bỏ ra!"

    announcement += f"\n💳 Số dư hiện tại: `{format_vnd(get_balance(user_id))} VND`"
    bot.reply_to(message, announcement, parse_mode='Markdown')

@bot.message_handler(commands=['lo', 'lô'])
def play_lo(message):
    user_id = message.from_user.id
    is_jailed, time_left = check_jail(user_id)
    if is_jailed: return bot.reply_to(message, f"🚓 **ĐANG TRONG TÙ!** Hãy bóc lịch nốt đã.")
    is_overdue, loan = check_loan_overdue(user_id)
    if is_overdue: return bot.reply_to(message, f"⛔ **BỊ PHONG TỎA!** Đang trốn nợ. Gõ `/tra` đi!")

    args = message.text.split()
    if len(args) < 3 or not args[1].isdigit() or len(args[1]) != 2:
        return bot.reply_to(message, "⚠️ Dùng: `/lo <00-99> <số_tiền/all>`", parse_mode='Markdown')
        
    bal = get_balance(user_id, message.from_user.first_name)
    bet = get_bet_amount(args[2], bal)
    
    if bet <= 0 or bet > bal:
        return bot.reply_to(message, "❌ Không đủ tiền!")

    update_balance(user_id, -bet)
    winning_num = str(random.randint(0, 99)).zfill(2)
    bot.send_message(message.chat.id, f"🎰 Số độc đắc: **{winning_num}**\n*(Tiền cược: {format_vnd(bet)} VND)*", parse_mode='Markdown')
    
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
    
    conn = sqlite3.connect('economy_v5.db')
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
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, message.reply_to_message.from_user.id))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"🔧 Set số dư thành `{format_vnd(amount)} VND`", parse_mode='Markdown')

@bot.message_handler(commands=['globalwipe'])
def cheat_wipe(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('economy_v5.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = 0, loan = 0, loan_time = 0, jail_time = 0, last_cuop = 0")
    conn.commit()
    conn.close()
    bot.reply_to(message, "🚨 Server đã bị reset hoàn toàn!")

# ================= CHẠY BOT =================
if __name__ == "__main__":
    init_db()
    print("Bot đang hoạt động... Tỷ lệ cướp ngân hàng thành công: 5%. Án tù: 1 Giờ.")
    bot.polling(none_stop=True)