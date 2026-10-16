"""
Client request (16 Oct 2026): "IT Essentials: Computer Hardware Basics" becomes
"IT Essentials and Digital Literacy", with a curriculum that includes the
Microsoft Office package. Updates only this programme; fee, duration, capacity
and schedules are unchanged. Modules are renamed in place by position (results
stay attached), extra ones are added.
"""
from django.db import migrations

NEW = {
    "name": "IT Essentials and Digital Literacy",
    "track": "Digital Literacy",
    "icon": "fa-desktop",
    "overview": "An entry-level programme for complete beginners: computer basics and hardware, Windows, the internet and email, and the Microsoft Office package — Word, Excel and PowerPoint — plus everyday troubleshooting. The perfect starting point for school, office work and a career in tech.",
    "outcomes": [
        "Use a computer confidently, and understand its hardware and software",
        "Manage files and settings in Windows",
        "Create professional documents in Microsoft Word",
        "Build spreadsheets with formulas and charts in Microsoft Excel",
        "Design and deliver presentations in Microsoft PowerPoint",
        "Use the internet, email and online tools safely, and fix common computer problems"
    ],
    "modules": [
        "Introduction to Computers & Digital Literacy",
        "Computer Hardware Components",
        "Windows & File Management",
        "Microsoft Word",
        "Microsoft Excel",
        "Microsoft PowerPoint",
        "Internet, Email (Outlook) & Online Safety",
        "Basic Troubleshooting & IT Support Practicals"
    ],
    "audience": [
        "Complete beginners",
        "Secondary school leavers",
        "Office staff and civil servants",
        "Small business owners"
    ],
    "careers": [
        "Computer Operator",
        "Office Administrator / Secretary",
        "Data Entry Clerk",
        "IT Support Assistant"
    ]
}
OLD = {"name": "IT Essentials: Computer Hardware Basics", "track": "Hardware"}


def forwards(apps, schema_editor):
    Programme = apps.get_model("programmes", "Programme")
    Module = apps.get_model("programmes", "Module")
    programme = Programme.objects.filter(slug="it-essentials").first()
    if programme is None:  # a fresh database is seeded from catalogue.json instead
        return
    for field in ("name", "track", "icon", "overview", "outcomes", "audience", "careers"):
        setattr(programme, field, NEW[field])
    programme.save()
    existing = {m.order: m for m in Module.objects.filter(programme=programme)}
    for order, title in enumerate(NEW["modules"], start=1):
        module = existing.pop(order, None)
        if module is None:
            Module.objects.create(programme=programme, order=order, title=title)
        elif module.title != title:
            module.title = title
            module.save(update_fields=["title"])
    for module in existing.values():  # (the new list is longer, so normally none)
        if not module.results.exists():
            module.delete()


def backwards(apps, schema_editor):
    Programme = apps.get_model("programmes", "Programme")
    Programme.objects.filter(slug="it-essentials").update(**OLD)


class Migration(migrations.Migration):

    dependencies = [
        ("programmes", "0001_initial"),
        ("academics", "0003_student_email_student_guardian_and_more"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
