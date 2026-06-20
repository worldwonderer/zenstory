"""DeepSeek LLM client for material and Prefect flows."""

import json
import os
from dataclasses import dataclass
from typing import Any

from agent.core.deepseek_client import DEEPSEEK_CHAT_MODEL, DEFAULT_DEEPSEEK_BASE_URL
from config.material_settings import material_settings as settings
from flows.utils.helpers.exceptions import LLMAPIError
from flows.utils.helpers.logging import get_logger, log_error_with_context


@dataclass
class LLMResponse:
    """LLM API 响应数据类"""

    content: str
    usage: dict[str, int]
    model: str
    finish_reason: str


class DeepSeekClient:
    """DeepSeek OpenAI-compatible LLM client for material flows."""

    def __init__(
        self,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.temperature = temperature or settings.LLM_TEMPERATURE
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
        self.model = DEEPSEEK_CHAT_MODEL

        if not self.api_key:
            raise LLMAPIError("DEEPSEEK_API_KEY 环境变量未设置")

        from openai import OpenAI

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """调用 DeepSeek OpenAI-compatible 聊天补全接口。"""
        logger = get_logger(__name__)

        try:
            return self._call_deepseek(messages, system_prompt, temperature, max_tokens, logger, **kwargs)
        except Exception as e:
            log_error_with_context(e, "DeepSeek API 调用失败", logger)
            raise LLMAPIError(f"API 调用失败: {str(e)}") from e

    def _call_deepseek(self, messages, system_prompt, temperature, max_tokens, logger, **kwargs) -> LLMResponse:
        """调用 DeepSeek OpenAI-compatible API。"""
        logger.info(f"调用 DeepSeek API: {self.model}")

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
            **kwargs,
        )

        content = response.choices[0].message.content or ""
        usage = response.usage.model_dump() if response.usage else {}

        logger.info(f"DeepSeek API 调用成功，tokens: {usage}")

        return LLMResponse(
            content=content,
            usage=usage,
            model=response.model,
            finish_reason=response.choices[0].finish_reason,
        )

    def extract_json_from_response(self, response: LLMResponse) -> dict[str, Any]:
        """
        从响应中提取 JSON 数据

        Args:
            response: LLM 响应对象

        Returns:
            解析后的 JSON 数据
        """
        content = response.content.strip()

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取代码块中的 JSON
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                json_str = content[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        # 尝试提取 {} 包围的 JSON
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            json_str = content[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        raise LLMAPIError(f"无法从响应中提取有效的 JSON: {content}")

    def validate_response_format(
        self,
        response: LLMResponse,
        required_fields: list[str],
    ) -> bool:
        """
        验证响应格式

        Args:
            response: LLM 响应对象
            required_fields: 必需字段列表

        Returns:
            是否符合格式要求
        """
        logger = get_logger(__name__)
        try:
            data = self.extract_json_from_response(response)

            # 检查必需字段
            for field in required_fields:
                if field not in data:
                    logger.warning(f"响应缺少必需字段: {field}")
                    return False

            return True

        except Exception as e:
            log_error_with_context(e, "响应格式验证失败", logger)
            return False


_deepseek_client: DeepSeekClient | None = None


def get_deepseek_client() -> DeepSeekClient:
    """获取全局 DeepSeek 客户端实例。"""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = DeepSeekClient()
    return _deepseek_client


def call_deepseek_api(
    messages: list[dict[str, str]],
    system_prompt: str | None = None,
    **kwargs,
) -> LLMResponse:
    """便捷的 DeepSeek API 调用函数。"""
    client = get_deepseek_client()
    return client.chat_completion(messages, system_prompt, **kwargs)
