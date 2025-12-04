# # db.py
#
# import asyncpg
# import config
# import json
# import logging
#
# pool = None
# logging.basicConfig(level=logging.INFO)
#
#
# # 1. 🌐 Ulanish poolini yaratish
# async def create_db_pool():
#     global pool
#     try:
#         pool = await asyncpg.create_pool(
#             user=config.DB_USER,
#             password=config.DB_PASS,
#             host=config.DB_HOST,
#             port=config.DB_PORT,
#             database=config.DB_NAME,
#             timeout=5
#         )
#         logging.info("✅ DB pool muvaffaqiyatli yaratildi.")
#     except Exception as e:
#         logging.error(f"❌ DB ulanishida xatolik yuz berdi: {e}")
#         pool = None
#
#     # 2. 🛑 Ulanish poolini yopish
#
#
# async def close_db_pool():
#     global pool
#     if pool:
#         await pool.close()
#         logging.info("🔴 DB pool yopildi.")
#
#
# # 3. 📊 Jadval yaratish
# async def create_tables():
#     if pool is None:
#         logging.warning("Jadval yaratish uchun DB ulanishi mavjud emas.")
#         return
#
#     query = """
#     CREATE TABLE IF NOT EXISTS orders (
#         order_id SERIAL PRIMARY KEY,
#         user_id BIGINT NOT NULL,
#         username VARCHAR(255),
#         created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
#         modification_count INTEGER DEFAULT 0,
#         offered_price INTEGER,
#         data JSONB
#     );
#     """
#     try:
#         await pool.execute(query)
#         logging.info("📊 'orders' jadvali tayyor.")
#     except Exception as e:
#         logging.error(f"❌ Jadval yaratishda xatolik yuz berdi: {e}")
#
#
# # 4. 💾 Buyurtmani saqlash (YANGILANDI: offered_price=0 default qiymat sifatida)
# async def save_order_to_db(user_id, username, data, offered_price=0):
#     if pool is None:
#         logging.error("🛑 Buyurtma saqlanmadi: DB ulanishi yo'q.")
#         return None
#
#     price = offered_price  # Narxni 0 yoki None deb saqlaymiz
#     data_json = json.dumps(data)
#
#     query = """
#     INSERT INTO orders (user_id, username, offered_price, data, modification_count)
#     VALUES ($1, $2, $3, $4, 0)
#     RETURNING order_id;
#     """
#     try:
#         order_id = await pool.fetchval(query, user_id, username, price, data_json)
#         return order_id
#     except Exception as e:
#         logging.error(f"❌ Buyurtmani saqlashda xato: {e}")
#         return None
#
#
# # 5. 🔄 Oxirgi buyurtmani olish
# async def get_last_order(user_id):
#     if pool is None: return None
#     query = """
#         SELECT order_id, modification_count
#         FROM orders
#         WHERE user_id = $1
#         ORDER BY created_at DESC
#         LIMIT 1;
#     """
#     record = await pool.fetchrow(query, user_id)
#     if record:
#         return {
#             'order_id': record['order_id'],
#             'modification_count': record['modification_count']
#         }
#     return None
#
#
# # 6. 🎯 ID orqali to'liq buyurtmani olish (TUZATILGAN: data JSON stringdan dictga o'tkazildi)
# async def get_order_by_id(order_id):
#     if pool is None: return None
#     query = "SELECT user_id, username, offered_price, modification_count, data FROM orders WHERE order_id = $1;"
#     record = await pool.fetchrow(query, order_id)
#     if record:
#         order_data = record['data']
#         if isinstance(order_data, str):
#             order_data = json.loads(order_data)
#
#         return {
#             'user_id': record['user_id'],
#             'username': record['username'],
#             'offered_price': record['offered_price'],
#             'modification_count': record['modification_count'],
#             'data': order_data
#         }
#     return None
#
#
# # 7. 📝 Buyurtma ma'lumotlarini yangilash (offered_price maydoni endi ishlatilmaydi, lekin saqlanib qoladi)
# async def update_order_data(order_id, field, value):
#     if pool is None: return
#
#     # offered_price yangilash olib tashlandi, lekin agar kelib qolsa, shunday qoladi
#     if field == 'offered_price':
#         query = "UPDATE orders SET offered_price = $1 WHERE order_id = $2;"
#         await pool.execute(query, value, order_id)
#         return
#
#     query = f"""
#         UPDATE orders
#         SET data = jsonb_set(data, '{{ {field} }}', $1::jsonb)
#         WHERE order_id = $2;
#     """
#     try:
#         await pool.execute(query, json.dumps(value), order_id)
#     except Exception as e:
#         logging.error(f"JSON data yangilanishida xato: {e}")
#
#
# # 8. ➕ O'zgartirish sonini oshirish
# async def increment_modification_count(order_id):
#     if pool is None: return 0
#     query = """
#     UPDATE orders
#     SET modification_count = modification_count + 1
#     WHERE order_id = $1
#     RETURNING modification_count;
#     """
#     new_count = await pool.fetchval(query, order_id)
#     return new_count if new_count is not None else 0



