"""
LLM 客户端（支持 Anthropic 和 OpenAI 兼容 API）
"""
import json
from dataclasses import dataclass
from typing import Any

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


class GeminiClient:
    """
    LLM API 客户端
    支持 Anthropic 和 OpenAI 兼容接口
    """

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        self.provider = provider or settings.LLM_PROVIDER
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.temperature = temperature or settings.LLM_TEMPERATURE

        if self.provider == "anthropic":
            self.api_key = api_key or settings.ANTHROPIC_API_KEY
            self.base_url = base_url or settings.ANTHROPIC_BASE_URL
            self.model = model or settings.ANTHROPIC_MODEL
        else:
            self.api_key = api_key or settings.OPENAI_API_KEY
            self.base_url = base_url or settings.OPENAI_BASE_URL
            self.model = model or settings.OPENAI_MODEL

        if not self.api_key:
            raise LLMAPIError(f"{self.provider.upper()}_API_KEY 环境变量未设置")

        # 初始化客户端
        self._init_client()

    def _init_client(self):
        """初始化 LLM 客户端"""
        if self.provider == "anthropic":
            # 智谱 Anthropic 兼容接口使用 httpx 直接调用
            import httpx
            self.client = httpx.Client(timeout=120.0)
        else:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs
    ) -> LLMResponse:
        """
        调用聊天补全接口

        Args:
            messages: 消息列表
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLMResponse: 响应对象
        """
        logger = get_logger(__name__)

        try:
            if self.provider == "anthropic":
                return self._call_anthropic(messages, system_prompt, temperature, max_tokens, logger)
            else:
                return self._call_openai(messages, system_prompt, temperature, max_tokens, logger, **kwargs)
        except Exception as e:
            log_error_with_context(e, f"{self.provider} API 调用失败", logger)
            raise LLMAPIError(f"API 调用失败: {str(e)}") from e

    def _call_anthropic(self, messages, system_prompt, temperature, max_tokens, logger) -> LLMResponse:
        """调用智谱 Anthropic 兼容 API"""
        logger.info(f"调用智谱 Anthropic API: {self.model}")

        # 构建请求
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
            "temperature": temperature or self.temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = self.client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["content"][0]["text"] if data.get("content") else ""
        usage = {
            "input_tokens": data.get("usage", {}).get("input_tokens", 0),
            "output_tokens": data.get("usage", {}).get("output_tokens", 0),
        }

        logger.info(f"智谱 API 调用成功，tokens: {usage}")

        return LLMResponse(
            content=content,
            usage=usage,
            model=data.get("model", self.model),
            finish_reason=data.get("stop_reason", "end_turn")
        )

    def _call_openai(self, messages, system_prompt, temperature, max_tokens, logger, **kwargs) -> LLMResponse:
        """调用 OpenAI 兼容 API"""
        logger.info(f"调用 OpenAI API: {self.model}")

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
            **kwargs
        )

        content = response.choices[0].message.content
        usage = response.usage.model_dump() if response.usage else {}

        logger.info(f"OpenAI API 调用成功，tokens: {usage}")

        return LLMResponse(
            content=content,
            usage=usage,
            model=response.model,
            finish_reason=response.choices[0].finish_reason
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
        required_fields: list[str]
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


# 全局客户端实例
_gemini_client = None


def get_gemini_client() -> GeminiClient:
    """获取全局 Gemini 客户端实例"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def call_gemini_api(
    messages: list[dict[str, str]],
    system_prompt: str | None = None,
    **kwargs
) -> LLMResponse:
    """
    便捷的 Gemini API 调用函数

    Args:
        messages: 消息列表
        system_prompt: 系统提示词
        **kwargs: 其他参数

    Returns:
        LLMResponse: 响应对象
    """
    client = get_gemini_client()
    return client.chat_completion(messages, system_prompt, **kwargs)
