import openpyxl
from io import BytesIO
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import TraineeProfile
from apps.courses.models import Group

User = get_user_model()

class ImportExportService:
    @staticmethod
    def generate_safe_username(first_name=None, last_name=None, email_val=None, prefix='user'):
        import re
        import random
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        base = None
        # 1. Try from email
        if email_val and '@' in str(email_val):
            local_part = str(email_val).split('@')[0]
            clean = re.sub(r'[^a-zA-Z0-9_.-]', '', local_part)
            if clean and len(clean) >= 3:
                base = clean

        # 2. Try from name
        if not base:
            name_parts = []
            if first_name:
                name_parts.append(str(first_name).strip())
            if last_name:
                name_parts.append(str(last_name).strip())
            
            if name_parts:
                full_name = " ".join(name_parts)
                trans_map = {
                    'أ': 'a', 'إ': 'i', 'آ': 'a', 'ا': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th',
                    'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z',
                    'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a',
                    'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
                    'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'h', 'ئ': 'y', 'ؤ': 'w',
                    'ء': ''
                }
                translit = "".join(trans_map.get(c, c) for c in full_name.lower())
                clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', translit)
                clean = re.sub(r'_+', '_', clean).strip('_')
                if clean:
                    base = clean
                
        if not base:
            base = prefix

        # Ensure uniqueness
        username = base
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}_{random.randint(10, 999)}"
        
        return username

    @staticmethod
    def import_from_excel(file_io, group_id=None):
        from django.db.models import Q
        import re
        wb = openpyxl.load_workbook(file_io)
        sheet = wb.active
        
        imported_count = 0
        errors = []
        
        group = None
        if group_id:
            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return 0, ["المجموعة التدريبية المحددة غير موجودة."]

        # Read headers from Row 1 dynamically
        headers = [str(sheet.cell(row=1, column=c).value or '').strip() for c in range(1, sheet.max_column + 1)]
        
        # Default column indices (1-based)
        col_username = None
        col_email = None
        col_first_name = None
        col_last_name = None
        col_gov = None
        col_dist = None
        col_uni = None
        col_col = None
        col_dept = None
        col_stage = None
        col_spec = None
        col_full_name = None
        col_group = None
        col_gender = None
        
        for idx, h in enumerate(headers, 1):
            h_clean = h.strip().lower()
            if not h_clean:
                continue
            if "الرقم" in h_clean or "training" in h_clean:
                col_username = idx
            elif "البريد" in h_clean or "الايميل" in h_clean or "email" in h_clean:
                col_email = idx
            elif "الأول" in h_clean or "first" in h_clean:
                col_first_name = idx
            elif "العائلة" in h_clean or "الأخير" in h_clean or "last" in h_clean or "اللقب" in h_clean:
                col_last_name = idx
            elif "المستخدم" in h_clean:
                col_full_name = idx
            elif "الكامل" in h_clean or "الاسم" in h_clean or "name" in h_clean:
                col_full_name = idx
            elif "المحافظة" in h_clean or "gov" in h_clean:
                col_gov = idx
            elif "القضاء" in h_clean or "dist" in h_clean:
                col_dist = idx
            elif "الجامعة" in h_clean or "uni" in h_clean:
                col_uni = idx
            elif "الكلية" in h_clean or "col" in h_clean:
                col_col = idx
            elif "الشعبة" in h_clean or "المجموعة" in h_clean or "group" in h_clean or "section" in h_clean:
                col_group = idx
            elif "القسم" in h_clean or "dept" in h_clean:
                col_dept = idx
            elif "المستخدم" in h_clean:
                col_full_name = idx
            elif "الكامل" in h_clean or "الاسم" in h_clean or "name" in h_clean:
                col_full_name = idx
            elif "المحافظة" in h_clean or "gov" in h_clean:
                col_gov = idx
            elif "القضاء" in h_clean or "dist" in h_clean:
                col_dist = idx
            elif "الجامعة" in h_clean or "uni" in h_clean:
                col_uni = idx
            elif "الكلية" in h_clean or "col" in h_clean:
                col_col = idx
            elif "المرحلة" in h_clean or "stage" in h_clean:
                col_stage = idx
            elif "الاختصاص" in h_clean or "التخصص" in h_clean or "spec" in h_clean:
                col_spec = idx
            elif "الجنس" in h_clean or "gender" in h_clean:
                col_gender = idx

        # Helper to match group names robustly
        def resolve_group_match(raw_val):
            if not raw_val:
                return None
            val_s = str(raw_val).strip()
            if not val_s:
                return None
            
            # 1. Exact match by name or code
            db_g = Group.objects.filter(Q(name__iexact=val_s) | Q(code__iexact=val_s)).first()
            if db_g:
                return db_g
                
            # 2. Normalized match
            norm = val_s.upper()
            for g in Group.objects.all():
                if g.name.upper() == norm or g.code.upper() == norm:
                    return g
                    
            # 3. Strip noise words to isolate section identifier (A, B, أ, ب, 1, 2)
            clean = norm
            for noise in ['الشعبة', 'شعبة', 'المجموعة', 'مجموعة', 'SECTION', 'GROUP', 'GRP', 'فرع', 'قسم']:
                clean = clean.replace(noise, '')
            clean = clean.strip(' :-_')
            
            # 4. Check for Section B
            if any(k in clean for k in ['B', 'ب', '2', 'ثانية', 'SECOND']) or 'GRP-B' in norm:
                db_g = Group.objects.filter(Q(name__icontains='B') | Q(code__icontains='B') | Q(name__icontains='الثانية') | Q(code__iexact='GRP-B')).first()
                if db_g:
                    return db_g
                    
            # 5. Check for Section A
            if any(k in clean for k in ['A', 'أ', '1', 'أولى', 'FIRST']) or 'GRP-A' in norm:
                db_g = Group.objects.filter(Q(name__icontains='A') | Q(code__icontains='A') | Q(name__icontains='الأولى') | Q(code__iexact='GRP-A')).first()
                if db_g:
                    return db_g
                    
            return Group.objects.filter(name__icontains=val_s).first()

        for row_idx in range(2, sheet.max_row + 1):
            # Extract values based on mapped columns
            username_val = sheet.cell(row=row_idx, column=col_username).value if col_username else None
            email_val = sheet.cell(row=row_idx, column=col_email).value if col_email else None
            
            first_name = None
            last_name = None
            
            if col_full_name:
                full_name_val = str(sheet.cell(row=row_idx, column=col_full_name).value or '').strip()
                if full_name_val:
                    parts = full_name_val.split()
                    if parts:
                        first_name = parts[0]
                        if len(parts) > 1:
                            last_name = " ".join(parts[1:])
            
            if not first_name and col_first_name:
                first_name = sheet.cell(row=row_idx, column=col_first_name).value
            if not last_name and col_last_name:
                last_name = sheet.cell(row=row_idx, column=col_last_name).value

            gov = sheet.cell(row=row_idx, column=col_gov).value if col_gov else None
            dist = sheet.cell(row=row_idx, column=col_dist).value if col_dist else None
            uni = sheet.cell(row=row_idx, column=col_uni).value if col_uni else None
            col = sheet.cell(row=row_idx, column=col_col).value if col_col else None
            dept = sheet.cell(row=row_idx, column=col_dept).value if col_dept else None
            stage = sheet.cell(row=row_idx, column=col_stage).value if col_stage else None
            spec = sheet.cell(row=row_idx, column=col_spec).value if col_spec else None
            group_val = sheet.cell(row=row_idx, column=col_group).value if col_group else None
            gender_val = sheet.cell(row=row_idx, column=col_gender).value if col_gender else None

            if not any([username_val, email_val, first_name, last_name, gov, dist, uni, col, dept, stage, spec, group_val, gender_val]):
                continue

            # Smart username handling
            if username_val:
                username = re.sub(r'[^a-zA-Z0-9_.-]', '_', str(username_val).strip())
            else:
                username = ImportExportService.generate_safe_username(first_name, last_name, email_val, prefix='trainee')
            
            # Smart email/group handling
            email = None
            resolved_group = group
            
            if email_val:
                email_str = str(email_val).strip()
                if '@' in email_str:
                    email = email_str
                else:
                    if not group_val:
                        group_val = email_str
            
            if group_val:
                matched_g = resolve_group_match(group_val)
                if matched_g:
                    resolved_group = matched_g
            elif not resolved_group and dept:
                matched_g = resolve_group_match(dept)
                if matched_g:
                    resolved_group = matched_g

            try:
                with transaction.atomic():
                    # Determine gender
                    gender = 'male'
                    if gender_val:
                        gender_str = str(gender_val).strip().lower()
                        if any(x in gender_str for x in ['أنثى', 'انثى', 'female', 'f']):
                            gender = 'female'
                        elif any(x in gender_str for x in ['ذكر', 'male', 'm']):
                            gender = 'male'

                    user = User.objects.filter(Q(username=username) | Q(email=email) if email else Q(username=username)).first()
                    if not user:
                        user = User.objects.create_user(
                            username=username,
                            email=email if email else f"{username}@1000programmers.org",
                            first_name=str(first_name).strip() if first_name else '',
                            last_name=str(last_name).strip() if last_name else '',
                            role=User.Role.TRAINEE,
                            password="Password123",
                            gender=gender
                        )
                    else:
                        if first_name: user.first_name = str(first_name).strip()
                        if last_name: user.last_name = str(last_name).strip()
                        if email: user.email = email
                        if gender_val: user.gender = gender
                        user.save()

                    profile, p_created = TraineeProfile.objects.get_or_create(user=user)
                    
                    if username_val:
                        profile.custom_training_number = str(username_val).strip()
                    
                    if gov: profile.governorate = str(gov).strip()
                    elif p_created: profile.governorate = 'البصرة'
                    
                    if dist: profile.district = str(dist).strip()
                    elif p_created: profile.district = 'المركز'
                    
                    if uni: profile.university = str(uni).strip()
                    if col: profile.college = str(col).strip()
                    if dept: profile.department = str(dept).strip()
                    if stage: profile.academic_stage = str(stage).strip()
                    if spec: profile.specialty = str(spec).strip()
                    if resolved_group: profile.group = resolved_group
                    profile.save()

                    # Ensure CustomUser governorate is set correctly
                    if resolved_group and resolved_group.governorate:
                        if user.governorate != resolved_group.governorate:
                            user.governorate = resolved_group.governorate
                            user.save(update_fields=['governorate'])
                    elif gov:
                        from apps.locations.models import Governorate
                        gov_obj = Governorate.objects.filter(name__icontains=str(gov).strip()).first()
                        if gov_obj and not user.governorate:
                            user.governorate = gov_obj
                            user.save(update_fields=['governorate'])
                    
                    # Update email to use training number if it was generated/placeholder
                    if not email_val or '@' not in str(email_val):
                        user.email = f"{profile.training_number.lower()}@1000programmers.org"
                        user.save()
                        
                    imported_count += 1
            except Exception as e:
                errors.append(f"السطر {row_idx}: فشل الاستيراد للمستخدم {username} بسبب: {str(e)}")
                
        return imported_count, errors

    @staticmethod
    def import_lecturers_from_excel(file_io):
        import re
        wb = openpyxl.load_workbook(file_io)
        sheet = wb.active
        imported_count = 0
        errors = []
        
        # Read headers dynamically
        headers = [str(sheet.cell(row=1, column=c).value or '').strip() for c in range(1, sheet.max_column + 1)]
        
        col_username = None
        col_email = None
        col_first_name = None
        col_last_name = None
        col_spec = None
        col_bio = None
        col_full_name = None
        
        for idx, h in enumerate(headers, 1):
            h_clean = h.strip().lower()
            if not h_clean:
                continue
            if "اسم المستخدم" in h_clean or "username" in h_clean:
                col_username = idx
            elif "البريد" in h_clean or "الايميل" in h_clean or "email" in h_clean:
                col_email = idx
            elif "الأول" in h_clean or "first" in h_clean:
                col_first_name = idx
            elif "العائلة" in h_clean or "الأخير" in h_clean or "last" in h_clean or "اللقب" in h_clean:
                col_last_name = idx
            elif "الكامل" in h_clean or "الاسم" in h_clean or "name" in h_clean:
                col_full_name = idx
            elif "الاختصاص" in h_clean or "التخصص" in h_clean or "spec" in h_clean:
                col_spec = idx
            elif "سيرة" in h_clean or "نبذة" in h_clean or "bio" in h_clean:
                col_bio = idx

        if not any([col_username, col_email, col_first_name, col_full_name]):
            col_username = 1
            col_email = 2
            col_first_name = 3
            col_last_name = 4
            col_spec = 5
            col_bio = 6

        for row_idx in range(2, sheet.max_row + 1):
            username_val = sheet.cell(row=row_idx, column=col_username).value if col_username else None
            email_val = sheet.cell(row=row_idx, column=col_email).value if col_email else None
            
            first_name = None
            last_name = None
            
            if col_full_name:
                full_name_val = str(sheet.cell(row=row_idx, column=col_full_name).value or '').strip()
                if full_name_val:
                    parts = full_name_val.split()
                    if parts:
                        first_name = parts[0]
                        if len(parts) > 1:
                            last_name = " ".join(parts[1:])
            
            if not first_name and col_first_name:
                first_name = sheet.cell(row=row_idx, column=col_first_name).value
            if not last_name and col_last_name:
                last_name = sheet.cell(row=row_idx, column=col_last_name).value

            specialty = sheet.cell(row=row_idx, column=col_spec).value if col_spec else None
            bio = sheet.cell(row=row_idx, column=col_bio).value if col_bio else None
            
            if not any([username_val, email_val, first_name, last_name, specialty, bio]):
                continue
                
            if username_val:
                username = re.sub(r'[^a-zA-Z0-9_.-]', '_', str(username_val).strip())
            else:
                username = ImportExportService.generate_safe_username(first_name, last_name, email_val, prefix='lecturer')
                
            clean_email = None
            if email_val:
                email_str = str(email_val).strip()
                if '@' in email_str:
                    clean_email = email_str
            
            if not clean_email:
                clean_email = f"{username}@1000programmers.iq"
            
            try:
                with transaction.atomic():
                    user = User.objects.filter(username=username).first()
                    if not user and clean_email:
                        user = User.objects.filter(email=clean_email).first()
                    
                    if not user:
                        user = User.objects.create_user(
                            username=username,
                            email=clean_email,
                            first_name=str(first_name).strip() if first_name else '',
                            last_name=str(last_name).strip() if last_name else '',
                            role=User.Role.LECTURER,
                            password="Password123"
                        )
                    else:
                        if first_name: user.first_name = str(first_name).strip()
                        if last_name: user.last_name = str(last_name).strip()
                        if clean_email: user.email = clean_email
                        user.role = User.Role.LECTURER
                        user.save()
                        
                    from .models import LecturerProfile
                    LecturerProfile.objects.update_or_create(
                        user=user,
                        defaults={
                            'specialty': str(specialty).strip() if specialty else 'مدرب تقني',
                            'bio': str(bio).strip() if bio else ''
                        }
                    )
                    imported_count += 1
            except Exception as e:
                errors.append(f"السطر {row_idx}: فشل استيراد المحاضر {username} بسبب: {str(e)}")
                
        return imported_count, errors

    @staticmethod
    def generate_batch_accounts(prefix, count, role, group_id=None, names_list=None, governorate=None):
        import random
        import string
        from apps.locations.models import Governorate
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "الحسابات المولدة"
        
        sheet.views.sheetView[0].showGridLines = True
        headers = ["الاسم الكامل", "اسم المستخدم", "البريد الإلكتروني", "كلمة المرور المؤقتة", "الدور الوظيفي", "المحافظة", "المجموعة"]
        for col_num, header in enumerate(headers, 1):
            sheet.cell(row=1, column=col_num, value=header)
            
        group = None
        if group_id and role == User.Role.TRAINEE:
            try:
                group = Group.objects.get(id=group_id)
                if not governorate and group.governorate:
                    governorate = group.governorate
            except Group.DoesNotExist:
                pass
                
        if not governorate:
            governorate = Governorate.objects.filter(status='active').first()

        generated_count = 0
        row_idx = 2
        
        if names_list and len(names_list) > 0:
            target_names = names_list
        else:
            target_names = [None] * count
        
        for i, raw_name in enumerate(target_names, 1):
            first_name = ""
            last_name = ""
            
            if raw_name:
                name_parts = str(raw_name).strip().split()
                if name_parts:
                    first_name = name_parts[0]
                    if len(name_parts) > 1:
                        last_name = " ".join(name_parts[1:])
                full_name = str(raw_name).strip()
                # Check if existing user with this full name or name parts exists
                existing_user = User.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name).first()
                if not existing_user and full_name:
                    existing_user = User.objects.filter(first_name__iexact=full_name).first()
                
                if existing_user:
                    username = existing_user.username
                else:
                    if prefix and prefix != 'student':
                        username = f"{prefix}_{i:02d}"
                        base_username = username
                        while User.objects.filter(username=username).exists():
                            username = f"{base_username}_{random.randint(10, 99)}"
                    else:
                        username = ImportExportService.generate_safe_username(first_name, last_name, prefix=prefix or 'student')
            else:
                full_name = f"طالب المبادرة {i}" if role == User.Role.TRAINEE else f"مستخدَم {i}"
                if group:
                    full_name += f" ({group.name})"
                username = f"{prefix}_{i:02d}"
                base_username = username
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}_{random.randint(10, 99)}"
                existing_user = None
                
            chars = string.ascii_letters + string.digits
            password = "".join(random.choice(chars) for _ in range(8))
            
            try:
                with transaction.atomic():
                    if existing_user:
                        user = existing_user
                        user.set_password(password)
                        user.temp_password = password
                        if governorate and not user.governorate:
                            user.governorate = governorate
                        if group and role == User.Role.TRAINEE:
                            profile, _ = TraineeProfile.objects.get_or_create(user=user)
                            profile.group = group
                            if governorate: profile.governorate = governorate.name
                            profile.save()
                        user.save()
                        email = user.email
                    else:
                        email = f"{username}@1000programmers.org"
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            first_name=first_name if first_name else full_name,
                            last_name=last_name if last_name else '',
                            role=role,
                            governorate=governorate,
                            password=password,
                            temp_password=password
                        )

                        if role == User.Role.TRAINEE:
                            profile = TraineeProfile.objects.create(
                                user=user,
                                governorate=governorate.name if governorate else 'البصرة',
                                group=group
                            )
                            user.email = f"{profile.training_number.lower()}@1000programmers.org"
                            user.save()
                            email = user.email
                        elif role == User.Role.LECTURER:
                            from .models import LecturerProfile
                            LecturerProfile.objects.create(
                                user=user,
                                specialty='مدرب تقني'
                            )
                        elif role == User.Role.SUPERVISOR:
                            from .models import SupervisorProfile
                            SupervisorProfile.objects.create(
                                user=user
                            )
                        
                    sheet.cell(row=row_idx, column=1, value=user.get_full_name() or full_name)
                    sheet.cell(row=row_idx, column=2, value=user.username)
                    sheet.cell(row=row_idx, column=3, value=user.email)
                    sheet.cell(row=row_idx, column=4, value=password)
                    sheet.cell(row=row_idx, column=5, value=dict(User.Role.choices).get(role, role))
                    sheet.cell(row=row_idx, column=6, value=governorate.name if governorate else '')
                    sheet.cell(row=row_idx, column=7, value=group.name if group else (user.trainee_profile.group.name if hasattr(user, 'trainee_profile') and user.trainee_profile.group else ''))
                    row_idx += 1
                    generated_count += 1
            except Exception as e:
                pass

                
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer, generated_count

    @staticmethod
    def export_to_excel(group_id=None, governorate=None):
        """Exports trainees data to a formatted Excel spreadsheet."""
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.db.models import Q
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "المتدربين"
        sheet.sheet_view.rightToLeft = True
        
        headers = [
            "الرقم التدريبي", "اسم المستخدم", "البريد الإلكتروني",
            "الاسم الأول", "اسم العائلة", "المحافظة", "القضاء",
            "المدرسة", "الصف الدراسي", "التفاصيل", "المرحلة الدراسية",
            "الاختصاص", "الشعبة", "الحالة", "النقاط", "الجنس"
        ]
        
        # Style headers
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="198754", end_color="198754", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        for col_num, header in enumerate(headers, 1):
            cell = sheet.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # Query trainees
        trainees_qs = TraineeProfile.objects.select_related('user', 'group').all()
        if group_id:
            trainees_qs = trainees_qs.filter(group_id=group_id)
        if governorate:
            gov_name = governorate.name if hasattr(governorate, 'name') else str(governorate)
            trainees_qs = trainees_qs.filter(
                Q(user__governorate=governorate) | 
                Q(group__governorate=governorate) | 
                Q(governorate__icontains=gov_name)
            )
        
        for row_idx, t in enumerate(trainees_qs, 2):
            sheet.cell(row=row_idx, column=1, value=t.training_number)
            sheet.cell(row=row_idx, column=2, value=t.user.username)
            sheet.cell(row=row_idx, column=3, value=t.user.email)
            sheet.cell(row=row_idx, column=4, value=t.user.first_name)
            sheet.cell(row=row_idx, column=5, value=t.user.last_name)
            sheet.cell(row=row_idx, column=6, value=t.governorate or '')
            sheet.cell(row=row_idx, column=7, value=t.district or '')
            sheet.cell(row=row_idx, column=8, value=t.university or '')
            sheet.cell(row=row_idx, column=9, value=t.college or '')
            sheet.cell(row=row_idx, column=10, value=t.department or '')
            sheet.cell(row=row_idx, column=11, value=t.academic_stage or '')
            sheet.cell(row=row_idx, column=12, value=t.specialty or '')
            sheet.cell(row=row_idx, column=13, value=t.group.name if t.group else '')
            sheet.cell(row=row_idx, column=14, value=t.get_status_display())
            sheet.cell(row=row_idx, column=15, value=t.points)
            sheet.cell(row=row_idx, column=16, value='أنثى' if t.user.gender == 'female' else 'ذكر')
        
        # Auto-fit column widths
        for col in sheet.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            sheet.column_dimensions[col_letter].width = min(max_length + 4, 40)
        
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def export_lecturers_to_excel():
        """Exports lecturers data to a formatted Excel spreadsheet."""
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from .models import LecturerProfile
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "المدربين"
        sheet.sheet_view.rightToLeft = True
        
        headers = [
            "اسم المستخدم", "البريد الإلكتروني",
            "الاسم الأول", "اسم العائلة",
            "التخصص", "السيرة الذاتية"
        ]
        
        # Style headers
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        for col_num, header in enumerate(headers, 1):
            cell = sheet.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        lecturers = User.objects.filter(role=User.Role.LECTURER).prefetch_related('lecturer_profile')
        
        for row_idx, lec in enumerate(lecturers, 2):
            profile = getattr(lec, 'lecturer_profile', None)
            sheet.cell(row=row_idx, column=1, value=lec.username)
            sheet.cell(row=row_idx, column=2, value=lec.email)
            sheet.cell(row=row_idx, column=3, value=lec.first_name)
            sheet.cell(row=row_idx, column=4, value=lec.last_name)
            sheet.cell(row=row_idx, column=5, value=profile.specialty if profile else '')
            sheet.cell(row=row_idx, column=6, value=profile.bio if profile else '')
        
        # Auto-fit column widths
        for col in sheet.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            sheet.column_dimensions[col_letter].width = min(max_length + 4, 50)
        
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def bulk_delete_trainees(trainee_ids=None, delete_all=False):
        """Deletes trainees by IDs or all trainees. Returns the count of deleted records."""
        if delete_all:
            count = TraineeProfile.objects.count()
            # Delete the User objects which cascade to profiles
            User.objects.filter(role=User.Role.TRAINEE).delete()
            return count
        elif trainee_ids:
            profiles = TraineeProfile.objects.filter(id__in=trainee_ids)
            count = profiles.count()
            user_ids = list(profiles.values_list('user_id', flat=True))
            User.objects.filter(id__in=user_ids).delete()
            return count
        return 0

    @staticmethod
    def bulk_delete_lecturers(lecturer_ids=None, delete_all=False):
        """Deletes lecturers by IDs or all lecturers. Returns the count of deleted records."""
        if delete_all:
            count = User.objects.filter(role=User.Role.LECTURER).count()
            User.objects.filter(role=User.Role.LECTURER).delete()
            return count
        elif lecturer_ids:
            users = User.objects.filter(id__in=lecturer_ids, role=User.Role.LECTURER)
            count = users.count()
            users.delete()
            return count
        return 0


