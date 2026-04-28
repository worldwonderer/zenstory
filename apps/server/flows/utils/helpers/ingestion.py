"""
摄取辅助工具函数（参考 deepscript）

提供对小说文件的验证、校验和计算、编码检测、元数据提取、内容标准化等纯函数。
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from ..processors.file import FileProcessor, FileValidator

# 模块常量
DEFAULT_MAX_SIZE = 100 * 1024 * 1024  # 100MB（小说文件可能较大）
HASH_CHUNK_SIZE = 1024 * 1024  # 1MB


class ValidationResult(TypedDict):
    """validate_input 的返回结构"""

    file_path: str
    file_size: int
    file_extension: str
    validation_passed: bool


class ChecksumResult(TypedDict):
    """calculate_checksum 的返回结构"""

    md5_checksum: str
    sha256_checksum: str


class EncodingResult(TypedDict):
    """detect_encoding 的返回结构"""

    encoding: str | None
    encoding_confidence: float | None
    is_fallback: bool


def _to_iso_utc(ts: float) -> str:
    """将时间戳转为 ISO-8601 UTC 字符串"""
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def validate_input(file_path: str, max_size: int = DEFAULT_MAX_SIZE) -> ValidationResult:
    """
    验证输入文件是否存在、格式是否支持、大小是否合规

    Args:
        file_path: 文件路径
        max_size: 允许的最大文件大小（字节）

    Returns:
        ValidationResult: 验证结果
    """
    logger = logging.getLogger("helpers.ingestion.validate_input")

    if not file_path:
        raise ValueError("缺少文件路径参数")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    validator = FileValidator()
    if not validator.is_supported_format(path):
        raise ValueError(f"不支持的文件格式: {path.suffix}")

    file_size = path.stat().st_size
    if file_size > max_size:
        raise ValueError(f"文件过大: {file_size} bytes (最大: {max_size} bytes)")

    logger.info("文件验证通过: %s (%d bytes)", path, file_size)
    return {
        "file_path": str(path),
        "file_size": file_size,
        "file_extension": path.suffix.lower(),
        "validation_passed": True,
    }


def normalize_filename(file_path: str, output_dir: str | None = None) -> str:
    """
    将文件名标准化为UUID格式，避免中文字符编码问题

    Args:
        file_path: 原始文件路径
        output_dir: 输出目录（可选），如果不指定则使用原文件所在目录

    Returns:
        str: 新文件路径
    """
    logger = logging.getLogger("helpers.ingestion.normalize_filename")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    # 生成新的文件名，保持原始扩展名
    file_extension = path.suffix.lower()
    new_filename = f"{uuid.uuid4().hex}{file_extension}"

    # 确定输出目录
    target_dir = Path(output_dir) if output_dir else path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    # 构建新路径
    new_path = target_dir / new_filename

    logger.info("标准化文件名: %s -> %s", path.name, new_filename)
    return str(new_path)


def calculate_checksum(file_path: str) -> ChecksumResult:
    """
    计算文件的 MD5 和 SHA256 校验和

    Args:
        file_path: 文件路径

    Returns:
        ChecksumResult: 校验和结果
    """
    logger = logging.getLogger("helpers.ingestion.calculate_checksum")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()

    with open(path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)

    result = {
        "md5_checksum": md5_hash.hexdigest(),
        "sha256_checksum": sha256_hash.hexdigest(),
    }

    logger.info("校验和计算完成: md5=%s", result["md5_checksum"])
    return result


def detect_encoding(file_path: str, fallback: str = "utf-8") -> EncodingResult:
    """
    检测文件编码

    Args:
        file_path: 文件路径
        fallback: 检测失败时的兜底编码

    Returns:
        EncodingResult: 编码检测结果
    """
    logger = logging.getLogger("helpers.ingestion.detect_encoding")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    processor = FileProcessor()
    encoding, confidence = processor.detect_encoding(path)

    is_fallback = False
    if not encoding or confidence < 0.7:
        logger.warning("编码检测置信度低 (%.2f)，使用兜底编码: %s", confidence, fallback)
        encoding = fallback
        is_fallback = True

    logger.info("编码检测: %s (置信度: %.2f)", encoding, confidence)
    return {
        "encoding": encoding,
        "encoding_confidence": confidence,
        "is_fallback": is_fallback,
    }


def extract_metadata(
    file_path: str,
    file_size: int,
    file_extension: str,
    md5_checksum: str,
    sha256_checksum: str,
    encoding: str,
    encoding_confidence: float,
) -> dict[str, Any]:
    """
    提取文件元数据

    Args:
        file_path: 文件路径
        file_size: 文件大小
        file_extension: 文件扩展名
        md5_checksum: MD5 校验和
        sha256_checksum: SHA256 校验和
        encoding: 文件编码
        encoding_confidence: 编码置信度

    Returns:
        Dict: 元数据
    """
    path = Path(file_path)
    stat = path.stat()

    return {
        "file_name": path.name,
        "file_path": str(path),
        "file_size": file_size,
        "file_extension": file_extension,
        "md5_checksum": md5_checksum,
        "sha256_checksum": sha256_checksum,
        "encoding": encoding,
        "encoding_confidence": encoding_confidence,
        "created_at": _to_iso_utc(stat.st_ctime),
        "modified_at": _to_iso_utc(stat.st_mtime),
    }


def normalize_content(
    file_path: str,
    encoding: str,
    output_dir: str | None = None,
    write_to_disk: bool = False,
) -> dict[str, Any]:
    """
    标准化文件内容

    Args:
        file_path: 文件路径
        encoding: 文件编码
        output_dir: 输出目录（如果写入磁盘）
        write_to_disk: 是否写入磁盘

    Returns:
        Dict: 标准化结果
    """
    logger = logging.getLogger("helpers.ingestion.normalize_content")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    # 读取内容
    with open(path, encoding=encoding) as f:
        content = f.read()

    # 标准化：去除多余空白、统一换行符
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))

    result = {
        "content": normalized,
        "original_length": len(content),
        "normalized_length": len(normalized),
    }

    # 可选：写入磁盘
    if write_to_disk and output_dir:
        output_path = Path(output_dir) / f"{path.stem}_normalized{path.suffix}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(normalized)
        result["output_path"] = str(output_path)
        logger.info("标准化内容已写入: %s", output_path)

    return result
