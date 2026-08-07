import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from django.conf import settings

from django.utils.crypto import get_random_string

logger = logging.getLogger(__name__)

def get_clean_bot_token():
    """Retrieves and normalizes TELEGRAM_BOT_TOKEN from settings or env."""
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or ''
    token = token.strip()
    if not token or 'Placeholder' in token:
        return None
    if ':' in token:
        parts = token.split(':', 1)
        # If user pasted token backwards (hash:id instead of id:hash e.g. AAGj...:8860808416)
        if not parts[0].isdigit() and parts[1].isdigit():
            token = f"{parts[1]}:{parts[0]}"
    return token


def send_telegram_message(chat_id, text, inline_keyboard=None, parse_mode="HTML"):
    """
    Sends a message via Telegram Bot API to the given chat_id.
    """
    if not chat_id:
        return False, "يرجى إدخال معرف الشات (Chat ID) الخاص بك أولاً."

    token = get_clean_bot_token()
    if not token:
        logger.warning(f"Telegram message skipped: Token missing in .env (chat_id: {chat_id})")
        return False, "تنبيه: توكن البوت (TELEGRAM_BOT_TOKEN) غير مضاف في ملف .env بالنظام حتى الآن. يرجى تزويدنا بتوكن البوت الخاص بك من @BotFather لإضافته والتفعيل الفوري!"

    # Clean up chat_id if user pasted bot username or bot numeric ID instead of user chat_id
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'Programmers1000_Bot')
    bot_id = token.split(':')[0] if ':' in token else ''
    
    if chat_id.replace('@', '').lower() == bot_username.replace('@', '').lower():
        return False, f"تنبيه: لقد أدخلت اسم البوت نفسه ({chat_id}) بدلاً من رقم حسابك الشخصي! اضغط على زر 'فتح البوت وتفعيل الربط تلقائياً' ثم ضغط START داخل البوت ليتم ربط حسابك تلقائياً."

    if str(chat_id).strip() == str(bot_id).strip():
        return False, f"تنبيه: الرقم الذي أدخلته ({chat_id}) هو رقم البوت نفسه وليس رقم حسابك الشخصي! يرجى التحدث لبوت @userinfobot في تليغرام لمعرفة رقم حسابك الشخصي الرقمي، أو الضغط على زر 'فتح البوت وتفعيل الربط تلقائياً'."

    url = f"https://api.telegram.org/bot{token}/sendMessage"



    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    if inline_keyboard:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}

    try:
        import requests
        response = requests.post(url, json=payload, timeout=5)
        res_data = response.json()
        if response.status_code == 200 and res_data.get('ok'):
            return True, "تم إرسال الإشعار عبر التليغرام بنجاح."
        else:
            desc = res_data.get('description', f'HTTP {response.status_code}')
            if 'chat not found' in desc.lower() or 'bad request' in desc.lower():
                return False, f"تنبيه التليغرام ({desc}): يجب أولاً الضغط على 'فتح البوت وتفعيل الربط تلقائياً' والضغط على START داخل تليغرام، أو استخدام رقم Chat ID الرقمي من بوت @userinfobot."
            return False, f"فشل التليغرام: {desc}"
    except requests.exceptions.Timeout:
        logger.error("Telegram API Connection Timeout")
        return False, "فشل الاتصال بسيرفرات التليغرام (Timeout): يبدو أن مزود الإنترنت (ISP) على جهازك يحظر أو يمنع الاتصال المباشر بـ api.telegram.org. يرجى التوصيل بشبكة ثانية أو تفعيل VPN على الجهاز."
    except requests.exceptions.ConnectionError as ce:
        logger.error(f"Telegram Connection Error: {ce}")
        return False, "تعذر الوصول إلى سيرفر التليغرام. تأكد من توفر الاتصال بالإنترنت على الجهاز (قد تكون سيرفرات التليغرام محظورة على شبكتك الحالية)."
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False, f"خطأ في الاتصال بالتليغرام: {str(e)}"




def generate_telegram_link_code(user):
    """Generates and saves a unique linking code for the user."""
    code = f"LINK-{get_random_string(8).upper()}"
    user.telegram_link_code = code
    user.save(update_fields=['telegram_link_code'])
    return code


def notify_user_telegram(user, title, body, action_url=None, icon="🔔"):
    """
    High-level notifier that sends a formatted notification to a single user if Telegram is linked.
    """
    if not user or not user.telegram_chat_id or not user.telegram_notifications_enabled:
        return False, "إشعارات التليغرام غير مفعّلة أو الحساب غير مربوط."

    text = (
        f"<b>{icon} {title}</b>\n\n"
        f"{body}\n\n"
        f"<i>منصة 1000 برنامج - نظام الإشعارات الذكي</i>"
    )

    inline_keyboard = None
    if action_url:
        inline_keyboard = [
            [{"text": "🔗 فتح الرابط في المنصة", "url": action_url}]
        ]

    return send_telegram_message(user.telegram_chat_id, text, inline_keyboard=inline_keyboard)


