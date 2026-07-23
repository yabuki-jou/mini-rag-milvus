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
    """清理并校验客户端提供的上传文件名。

    Args:
        filename: UploadFile 中可能为空或包含目录部分的文件名。

    Returns:
        只保留末级名称且扩展名受支持的安全文件名。

    Raises:
        AppError: 文件名为空、格式无效、过长或扩展名不受支持。
    """
    # UploadFile 可能没有文件名，空名称不能用于创建存储路径。
    if filename is None or not filename.strip():
        raise AppError(400, "INVALID_FILENAME", "文件名不能为空。")

    # 同时移除 Windows 和 Unix 目录部分，防止客户端控制保存目录。
    safe_name = filename.replace("\\", "/").split("/")[-1].strip()

    # 拒绝特殊目录名、空字节和超过数据库字段上限的名称。
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

    # 只允许已有解析器支持的文件扩展名。
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
    """流式保存上传文件，并在写入时计算 SHA-256。

    Args:
        upload: FastAPI 接收到的上传文件。
        kb_id: 文件所属知识库的 UUID。
        document_id: 上传前生成的文档 UUID。

    Returns:
        安全文件名、绝对存储路径和内容摘要。

    Raises:
        AppError: 文件名无效、文件为空或写入文件系统失败。
    """
    # 文档独立目录避免不同知识库或同名文件相互覆盖。
    safe_name = validate_filename(upload.filename)
    target_dir = settings.file_storage_path / str(kb_id) / str(document_id)
    target_path = target_dir / safe_name
    target_dir.mkdir(parents=True, exist_ok=True)

    # 在流式写入的同时累计哈希和大小，避免保存后再次读取整个文件。
    content_hasher = sha256()
    total_size = 0
    try:
        with target_path.open("wb") as output_file:
            while chunk := await upload.read(FILE_READ_CHUNK_SIZE):
                output_file.write(chunk)
                content_hasher.update(chunk)
                total_size += len(chunk)

        # 空文件无法生成有效 Chunk，因此上传阶段直接拒绝并清理。
        if total_size == 0:
            _cleanup_partial_file(target_path)
            raise AppError(400, "EMPTY_FILE", "上传文件不能为空。")
    except AppError:
        # 已知业务错误保留原状态码和错误代码。
        raise
    except Exception as exc:
        # 写入异常执行补偿清理，并隐藏操作系统路径等内部细节。
        _cleanup_partial_file(target_path)
        raise AppError(500, "FILE_SAVE_FAILED", "文件保存失败。") from exc
    finally:
        # 无论成功或失败都关闭上传流，及时释放临时文件句柄。
        await upload.close()

    # 仅在完整写入成功后返回文件身份和绝对路径。
    return StoredFile(
        filename=safe_name,
        path=target_path.resolve(),
        content_hash=content_hasher.hexdigest(),
    )


def _cleanup_partial_file(target_path: Path) -> None:
    """尽量删除写入失败后遗留的文件和空文档目录。

    清理失败不会覆盖最初的上传异常，因此本函数不向外抛出
    ``OSError``。

    Args:
        target_path: 需要清理的目标文件路径。
    """
    # 删除文件后尝试删除空目录；非空或被占用时静默保留。
    try:
        target_path.unlink(missing_ok=True)
        target_path.parent.rmdir()
    except OSError:
        pass
