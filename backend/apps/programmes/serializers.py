from rest_framework import serializers

from .models import Programme


class ProgrammeSerializer(serializers.ModelSerializer):
    """Catalogue entry in the shape the frontend's Programmes module uses."""

    id = serializers.CharField(source="slug")
    colorBg = serializers.CharField(source="color_bg")
    modules = serializers.SerializerMethodField()
    instructor = serializers.SerializerMethodField()
    seats = serializers.SerializerMethodField()

    class Meta:
        model = Programme
        fields = [
            "id", "code", "name", "track", "category", "weeks", "fee", "capacity", "status", "icon", "color",
            "colorBg", "overview", "outcomes", "audience", "careers", "requirements", "schedules", "modules",
            "instructor", "seats",
        ]

    def get_modules(self, obj):
        return [m.title for m in obj.modules.all()]  # prefetched, ordered

    def get_instructor(self, obj):
        return obj.instructor.full_name if obj.instructor else None

    def get_seats(self, obj):
        taken = min(obj.capacity, self.context.get("seats_taken", {}).get(obj.pk, 0))
        return {
            "enrolled": taken,
            "capacity": obj.capacity,
            "available": obj.capacity - taken,
            "pct": round(taken / obj.capacity * 100),
        }
