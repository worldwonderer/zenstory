"""
Voice Recognition API endpoints

使用腾讯云 ASR 实现语音识别功能
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time

from fastapi import APIRouter, status
from pydantic import BaseModel

from core.error_codes import ErrorCode
from core.error_handler import APIException
from utils.logger import get_logger, log_with_context

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
logger = get_logger(__name__)


# Request/Response schemas
class VoiceRecognizeRequest(BaseModel):
    """语音识别请求"""
    audio_data: str  # Base64 编码的音频数据
    audio_format: str = "wav"  # wav, pcm, mp3, m4a, flac, ogg-opus
    sample_rate: int = 16000  # 采样率: 8000 或 16000
    language: str = "zh"  # zh | en (also accepts zh-CN/en-US)


class VoiceRecognizeResponse(BaseModel):
    """语音识别响应"""
    text: str
    success: bool
    error: str | None = None
    duration_ms: int | None = None  # 音频时长（毫秒）


def get_tencent_credentials():
    """获取腾讯云凭证"""
    secret_id = os.getenv("TENCENT_SECRET_ID")
    secret_key = os.getenv("TENCENT_SECRET_KEY")

    if not secret_id or not secret_key:
        raise APIException(
            error_code=ErrorCode.VOICE_CREDENTIALS_NOT_CONFIGURED,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return secret_id, secret_key


def generate_tencent_signature(
    secret_key: str,
    method: str,
    endpoint: str,
    payload: str,  # 改为直接接收已序列化的JSON字符串
    timestamp: int
) -> str:
    """
    生成腾讯云 API v3 签名

    参考文档: https://cloud.tencent.com/document/api/1093/35641

    注意: payload 必须是已序列化的JSON字符串，与实际发送的请求体完全一致
    """
    # 规范请求串
    http_request_method = method.upper()
    canonical_uri = "/"
    canonical_querystring = ""

    # 按字母顺序排序的请求头 (content-type 在 host 之前)
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{endpoint}\n"
    signed_headers = "content-type;host"

    # 请求体哈希 - 直接使用传入的payload字符串
    hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical_request = (
        f"{http_request_method}\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{hashed_request_payload}"
    )

    # 待签名字符串
    algorithm = "TC3-HMAC-SHA256"
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    service = "asr"
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

    string_to_sign = (
        f"{algorithm}\n"
        f"{timestamp}\n"
        f"{credential_scope}\n"
        f"{hashed_canonical_request}"
    )

    # 计算签名
    def sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, service)
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return signature, credential_scope, signed_headers, algorithm


async def call_tencent_asr(
    audio_data: str,
    audio_format: str,
    sample_rate: int,
    secret_id: str,
    secret_key: str,
    language: str = "zh",
) -> dict:
    """
    调用腾讯云一句话识别 API

    参考文档: https://cloud.tencent.com/document/api/1093/37823
    """
    import httpx

    endpoint = "asr.tencentcloudapi.com"
    action = "SentenceRecognition"
    version = "2019-06-14"
    region = "ap-shanghai"
    timestamp = int(time.time())

    # 音频格式映射
    format_map = {
        "wav": "wav",
        "pcm": "pcm",
        "mp3": "mp3",
        "m4a": "m4a",
        "flac": "flac",
        "ogg-opus": "ogg-opus",
        "webm": "ogg-opus",  # WebM 通常使用 opus 编码
    }
    voice_format = format_map.get(audio_format.lower(), "wav")

    # Engine type (Tencent ASR)
    lang = (language or "").lower()
    if lang.startswith("en"):
        lang = "en"
    elif lang.startswith("zh"):
        lang = "zh"
    else:
        lang = "zh"

    engine_type = f"16k_{lang}" if sample_rate >= 16000 else f"8k_{lang}"

    # 计算音频数据长度
    try:
        # 清理Base64字符串（移除可能的空白字符和换行符）
        clean_audio_data = audio_data.strip().replace('\n', '').replace('\r', '')
        audio_bytes = base64.b64decode(clean_audio_data)
        data_len = len(audio_bytes)
    except Exception as e:
        raise APIException(
            error_code=ErrorCode.VOICE_AUDIO_DECODE_FAILED,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"音频数据 Base64 解码失败: {str(e)}"
        ) from e

    # 请求参数
    params = {
        "ProjectId": 0,
        "SubServiceType": 2,  # 一句话识别
        "EngSerViceType": engine_type,
        "SourceType": 1,  # 语音数据来源为语音数据
        "VoiceFormat": voice_format,
        "Data": clean_audio_data,  # 使用清理后的Base64字符串
        "DataLen": data_len,
        "FilterDirty": 0,  # 不过滤脏词
        "FilterModal": 0,  # 不过滤语气词
        "ConvertNumMode": 1,  # 数字转换为阿拉伯数字
    }

    # 关键：先序列化JSON，确保签名计算和请求发送使用完全相同的字符串
    # 腾讯云要求签名计算的payload与实际发送的body必须一字不差
    request_body = json.dumps(params, ensure_ascii=False, separators=(',', ':'))

    # 生成签名 - 传入已序列化的JSON字符串
    signature, credential_scope, signed_headers, algorithm = generate_tencent_signature(
        secret_key, "POST", endpoint, request_body, timestamp
    )

    # 构建 Authorization
    authorization = (
        f"{algorithm} "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    # 请求头
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": endpoint,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Region": region,
    }

    # 发送请求
    # 直接使用已序列化的request_body，确保与签名计算时使用的完全一致
    log_with_context(
        logger,
        logging.INFO,
        "腾讯云ASR请求",
        voice_format=voice_format,
        data_length=data_len,
        engine_type=engine_type,
        request_body_length=len(request_body),
        base64_length=len(clean_audio_data),
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://{endpoint}",
            headers=headers,
            content=request_body.encode("utf-8")
        )

        # 记录响应信息
        log_with_context(
            logger,
            logging.INFO,
            "腾讯云ASR响应",
            status_code=response.status_code,
        )

        if response.status_code != 200:
            log_with_context(
                logger,
                logging.ERROR,
                "腾讯云API请求失败",
                status_code=response.status_code,
                response=response.text[:500],  # Limit response length
            )
            raise APIException(
                error_code=ErrorCode.VOICE_API_REQUEST_FAILED,
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"腾讯云 API 请求失败: {response.status_code}"
            )

        return response.json()


@router.post("/recognize", response_model=VoiceRecognizeResponse)
async def recognize_voice(request: VoiceRecognizeRequest):
    """
    一句话语音识别

    将音频数据转换为文字，支持 60 秒以内的短音频。

    - **audio_data**: Base64 编码的音频数据
    - **audio_format**: 音频格式 (wav, pcm, mp3, m4a, flac, ogg-opus, webm)
    - **sample_rate**: 采样率 (8000 或 16000)
    """
    try:
        # 获取凭证
        secret_id, secret_key = get_tencent_credentials()

        # 调用腾讯云 API
        result = await call_tencent_asr(
            audio_data=request.audio_data,
            audio_format=request.audio_format,
            sample_rate=request.sample_rate,
            secret_id=secret_id,
            secret_key=secret_key,
            language=request.language,
        )

        # 解析响应
        response_data = result.get("Response", {})

        # 检查错误
        error = response_data.get("Error")
        if error:
            error_code = error.get("Code", "UnknownError")
            error_message = error.get("Message", "未知错误")
            return VoiceRecognizeResponse(
                text="",
                success=False,
                error=f"{error_code}: {error_message}"
            )

        # 获取识别结果
        recognized_text = response_data.get("Result", "")
        audio_duration = response_data.get("AudioDuration")

        return VoiceRecognizeResponse(
            text=recognized_text,
            success=True,
            duration_ms=int(audio_duration * 1000) if audio_duration else None
        )

    except APIException:
        raise
    except Exception as e:
        return VoiceRecognizeResponse(
            text="",
            success=False,
            error=f"语音识别失败: {str(e)}"
        )


@router.get("/status")
async def voice_status():
    """
    检查语音识别服务状态
    """
    secret_id = os.getenv("TENCENT_SECRET_ID")
    secret_key = os.getenv("TENCENT_SECRET_KEY")

    return {
        "configured": bool(secret_id and secret_key),
        "provider": "tencent",
        "service": "一句话识别",
        "max_duration_seconds": 60,
        "supported_formats": ["wav", "pcm", "mp3", "m4a", "flac", "ogg-opus", "webm"]
    }
