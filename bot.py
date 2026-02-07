import os
import logging
import asyncio
from io import BytesIO
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
import google.generativeai as genai

# ==========================================
# CONFIGURATION
# ==========================================
# On a VPS, we will set these as environment variables (safer)
GEMINI_KEY = os.getenv("GEMINI_API_KEY") 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Configure Gemini
genai.configure(api_key=GEMINI_KEY)
# Note: Use 'gemini-1.5-flash' for text, and your image model choice
TEXT_MODEL = genai.GenerativeModel('gemini-1.5-flash')
IMAGE_MODEL = genai.GenerativeModel('imagen-3.0-generate-001')

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================================
# GEMINI LOGIC
# ==========================================
SYSTEM_PROMPT = """
You are a Monster Data Generator.
Input: Name, Element, Rarity.
Rules:
- Common:    HP: 80-120  | ATK: 10-30   | DEF: 40-60    | SPD: 30-40
- Rare:      HP: 100-160 | ATK: 30-50   | DEF: 60-80    | SPD: 40-50
- Epic:      HP: 120-200 | ATK: 50-70   | DEF: 80-110   | SPD: 50-60
- Legendary: HP: 150-220 | ATK: 70-100  | DEF: 110-150  | SPD: 60-68
- Mythic:    HP: 200-250 | ATK: 100-130 | DEF: 150-180  | SPD: 68-75
- Sacred:    HP: 250-300 | ATK: 130-150 | DEF: 180-200  | SPD: 75-90

Output Format (Strictly No Markdown/Brackets):
Name: {Name}
Element: {Element}
Rarity: {Rarity}
Stats: {HP} {ATK} {DEF} {SPD}
Move 1: {Move Name} | {Power} | {Accuracy}
Move 2: {Move Name} | {Power} | {Accuracy}
Move 3: {Move Name} | {Power} | {Accuracy}
"""

async def get_gemini_response(name, element, rarity):
    # Wrapper to run blocking API calls in a separate thread
    def generate():
        prompt = f"{SYSTEM_PROMPT}\n\nUSER INPUT -> Name: {name}, Element: {element}, Rarity: {rarity}"
        try:
            txt_response = TEXT_MODEL.generate_content(prompt)
            stats_text = txt_response.text.strip()
        except Exception as e:
            stats_text = f"Error generating text: {e}"

        img_bytes = None
        try:
            img_prompt = f"Generate a image of {element} {name} monster, Quality - 4k, Ratio - 1:1"
            img_response = IMAGE_MODEL.generate_content(img_prompt)
            img = img_response.parts[0].image
            bio = BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            img_bytes = bio
        except Exception as e:
            logging.error(f"Image Error: {e}")
        
        return stats_text, img_bytes

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, generate)

# ==========================================
# TELEGRAM HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bot Online!\nUsage: `/generate Name Element Rarity`")

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("⚠️ Usage: `/generate [Name] [Element] [Rarity]`")
        return

    name, element, rarity = context.args[0], context.args[1], context.args[2]
    status_msg = await update.message.reply_text(f"⚡ Summoning {name}...")

    try:
        stats_text, img_bytes = await get_gemini_response(name, element, rarity)
        
        if img_bytes:
            await update.message.reply_photo(photo=img_bytes, caption=stats_text)
        else:
            await update.message.reply_text(stats_text)
            
    except Exception as e:
        await update.message.reply_text(f"Critical Error: {e}")

    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)

# ==========================================
# MAIN
# ==========================================
if __name__ == '__main__':
    if not GEMINI_KEY or not TELEGRAM_TOKEN:
        print("Error: Environment variables GEMINI_API_KEY or TELEGRAM_BOT_TOKEN are missing.")
        exit(1)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('generate', generate_command))
    
    print("Bot is running...")
    app.run_polling()
