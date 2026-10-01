from django.contrib import admin

from .models import AttendanceRecord, AttendanceSession, Certificate, Enrollment, Result, Student


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    fields = ["programme", "cohort", "schedule", "status", "progress", "amount_paid"]
    show_change_link = True


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["student_no", "full_name", "phone", "state", "created_at"]
    search_fields = ["student_no", "first_name", "last_name", "email", "user__email", "guardian__email", "phone"]
    readonly_fields = ["student_no", "created_at", "updated_at"]
    autocomplete_fields = ["user", "guardian"]
    inlines = [EnrollmentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "programme", "cohort", "status", "progress", "start_date", "end_date"]
    list_filter = ["status", "cohort", "programme"]
    search_fields = ["student__student_no", "student__first_name", "student__last_name"]
    raw_id_fields = ["student", "application"]
    list_select_related = ["student", "programme", "cohort"]


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    raw_id_fields = ["enrollment"]


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ["date", "programme", "cohort", "module", "recorded_by"]
    list_filter = ["programme", "cohort"]
    date_hierarchy = "date"
    inlines = [AttendanceRecordInline]


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "module", "type", "score", "grade", "status", "assessed_on"]
    list_filter = ["status", "grade", "type", "enrollment__programme"]
    search_fields = ["enrollment__student__first_name", "enrollment__student__last_name", "enrollment__student__student_no"]
    raw_id_fields = ["enrollment", "module"]


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ["number", "enrollment", "status", "issued_at", "issued_by"]
    list_filter = ["status"]
    search_fields = ["number", "enrollment__student__first_name", "enrollment__student__last_name"]
    raw_id_fields = ["enrollment"]
    readonly_fields = ["number"]
