"""校验上传文件，并将原文件流式保存到本地文件系统。"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import AppError


ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx"})
FILE_READ_CHUNK_SIZE = 1024 * 1024


def validate_filename(filename: str | None) -> str:
    """清理并校验客户端提供的上传文件名。"""
    if filename is None or not filename.strip():
        raise AppError(400, "INVALID_FILENAME", "文件名不能为空。")

    safe_name = filename.replace("\\", "/").split("/")[-1].strip()
    if (
        not safe_name
        or safe_name in {".", ".."}
        or "\x00" in safe_name
        or len(safe_name) > 255
    ):
        raise AppError(
            400,
            "INVALID_FILENAME",
            "文件名无效或长度超过 255 个字符。",
        )

    if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise AppError(
            400,
            "UNSUPPORTED_FILE_TYPE",
            "仅支持 TXT、Markdown、PDF 和 DOCX 文件。",
        )
    return safe_name


@dataclass(frozen=True)
class StoredFile:
    """表示成功保存的原文件信息。

    Attributes:
        filename: 已清除目录部分的安全文件名。
        path: 原文件在服务器上的绝对存储路径。
        content_hash: 原文件内容的 SHA-256 十六进制摘要。
    """

    filename: str
    path: Path
    content_hash: str


async def save_upload_file(
    upload: UploadFile,
    kb_id: UUID,
    document_id: UUID,
) -> StoredFile:
    """流式保存上传文件，并在写入时计算 SHA-256。"""
    safe_name = validate_filename(upload.filename)
    target_dir = settings.file_storage_path / str(kb_id) / str(document_id)
    target_path = target_dir / safe_name
    target_dir.mkdir(parents=True, exist_ok=True)

    content_hasher = sha256()
    total_size = 0
    try:
        with target_path.open("wb") as output_file:
            while chunk := await upload.read(FILE_READ_CHUNK_SIZE):
                output_file.write(chunk)
                content_hasher.update(chunk)
                total_size += len(chunk)

        if total_size == 0:
            _cleanup_partial_file(target_path)
            raise AppError(400, "EMPTY_FILE", "上传文件不能为空。")
    except AppError:
        raise
    except Exception as exc:
        _cleanup_partial_file(target_path)
        raise AppError(500, "FILE_SAVE_FAILED", "文件保存失败。") from exc
    finally:
        await upload.close()

    return StoredFile(
        filename=safe_name,
        path=target_path.resolve(),
        content_hash=content_hasher.hexdigest(),
    )


def _cleanup_partial_file(target_path: Path) -> None:
    """尽量删除写入失败后遗留的文件和空文档目录。"""
    try:
        target_path.unlink(missing_ok=True)
        target_path.parent.rmdir()
    except OSError:
        pass