def notify_lecturer_lecture_reminder(lecture):
    """Notifies the assigned instructor about today's upcoming lecture."""
    instructor = lecture.group.instructor if lecture.group else None
    if not instructor or not instructor.telegram_chat_id:
        return False, "لا يوجد مدرب مسند أو حساب التليغرام غير مربوط."

    title = f"تذكير بمحاضرة اليوم: {lecture.title}"
    body = (
        f"📚 <b>المادة/الشعبة:</b> {lecture.group.name} ({lecture.group.course.title})\n"
        f"📅 <b>التاريخ:</b> {lecture.date}\n"
        f"⏰ <b>الوقت:</b> {lecture.start_time.strftime('%H:%M')} - {lecture.end_time.strftime('%H:%M')}\n"
        f"🏫 <b>القاعة:</b> {lecture.group.classroom}\n\n"
        f"⚡ يرجى تسجيل حضور المتدربين عبر المنصة عند بدء المحاضرة."
    )
    
    return send_telegram_message(
        chat_id=instructor.telegram_chat_id,
        text=f"<b>👨‍🏫 إشعار الكادر التدريبي</b>\n\n<b>{title}</b>\n\n{body}",
        inline_keyboard=[[{"text": "📋 تسجيل الحضور الآن", "url": "https://1000programmers.net/portal/dashboard/"}]]
    )


def notify_lecturer_assignment_submission(submission):
    """Notifies instructor when a trainee submits an assignment."""
    group = submission.assignment.group
    instructor = group.instructor if group else None
    if not instructor or not instructor.telegram_chat_id:
        return False, "المدرب غير موجود أو التليغرام غير مربوط."

    trainee_name = submission.trainee.get_full_name() or submission.trainee.username
    title = f"تسليم واجب جديد من {trainee_name}"
    body = (
        f"📝 <b>الواجب:</b> {submission.assignment.title}\n"
        f"👥 <b>الشعبة:</b> {group.name}\n"
        f"👤 <b>الطالب:</b> {trainee_name}\n"
        f"⏱️ <b>تاريخ التسليم:</b> {submission.submitted_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"يمكنك مراجعة وتصحيح التسليم عبر لوحة تحكم المدرب."
    )

    return send_telegram_message(
        chat_id=instructor.telegram_chat_id,
        text=f"<b>📥 تسليم جديد</b>\n\n<b>{title}</b>\n\n{body}"
    )


def sync_telegram_updates():
    """
    Polls getUpdates from Telegram Bot API to automatically pair users who clicked /start LINK-XXXX.
    """
    token = get_clean_bot_token()
    if not token:
        return False, "توكن البوت غير مضاف."

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        import requests
        response = requests.get(url, timeout=5)
        data = response.json()
        if not data.get('ok'):
            return False, data.get('description', 'خطأ في الاتصال بالسيرفر')
        
        updates = data.get('result', [])
        matched_count = 0
        
        from apps.users.models import CustomUser
        for upd in updates:
            msg = upd.get('message', {})
            text = msg.get('text', '')
            chat_info = msg.get('chat', {})
            chat_id = str(chat_info.get('id', ''))
            
            if chat_id and ('/start' in text or 'LINK-' in text):
                parts = text.split()
                for part in parts:
                    if part.startswith('LINK-'):
                        user = CustomUser.objects.filter(telegram_link_code=part).first()
                        if user:
                            user.telegram_chat_id = chat_id
                            user.save(update_fields=['telegram_chat_id'])
                            matched_count += 1
                            # Send welcome notification
                            send_telegram_message(
                                chat_id,
                                f"<b>🎉 تم ربط حسابك في منصة 1000 برمجة بنجاح!</b>\n\nأهلاً بك {user.get_full_name() or user.username}، ستصلك جميع الإشعارات والتبليغات الإدارية والتنبيهات فوراً عبر هذا الحساب."
                            )
        return True, f"تمت المزامنة بنجاح. تم ربط {matched_count} حساب/حسابات جديدة."
    except requests.exceptions.ConnectTimeout:
        return False, "تنبيه شبكة: تعذر الوصول إلى سيرفرات التليغرام من السيرفر المحلي (Timeout). شبكة الإنترنت الحالية في جهازك تفرض قيوداً على api.telegram.org. عند رفع المنصة على السيرفر والاستضافة (VPS Server)، ستعمل المزامنة الفورية وتصل الرسائل فوراً للجميع!"
    except requests.exceptions.RequestException as re:
        return False, "تنبيه شبكة: تعذر الاتصال بسيرفر التليغرام من جهاز السيرفر المحلي حالياً. (البرمجيات مضبوطة بالكامل وستعمل فور رفع الموقع على الاستضافة الرسمية)."
    except Exception as e:
        logger.error(f"Error syncing Telegram updates: {e}")
        return False, f"تعذر استكمال المزامنة: {str(e)}"


