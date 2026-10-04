"""Database-backed file storage for uploaded profile photos.

LocalFix deploys to Vercel, where the filesystem is read-only and ephemeral:
``FileSystemStorage`` answered every avatar upload with a 500
(``PermissionError`` from ``os.makedirs``). Profile photos are small and few,
so the bytes are kept in the database instead and streamed back by
``core.views.media_file``. Nothing else in the project uses file storage, so
this is installed as the default backend in settings.
"""
import mimetypes
from io import BytesIO
from urllib.parse import quote, urljoin

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils import timezone
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    """Store uploaded files as rows in ``accounts.StoredFile``."""

    def _record(self, name):
        from .models import StoredFile

        try:
            return StoredFile.objects.get(name=name)
        except StoredFile.DoesNotExist:
            raise FileNotFoundError(f"No stored file named {name!r}")

    def _open(self, name, mode="rb"):
        record = self._record(name)
        return File(BytesIO(record.content_bytes()), name=name)

    def _save(self, name, content):
        from .models import StoredFile

        if hasattr(content, "seek"):
            content.seek(0)
        data = content.read()
        StoredFile.objects.update_or_create(
            name=name,
            defaults={
                "content": data,
                "size": len(data),
                "content_type": mimetypes.guess_type(name)[0]
                or "application/octet-stream",
            },
        )
        return name

    def delete(self, name):
        from .models import StoredFile

        StoredFile.objects.filter(name=name).delete()

    def exists(self, name):
        from .models import StoredFile

        return StoredFile.objects.filter(name=name).exists()

    def listdir(self, path):
        return [], []

    def size(self, name):
        return self._record(name).size

    def url(self, name):
        return urljoin(settings.MEDIA_URL, quote(name))

    def get_created_time(self, name):
        return self._record(name).created_at

    def get_modified_time(self, name):
        return self._record(name).created_at

    def get_accessed_time(self, name):
        return self._record(name).created_at or timezone.now()
