import telebot
from telebot import types
import re
import io

# ضع توكن البوت الخاص بك هنا
API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
bot = telebot.TeleBot(API_TOKEN)

# حالات المستخدمين لتتبع الخطوات
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
        bot.send_message(chat_id, "📥 أرسل بطاقاتك بأي صيغة في رسالة واحدة أو ملف (حتى 300 ميجابايت).")

    elif text == "2- استخراج عبر الـ BIN":
        user_states[chat_id] = {'step': 'bin_wait_file'}
        bot.send_message(chat_id, "📥 أرسل بطاقاتك بأي صيغة في رسالة واحدة أو ملف (حتى 300 ميجابايت).")

    elif text == "3- تنظيف الملف (Clear)":
        user_states[chat_id] = {'step': 'clear_wait_file'}
        bot.send_message(chat_id, "📥 أرسل بطاقاتك بأي صيغة في رسالة واحدة أو ملف (حتى 300 ميجابايت).")
        
    else:
        # إذا كان المستخدم في خطوة انتظار الـ BINs (نصوص وليس ملفات)
        if chat_id in user_states and user_states[chat_id].get('step') == 'bin_wait_bins':
            process_bin_extraction(message)

# --- معالجة الملفات والرسائل الكبيرة بسرعة فائقة ---

@bot.message_handler(content_types=['document', 'text'])
def handle_docs_and_text(message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        return

    step = user_states[chat_id].get('step')
    
    # 1. الحصول على النص سواء كان رسالة نصية أو ملف
    content = ""
    if message.content_type == 'text':
        content = message.text
    elif message.content_type == 'document':
        # التحقق من حجم الملف (أقل من 300 ميجا)
        if message.document.file_size > 300 * 1024 * 1024:
            bot.reply_to(message, "❌ حجم الملف كبير جداً! الحد الأقصى هو 300 ميجابايت.")
            return
        
        status_msg = bot.reply_to(message, "⚡ جاري القراءة والمعالجة بسرعة فائقة...")
        
        # تحميل الملف مباشرة إلى الذاكرة دون حفظه على القرص لسرعة خيالية
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8', errors='ignore')
        bot.delete_message(chat_id, status_msg.message_id)

    # 2. توجيه المحتوى حسب الزر المضغوط سابقاً
    if step == 'split_wait_file':
        process_splitting(message, content)
        
    elif step == 'bin_wait_file':
        # حفظ محتوى الملف مؤقتاً في ذاكرة السيرفر للانتقال للخطوة التالية
        user_states[chat_id]['file_content'] = content
        user_states[chat_id]['step'] = 'bin_wait_bins'
        bot.reply_to(message, "✅ تم قراءة الملف بنجاح.\n\n📥 الآن، أرسل قائمة الـ BINs (من 6 إلى 11 رقم) المراد استخراجها، مفصولة بأي فاصل.\n\nمثال: 442755, 4852464, 434769")

    elif step == 'clear_wait_file':
        process_clearing(message, content)

# --- الوظائف التنفيذية (Engine) ---

def process_splitting(message, content):
    """الزر 1: استخراج الأسطر التي تبدأ بأرقام وتصفيتها كبطاقات تحت بعضها"""
    # Regex لجلب الأسطر التي تبدأ بـ 6 أرقام على الأقل وتستمر كصيغة بطاقة
    pattern = re.compile(r'^\d{6,}.*$', re.MULTILINE)
    matches = pattern.findall(content)
    
    if not matches:
        bot.reply_to(message, "❌ لم يتم العثور على أي بطاقات مطابقة للصيغة.")
        return

    output = "\n".join(matches)
    send_result(message, output, "cards_split.txt")

def process_bin_extraction(message):
    """الزر 2: استخراج البطاقات بناءً على الـ BINs المرسلة"""
    chat_id = message.chat.id
    bin_text = message.text
    file_content = user_states[chat_id].get('file_content', '')

    # استخراج الـ BINs من رسالة المستخدم (أي أرقام طولها بين 6 و 11)
    bins = re.findall(r'\d{6,11}', bin_text)
    
    if not bins:
        bot.reply_to(message, "❌ الرجاء إرسال أرقام BIN صالحة (من 6 إلى 11 رقم).")
        return

    # إنشاء تعبير نمطي فائق السرعة للبحث عن الأسطر التي تبدأ بهذه الـ BINs
    bin_pattern = "|".join(bins)
    pattern = re.compile(rf'^({bin_pattern}).*$', re.MULTILINE)
    matches = pattern.findall(file_content)

    # إعادة تجميع الأسطر كاملة التي تطابقت مع الـ BINs المحفوظة
    # بما أن findall مع المجموعات ترجع الـ group فقط، سنستخدم split أو finditer للسطر الكامل لضمان السرعة والدقة:
    full_lines = [line for line in file_content.splitlines() if any(line.startswith(b) for b in bins)]

    if not full_lines:
        bot.reply_to(message, "❌ لم يتم العثور على أي بطاقات تبدأ بالـ BINs المذكورة.")
        return

    output = "\n".join(full_lines)
    send_result(message, output, "extracted_bins.txt")
    # تنظيف الحالة
    user_states.pop(chat_id, None)

def process_clearing(message, content):
    """الزر 3: تنظيف الأسطر وحذف الكلام الزائد لتبدو كبطاقات صافية"""
    # تنظيف الأسطر بحيث نأخذ فقط الأرقام والرموز الخاصة بالبطاقة مثل (| أو / أو :) ونحذف الحروف العشوائية
    # هذا النمط يستخرج السلسلة التي تبدأ بأرقام وتحتوي على فواصل البطاقات المعروفة ويترك الحروف الزائدة.
    cleaned_lines = []
    for line in content.splitlines():
        # البحث عن أرقام البطاقة الأساسية وما يتصل بها من فواصل وأرقام أخرى
        match = re.search(r'\d{12,19}[\s|/;:|-]\d{1,4}[\s|/;:|-]\d{1,4}[\s|/;:|-]\d{3,4}|\d{6,}', line)
        if match:
            cleaned_lines.append(match.group(0))

    if not cleaned_lines:
        bot.reply_to(message, "❌ لم يتم العثور على بيانات صالحة للتنظيف.")
        return

    output = "\n".join(cleaned_lines)
    send_result(message, output, "cleaned_cards.txt")

# --- أداة إرسال النتائج الذكية ---
def send_result(message, output_text, filename):
    """ترسل النتيجة كنص إذا كانت قصيرة، أو كملف txt سريع إذا كانت ضخمة جداً"""
    chat_id = message.chat.id
    
    if len(output_text) < 4000:
        bot.reply_to(message, f"✅ **النتيجة:**\n\n```\n{output_text}\n```", parse_mode="Markdown")
    else:
        # تحويل النص إلى ملف في الذاكرة دون استهلاك الهارد ديسك وإرساله فوراً
        bio = io.BytesIO(output_text.encode('utf-8'))
        bio.name = filename
        bot.send_document(chat_id, bio, caption="✅ تم معالجة وتجهيز ملفك بنجاح وبأقصى سرعة!")

# تشغيل البوت المستمر
bot.infinity_polling()
