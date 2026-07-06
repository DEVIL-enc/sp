from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton
import io
import re
import math

# ضع بيانات البوت الخاصة بك هنا
API_ID = 39825025          # استبدله بـ api_id الخاص بك (رقم)
API_HASH = "47170fd9a11b3f591bbc56849519f0f8"    # استبدله بـ api_hash الخاص بك (نص)
BOT_TOKEN = "8923140239:AAHTBRLDDWoX__-JXSTBzTf39GKwO0_2oLc"

app = Client("card_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# تخزين مؤقت لحالات المستخدمين في الذاكرة
user_states = {}

# لوحة الأزرار الرئيسية
main_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("1- تقسيم ملفات (البطاقات)")],
     [KeyboardButton("2- استخراج عبر الـ BIN")],
     [KeyboardButton("3- تنظيف الملف (Clear)")]],
    resize_keyboard=True
)

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("أهلاً بك! اختر أحد الخيارات من الأزرار أدناه للبدء:", reply_markup=main_keyboard)

# --- معالجة الضغط على الأزرار ---
@app.on_message(filters.text & filters.incoming)
async def handle_text(client, message):
    chat_id = message.chat.id
    text = message.text

    if text == "1- تقسيم ملفات (البطاقات)":
        user_states[chat_id] = {"step": "split_wait_file"}
        await message.reply_text("📥 أرسل ملف البطاقات (حتى 300 ميجابايت بسرعات خيالية).")
        return
    elif text == "2- استخراج عبر الـ BIN":
        user_states[chat_id] = {"step": "bin_wait_file"}
        await message.reply_text("📥 أرسل ملف البطاقات الخاص بك (يدعم حتى 300 ميجابايت).")
        return
    elif text == "3- تنظيف الملف (Clear)":
        user_states[chat_id] = {"step": "clear_wait_file"}
        await message.reply_text("📥 أرسل ملف البطاقات المراد تنظيفه (يدعم حتى 300 ميجابايت).")
        return

    # استجابة الخطوات التالية للعمليات
    if chat_id in user_states:
        state = user_states[chat_id].get("step")
        if state == "split_wait_lines_count":
            await process_splitting_execution(message)
        elif state == "bin_wait_bins":
            await process_bin_extraction(message)

