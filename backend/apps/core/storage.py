from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage():
    """
    Storage for personal documents (e.g. WAEC results). PRIVATE_MEDIA_ROOT is
    never exposed by nginx; files are only downloadable through permission-
    checked API views.
    """
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)
