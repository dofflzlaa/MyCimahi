import json
import os
import shlex
import threading
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters
from keep_alive import keep_alive
from ttr_reminder import ttr_reminder_loop
from ttr_reminder import run_ttr_check_once  # Pastikan fungsi ini sudah ada di ttr_reminder.py
from google.oauth2.service_account import Credentials

creds_json = os.getenv("GOOGLE_CREDS_JSON")
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict)
TOKEN = "8137142032:AAHUeww0B9I4GGrGTFO64GdVNbgQYBXsZUo"
bot = Bot(TOKEN)

GROUP_MAP = {
    "group1": -1002711361278,
    "group2": -1002600448648
}

AUTHORIZED_SENDERS = [94494553, 250457790, 104256754]
ORDERS_FILE = "orders.json"
orders = []
order_counter = 1

TEKNISI_MAP = {
    "187341812": {"id": 187341812, "nama": "FAKHRI RASYAD R"},
    "7502933882": {"id": 7502933882, "nama": "GANJAR"},
    "698817453": {"id": 698817453, "nama": "IRFAN MAULANA"},
    "490182234": {"id": 490182234, "nama": "MUHAMMAD ALVA RIZKY"},
    "190329914": {"id": 190329914, "nama": "NAZLI RUDI YANTO"},
    "52592435": {"id": 52592435, "nama": "TARYANA"},
    "531045020": {"id": 531045020, "nama": "YOGI TJANDRA FERNANDO"},
    "432909325": {"id": 432909325, "nama": "YUNUS"},
    "152714062": {"id": 152714062, "nama": "UJANG MUKSIN"},
    "5803062407": {"id": 5803062407, "nama": "DENI EGI"},
    "775806683": {"id": 775806683, "nama": "DENI WARDANI"},
    "1146830037": {"id": 1146830037, "nama": "ALFIAN"},
    "1264932854": {"id": 1264932854, "nama": "AZIS"},
    "85837025": {"id": 85837025, "nama": "ASEP SULAEMAN"},
    "7562452591": {"id": 204904444, "nama": "ENGKOS KOSTAMAN"},
    "164437085": {"id": 164437085, "nama": "GIAN KRISTAL"},
    "96431080": {"id": 96431080, "nama": "HENDRA PERMANA"},
    "1248239258": {"id": 1248239258, "nama": "INDRA PRATAMA"},
    "103280105": {"id": 103280105, "nama": "JULI SURYANA"},
    "604372370": {"id": 604372370, "nama": "RIDWAN RISWANDI"},
    "62669475": {"id": 62669475, "nama": "SAHIBUL AHYAD"},
    "237579695": {"id": 237579695, "nama": "TAUFIK HIDAYAT"},
    "98398750": {"id": 98398750, "nama": "DENIEC GORO SULISTYANTO"}
}

def load_orders():
    global orders, order_counter
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            orders = json.load(f)
            for order in orders:
                order['created_at'] = datetime.fromisoformat(order['created_at'])
            order_counter = len(orders) + 1

def save_orders():
    with open(ORDERS_FILE, "w") as f:
        temp = [dict(order, created_at=order['created_at'].isoformat()) for order in orders]
        json.dump(temp, f, indent=2)

def reminder_loop():
    now = datetime.now()
    for order in orders:
        if order['status'] == 'Open':
            deadline = order['created_at'] + timedelta(days=1)
            if now > deadline and not order['reminded']:
                msg = (
                    f"⏰ <b>Reminder Order Belum Selesai</b>\n"
                    f"🔧 <a href=\"tg://user?id={order['teknisi_id']}\">{order['teknisi_nama']}</a>\n"
                    f"🆔 Order ID: {order['id']}"
                    f"🆔 Nomer Inet: {order['nomor_inet']}"
                )
                bot.send_message(chat_id=order['chat_id'], text=msg, parse_mode='HTML')
                order['reminded'] = True
    save_orders()
    threading.Timer(3600, reminder_loop).start()

def parse_order_message(msg: str):
    lines = msg.strip().split("\n")
    keluhan = lines[0].strip()
    nomor = nama = cp = alamat = ""
    for line in lines:
        if "ND" in line:
            nomor = line.split(":", 1)[-1].strip()
        elif "Nama" in line:
            nama = line.split(":", 1)[-1].strip()
        elif "CP" in line:
            cp = line.split(":", 1)[-1].strip()
        elif "Alamat" in line:
            alamat = line.split(":", 1)[-1].strip()
    return nomor, nama, cp, alamat, keluhan

