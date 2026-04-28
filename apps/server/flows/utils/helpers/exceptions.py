"""
自定义异常类
"""


class DeepNovelException(Exception):
    """基础异常类"""
    pass


class LLMAPIError(DeepNovelException):
    """LLM API 调用错误"""
    pass


class ValidationError(DeepNovelException):
    """数据验证错误"""
    pass


class FileProcessingError(DeepNovelException):
    """文件处理错误"""
    pass


class DatabaseError(DeepNovelException):
    """数据库操作错误"""
    pass