# --- معالجة تحميل وقراءة الملفات الضخمة بالذاكرة ---
@app.on_message((filters.document | filters.text) & filters.incoming)
async def handle_files(client, message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        return

    state = user_states[chat_id].get("step")
    if state in ["split_wait_lines_count", "bin_wait_bins"]:
        return  # تخطي معالجة المستندات إذا كنا ننتظر مدخلات نصية

    content = ""
    
    if message.text:
        content = message.text
    elif message.document:
        status_msg = await message.reply_text("⚡ جاري تحميل وقراءة الملف بسرعة فائقة جداً...")
        
        # تحميل مباشر في الرام لتوفير السرعة
        file_buffer = io.BytesIO()
        await client.download_media(message.document, in_memory=file_buffer)
        file_buffer.seek(0)
        
        content = file_buffer.read().decode("utf-8", errors="ignore")
        await status_msg.delete()

    # --- تنفيذ التوجيه بناءً على الحالة ---
    
    if state == "split_wait_file":
        # الآن نأخذ جميع الأسطر بدون أي تصفية لضمان قراءة ملفك بنسبة 100% مهما كان شكله
        cards = [line.strip() for line in content.splitlines() if line.strip()]
                
        if not cards:
            await message.reply_text("❌ الملف فارغ أو لا يحتوي على أسطر صالحة للقراءة.")
            user_states.pop(chat_id, None)
            return
        
        user_states[chat_id]["cards_list"] = cards
        user_states[chat_id]["step"] = "split_wait_lines_count"
        await message.reply_text(f"✅ تم قراءة {len(cards)} سطر بنجاح.\n\n🔢 كم سطر تريد في كل ملف؟ (أرسل الرقم فقط)")

    elif state == "bin_wait_file":
        user_states[chat_id]["file_content"] = content
        user_states[chat_id]["step"] = "bin_wait_bins"
        await message.reply_text("✅ تم قراءة الملف بنجاح.\n\n📥 الآن، أرسل قائمة الـ BINs (من 6 إلى 11 رقم)، مفصولة بأي فاصل.\n\nمثال: 442755, 4852464")

    elif state == "clear_wait_file":
        await process_clearing(message, content)

# --- تنفيذ التقسيم (الزر 1) ---
async def process_splitting_execution(message):
    chat_id = message.chat.id
    input_text = message.text

    if not input_text.isdigit() or int(input_text) <= 0:
        await message.reply_text("❌ الرجاء إرسال رقم صحيح أكبر من 0!")
        return

    lines_per_file = int(input_text)
    cards_list = user_states[chat_id].get("cards_list", [])
    total_cards = len(cards_list)
    total_files = math.ceil(total_cards / lines_per_file)

    await message.reply_text(f"⚡ جاري التقسيم الفوري لـ {total_files} ملف(ات)...")

    for i in range(total_files):
        chunk = cards_list[i * lines_per_file : (i + 1) * lines_per_file]
        output_text = "\n".join(chunk)
        
        bio = io.BytesIO(output_text.encode("utf-8"))
        bio.name = f"split_part_{i+1}.txt"
        
        await message.reply_document(bio, caption=f"📄 جزء رقم {i+1} يحتوي على {len(chunk)} سطر.")

    user_states.pop(chat_id, None)
    await message.reply_text("✅ تم الانتهاء من إرسال كافة الملفات!", reply_markup=main_keyboard)

# --- تنفيذ الـ BIN (الزر 2) ---
async def process_bin_extraction(message):
    chat_id = message.chat.id
    bin_text = message.text
    file_content = user_states[chat_id].get("file_content", "")

    bins = re.findall(r'\d{6,11}', bin_text)
    if not bins:
        await message.reply_text("❌ الرجاء إرسال أرقام BIN صالحة.")
        return

    # الفلترة الذكية للـ BIN في أي مكان يبدأ به السطر النظيف
    full_lines = []
    for line in file_content.splitlines():
        clean_line = line.strip()
        if any(clean_line.startswith(b) for b in bins):
            full_lines.append(clean_line)

    if not full_lines:
        await message.reply_text("❌ لم يتم العثور على أي بطاقات تبدأ بهذه الـ BINs.")
        return

    output = "\n".join(full_lines)
    await send_result(message, output, "extracted_bins.txt")
    user_states.pop(chat_id, None)

# --- تنفيذ التنظيف (الزر 3) ---
async def process_clearing(message, content):
    cleaned_lines = []
    for line in content.splitlines():
        # استخراج أرقام البطاقة والفواصل فقط من السطر وحذف أي نصوص وحروف عشوائية زائدة
        match = re.search(r'\d{12,19}[\s|/;:|-]\d{1,4}[\s|/;:|-]\d{1,4}[\s|/;:|-]\d{3,4}|\d{6,}', line)
        if match:
            cleaned_lines.append(match.group(0))

    if not cleaned_lines:
        await message.reply_text("❌ لم يتم العثور على بيانات صالحة لتنظيفها.")
        return

    output = "\n".join(cleaned_lines)
    await send_result(message, output, "cleaned_cards.txt")
    user_states.pop(message.chat.id, None)

# --- أداة إرسال النتائج الذكية ---
async def send_result(message, output_text, filename):
    if len(output_text) < 4000:
        await message.reply_text(f"✅ **النتيجة:**\n\n```\n{output_text}\n```")
    else:
        bio = io.BytesIO(output_text.encode("utf-8"))
        bio.name = filename
        await message.reply_document(bio, caption="✅ تم استخراج وتجهيز الملف بنجاح وبسرعة فائقة!")

# تشغيل البوت
app.run()