def handle_reply(update: Update, context: CallbackContext):
    # Abaikan pesan jika dikirim di grup
    if update.message.chat.type != "private":
        return

    # Batasi hanya user yang diizinkan
    if update.effective_user.id not in AUTHORIZED_SENDERS:
        return

    reply = update.message.reply_to_message
    if not reply:
        return

    if not update.message.text:
        return

    args = update.message.text.split()
    if len(args) < 2:
        return

    teknisi_id = args[0]
    group_key = args[1].lower()

    if group_key not in GROUP_MAP or teknisi_id not in TEKNISI_MAP:
        context.bot.send_message(chat_id=update.effective_user.id, text="❗ ID teknisi atau grup tidak dikenali")

        return

    nomor, nama, cp, alamat, keluhan = parse_order_message(reply.text)
    group_id = GROUP_MAP[group_key]
    global order_counter

    order_id = f"ORD{order_counter:03d}"
    order_counter += 1

    teknisi = TEKNISI_MAP[teknisi_id]
    order_data = {
        'id': order_id,
        'nomor_inet': nomor,
        'nama': nama,
        'cp': cp,
        'alamat': alamat,
        'keluhan': keluhan,
        'teknisi_id': teknisi['id'],
        'teknisi_nama': teknisi['nama'],
        'created_at': datetime.now(),
        'status': 'Open',
        'reminded': False,
        'chat_id': group_id
    }
    orders.append(order_data)
    save_orders()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Selesai", callback_data=f"done|{order_id}")]
    ])

    pesan = (
        f"📋 <b>Order Baru LAPORAN LANGSUNG</b>\n"
        f"🆔 Order ID: {order_id}\n"
        f"🌐 Nomor Internet: {nomor}\n"
        f"👤 Nama Pelanggan: {nama}\n"
        f"📱 CP: {cp}\n"
        f"📍 Alamat: {alamat}\n"
        f"💬 Keluhan: {keluhan}\n"
        f"🔧 Teknisi: <a href=\"tg://user?id={teknisi['id']}\">{teknisi['nama']}</a>"
    )

    context.bot.send_message(chat_id=group_id, text=pesan, reply_markup=keyboard, parse_mode='HTML')

def done_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    _, order_id = query.data.split('|')

    for order in orders:
        if order['id'] == order_id:
            if order['status'] == 'Done':
                query.edit_message_text(f"✅ Order {order_id} sudah diselesaikan sebelumnya.")
                return

            if user_id != order['teknisi_id']:
                query.answer("❌ Hanya teknisi yang ditugaskan yang bisa menyelesaikan order ini.", show_alert=True)
                return

            order['status'] = 'Done'
            context.bot.send_message(
                chat_id=order['chat_id'],
                text=f"✅ Order {order_id} telah ditandai sebagai <b>Selesai</b> oleh <a href='tg://user?id={user_id}'>teknisi</a>.",
                parse_mode='HTML'
            )
            query.edit_message_reply_markup(reply_markup=None)
            save_orders()
            return

def list_order(update: Update, context: CallbackContext):
    open_orders = [order for order in orders if order['status'] == "Open"]
    if not open_orders:
        update.message.reply_text("📭 Tidak ada order *Open* saat ini.", parse_mode="Markdown")
        return

    pesan = "📋 <b>Daftar Order Open:</b>\n"
    for order in open_orders:
        pesan += (
            f"\n🆔 <b>{order['id']}</b>\n"
            f"👤 {order['nama']}\n"
            f"📞 {order['cp']}\n"
            f"📍 {order['nomor_inet']}\n"
            f"🔧 <a href='tg://user?id={order['teknisi_id']}'>{order['teknisi_nama']}</a>\n"
        )

    update.message.reply_text(pesan, parse_mode="HTML")

def hapus_order(update: Update, context: CallbackContext):
    if update.effective_user.id not in AUTHORIZED_SENDERS:
        update.message.reply_text("❌ Anda tidak memiliki izin untuk menghapus order.")
        return

    if len(context.args) != 1:
        update.message.reply_text("⚠️ Format salah. Gunakan /hapusorder [ORDER_ID]")
        return

    order_id = context.args[0]
    global orders
    for order in orders:
        if order["id"] == order_id:
            orders.remove(order)
            save_orders()
            update.message.reply_text(f"✅ Order {order_id} berhasil dihapus.")
            return


    
    update.message.reply_text(f"❌ Order {order_id} tidak ditemukan.")
updater = Updater(TOKEN, use_context=True)

def trigger_ttr(update: Update, context: CallbackContext):
    if update.effective_user.id not in AUTHORIZED_SENDERS:
        update.message.reply_text("❌ Anda tidak memiliki izin untuk menjalankan TTR reminder.")
        return

    update.message.reply_text("🔍 Memeriksa tiket TTR sekarang...")
    run_ttr_check_once(bot, TEKNISI_MAP)
    update.message.reply_text("✅ Reminder TTR sudah dikirim (jika ada yang memenuhi).")


dp = updater.dispatcher
dp.add_handler(CommandHandler("hapusorder", hapus_order))
dp.add_handler(CommandHandler("listorder", list_order))
dp.add_handler(MessageHandler(Filters.reply & Filters.text, handle_reply))
dp.add_handler(CallbackQueryHandler(done_callback))
dp.add_handler(CommandHandler("cekttr", trigger_ttr))

keep_alive()
load_orders()
ttr_reminder_loop(bot, TEKNISI_MAP)
reminder_loop()

from laporan_progres import laporan_progres_scheduler
laporan_progres_scheduler(bot)

from laporan_progres import generate_laporan_progres
generate_laporan_progres(bot)

print("Bot aktif...")
updater.start_polling()
updater.idle()
