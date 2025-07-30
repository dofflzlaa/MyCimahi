import threading
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from telegram import Bot, error
import pytz

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1JPuVh2Nje8a64I7aImgPnIzC-jorQjX0VjMawrC1xLs'
SHEET_NAME = 'CMI-NJG'

JAKARTA_TZ = pytz.timezone('Asia/Jakarta')

SLA_MAP = {
    "PLATINUM": 6,
    "DIAMOND": 3,
    "FFG": 3,
    "GOLD": 12,
    "HVC_GOLD": 12,
    "REGULER": 12
}

# Mapping ID Telegram yang termasuk grup 1
GROUP1_TECH_IDS = {
    187341812, 7502933882, 698817453, 490182234, 190329914,
    52592435, 531045020, 432909325, 152714062, 5803062407,
    775806683, 1146830037
}

GROUP2_TECH_IDS = {
    1264932854, 85837025, 204904444, 164437085, 96431080,
    1248239258, 103280105, 604372370, 62669475, 237579695,
    98398750
}

# Mapping grup Telegram
GROUP_MAP = {
    "group1": -1002711361278,
    "group2": -1002600448648
}

def get_service():
    creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def parse_datetime(dt_str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt_naive = datetime.strptime(dt_str.strip(), fmt)
            return JAKARTA_TZ.localize(dt_naive)  # pastikan jadi offset-aware
        except:
            continue
    return None



def get_sla_hours(cust_type):
    return SLA_MAP.get(cust_type.strip().upper(), 12)

def ttr_reminder_loop(bot: Bot, teknisi_map: dict):
    try:
        service = get_service()
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1:DH"
        ).execute()
        rows = result.get("values", [])

        if not rows or len(rows) < 2:
            print("Data kosong.")
            threading.Timer(3600, ttr_reminder_loop, args=(bot, teknisi_map)).start()
            return

        data_rows = rows[1:]

        for i, row in enumerate(data_rows):
            row_num = i + 2
            try:
                incident = row[0] if len(row) > 0 else ""
                summary = row[2] if len(row) > 2 else ""
                status = row[10] if len(row) > 10 else ""
                reported_str = row[3] if len(row) > 3 else ""
                teknisi_nama = row[82] if len(row) > 82 else ""
                customer_type = row[24] if len(row) > 24 else ""

                if "SQM" in summary.upper() or customer_type.strip().upper() == "Z_NN":
                    continue
                if status.strip().upper() not in {"BACKEND", "ANALYSIS"}:
                    continue

                reported_date = parse_datetime(reported_str)
                if not reported_date:
                    continue
                now = datetime.now(JAKARTA_TZ)

                sla_hours = get_sla_hours(customer_type)
                deadline = reported_date + timedelta(hours=sla_hours)

                durasi = now - reported_date
                sisa = deadline - now

                durasi_str = f"{durasi.days * 24 + durasi.seconds//3600} jam {((durasi.seconds % 3600)//60)} menit"
                sisa_str = (
                    f"{sisa.days * 24 + sisa.seconds//3600} jam {((sisa.seconds % 3600)//60)} menit"
                    if sisa.total_seconds() > 0 else "❗ Sudah Lewat Waktu"
                )

                found_teknisi = None
                for teknisi_id, info in teknisi_map.items():
                    if info['nama'].strip().lower() in teknisi_nama.strip().lower():
                        found_teknisi = info
                        break

                msg_individual = (
                    f"🔔 <b>Reminder TTR Tiket</b>\n"
                    f"📋 Incident: {incident.strip()}\n"
                    f"👥 Customer Type: {customer_type.strip()}\n"
                    f"📅 Reported: {reported_str.strip()}\n"
                    f"⏱ Durasi: {durasi_str}\n"
                    f"⏳ Sisa TTR: {sisa_str}"
                )

                if found_teknisi:
                    try:
                        bot.send_message(chat_id=found_teknisi['id'], text=msg_individual, parse_mode='HTML')
                        print(f"[OK] Terkirim ke teknisi: {found_teknisi['nama']}")
                    except error.Unauthorized:
                        print(f"[GAGAL] Tidak bisa kirim ke {found_teknisi['nama']} (ID: {found_teknisi['id']})")
                else:
                    print(f"[SKIP] Tidak ada teknisi match untuk: '{teknisi_nama}'")

                # Kirim hanya ke grup yang sesuai
                if found_teknisi:
                    teknisi_id = found_teknisi["id"]
                    target_group_key = "group1" if teknisi_id in GROUP1_TECH_IDS else "group2"
                    group_chat_id = GROUP_MAP[target_group_key]

                    msg_group = (
                        f"🔔 <b>Reminder TTR Tiket</b>\n"
                        f"👤 Teknisi: <a href='tg://user?id={teknisi_id}'>{found_teknisi['nama']}</a>\n"
                        f"📋 Incident: {incident.strip()}\n"
                        f"👥 Customer Type: {customer_type.strip()}\n"
                        f"📅 Reported: {reported_str.strip()}\n"
                        f"⏱ Durasi: {durasi_str}\n"
                        f"⏳ Sisa TTR: {sisa_str}"
                    )

                    try:
                        bot.send_message(chat_id=group_chat_id, text=msg_group, parse_mode='HTML')
                        print(f"[OK] Reminder terkirim ke grup {target_group_key}")
                    except Exception as err:
                        print(f"[ERROR] Gagal kirim ke grup {target_group_key}: {err}")

            except Exception as e:
                print(f"[ERROR] Baris {row_num}: {e}")

    except Exception as e:
        print(f"[FATAL] Gagal ambil data: {e}")

    threading.Timer(3600, ttr_reminder_loop, args=(bot, teknisi_map)).start()

