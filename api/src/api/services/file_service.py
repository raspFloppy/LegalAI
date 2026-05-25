import uuid
from pathlib import Path

import aiofiles

from api.config import settings


class FileService:
    """Handles persistent storage of files uploaded through the bot.

    Files are written to ``{upload_dir}/{case_id}/{uuid}{ext}`` so each case
    has its own sub-directory.  The caller is responsible for passing the
    returned path into the ``Case`` model.

    Args:
        upload_dir: Root directory for uploads (defaults to
            ``settings.upload_dir``).
    """

    def __init__(self, upload_dir: str = settings.upload_dir) -> None:
        self._root = Path(upload_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        file_bytes: bytes,
        original_name: str | None,
        case_id: int,
        mime_type: str = "application/octet-stream",
    ) -> Path:
        """Persist file bytes to disk and return the storage path.

        Args:
            file_bytes: Raw file content.
            original_name: Filename as reported by the client (used only for
                extension extraction).
            case_id: Database ID of the owning case (used as sub-directory).
            mime_type: MIME type hint for extension inference when
                ``original_name`` is absent.

        Returns:
            Absolute ``Path`` of the stored file.
        """
        case_dir = self._root / str(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)

        ext = self._resolve_extension(original_name, mime_type)
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = case_dir / filename

        async with aiofiles.open(dest, "wb") as fh:
            await fh.write(file_bytes)

        return dest

    def _resolve_extension(
        self,
        original_name: str | None,
        mime_type: str,
    ) -> str:
        """Determine the file extension from the original name or MIME type.

        Args:
            original_name: Optional filename supplied by the client.
            mime_type: MIME type to fall back on.

        Returns:
            Extension string including the leading dot, e.g. ``".pdf"``, or
            an empty string when neither source yields a known extension.
        """
        if original_name:
            suffix = Path(original_name).suffix
            if suffix:
                return suffix

        _mime_map = {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
        }
        return _mime_map.get(mime_type, "")

    def resolve_path(self, relative_or_absolute: str) -> Path:
        """Return an absolute Path for a stored file.

        Args:
            relative_or_absolute: Either the string returned by ``save`` or
                a path relative to the upload root.

        Returns:
            Absolute ``Path`` to the file.
        """
        p = Path(relative_or_absolute)
        return p if p.is_absolute() else self._root / p
