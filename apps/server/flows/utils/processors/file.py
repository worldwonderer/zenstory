"""
文件处理和验证工具类
"""
from pathlib import Path

import chardet


class FileValidator:
    """文件验证器"""

    # 支持的文件格式
    SUPPORTED_FORMATS = {".txt", ".md", ".markdown"}

    def is_supported_format(self, file_path: Path) -> bool:
        """
        检查文件格式是否支持

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否支持
        """
        return file_path.suffix.lower() in self.SUPPORTED_FORMATS


class FileProcessor:
    """文件处理器"""

    def detect_encoding(
        self,
        file_path: Path,
        sample_size: int = 10000
    ) -> tuple[str | None, float]:
        """
        检测文件编码

        Args:
            file_path: 文件路径
            sample_size: 采样大小（字节）

        Returns:
            Tuple[编码名称, 置信度]
        """
        with open(file_path, "rb") as f:
            raw_data = f.read(sample_size)

        result = chardet.detect(raw_data)
        encoding = result.get("encoding")
        confidence = result.get("confidence", 0.0)

        return encoding, confidence
