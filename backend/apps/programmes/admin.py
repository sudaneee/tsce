from django.contrib import admin

from .models import Cohort, Module, Programme


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    ordering = ["order"]


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "track", "weeks", "fee", "capacity", "instructor", "status"]
    list_filter = ["status", "track"]
    search_fields = ["code", "name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["instructor"]
    inlines = [ModuleInline]


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "enrolment_opens", "enrolment_closes", "early_bird_deadline"]
    search_fields = ["name"]
