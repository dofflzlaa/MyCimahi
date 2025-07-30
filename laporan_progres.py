from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import ParseMode
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pytz

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1N2h-r4wUka0ZYf6FMJ5BnOE695eS3jqL0CVmXHlWz24'
RANGE_NAME = "'SALDO UNSPEC'!A1:Z"

# Daftar teknisi dan grup
GROUP1_TEKNISI_IDS = [
    187341812, 7502933882, 698817453, 490182234, 190329914, 52592435,
    531045020, 432909325, 152714062, 5803062407, 775806683, 1146830037
]
GROUP2_TEKNISI_IDS = [
    1264932854, 85837025, 204904444, 164437085, 96431080, 1248239258,
    103280105, 604372370, 62669475, 237579695, 98398750
]

TEKNISI_MAP = {
    "FAKHRI RASYAD R": 187341812,
    "GANJAR": 7502933882,
    "IRFAN MAULANA": 698817453,
    "MUHAMMAD ALVA RIZKY": 490182234,
    "NAZLI RUDI YANTO": 190329914,
    "TARYANA": 52592435,
    "YOGI TJANDRA FERNANDO": 531045020,
    "YUNUS": 432909325,
    "UJANG MUKSIN": 152714062,
    "DENI EGI": 5803062407,
    "DENI WARDANI": 775806683,
    "ALFIAN": 1146830037,
    "AZIS": 1264932854,
    "ASEP SULAEMAN": 85837025,
    "ENGKOS KOSTAMAN": 204904444,
    "GIAN KRISTAL": 164437085,
    "HENDRA PERMANA": 96431080,
    "INDRA PRATAMA": 1248239258,
    "JULI SURYANA": 103280105,
    "RIDWAN RISWANDI": 604372370,
    "SAHIBUL AHYAD": 62669475,
    "TAUFIK HIDAYAT": 237579695,
    "DENIEC GORO SULISTYANTO": 98398750
}

GROUP_MAP = {"group1": -1002711361278, "group2": -1002600448648}

# Kredensial Google
creds = Credentials.from_service_account_file("credentials.json",
                                              scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()


def format_status(status):
    if "UNSPEC T-SEL" in status:
        return f"❌ {status}"
    elif "SPEC T-SEL" in status:
        return f"✅ {status}"
    else:
        return status


def buat_laporan_progres(data):
    teknisi_hari_ini = {}
    now = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%d/%m/%Y")

    for row in data:
        if len(row) < 26:
            continue

        tgl_semesta = row[17]  # Kolom R
        teknisi_nama = row[23]  # Kolom X
        no_inet = row[10]  # Kolom K
        alamat = row[22]  # Kolom W
        status = row[25]  # Kolom Z

        if tgl_semesta != now:
            continue

        if teknisi_nama not in TEKNISI_MAP:
            continue

        if teknisi_nama not in teknisi_hari_ini:
            teknisi_hari_ini[teknisi_nama] = []

        teknisi_hari_ini[teknisi_nama].append({
            "nd": no_inet,
            "alamat": alamat,
            "status": status
        })

    laporan_per_teknisi = {}
    for nama, daftar in teknisi_hari_ini.items():
        baris = "| ND | Alamat | Status |\n|----|--------|--------|\n"
        semua_spec = True
        ada_unspec = False

        for d in daftar:
            status_format = format_status(d["status"])
            if "UNSPEC T-SEL" in d["status"]:
                ada_unspec = True
                semua_spec = False
            elif "SPEC T-SEL" in d["status"]:
                pass  # tetap dianggap sudah selesai
            else:
                semua_spec = False

            baris += f"| {d['nd']} | {d['alamat']} | {status_format} |\n"

        catatan = ""
        if ada_unspec:
            catatan = "\nMasih unspec nih, ada update progress atau kendala nya?"
        elif semua_spec:
            catatan = "\nSemua pekerjaan hari ini sudah SPEC, good job!"

        laporan_per_teknisi[nama] = baris.strip() + catatan

    return laporan_per_teknisi


def kirim_laporan(bot):
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range=RANGE_NAME).execute()
    values = result.get('values', [])

    laporan = buat_laporan_progres(values)

    for teknisi_nama, pesan in laporan.items():
        user_id = TEKNISI_MAP[teknisi_nama]
        group_key = "group1" if user_id in GROUP1_TEKNISI_IDS else "group2"
        group_id = GROUP_MAP[group_key]

        mention_teknisi = f"<a href='tg://user?id={user_id}'>{teknisi_nama}</a>"

        full_pesan = (
            f"📊 Laporan Progres Unspec Hari Ini\n"
            f"👷 Teknisi: {mention_teknisi}\n\n"
            f"{pesan}"
        )

        print("Data ditemukan:", laporan)

        # Kirim ke grup teknisi
        bot.send_message(chat_id=94494553,
                         text=full_pesan,
                         parse_mode=ParseMode.HTML)

        # Juga kirim ke private teknisi
        #bot.send_message(chat_id=user_id, text=full_pesan, parse_mode=ParseMode.HTML)


def laporan_progres_scheduler(bot):
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    scheduler.add_job(lambda: kirim_laporan(bot),
                      'cron',
                      hour='10,12,15,17',
                      minute=0)
    scheduler.start()


def generate_laporan_progres(bot):
    kirim_laporan(bot)


if __name__ == "__main__":
    from telegram import Bot
    from telegram import ParseMode

    bot = Bot(token="8137142032:AAHUeww0B9I4GGrGTFO64GdVNbgQYBXsZUo")
    from laporan_progres import kirim_laporan
    kirim_laporan(bot)
