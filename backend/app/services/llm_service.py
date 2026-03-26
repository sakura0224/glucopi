# app/services/llm_service.py

import openai
import logging  # 导入 logging 模块用于日志记录
from typing import Dict, Any, List, Optional  # 导入类型提示
from openai import APIConnectionError, RateLimitError, APIStatusError  # 导入 OpenAI API 错误类型

from app.core.config import settings  # 导入项目配置

# 配置 logger
logger = logging.getLogger(__name__)


# LLM 对话管理类
class LLMConversation:
    """
    管理单个用户与 LLM 的对话历史和 API 调用。
    支持非流式和流式生成。
    """

    def __init__(self, api_key: str, model: str = settings.LLM_MODEL_NAME, initial_system_message: Optional[str] = None, base_url: str = settings.LLM_API_BASE_URL, **kwargs):
        """
        初始化 LLM 对话实例。

        Args:
            api_key: 用于认证的 API 密钥。
            model: 使用的 LLM 模型名称。
            initial_system_message: 可选的初始系统消息。
            base_url: API 请求的基础 URL。
            **kwargs: 其他传递给 OpenAI 客户端的参数。
        """
        # 检查 API 密钥是否提供
        if not api_key:
            logger.error("初始化 LLMConversation 失败：API 密钥未提供。")
            raise ValueError("API 密钥必须提供。")

        try:
            # 初始化 OpenAI 客户端
            self.client = openai.OpenAI(
                base_url=base_url,
                api_key=api_key,
                **kwargs
            )
            logger.info(f"OpenAI 客户端初始化成功，Base URL: {base_url}")
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI 认证失败：API 密钥无效。详情: {e}")
            raise e
        except Exception as e:
            logger.error(f"初始化 OpenAI 客户端失败: {e}")
            raise e

        self.model = model  # 存储模型名称
        self.messages: List[Dict[str, str]] = []  # 存储对话历史消息列表
        self.initial_system_message_content = initial_system_message  # 存储初始系统消息内容

        # 如果提供了初始系统消息，添加到对话历史
        if initial_system_message:
            self.add_message("system", initial_system_message)

    # 添加消息到对话历史
    def add_message(self, role: str, content: str):
        """
        添加一条消息到对话历史。

        Args:
            role: 消息角色 ('system', 'user', 'assistant', 'tool')。
            content: 消息内容。
        """
        # 检查消息角色是否有效
        if role not in ['system', 'user', 'assistant', 'tool']:
            logger.warning(f"不支持的消息角色 '{role}'，消息未添加到历史。")
            return
        self.messages.append({"role": role, "content": content})
        # logger.debug(f"添加消息 ({role}): {content[:50]}...")

    # 添加用户消息到历史
    def add_user_message(self, content: str):
        """添加用户消息到对话历史"""
        self.add_message("user", content)

    # 添加助手消息到历史
    def add_assistant_message(self, content: str):
        """添加助手消息到对话历史"""
        self.add_message("assistant", content)

    # 获取当前对话历史
    def get_history(self) -> List[Dict[str, str]]:
        """返回当前对话历史的副本"""
        return self.messages[:]  # 返回副本，防止外部修改影响内部状态

    # 重置对话历史
    def reset_history(self):
        """清空当前对话历史，并重新添加初始系统消息（如果存在）"""
        logger.info("重置对话历史")
        self.messages = []
        if self.initial_system_message_content:
            self.add_message("system", self.initial_system_message_content)

    # 调用 LLM 生成非流式回复
    def chat_non_stream(self, user_message: Optional[str] = None, model: Optional[str] = None, **params) -> str:
        """
        调用 LLM API 生成非流式回复。
        将用户消息（如果提供）和助手回复添加到对话历史。

        Args:
            user_message: 本次请求的用户消息内容。
            model: 本次请求使用的模型名称（覆盖初始化时的设置）。
            **params: 其他传递给 API 的参数（如 temperature, max_tokens 等）。

        Returns:
            str: 模型生成的完整文本回复。

        Raises:
            Exception: API 错误或意外错误。
        """
        # 如果提供了用户消息，添加到历史
        if user_message:
            self.add_user_message(user_message)

        # 确定本次 API 调用使用的模型
        current_model = model if model else self.model
        if not current_model:
            logger.error("调用 LLM non-stream 失败：未指定模型名称。")
            raise ValueError("模型名称必须指定。")

        try:
            # 构造 API 请求参数
            api_params = {
                "model": current_model,
                "messages": self.messages,  # 使用当前的对话历史
                "stream": False,  # 明确指定非流式
                **params  # 合并其他参数
            }
            # logger.debug(f"调用 LLM non-stream API, 参数: {api_params}")

            # 调用 API 获取回复
            response = self.client.chat.completions.create(**api_params)
            assistant_response = response.choices[0].message  # 获取助手消息对象

            full_response_content = assistant_response.content  # 获取回复内容

            # 如果回复内容不为空，添加到对话历史
            if full_response_content:
                self.add_assistant_message(full_response_content)
                # logger.debug(f"LLM non-stream 回复已添加到历史: {full_response_content[:50]}...")
            # else: 可选：处理工具调用等非文本回复类型

            return full_response_content  # 返回完整的回复内容

        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            logger.error(f"LLM API 错误 (Non-Stream): {e}", exc_info=True)
            # 重新抛出异常，由调用方处理
            raise e
        except Exception as e:
            logger.error(f"调用 LLM non-stream 发生未预期错误: {e}", exc_info=True)
            # 重新抛出异常
            raise e

    # 调用 LLM 生成流式回复
    def chat_stream(self, user_message: Optional[str] = None, model: Optional[str] = None, **params):
        """
        调用 LLM API 生成流式回复。
        返回一个生成器，逐块 yield 模型生成的文本片段。
        流式结束后，将完整的回复添加到对话历史。

        Args:
            user_message: 本次请求的用户消息内容。
            model: 本次请求使用的模型名称（覆盖初始化时的设置）。
            **params: 其他传递给 API 的参数（如 temperature, max_tokens 等）。

        Yields:
            str: 模型生成的文本片段 (chunk)。

        Raises:
            Exception: API 错误或迭代过程中的未预期错误。
        """
        # 如果提供了用户消息，添加到历史
        if user_message:
            self.add_user_message(user_message)

        # 确定本次 API 调用使用的模型
        current_model = model if model else self.model
        if not current_model:
            logger.error("调用 LLM stream 失败：未指定模型名称。")
            raise ValueError("模型名称必须指定。")

        try:
            # 构造 API 请求参数
            api_params = {
                "model": current_model,
                "messages": self.messages,  # 使用当前的对话历史
                "stream": True,  # 明确指定流式
                **params  # 合并其他参数
            }
            # logger.debug(f"调用 LLM stream API, 参数: {api_params}")

            # 调用 API 获取流式响应
            stream_response = self.client.chat.completions.create(**api_params)

            full_response_content = ""  # 用于累积完整的回复内容
            # 迭代流式响应，逐块处理
            for chunk in stream_response:
                # 检查并提取文本内容
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response_content += content  # 累积内容
                    yield content  # 逐块 yield 给调用方 (chat_service)

            # 流式迭代完成后，将完整的回复添加到对话历史
            # 注意：如果迭代过程中发生异常，此行不会被执行，历史将不会添加不完整的回复
            if full_response_content:
                self.add_assistant_message(full_response_content)
                # logger.debug(f"LLM stream 完整回复已添加到历史: {full_response_content[:50]}...")

        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            logger.error(f"LLM API 错误 (Stream): {e}", exc_info=True)
            # 重新抛出异常，由调用方 (chat_service) 处理流式错误和保存
            raise e
        except Exception as e:
            logger.error(f"调用 LLM stream 发生未预期错误: {e}", exc_info=True)
            # 重新抛出异常
            raise e

# 注意：全局的 _conversations 字典和 get_llm_response 函数已移至 chat_service.py 管理


# 如果需要，可以在这里添加一些其他辅助函数，但核心逻辑都在 LLMConversation 类中
