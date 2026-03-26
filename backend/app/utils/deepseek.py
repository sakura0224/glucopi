import openai
import os
import json
from openai import APIConnectionError, RateLimitError, APIStatusError
from app.core.config import settings

KEY = settings.DEEPSEEK_API_KEY

class LLMConversation:
    def __init__(self, api_key=None, model="deepseek-chat", initial_system_message=None, **kwargs):
        if api_key:
            self.client = openai.OpenAI(base_url="https://api.deepseek.com", api_key=api_key, **kwargs)
        else:
            try:
                DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
                if not DEEPSEEK_API_KEY:
                    raise ValueError("DEEPSEEK_API_KEY 环境变量未设置。")
                self.client = openai.OpenAI(base_url="https://api.deepseek.com", api_key=DEEPSEEK_API_KEY, **kwargs)
            except openai.AuthenticationError as e:
                print(f"错误: DeepSeek API key 未找到或无效。请设置 DEEPSEEK_API_KEY 环境变量或在初始化时提供 api_key 参数。")
                print(f"详情: {e}")
                raise e

        self.model = model
        self.messages = []
        self.initial_system_message_content = initial_system_message

        if initial_system_message:
            self.add_message("system", initial_system_message)

    def add_message(self, role: str, content: str):
        if role not in ['system', 'user', 'assistant', 'tool']:
             print(f"警告: 不支持的消息角色 '{role}'。消息未添加到历史。")
             return
        self.messages.append({"role": role, "content": content})

    def add_user_message(self, content: str):
        self.add_message("user", content)

    def add_assistant_message(self, content: str):
        self.add_message("assistant", content)

    def get_history(self):
        return self.messages[:]

    def reset_history(self):
        print("重置对话历史...")
        self.messages = []
        if self.initial_system_message_content:
            self.add_message("system", self.initial_system_message_content)
        print("历史已重置。")

    # --- 新增的非流式方法 ---
    def chat_non_stream(self, user_message=None, model=None, **params):
        """
        调用OpenAI API生成回复 (非流式)。
        回复会添加到对话历史中。

        Returns:
            str: 模型生成的文本回复。
        """
        if user_message:
            self.add_user_message(user_message)

        current_model = model if model else self.model

        try:
            api_params = {
                "model": current_model,
                "messages": self.messages,
                "stream": False, # 明确设置为 False
                **params
            }

            # print("Calling API (Non-Stream)...") # 现在这个打印会执行了

            response = self.client.chat.completions.create(**api_params)

            assistant_response = response.choices[0].message

            if assistant_response.content:
                self.add_assistant_message(assistant_response.content)
            # else: # Consider handling tool calls etc. if needed
            #     pass

            return assistant_response.content

        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            print(f"API错误: {e}")
            raise e
        except Exception as e:
            print(f"发生了一个意外错误: {e}")
            raise e

    # --- 新增的流式方法 ---
    def chat_stream(self, user_message=None, model=None, **params):
        """
        调用OpenAI API生成回复 (流式)。
        返回一个生成器， yield 模型生成的文本片段。
        完整的回复会在流结束后添加到对话历史中。

        Returns:
            iterator: 一个生成器， yielding 模型生成的文本片段 (str)。
        """
        if user_message:
            self.add_user_message(user_message)

        current_model = model if model else self.model

        try:
            api_params = {
                "model": current_model,
                "messages": self.messages,
                "stream": True, # 明确设置为 True
                **params
            }

            # print("Calling API (Stream)...") # 现在这个打印会执行了

            stream_response = self.client.chat.completions.create(**api_params)

            full_response_content = ""
            # This is the generator that will be returned and iterated over
            for chunk in stream_response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response_content += content
                    yield content # This is where the generator yields

            # After the loop finishes, add the complete response to history
            if full_response_content:
                self.add_assistant_message(full_response_content)
            # Note: Generators implicitly return None or StopIteration at the end

        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            print(f"API错误: {e}")
            # If an error occurs during streaming, raise it.
            # The generator will be closed by the caller's loop handling.
            raise e
        except Exception as e:
            print(f"发生了一个意外错误: {e}")
            raise e


# --- 示例用法 if __name__ == "__main__" ---

if __name__ == "__main__":
    print("--- 示例 (改进版类): 基本非流式对话 ---")
    try:
        conversation_improved_basic = LLMConversation(
            initial_system_message="你是一个友善且乐于助人的通用AI助手。",
            api_key=KEY, # 或者使用环境变量 OPENAI_API_KEY
        )

        print("\n用户: 你好，请介绍一下自己。")
        # 调用新的非流式方法
        response1_improved = conversation_improved_basic.chat_non_stream("你好，请介绍一下自己。")
        print("AI助手:", response1_improved) # 直接打印字符串结果

        print("\n--- 当前历史 ---")
        for msg in conversation_improved_basic.get_history():
            print(f"{msg['role'].capitalize()}: {msg['content'][:80]}...")

    except Exception as e:
         print(f"改进版示例 1 发生错误: {e}")

    print("-" * 30)

    print("\n--- 示例 (改进版类): 使用流式输出 ---")
    try:
        conversation_improved_stream = LLMConversation(
             model="deepseek-chat",
             initial_system_message="你是一个富有想象力的故事作家。",
             api_key=KEY,
        )

        print("\n用户: 给我写一个关于一只会飞的猫的短故事。")
        user_input_stream_improved = "给我写一个关于一只会飞的猫的短故事。"
        print("AI助手 (流式输出): ", end="")

        # 调用新的流式方法
        stream_generator_improved = conversation_improved_stream.chat_stream(
            user_message=user_input_stream_improved,
            max_tokens=150,
            temperature=0.8 # 可以传递参数
        )

        # 迭代生成器
        full_streamed_response_improved = ""
        for chunk in stream_generator_improved:
            print(chunk, end="")
            full_streamed_response_improved += chunk
        print()

        print("\n--- 更新后的历史 (流式) ---")
        for msg in conversation_improved_stream.get_history():
             print(f"{msg['role'].capitalize()}: {msg['content'][:80]}...")

    except Exception as e:
         print(f"改进版示例 2 发生错误: {e}")

    print("-" * 30)

    # 示例：传入参数（非流式）
    print("\n--- 示例 (改进版类): 传入参数 (非流式) ---")
    try:
        conversation_improved_params = LLMConversation(
             model="deepseek-chat", # 或 gpt-3.5-turbo
             initial_system_message="你是一个严格按照JSON格式输出的AI助手。请只输出JSON。",
             api_key=KEY
        )
        print("\n用户: 将我喜欢的颜色和水果转为JSON：颜色是蓝色，水果是苹果和香蕉。")
        user_input_json_improved = "将我喜欢的颜色和水果转为JSON：颜色是蓝色，水果是苹果和香蕉。"
        response_json_improved = conversation_improved_params.chat_non_stream(
            user_message=user_input_json_improved,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        print("AI助手 (JSON):", response_json_improved)
        try:
            parsed_json_improved = json.loads(response_json_improved)
            print("解析后的JSON:", parsed_json_improved)
        except json.JSONDecodeError:
            print("警告: 输出不是有效JSON。")

    except Exception as e:
        print(f"改进版示例 3 发生错误: {e}")

    print("-" * 30)