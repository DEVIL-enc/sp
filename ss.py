import telebot
from telebot import types
import re
import io
import math

# ضع توكن البوت الخاص بك هنا
API_TOKEN = '8923140239:AAHTBRLDDWoX__-JXSTBzTf39GKwO0_2oLc'
bot = telebot.TeleBot(API_TOKEN)

# حالات المستخدمين لتتبع الخطوات والبيانات المؤقتة
user_states = {}

# لوحة الأزرار الرئيسية
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn1 = types.KeyboardButton("1- تقسيم ملفات (البطاقات)")
    btn2 = types.KeyboardButton("2- استخراج عبر الـ BIN")
    btn3 = types.KeyboardButton("3- تنظيف الملف (Clear)")
    markup.add(btn1, btn2, btn3)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! اختر أحد الخيارات من الأزرار أدناه للبدء:", reply_markup=main_keyboard())

# --- التعامل مع الضغط على الأزرار ---
@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    chat_id = message.chat.id
    text = message.text

    if text == "1- تقسيم ملفات (البطاقات)":
        user_states[chat_id] = {'step': 'split_wait_file'}
        bot.send_message(chat_id, "📥 أرسل ملف البطاقات (حتى 300 ميجابايت).")

    elif text == "2- استخراج عبر الـ BIN":
        user_states[chat_id] = {'step': 'bin_wait_file'}
        bot.send_message(chat_id, "📥 أرسل بطاقاتك بأي صيغة في رسالة واحدة أو ملف (حتى 300 ميجابايت).")

    elif text == "3- تنظيف الملف (Clear)":
        user_states[chat_id] = {'step': 'clear_wait_file'}
        bot.send_message(chat_id, "📥 أرسل بطاقاتك بأي صيغة في رسالة واحدة أو ملف (حتى 300 ميجابايت).")
        
    else:
        # التعامل مع المدخلات النصية التالية للخطوات
        if chat_id in user_states:
            current_step = user_states[chat_id].get('step')
            if current_step == 'split_wait_lines_count':
                process_splitting_execution(message)
            elif current_step == 'bin_wait_bins':
                process_bin_extraction(message)

