# # Bot va DB uchun kerakli ma'lumotlar
# BOT_TOKEN = "8512718251:AAGGcXzuf1BLLSYKnhEPbxpTMdlNeWXUQbA"
#
# # MUHIM: Nomi OPERATOR_IDS bo'lishi shart
# OPERATOR_IDS = [
#     5617184769,  # Operator 1 ID'si
#     7394345210   # Operator 2 ID'si
# ]
#  # Xabarni yuborish kerak bo'lgan operatorning ID'si
# #5617184769
# # PostgreSQL ulanish ma'lumotlari
# DB_USER = "postgres"
# DB_PASS = "rood"
# DB_PORT = 5432
# DB_HOST = "localhost"
# DB_NAME = "postgres"
#


import os

# --- Telegram Ma'lumotlari ---

# Bot tokeni Environment Variables dan olinadi
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8512718256:AAGGcXzuf1BLLSYKnhEPbxpTMdlNeWXUQbA")

# Operator ID'lari Environment Variables dan vergul bilan ajratilgan holda olinadi
# Agar topilmasa, lokal/qattiq yozilgan qiymat ishlatiladi.
OPERATOR_IDS_STR = os.environ.get("OPERATOR_IDS", "5617184769, 7394345210")
OPERATOR_IDS = [int(i.strip()) for i in OPERATOR_IDS_STR.split(',') if i.strip()]

# Agar BOT_TOKEN topilmasa, xato chiqarish (Muhim)
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN muhit o'zgaruvchisi topilmadi.")


# --- PostgreSQL Ulanish Ma'lumotlari ---
# Railway/Render da PGHOST, PGDATABASE kabi o'zgaruvchilar ishlatiladi.
# Agar serverda bo'lsa (os.environ.get topilsa), o'sha qiymatni oladi.
# Agar topilmasa (lokal ishlaganda), "localhost" kabi qiymatlarni oladi.

DB_HOST = os.environ.get("PGHOST") or os.environ.get("DB_HOST", "postgres.railway.internal")
DB_USER = os.environ.get("PGUSER") or os.environ.get("DB_USER", "postgres")
# Serverlar ko'pincha PGPASSWORD nomini ishlatadi
DB_PASSWORD = os.environ.get("PGPASSWORD") or os.environ.get("DB_PASS", "jgtMpEaSjvsrTYMeZldwLhqRieFZAYWW")
DB_NAME = os.environ.get("PGDATABASE") or os.environ.get("DB_NAME", "railway")
DB_PORT = int(os.environ.get("PGPORT") or os.environ.get("DB_PORT", 5432))

# DB ma'lumotlari topilmaganligi haqida ogohlantirish
if DB_HOST == "localhost":
    print("DIQQAT: DB ulanish ma'lumotlari Environment Variables dan olinmadi. Lokal sozlamalar ishlatilmoqda.")
