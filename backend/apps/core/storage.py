import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMediaStorage(FileSystemStorage):
    """
    Storage for personal documents (e.g. WAEC results). PRIVATE_MEDIA_ROOT is
    never exposed by nginx; files are only downloadable through permission-
    checked API views. The location is read on every access (not cached), so
    it follows settings overrides in tests.
    """

    def __init__(self):
        super().__init__(base_url=None)

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private files have no public URL; serve them through a permission-checked view.")


def private_storage():
    return PrivateMediaStorage()
