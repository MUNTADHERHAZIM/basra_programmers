# 🚀 منصة تدريب المبرمجين — Basra Programmers Initiative

نظام إدارة تدريب برمجي متكامل مبني بـ **Django** يدعم تعدد المحافظات والأدوار مع إشعارات Telegram وتطبيق PWA ومنصة دردشة مباشرة.

---

## 📋 جدول المحتويات

- [البنية العامة](#البنية-العامة)
- [الأدوار والصلاحيات](#الأدوار-والصلاحيات)
- [نظام المحافظات](#نظام-المحافظات)
- [الميزات الرئيسية](#الميزات-الرئيسية)
- [منصة التواصل والدردشة](#منصة-التواصل-والدردشة)
- [إشعارات Telegram](#إشعارات-telegram)
- [PWA - تطبيق الهاتف](#pwa---تطبيق-الهاتف)
- [التقارير والإحصاءات](#التقارير-والإحصاءات)
- [تصدير واستيراد البيانات](#تصدير-واستيراد-البيانات)
- [بنية المشروع](#بنية-المشروع)
- [التثبيت المحلي](#التثبيت-المحلي)
- [الرفع على PythonAnywhere](#الرفع-على-pythonanywhere)
- [المتغيرات البيئية](#المتغيرات-البيئية)

---

## البنية العامة

```
مبادرة تدريب المبرمجين
├── نظام متعدد المحافظات (Multi-Governorate Tenancy)
├── صلاحيات متدرجة (Role-Based Access Control)
├── إشعارات فورية عبر Telegram
├── منصة دردشة داخلية بالاستطلاع التلقائي (Polling)
├── تطبيق Progressive Web App (PWA)
└── لوحة تحكم إدارية متكاملة
```

---

## الأدوار والصلاحيات

| الدور | الرمز | الصلاحيات |
|-------|-------|-----------|
| مسؤول النظام | `super_admin` | صلاحيات كاملة على جميع المحافظات |
| مسؤول المحافظة | `governorate_admin` | يدير محافظته فقط |
| مدير المبادرة | `director` | صلاحيات إدارية واسعة |
| مسؤول التدريب | `training_officer` | يدير جداول التدريب والحضور |
| مشرف | `supervisor` | يشرف على مجموعات محددة |
| محاضر | `lecturer` | يدير محاضراته ويتواصل مع شعبه |
| متدرب | `trainee` | يشاهد محاضراته ويشارك في الدردشة |
| زائر | `visitor` | وصول محدود للقراءة فقط |

---

## نظام المحافظات

### مبدأ العزل الصارم
كل بيانات النظام مرتبطة بمحافظة:
- **المستخدمون** → `CustomUser.governorate`
- **المجموعات** → `Group.governorate`
- **المحاضرون** والمتدربون يرتبطون بمحافظتهم تلقائياً عبر المجموعات

### آلية التصفية
```python
# المستخدم يرى فقط بيانات محافظته
if not is_national:
    queryset = queryset.filter(group__governorate=user.governorate)
```

### Super Admin
- لا يملك محافظة (`governorate = NULL`)
- يرى جميع المحافظات بدون فلتر
- في منصة التواصل: يمكنه اختيار أي محافظة من قائمة منسدلة

---

## الميزات الرئيسية

### 1. إدارة الحسابات
- إنشاء حسابات جديدة مع تعيين الدور والمحافظة
- تعيين كلمات مرور مؤقتة وإشعار المستخدم
- تصفية الحسابات حسب المحافظة والدور
- عرض عمود المحافظة في جميع الجداول الإدارية

### 2. إدارة المواد والمجموعات
- **المواد الدراسية** (Course): عنوان، وصف، مدة
- **المجموعات** (Group): ترتبط بمادة ومحافظة، لها محاضر ومشرف
- الشعب محدودة بمحافظتها — لا تضارب بين المحافظات

### 3. إدارة المحاضرات
- إنشاء محاضرات مرتبطة بمجموعة محددة
- رفع ملفات PDF، فيديو، أو روابط خارجية
- معاينة المحاضرات للمتدربين مباشرةً من داخل المنصة
- تعديل وحذف المحاضرات بأزرار مخصصة

### 4. التقارير اليومية
- المتدربون يرفعون تقارير يومية (نص + ملفات)
- المشرفون والمحاضرون يراجعون ويقيّمون
- Super Admin يرى تقارير جميع المحافظات مع بادج المحافظة
- مسؤول المحافظة يرى تقارير محافظته فقط

### 5. مركز الإدارة
- جداول شاملة: الحسابات، المجموعات، المتدربين، المحاضرين
- كل جدول يعرض عمود المحافظة للتمييز
- فلاتر سريعة حسب المحافظة والدور

---

## منصة التواصل والدردشة

### هيكل القنوات
```
القنوات المتاحة لكل مستخدم:
├── القناة العامة للمحافظة  (general_{gov_id})
├── قنوات المواد الدراسية   (course_{course_id})
├── قنوات الشعب الدراسية    (group_{group_id})
└── رسائل مباشرة             (direct → user_id)
```

### Super Admin في منصة التواصل
- يرى القناة الوطنية العامة إذا لم يختر محافظة
- يختار محافظة من القائمة العلوية لرؤية قنواتها فقط
- مرسِل الرسالة يظهر معه badge المحافظة

### آلية عمل الإرسال والاستقبال
1. المستخدم يكتب رسالة ويضغط إرسال
2. `FormData` يُرسَل إلى `POST /chat/send/` مع `target_type` و `target_id`
3. الخادم يحفظ `InternalMessage` بالنموذج المناسب
4. Polling كل 5 ثوانٍ يجلب الرسائل الجديدة تلقائياً
5. زر الإرسال يتعطل أثناء الإرسال لمنع الإرسال المزدوج

### نموذج بيانات الرسائل
```python
class InternalMessage(models.Model):
    sender    = ForeignKey(User)           # المرسل
    recipient = ForeignKey(User, null=True) # للرسائل المباشرة
    group     = ForeignKey(Group, null=True) # لقنوات الشعب
    course    = ForeignKey(Course, null=True) # لقنوات المواد
    content   = TextField(blank=True)
    image     = ImageField(...)
    file      = FileField(...)
    is_read   = BooleanField(default=False)
```

---

## إشعارات Telegram

### الإعداد
1. أنشئ بوت Telegram عبر `@BotFather` واحصل على `BOT_TOKEN`
2. أضف `TELEGRAM_BOT_TOKEN` إلى المتغيرات البيئية
3. كل مستخدم يربط حسابه عبر رمز الربط في الملف الشخصي

### الإشعارات التلقائية
- إضافة محاضرة جديدة
- مراجعة التقرير اليومي وإعطاء التغذية الراجعة
- رسائل النظام الإدارية المهمة

---

## PWA - تطبيق الهاتف

### الميزات
- قابل للتثبيت على الهاتف كتطبيق مستقل
- يعمل بدون متصفح بعد التثبيت
- أيقونة على الشاشة الرئيسية للهاتف

### آلية التثبيت
1. عند أول زيارة تظهر نافذة ترحيبية مع زر التثبيت
2. بعد الإغلاق لا تظهر النافذة مرة ثانية في نفس الجلسة (`sessionStorage`)
3. المستخدم يستطيع التثبيت يدوياً من قائمة المتصفح

---

## التقارير والإحصاءات

### لوحة تحكم Super Admin
- إجمالي المتدربين، المحاضرين، المجموعات لكل محافظة
- المجموعات النشطة مع عمود المحافظة
- سجل التقارير اليومية بكامل المحافظات

### لوحة تحكم مسؤول المحافظة
- إحصاءات محافظته فقط
- عدد المتدربين النشطين ومعدل الحضور

---

## تصدير واستيراد البيانات

### التصدير (Export to Excel)
```
الرابط:  /manage/export/trainees/
الرابط:  /manage/export/groups/
الصيغة: .xlsx
```

### الاستيراد (Import from Excel)
```
الرابط:  /manage/import/trainees/
الصيغة: .xlsx
```
> **ملاحظة**: الاستيراد يتحقق من صحة البيانات ويرفض الصفوف المكررة أو الناقصة

---

## بنية المشروع

```
1000_programmers/
├── apps/
│   ├── users/           # نماذج المستخدمين والأدوار
│   │   ├── models.py    # CustomUser, TraineeProfile, LecturerProfile
│   │   └── services.py  # منطق إنشاء الحسابات
│   ├── courses/         # المواد والمجموعات والمحاضرات
│   │   └── models.py    # Course, Group, Lecture, Attendance
│   ├── portal/          # الواجهة الرئيسية والمنطق
│   │   ├── views.py     # جميع العروض والـ APIs
│   │   └── urls.py      # جداول الروابط
│   ├── notifications/   # نظام الإشعارات والرسائل
│   │   └── models.py    # Notification, InternalMessage
│   ├── locations/       # المحافظات
│   │   └── models.py    # Governorate
│   └── telegram_bot/    # بوت Telegram
├── templates/
│   ├── base.html        # القالب الأساسي + PWA hooks
│   └── portal/          # جميع صفحات المنصة
├── static/              # CSS, JS, الصور
├── media/               # الملفات المرفوعة من المستخدمين
├── manage.py
└── config/
    ├── settings.py
    └── urls.py
```

---

## التثبيت المحلي

```bash
# 1. استنساخ المشروع
git clone <repo-url>
cd 1000_programmers

# 2. إنشاء بيئة افتراضية
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. تثبيت المتطلبات
pip install -r requirements.txt

# 4. إعداد قاعدة البيانات
python manage.py migrate

# 5. إنشاء مسؤول النظام
python manage.py createsuperuser

# 6. تشغيل الخادم
python manage.py runserver
```

---

## الرفع على PythonAnywhere

### عند كل تحديث

```bash
# على جهازك المحلي:
git add .
git commit -m "وصف التغييرات"
git push origin main

# على PythonAnywhere (Bash Console):
cd ~/1000_programmers
git pull origin main
python manage.py migrate          # إذا كانت هناك هجرات جديدة
python manage.py collectstatic --noinput

# ثم اضغط "Reload" في تبويب Web
```

### إعداد أول مرة على PythonAnywhere

1. أنشئ **Web App** → Manual Configuration → Python 3.10
2. في ملف **WSGI** أضف:
   ```python
   import os, sys
   sys.path.insert(0, '/home/USERNAME/1000_programmers')
   os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
3. **Static Files**: URL `/static/` → `/home/USERNAME/1000_programmers/staticfiles/`
4. **Media Files**: URL `/media/` → `/home/USERNAME/1000_programmers/media/`

---

## المتغيرات البيئية

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.pythonanywhere.com

# Telegram (اختياري)
TELEGRAM_BOT_TOKEN=your-bot-token-here
```

---

## روابط المنصة

| الصفحة | الرابط |
|--------|--------|
| لوحة التحكم | `/dashboard/` |
| إدارة الحسابات | `/accounts/` |
| المجموعات والشعب | `/groups/` |
| منصة التواصل والدردشة | `/chat/` |
| التقارير اليومية | `/reports/daily/list/` |
| مركز الإدارة الشامل | `/admin/hub/` |
| إدارة المحاضرات | `/lectures/` |
| وسائط المبادرة | `/media/` |

---

## التقنيات المستخدمة

| التقنية | الغرض |
|---------|-------|
| Django 4.x | إطار العمل الرئيسي |
| SQLite / MySQL | قاعدة البيانات |
| Bootstrap 5 | واجهة المستخدم |
| Font Awesome 6 | الأيقونات |
| python-telegram-bot | إشعارات Telegram |
| openpyxl | تصدير/استيراد Excel |
| Pillow | معالجة الصور |
| PWA (manifest + SW) | تطبيق الهاتف |

---

*آخر تحديث: سبتمبر 2026 — منصة تدريب المبرمجين*