def run_ttr_check_once(bot: Bot, teknisi_map: dict):
    print("[INFO] Menjalankan pengecekan TTR manual...")

    try:
        service = get_service()
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1:DH" # Diperluas ke DH untuk memastikan DG (indeks 82) terbaca
        ).execute()
        rows = result.get("values", [])

        if not rows or len(rows) < 2:
            print("Data kosong.")
            return

        data_rows = rows[1:]

        for i, row in enumerate(data_rows):
            row_num = i + 2
            try:
                # Kolom Incident ada di A (indeks 0) - untuk ditampilkan di pesan
                incident = row[0] if len(row) > 0 else ""
                # Kolom Summary ada di C (indeks 2) - untuk filter SQM
                summary = row[2] if len(row) > 2 else ""
                # Kolom Status ada di K (indeks 10) - untuk filter BACKEND/ANALYSIS
                status = row[10] if len(row) > 10 else ""
                # Kolom Reported ada di D (indeks 3)
                reported_str = row[3] if len(row) > 3 else ""
                # Kolom Teknisi Nama ada di DG (indeks 82)
                teknisi_nama = row[82] if len(row) > 82 else ""
                # Kolom Customer Type ada di Y (indeks 24) - untuk filter Z_NN dan ditampilkan di pesan
                customer_type = row[24] if len(row) > 24 else ""

                print(f"[DEBUG BARIS {row_num}] Incident='{incident}', Summary='{summary}', Status='{status}', Reported='{reported_str}', Teknisi='{teknisi_nama}', Cust Type='{customer_type}'")

                if "SQM" in summary.upper() or customer_type.strip().upper() == "Z_NN":
                    continue
                if status.strip().upper() not in {"BACKEND", "ANALYSIS", "NEW"}:
                    continue

                reported_date = parse_datetime(reported_str)
                if not reported_date:
                    continue

                sla_hours = get_sla_hours(customer_type)
                deadline = reported_date + timedelta(hours=sla_hours)
                now = datetime.now(JAKARTA_TZ)

                durasi = now - reported_date
                sisa = deadline - now

                durasi_str = f"{durasi.seconds//3600} jam {((durasi.seconds%3600)//60)} menit"
                sisa_str = (
                    f"{sisa.seconds//3600} jam {((sisa.seconds%3600)//60)} menit"
                    if sisa.total_seconds() > 0 else "❗ Sudah Lewat Waktu"
                )

                msg_individual = (
                    f"🔔 <b>Reminder TTR Tiket</b>\n"
                    f"📋 Incident: {incident.strip()}\n" # Menampilkan Incident dari kolom A
                    f"👥 Customer Type: {customer_type.strip()}\n" # Menampilkan Customer Type
                    f"📅 Reported: {reported_str.strip()}\n"
                    f"⏱ Durasi: {durasi_str}\n"
                    f"⏳ Sisa TTR: {sisa_str}"
                )

                msg_group = (
                    f"🔔 <b>Reminder TTR Tiket</b>\n"
                    f"👤 Teknisi: {teknisi_nama.strip()}\n"
                    f"📋 Incident: {incident.strip()}\n" # Menampilkan Incident dari kolom A
                    f"👥 Customer Type: {customer_type.strip()}\n" # Menampilkan Customer Type
                    f"📅 Reported: {reported_str.strip()}\n"
                    f"⏱ Durasi: {durasi_str}\n"
                    f"⏳ Sisa TTR: {sisa_str}"
                )

                found_teknisi_for_individual_message = False
                for teknisi_id, info in teknisi_map.items():
                    if info['nama'].strip().lower() in teknisi_nama.strip().lower():
                        found_teknisi_for_individual_message = True
                        print(f"[DEBUG BARIS {row_num}] Mencoba mengirim reminder ke teknisi: {info['nama']} (ID: {info['id']})")
                        try:
                            bot.send_message(chat_id=info['id'], text=msg_individual, parse_mode='HTML')
                            print(f"[DEBUG BARIS {row_num}] Berhasil mengirim ke teknisi {info['nama']}.")
                        except error.Unauthorized:
                            print(f"[ERROR TELEGRAM] BARIS {row_num}: Bot tidak bisa mengirim pesan ke teknisi {info['nama']} (ID: {info['id']}). Pastikan sudah memulai percakapan dengan bot atau tidak diblokir.")
                        except Exception as telegram_err:
                            print(f"[ERROR TELEGRAM] BARIS {row_num}: Gagal mengirim pesan ke teknisi {info['nama']} (ID: {info['id']}): {telegram_err}")
                        break

                if not found_teknisi_for_individual_message:
                    print(f"[DEBUG BARIS {row_num}] Tidak ada teknisi yang cocok ditemukan di map untuk nama teknisi: '{teknisi_nama}'. Pesan individual tidak terkirim.")

                for group_name, group_chat_id in GROUP_MAP.items():
                    print(f"[DEBUG BARIS {row_num}] Mencoba mengirim reminder ke {group_name} (ID: {group_chat_id}).")
                    try:
                        bot.send_message(chat_id=group_chat_id, text=msg_group, parse_mode='HTML')
                        print(f"[DEBUG BARIS {row_num}] Berhasil mengirim ke {group_name} (ID: {group_chat_id}).")
                    except error.Unauthorized:
                        print(f"[ERROR TELEGRAM] BARIS {row_num}: Bot tidak bisa mengirim pesan ke grup {group_name} (ID: {group_chat_id}). Pastikan bot sudah di grup dan grup sudah berinteraksi dengan bot.")
                    except Exception as telegram_err:
                        print(f"[ERROR TELEGRAM] BARIS {row_num}: Gagal mengirim pesan ke grup {group_name} (ID: {group_chat_id}): {telegram_err}")


            except Exception as e:
                print(f"[ERROR PROCESSING ROW] Baris {row_num}: Gagal proses baris: {e}")

    except Exception as e:
        print(f"[FATAL] Gagal baca sheet: {e}")