import asyncpg
import config
import json
import logging

pool = None
logging.basicConfig(level=logging.INFO)


# 1. 🌐 Ulanish poolini yaratish
async def create_db_pool():
    global pool
    try:
        pool = await asyncpg.create_pool(
            user=config.DB_USER,
            # ESKI: password=config.DB_PASS,
            password=config.DB_PASSWORD,  # Yangi config.py ga moslandi
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
            timeout=5
        )
        logging.info("✅ DB pool muvaffaqiyatli yaratildi.")
    except Exception as e:
        logging.error(f"❌ DB ulanishida xatolik yuz berdi: {e}")
        pool = None

    # 2. 🛑 Ulanish poolini yopish


async def close_db_pool():
    global pool
    if pool:
        await pool.close()
        logging.info("🔴 DB pool yopildi.")


# 3. 📊 Jadval yaratish
async def create_tables():
    if pool is None:
        logging.warning("Jadval yaratish uchun DB ulanishi mavjud emas.")
        return

    query = """
    CREATE TABLE IF NOT EXISTS orders (
        order_id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        username VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        modification_count INTEGER DEFAULT 0,
        offered_price INTEGER,
        data JSONB
    );
    """
    try:
        await pool.execute(query)
        logging.info("📊 'orders' jadvali tayyor.")
    except Exception as e:
        logging.error(f"❌ Jadval yaratishda xatolik yuz berdi: {e}")


# 4. 💾 Buyurtmani saqlash (YANGILANDI: offered_price=0 default qiymat sifatida)
async def save_order_to_db(user_id, username, data, offered_price=0):
    if pool is None:
        logging.error("🛑 Buyurtma saqlanmadi: DB ulanishi yo'q.")
        return None

    price = offered_price
    data_json = json.dumps(data)

    query = """
    INSERT INTO orders (user_id, username, offered_price, data, modification_count)
    VALUES ($1, $2, $3, $4, 0)
    RETURNING order_id;
    """
    try:
        order_id = await pool.fetchval(query, user_id, username, price, data_json)
        return order_id
    except Exception as e:
        logging.error(f"❌ Buyurtmani saqlashda xato: {e}")
        return None


# 5. 🔄 Oxirgi buyurtmani olish
async def get_last_order(user_id):
    if pool is None: return None
    query = """
        SELECT order_id, modification_count
        FROM orders
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 1;
    """
    record = await pool.fetchrow(query, user_id)
    if record:
        return {
            'order_id': record['order_id'],
            'modification_count': record['modification_count']
        }
    return None


# 6. 🎯 ID orqali to'liq buyurtmani olish (TUZATILGAN: data JSON stringdan dictga o'tkazildi)
async def get_order_by_id(order_id):
    if pool is None: return None
    query = "SELECT user_id, username, offered_price, modification_count, data FROM orders WHERE order_id = $1;"
    record = await pool.fetchrow(query, order_id)
    if record:
        order_data = record['data']
        # asyncpg ba'zan JSONB ustunini avtomatik dictga o'tkazadi.
        # Agar string bo'lsa, uni qo'lda o'tkazamiz (xavfsizlik uchun)
        if isinstance(order_data, str):
            order_data = json.loads(order_data)

        return {
            'user_id': record['user_id'],
            'username': record['username'],
            'offered_price': record['offered_price'],
            'modification_count': record['modification_count'],
            'data': order_data
        }
    return None


# 7. 📝 Buyurtma ma'lumotlarini yangilash (offered_price maydoni endi ishlatilmaydi, lekin saqlanib qoladi)
async def update_order_data(order_id, field, value):
    if pool is None: return

    # offered_price yangilash olib tashlandi, lekin agar kelib qolsa, shunday qoladi
    if field == 'offered_price':
        query = "UPDATE orders SET offered_price = $1 WHERE order_id = $2;"
        await pool.execute(query, value, order_id)
        return

    # JSONB ustunidagi qiymatni yangilash
    query = f"""
        UPDATE orders
        SET data = jsonb_set(data, '{{ {field} }}', $1::jsonb)
        WHERE order_id = $2;
    """
    try:
        await pool.execute(query, json.dumps(value), order_id)
    except Exception as e:
        logging.error(f"JSON data yangilanishida xato: {e}")


# 8. ➕ O'zgartirish sonini oshirish
async def increment_modification_count(order_id):
    if pool is None: return 0
    query = """
    UPDATE orders
    SET modification_count = modification_count + 1
    WHERE order_id = $1
    RETURNING modification_count;
    """
    new_count = await pool.fetchval(query, order_id)
    return new_count if new_count is not None else 0