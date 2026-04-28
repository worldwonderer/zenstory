"""
小说章节解析工具

功能：
- 从 txt 文件中按章节标题分割
- 支持多种章节标题格式
- 提取章节号和标题
"""

import re
from pathlib import Path

import cn2an  # 中文数字转阿拉伯数字

# 常见章节标题模式
CHAPTER_PATTERNS = [
    r"^第[零一二三四五六七八九十百千万\d]+章\s*[：:：]?\s*(.*)$",  # 第X章：标题
    r"^第[零一二三四五六七八九十百千万\d]+节\s*[：:：]?\s*(.*)$",  # 第X节：标题
    r"^Chapter\s+(\d+)\s*[：:：]?\s*(.*)$",  # Chapter X: Title
    r"^(\d+)[\.、]\s*(.*)$",  # 1. 标题
    r"^【第[零一二三四五六七八九十百千万\d]+章】\s*(.*)$",  # 【第X章】标题
]


def chinese_num_to_int(chinese_num: str) -> int:
    """
    将中文数字转换为阿拉伯数字（使用 cn2an 库）

    支持格式：
    - 一、二、三...九
    - 十、十一、十二...十九
    - 二十、二十一...九十九
    - 一百、一百零一...九百九十九
    - 一千、一千零一...九千九百九十九

    Args:
        chinese_num: 中文数字（如：一、十、百）

    Returns:
        int: 阿拉伯数字，解析失败返回 1
    """
    token = (chinese_num or "").strip()
    if not token:
        return 1

    # 纯数字直接返回
    if token.isdigit():
        try:
            return int(token)
        except ValueError:
            return 1

    # 使用 cn2an 库转换中文数字（smart 模式）
    try:
        return int(cn2an.cn2an(token, "smart"))
    except Exception:
        # 解析失败，返回默认值 1
        return 1


def extract_chapter_number(title_line: str) -> tuple[int, str]:
    """
    从章节标题行提取章节号和标题

    Args:
        title_line: 章节标题行

    Returns:
        Tuple[int, str]: (章节号, 标题)
    """
    for pattern in CHAPTER_PATTERNS:
        match = re.match(pattern, title_line.strip(), re.IGNORECASE)
        if match:
            groups = match.groups()

            # 第X章：标题 格式
            if "第" in pattern and "章" in pattern:
                # 提取章节号
                num_match = re.search(r"第([零一二三四五六七八九十百千万\d]+)章", title_line)
                if num_match:
                    num_str = num_match.group(1)
                    chapter_num = chinese_num_to_int(num_str)
                    title = groups[0] if groups else ""
                    return chapter_num, title.strip()

            # Chapter X: Title 格式
            elif "Chapter" in pattern or pattern.startswith(r"^(\d+)"):
                chapter_num = int(groups[0])
                title = groups[1] if len(groups) > 1 else ""
                return chapter_num, title.strip()

    # 默认返回
    return 0, title_line.strip()


def split_txt_by_chapter(
    file_path: str,
    encoding: str = "utf-8",
    min_chapter_length: int = 100,
) -> list[dict[str, any]]:
    """
    按章节分割 txt 文件

    Args:
        file_path: 文件路径
        encoding: 文件编码
        min_chapter_length: 最小章节长度（字符数）

    Returns:
        List[Dict]: 章节列表
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    with open(path, encoding=encoding) as f:
        content = f.read()

    lines = content.split("\n")
    chapters = []
    current_chapter = None
    current_content = []

    for line in lines:
        line = line.strip()
        if not line:
            if current_content:
                current_content.append("")
            continue

        # 检查是否是章节标题
        chapter_num, title = extract_chapter_number(line)

        if chapter_num > 0:
            # 保存上一章
            if current_chapter and current_content:
                content_text = "\n".join(current_content).strip()
                if len(content_text) >= min_chapter_length:
                    current_chapter["content"] = content_text
                    chapters.append(current_chapter)

            # 开始新章
            current_chapter = {
                "chapter_number": chapter_num,
                "title": title or f"第{chapter_num}章",
                "original_title_line": line,
            }
            current_content = []
        else:
            # 章节内容
            if current_chapter:
                current_content.append(line)

    # 保存最后一章
    if current_chapter and current_content:
        content_text = "\n".join(current_content).strip()
        if len(content_text) >= min_chapter_length:
            current_chapter["content"] = content_text
            chapters.append(current_chapter)

    return chapters


def parse_novel_chapters(
    file_path: str,
    encoding: str = "utf-8",
) -> dict[str, any]:
    """
    解析小说文件，提取章节信息

    Args:
        file_path: 文件路径
        encoding: 文件编码

    Returns:
        Dict: 解析结果
    """
    chapters = split_txt_by_chapter(file_path, encoding)

    # 推断小说标题（从文件名）
    path = Path(file_path)
    novel_title = path.stem

    return {
        "novel_title": novel_title,
        "chapters": chapters,
        "total_chapters": len(chapters),
        "source_file": str(path),
    }