from apps.courses.models import Lecture, Course

class LectureGroupImportExportService:
    @staticmethod
    def export_groups():
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "الشعب والمجموعات"
        sheet.views.sheetView[0].showGridLines = True
        
        headers = ["الاسم", "الدورة", "المحاضر (Username)", "المشرف (Username)", "القاعة الدراسية"]
        for col_num, header in enumerate(headers, 1):
            sheet.cell(row=1, column=col_num, value=header)
            
        groups = Group.objects.select_related('course', 'instructor', 'supervisor').all()
        for row_idx, g in enumerate(groups, 2):
            sheet.cell(row=row_idx, column=1, value=g.name)
            sheet.cell(row=row_idx, column=2, value=g.course.title if g.course else '')
            sheet.cell(row=row_idx, column=3, value=g.instructor.username if g.instructor else '')
            sheet.cell(row=row_idx, column=4, value=g.supervisor.username if g.supervisor else '')
            sheet.cell(row=row_idx, column=5, value=g.classroom or '')
            
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def import_groups(file_io):
        wb = openpyxl.load_workbook(file_io)
        sheet = wb.active
        imported_count = 0
        errors = []
        
        for row_idx in range(2, sheet.max_row + 1):
            name = sheet.cell(row=row_idx, column=1).value
            course_title = sheet.cell(row=row_idx, column=2).value
            instructor_user = sheet.cell(row=row_idx, column=3).value
            supervisor_user = sheet.cell(row=row_idx, column=4).value
            classroom = sheet.cell(row=row_idx, column=5).value
            
            if not name:
                continue
                
            try:
                name = str(name).strip()
                course = None
                if course_title:
                    course, _ = Course.objects.get_or_create(title=str(course_title).strip())
                
                instructor = None
                if instructor_user:
                    instructor = User.objects.filter(username=str(instructor_user).strip(), role=User.Role.LECTURER).first()
                    
                supervisor = None
                if supervisor_user:
                    supervisor = User.objects.filter(username=str(supervisor_user).strip(), role=User.Role.SUPERVISOR).first()
                    
                Group.objects.update_or_create(
                    name=name,
                    defaults={
                        'course': course,
                        'instructor': instructor,
                        'supervisor': supervisor,
                        'classroom': str(classroom).strip() if classroom else 'قاعة المبادرة العامة'
                    }
                )
                imported_count += 1
            except Exception as e:
                errors.append(f"السطر {row_idx}: فشل استيراد الشعبة بسبب: {str(e)}")
                
        return imported_count, errors

    @staticmethod
    def export_lectures():
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "المحاضرات"
        sheet.views.sheetView[0].showGridLines = True
        
        headers = ["عنوان المحاضرة", "الشعبة / المجموعة", "التاريخ (YYYY-MM-DD)", "وقت البدء (HH:MM)", "وقت الانتهاء (HH:MM)"]
        for col_num, header in enumerate(headers, 1):
            sheet.cell(row=1, column=col_num, value=header)
            
        lectures = Lecture.objects.select_related('group').all()
        for row_idx, lec in enumerate(lectures, 2):
            sheet.cell(row=row_idx, column=1, value=lec.title)
            sheet.cell(row=row_idx, column=2, value=lec.group.name if lec.group else '')
            sheet.cell(row=row_idx, column=3, value=lec.date.strftime('%Y-%m-%d') if lec.date else '')
            sheet.cell(row=row_idx, column=4, value=lec.start_time.strftime('%H:%M') if lec.start_time else '')
            sheet.cell(row=row_idx, column=5, value=lec.end_time.strftime('%H:%M') if lec.end_time else '')
            
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def import_lectures(file_io):
        wb = openpyxl.load_workbook(file_io)
        sheet = wb.active
        imported_count = 0
        errors = []
        
        for row_idx in range(2, sheet.max_row + 1):
            title = sheet.cell(row=row_idx, column=1).value
            group_name = sheet.cell(row=row_idx, column=2).value
            date_val = sheet.cell(row=row_idx, column=3).value
            start_val = sheet.cell(row=row_idx, column=4).value
            end_val = sheet.cell(row=row_idx, column=5).value
            
            if not title or not group_name:
                continue
                
            try:
                group = Group.objects.filter(name=str(group_name).strip()).first()
                if not group:
                    errors.append(f"السطر {row_idx}: لم يتم العثور على الشعبة '{group_name}'")
                    continue
                    
                from datetime import datetime
                # Parse date and times
                if isinstance(date_val, str):
                    date_obj = datetime.strptime(date_val.strip(), '%Y-%m-%d').date()
                elif isinstance(date_val, datetime):
                    date_obj = date_val.date()
                else:
                    date_obj = date_val
                    
                if isinstance(start_val, str):
                    start_time = datetime.strptime(start_val.strip(), '%H:%M').time()
                else:
                    start_time = start_val
                    
                if isinstance(end_val, str):
                    end_time = datetime.strptime(end_val.strip(), '%H:%M').time()
                else:
                    end_time = end_val
                    
                Lecture.objects.update_or_create(
                    title=str(title).strip(),
                    group=group,
                    date=date_obj,
                    defaults={
                        'start_time': start_time,
                        'end_time': end_time
                    }
                )
                imported_count += 1
            except Exception as e:
                errors.append(f"السطر {row_idx}: فشل استيراد المحاضرة بسبب: {str(e)}")
                
        return imported_count, errors

