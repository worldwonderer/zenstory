"""
i18n 基础设施
用于解析语言偏好和获取国际化消息
"""


from fastapi import Header

SUPPORTED_LANGUAGES: list[str] = ['zh', 'en']
DEFAULT_LANGUAGE: str = 'zh'


def get_accept_language(accept_language: str = Header(None)) -> str:
    """
    FastAPI 依赖函数,从 Accept-Language 头部解析语言代码

    Args:
        accept_language: Accept-Language 头部值,格式如 "zh-CN,zh;q=0.9,en;q=0.8"

    Returns:
        支持的语言代码 ('zh' 或 'en'),如果不支持或未提供则返回 DEFAULT_LANGUAGE

    Examples:
        >>> get_accept_language("zh-CN,zh;q=0.9,en;q=0.8")
        'zh'
        >>> get_accept_language("en-US,en;q=0.9")
        'en'
        >>> get_accept_language("fr-FR,fr;q=0.9")
        'zh'  # 不支持的语言返回默认值
        >>> get_accept_language(None)
        'zh'  # 未提供时返回默认值
    """
    if not accept_language:
        return DEFAULT_LANGUAGE

    # 解析 Accept-Language 头部
    # 格式: "zh-CN,zh;q=0.9,en;q=0.8" 或 "en-US,en"
    languages = accept_language.split(',')

    for language in languages:
        # 移除权重参数 (q=0.9)
        lang_code = language.split(';')[0].strip().lower()

        # 提取主要语言代码 (zh-CN -> zh, en-US -> en)
        primary_lang = lang_code.split('-')[0]

        # 检查是否支持
        if primary_lang in SUPPORTED_LANGUAGES:
            return primary_lang

    # 如果没有支持的语言,返回默认值
    return DEFAULT_LANGUAGE