# --- استقبال ومعالجة الملفات الكبيرة في الذاكرة ---
@bot.message_handler(content_types=['document', 'text'])
def handle_docs_and_text(message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        return

    step = user_states[chat_id].get('step')
    
    # الحصول على النص (من رسالة أو ملف تيكست)
    content = ""
    if message.content_type == 'text':
        content = message.text
    elif message.content_type == 'document':
        if message.document.file_size > 300 * 1024 * 1024:
            bot.reply_to(message, "❌ حجم الملف كبير جداً! الحد الأقصى هو 300 ميجابايت.")
            return
        
        status_msg = bot.reply_to(message, "⚡ جاري قراءة الملف بسرعة فائقة...")
        
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8', errors='ignore')
        bot.delete_message(chat_id, status_msg.message_id)

    # توجيه الملف حسب الخطوة
    if step == 'split_wait_file':
        # فلترة وتصفية الأسطر أولاً لضمان وجود بطاقات فقط تحت بعضها
        # النمط يبحث عن أي سطر يحتوي على سلسلة أرقام تبدأ بـ 6 أرقام على الأقل
        cards = re.findall(r'\d{6,}.*', content)
        
        if not cards:
            bot.reply_to(message, "❌ لم يتم العثور على أسطر تحتوي على بطاقات صالحة في هذا الملف.")
            user_states.pop(chat_id, None)
            return
            
        # حفظ البطاقات المفلترة والانتقال لسؤال المستخدم عن عدد الأسطر
        user_states[chat_id]['cards_list'] = cards
        user_states[chat_id]['step'] = 'split_wait_lines_count'
        bot.reply_to(message, f"✅ تم قراءة وتصفية {len(cards)} بطاقة بنجاح.\n\n🔢 كم سطر (بطاقة) تريد في كل ملف؟ (أرسل الرقم فقط)")
        
    elif step == 'bin_wait_file':
        user_states[chat_id]['file_content'] = content
        user_states[chat_id]['step'] = 'bin_wait_bins'
        bot.reply_to(message, "✅ تم قراءة الملف بنجاح.\n\n📥 الآن، أرسل قائمة الـ BINs (من 6 إلى 11 رقم) المراد استخراجها، مفصولة بأي فاصل.\n\nمثال: 442755, 4852464, 434769")

    elif step == 'clear_wait_file':
        process_clearing(message, content)

# --- تنفيذ عملية التقسيم (تعديل الزر 1) ---
def process_splitting_execution(message):
    chat_id = message.chat.id
    input_text = message.text
    
    if not input_text.isdigit():
        bot.reply_to(message, "❌ الرجاء إرسال رقم صحيح فقط!")
        return
        
    lines_per_file = int(input_text)
    if lines_per_file <= 0:
        bot.reply_to(message, "❌ يجب أن يكون العدد أكبر من 0.")
        return
        
    cards_list = user_states[chat_id].get('cards_list', [])
    total_cards = len(cards_list)
    
    # حساب عدد الملفات المطلوبة
    total_files = math.ceil(total_cards / lines_per_file)
    
    bot.send_message(chat_id, f"⚡ جاري تقسيم البطاقات إلى {total_files} ملف(ات)...")
    
    # تقسيم وإرسال الملفات بشكل فوري من الذاكرة
    for i in range(total_files):
        start_index = i * lines_per_file
        end_index = start_index + lines_per_file
        chunk = cards_list[start_index:end_index]
        
        output_text = "\n".join(chunk)
        filename = f"split_part_{i+1}.txt"
        
        # تحويل النص لملف في الذاكرة وإرساله بسرعة خيالية
        bio = io.BytesIO(output_text.encode('utf-8'))
        bio.name = filename
        bot.send_document(chat_id, bio, caption=f"📄 جزء رقم {i+1} يحتوي على {len(chunk)} بطاقة.")
        
    # تنظيف الحالة بعد الانتهاء
    user_states.pop(chat_id, None)
    bot.send_message(chat_id, "✅ تم الانتهاء من إرسال جميع الملفات المقسمة!", reply_markup=main_keyboard())

# --- تنفيذ عملية الـ BIN (الزر 2) ---
def process_bin_extraction(message):
    chat_id = message.chat.id
    bin_text = message.text
    file_content = user_states[chat_id].get('file_content', '')

    bins = re.findall(r'\d{6,11}', bin_text)
    if not bins:
        bot.reply_to(message, "❌ الرجاء إرسال أرقام BIN صالحة (من 6 إلى 11 رقم).")
        return

    full_lines = [line for line in file_content.splitlines() if any(line.startswith(b) for b in bins)]

    if not full_lines:
        bot.reply_to(message, "❌ لم يتم العثور على أي بطاقات تبدأ بالـ BINs المذكورة.")
        return

    output = "\n".join(full_lines)
    send_result(message, output, "extracted_bins.txt")
    user_states.pop(chat_id, None)

# --- تنفيذ عملية التنظيف (الزر 3) ---
def process_clearing(message, content):
    cleaned_lines = []
    for line in content.splitlines():
        # البحث عن أرقام البطاقة الأساسية وفواصلها وتجاهل الكلام الزائد
        match = re.search(r'\d{12,19}[\s|/;:|-]\d{1,4}[\s|/;:|-]\d{1,4}[\s|/;:|-]\d{3,4}|\d{6,}', line)
        if match:
            cleaned_lines.append(match.group(0))

    if not cleaned_lines:
        bot.reply_to(message, "❌ لم يتم العثور على بيانات صالحة للتنظيف.")
        return

    output = "\n".join(cleaned_lines)
    send_result(message, output, "cleaned_cards.txt")
    user_states.pop(message.chat.id, None)

# --- أداة إرسال النتائج للأزرار 2 و 3 ---
def send_result(message, output_text, filename):
    chat_id = message.chat.id
    if len(output_text) < 4000:
        bot.reply_to(message, f"✅ **النتيجة:**\n\n```\n{output_text}\n```", parse_mode="Markdown")
    else:
        bio = io.BytesIO(output_text.encode('utf-8'))
        bio.name = filename
        bot.send_document(chat_id, bio, caption="✅ تم معالجة وتجهيز ملفك بنجاح وبأقصى سرعة!")

# تشغيل البوت
bot.infinity_polling()
