import sqlite3
import requests
import json
import io
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.error import Forbidden # Zaruri import

# --- CONFIGURATION ---
TOKEN = '8454302579:AAEO3dDeCB27kNxPiTazN9riH3E8bVMeE68'
ADMIN_ID = 7668569080 
API_URL = "https://star-guest.vercel.app/gen"
CHANNELS = ["@narutocodex7", "@narutogiveawayy", "@narutogiiveaway"]

# States
REGION, NAME, COUNT, REDEEM_INP = range(4)

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect('kamod_bot.db', timeout=30, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;') 
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 20, referred_by INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes 
                 (code TEXT PRIMARY KEY, value INTEGER, uses_left INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS redeemed_history 
                 (user_id INTEGER, code TEXT, PRIMARY KEY (user_id, code))''')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    if not res:
        c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 20))
        conn.commit()
        conn.close()
        return 20
    conn.close()
    return res[0]

def update_balance(user_id, amount):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- FORCE JOIN UTILITY ---
async def is_subscribed(bot, user_id):
    if user_id == ADMIN_ID: return True
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']: return False
        except: return False
    return True

def get_join_markup():
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel 1", url="https://t.me/narutocodex7")],
        [InlineKeyboardButton("📢 Join Channel 2", url="https://t.me/narutogiveawayy")],
        [InlineKeyboardButton("📢 Join Channel 3", url="https://t.me/narutogiiveaway")],
        [InlineKeyboardButton("✅ VERIFY", callback_data="verify_join")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_permanent_keyboard():
    keyboard = [
        ["🔥 GENERATE ACCOUNTS"],
        ["💰 BALANCE", "🎁 REDEEM"],
        ["👤 OWNER", "👥 REFER"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- CORE HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return # Safety check
    
    user = update.effective_user
    user_id = user.id
    init_db()

    args = context.args
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone() is None:
        ref_id = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
        if ref_id:
            update_balance(ref_id, 20)
            try: await context.bot.send_message(chat_id=ref_id, text="🎁 **Referral Bonus!** +20 Coins mile.")
            except: pass
        c.execute("INSERT INTO users (user_id, balance, referred_by) VALUES (?, ?, ?)", (user_id, 20, ref_id))
        conn.commit()
    conn.close()

    if not await is_subscribed(context.bot, user_id):
        # ERROR FIX: Added try-except for Forbidden (Blocked user)
        try:
            await update.message.reply_text("❌ **Access Denied!** Join channels first.", reply_markup=get_join_markup())
        except Forbidden:
            pass
        return

    welcome_text = f"👋 **Hello, {user.first_name}!**\n💰 Your Balance: `{get_user_data(user_id)}`"
    try:
        photos = await user.get_profile_photos()
        if photos.total_count > 0:
            await update.message.reply_photo(photo=photos.photos[0][0].file_id, caption=welcome_text, reply_markup=get_permanent_keyboard(), parse_mode="Markdown")
        else:
            await update.message.reply_text(welcome_text, reply_markup=get_permanent_keyboard(), parse_mode="Markdown")
    except (Forbidden, Exception):
        try: await update.message.reply_text(welcome_text, reply_markup=get_permanent_keyboard(), parse_mode="Markdown")
        except: pass

async def verify_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if await is_subscribed(context.bot, user_id):
        try:
            await query.message.delete()
            await context.bot.send_message(chat_id=user_id, text=f"✅ **Verified!**\n💰 Balance: `{get_user_data(user_id)}`", reply_markup=get_permanent_keyboard())
        except Forbidden: pass
    else:
        await query.answer("❌ Abhi bhi join nahi kiya!", show_alert=True)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ERROR FIX: Added safety check for update.message
    if not update.message or not update.message.text:
        return 
        
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "🔥 GENERATE ACCOUNTS":
        if get_user_data(user_id) <= 0:
            await update.message.reply_text("❌ Low Balance!")
            return ConversationHandler.END
        await update.message.reply_text("🌍 **Region? (IND, BRA, ID):**")
        return REGION
        
    elif text == "💰 BALANCE":
        await update.message.reply_text(f"💰 **Balance:** `{get_user_data(user_id)} Coins`")
        
    elif text == "🎁 REDEEM":
        await update.message.reply_text("🎁 **Enter your Redeem Code below:**")
        return REDEEM_INP
        
    elif text == "👤 OWNER":
        await update.message.reply_text("👤 **Owner:** @narutocodex9")
        
    elif text == "👥 REFER":
        bot_user = (await context.bot.get_me()).username
        await update.message.reply_text(f"🔗 **Refer Link:**\n`https://t.me/{bot_user}?start={user_id}`\n\nHar refer par **20 Coins** milenge!")

# --- GENERATION LOGIC ---
async def fetch_acc(params):
    loop = asyncio.get_event_loop()
    try:
        r = await loop.run_in_executor(None, lambda: requests.get(API_URL, params=params, timeout=15))
        return r.json() if r.status_code == 200 else None
    except: return None

async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['region'] = update.message.text
    await update.message.reply_text("👤 **Name?**")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("🔢 ** accounts count?**\n💳 **Cost:** `1 Coin = 1 Account`")
    return COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count_str = update.message.text
        if not count_str.isdigit():
            await update.message.reply_text("❌ Please enter a number!")
            return COUNT

        count = int(count_str)
        user_id = update.effective_user.id
        balance = get_user_data(user_id)

        if count <= 0:
            await update.message.reply_text("❌ Enter valid number!")
            return COUNT

        if count > balance:
            await update.message.reply_text("❌ Low Balance!")
            return ConversationHandler.END

        msg = await update.message.reply_text(f"🚀 Starting... 0/{count}")
        params = {
            'name': context.user_data['name'],
            'count': 1,
            'region': context.user_data['region']
        }

        final_accs = []

        for i in range(1, count + 1):
            res = await fetch_acc(params)
            if res:
                final_accs.append(res)

            try:
                await msg.edit_text(f"🚀 Generating: {i}/{count} Accounts...")
            except:
                pass

            if i < count:
                await asyncio.sleep(2)

        update_balance(user_id, -count)

        f_io = io.BytesIO(json.dumps(final_accs, indent=4).encode())
        f_io.name = f"accounts_{user_id}.json"

        try:
            await msg.delete()
        except:
            pass

        await update.message.reply_document(
            document=f_io,
            caption=f"✅ Success! {len(final_accs)} Accounts Generated."
        )

        return ConversationHandler.END

    except Exception as e:
        print(f"Error in get_count: {e}")
        return ConversationHandler.END

async def handle_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return ConversationHandler.END
    
    code_txt = update.message.text.strip()
    user_id = update.effective_user.id
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT 1 FROM redeemed_history WHERE user_id = ? AND code = ?", (user_id, code_txt))
    if c.fetchone():
        await update.message.reply_text("❌ **Already Claimed!**")
        conn.close()
        return ConversationHandler.END

    c.execute("SELECT value, uses_left FROM promo_codes WHERE code = ?", (code_txt,))
    res = c.fetchone()
    if res and res[1] > 0:
        val = res[0]
        c.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code_txt,))
        c.execute("INSERT INTO redeemed_history VALUES (?, ?)", (user_id, code_txt))
        conn.commit()
        update_balance(user_id, val)
        await update.message.reply_text(f"✅ **Redeemed!** +{val} Coins added.")
    else:
        await update.message.reply_text("❌ Code invalid ya limit khatam!")
    conn.close()
    return ConversationHandler.END

async def admin_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        code, val, uses = context.args[0], int(context.args[1]), int(context.args[2])
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO promo_codes VALUES (?, ?, ?)", (code, val, uses))
        conn.commit()
        conn.close()
        
        poster = (
            "╔══════════════════════╗\n"
            "🚀  𝗡𝗘𝗪 𝗣𝗥𝗢𝗠𝗢 𝗖𝗢𝗗𝗘 𝗔𝗟𝗘𝗥𝗧  🚀\n"
            "╚══════════════════════╝\n\n"
            f"🎟️ 𝗖𝗢𝗗𝗘 ➤  `{code}`\n"
            f"💎 𝗩𝗔𝗟𝗨𝗘 ➤  {val} 𝗖𝗢𝗜𝗡𝗦\n"
            f"👥 𝗟𝗜𝗠𝗜𝗧 ➤  {uses} 𝗨𝗦𝗘𝗥𝗦\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ 𝗙𝗔𝗦𝗧 𝗥𝗘𝗗𝗘𝗘𝗠 𝗡𝗢𝗪!\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 NARUTO CODEX", url="https://t.me/narutocodex7")],
            [InlineKeyboardButton("🤖 BOT LINK", url=f"https://t.me/KAMOD_ACCOUNT_GENRETER_BOT?start={ADMIN_ID}")]
        ])
        await update.message.reply_text(poster, reply_markup=kb, parse_mode="Markdown")
    except: await update.message.reply_text("Usage: `/redeem CODE VALUE LIMIT`")

async def global_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sabhi anjane errors ko catch karne ke liye
    print(f"Update {update} caused error {context.error}")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^(🔥 GENERATE ACCOUNTS|🎁 REDEEM)$'), handle_buttons)],
        states={
            REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_region)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_count)],
            REDEEM_INP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_redeem)],
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True # Ise True rakhne se user bich mein start kar sakta hai
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("redeem", admin_redeem))
    app.add_handler(CallbackQueryHandler(verify_join, pattern="verify_join"))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    app.add_error_handler(global_error_handler)
    
    print("Bot is LIVE...")
    app.run_polling()

if __name__ == '__main__':
    main()
