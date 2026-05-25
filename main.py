import telebot
import sqlite3
import re
from datetime import datetime

TOKEN = "8636638353:AAECX09QCNTAKcLB0dDw981D2-4qtmxCFFY"
bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect("hamyon.db")
    cursor = conn.cursor()
    # tranzaksiyalar jadvali (turi: 'kirim' yoki 'chiqim')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tranzaksiyalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            turi TEXT,
            nima TEXT,
            qancha INTEGER,
            sana TEXT
        )
    ''')
    # Yangi sahifa/davr boshlanish sanalarini saqlash uchun jadval
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS davrlar (
            user_id INTEGER PRIMARY KEY,
            boshlanish_sana TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Foydalanuvchining oxirgi yangi sahifa ochgan sanasini olish
def get_start_date(user_id):
    conn = sqlite3.connect("hamyon.db")
    cursor = conn.cursor()
    cursor.execute("SELECT boshlanish_sana FROM davrlar WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "2000-01-01 00:00"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "💰 *Hamyon Nazorati Botiga xush kelibsiz!*\n\n"
        "✍️ **Xarajat (chiqim) kiritish:**\n"
        "Shunchaki matn va raqam yozing.\n"
        "👉 Misol: `Tushlik 45000` yoki `Yo'l kira 7000`\n\n"
        "➕ **Daromad (oylik, kirim) kiritish:**\n"
        "Boshiga **+** belgisi qo'yib yozing.\n"
        "👉 Misol: `+Oylik 6000000` yoki `+Bonus 500000`\n\n"
        "📊 **Buyruqlar:**\n"
        "/balans - Joriy sahifadagi (oxirgi oylikdan beri) balans\n"
        "/bugun - Bugungi kirim-chiqimlar\n"
        "/yangi_davr - Eski ma'lumotlarni o'chirmasdan, yangi sahifa ochish (oylik olganda bosiladi)\n"
        "/barcha_tarix - Bot ochilgandan beri jami qancha kirim va chiqim bo'lgani"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True and not message.text.startswith('/'))
def process_money(message):
    text = message.text.strip()
    turi = "chiqim"
    if text.startswith("+"):
        turi = "kirim"
        text = text[1:].strip()
        
    match = re.search(r'(\d+)[\s]*$', text)
    
    if match:
        qancha = int(match.group(1))
        nima = text[:match.start()].strip()
        if not nima:
            nima = "Oylik/Daromad" if turi == "kirim" else "Noma'lum xarajat"
            
        sana = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect("hamyon.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tranzaksiyalar (user_id, turi, nima, qancha, sana) VALUES (?, ?, ?, ?, ?)", 
                       (message.from_user.id, turi, nima, qancha, sana))
        conn.commit()
        conn.close()
        
        belgi = "✅" if turi == "kirim" else "🛑"
        bot.reply_to(message, f"{belgi} Saqlandi!\n📌 *{nima}* -> {qancha:,} so'm ({turi})", parse_mode="Markdown")
    else:
        bot.reply_to(message, "⚠️ Format xato.\nChiqim uchun: `Kofe 25000`\nKirim uchun: `+Oylik 5000000` deb yozing.")

@bot.message_handler(commands=['balans'])
def show_balans(message):
    start_date = get_start_date(message.from_user.id)
    conn = sqlite3.connect("hamyon.db")
    cursor = conn.cursor()
    
    # Faqat oxirgi yangi sahifadan keyingi kirimlar
    cursor.execute("SELECT SUM(qancha) FROM tranzaksiyalar WHERE user_id = ? AND turi = 'kirim' AND sana >= ?", (message.from_user.id, start_date))
    kirim = cursor.fetchone()[0] or 0
    
    # Faqat oxirgi yangi sahifadan keyingi chiqimlar
    cursor.execute("SELECT SUM(qancha) FROM tranzaksiyalar WHERE user_id = ? AND turi = 'chiqim' AND sana >= ?", (message.from_user.id, start_date))
    chiqim = cursor.fetchone()[0] or 0
    
    conn.close()
    balans = kirim - chiqim
    
    javob = (
        f"📋 *Joriy sahifa bo'yicha hisobot (Sana: {start_date[:10]} dan beri):*\n\n"
        f"➕ Kirim: {kirim:,} so'm\n"
        f"➖ Chiqim: {chiqim:,} so'm\n"
        f"💵 *Hamyonda qoldi:* {balans:,} so'm"
    )
    bot.reply_to(message, javob, parse_mode="Markdown")

@bot.message_handler(commands=['bugun'])
def show_today(message):
    bugun = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("hamyon.db")
    cursor = conn.cursor()
    cursor.execute("SELECT turi, nima, qancha FROM tranzaksiyalar WHERE user_id = ? AND sana LIKE ?", (message.from_user.id, f"{bugun}%"))
    rows = cursor.fetchall()
    conn.close()
    
    if rows:
        javob = "📅 *Bugungi aylanma:*\n\n"
        for row in rows:
            belgi = "➕" if row[0] == "kirim" else "➖"
            javob += f"{belgi} {row[1]}: {row[2]:,} so'm\n"
        bot.reply_to(message, javob, parse_mode="Markdown")
    else:
        bot.reply_to(message, "🤷‍♂️ Bugun hech qanday kirim-chiqim yozilmadi.")

@bot.message_handler(commands=['yangi_davr'])
def set_new_period(message):
    hozir = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("hamyon.db")
    cursor = conn.cursor()
    # Yangi davr boshlanish sanasini yangilaymiz yoki kiritamiz
    cursor.execute("INSERT OR REPLACE INTO davrlar (user_id, boshlanish_sana) VALUES (?, ?)", (message.from_user.id, hozir))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"🚀 *Yangi oylik davri boshlandi!* (Sana: {hozir[:10]})\n\nEski xarajatlaringiz o'chirilmadi, hamma ma'lumotlar tarixda turibdi. Lekin hozirgi /balans buyrug'i faqat shu daqiqadan keyingi pullarni hisoblaydi. Toza varaq muborak!")

@bot.message_handler(commands=['barcha_tarix'])
def show_all_history(message):
    conn = sqlite3.connect("hamyon.db")
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(qancha) FROM tranzaksiyalar WHERE user_id = ? AND turi = 'kirim'", (message.from_user.id,))
    jami_kirim = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(qancha) FROM tranzaksiyalar WHERE user_id = ? AND turi = 'chiqim'", (message.from_user.id,))
    jami_chiqim = cursor.fetchone()[0] or 0
    conn.close()
    
    javob = (
        f"🗂 *Botdan foydalanishni boshlaganingizdan beri umumiy tarix:*\n\n"
        f"📈 Jami kiritilgan daromadlar: {jami_kirim:,} so'm\n"
        f"📉 Jami qilingan xarajatlar: {jami_chiqim:,} so'm\n"
        f"⚖️ Umumiy aylanma: {(jami_kirim - jami_chiqim):,} so'm"
    )
    bot.reply_to(message, javob, parse_mode="Markdown")

if __name__ == "__main__":
    init_db()
    print("Bot muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()
