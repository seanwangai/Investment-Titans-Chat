import google.generativeai as genai
import asyncio
import streamlit as st
from vertexai.language_models import TextGenerationModel
import os
from google.cloud import aiplatform
from google.oauth2 import service_account
import requests
import json

# 设置 API key
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)


async def test_all_methods():
    prompt = "Explain how AI works in one paragraph"

    print("\n=== 开始测试所有 Gemini API 调用方法 ===\n")

    # 方法1: 使用 generate_text
    print("测试方法 1: genai.generate_text")
    try:
        response = genai.generate_text(
            model="gemini-1.5-flash",
            prompt=prompt,
            max_output_tokens=1000
        )
        print("✅ 成功! 响应:", response[:100], "...\n")
    except Exception as e:
        print("❌ 失败:", str(e), "\n")

    # 方法2: 使用 GenerativeModel
    print("测试方法 2: genai.GenerativeModel")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        print("✅ 成功! 响应:", response.text[:100], "...\n")
    except Exception as e:
        print("❌ 失败:", str(e), "\n")

    # 方法3: 使用 async generate_content
    print("测试方法 3: GenerativeModel async generate_content")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        print("✅ 成功! 响应:", response.text[:100], "...\n")
    except Exception as e:
        print("❌ 失败:", str(e), "\n")

    # 方法4: 使用 gemini-2.0-flash-exp
    print("测试方法 4: 使用 gemini-2.0-flash-exp")
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        print("✅ 成功! 响应:", response.text[:100], "...\n")
    except Exception as e:
        print("❌ 失败:", str(e), "\n")

    # 方法5: 使用 chat 模式
    print("测试方法 5: 使用 chat 模式")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        chat = model.start_chat()
        response = await chat.send_message_async(prompt)
        print("✅ 成功! 响应:", response.text[:100], "...\n")
    except Exception as e:
        print("❌ 失败:", str(e), "\n")

    print("=== 测试完成 ===")


def test_with_history():
    print("\n=== 测试带历史记录的对话 ===\n")

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        chat = model.start_chat(history=[])

        messages = [
            "Hello, I want to learn about investing",
            "What are the basic principles of value investing?",
            "Can you explain P/E ratio?"
        ]

        for msg in messages:
            print(f"\nUser: {msg}")
            response = chat.send_message(msg)
            print(f"Assistant: {response.text[:200]}...")

        print("\n✅ 历史记录测试成功!\n")
    except Exception as e:
        print(f"\n❌ 历史记录测试失败: {str(e)}\n")


def test_streaming():
    print("\n=== 测试流式响应 ===\n")

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            "Tell me a short story about AI",
            stream=True
        )

        print("Streaming response:")
        for chunk in response:
            print(chunk.text, end='', flush=True)
        print("\n\n✅ 流式响应测试成功!\n")
    except Exception as e:
        print(f"\n❌ 流式响应测试失败: {str(e)}\n")


def test_direct_api():
    print("\n=== 测试直接 API 调用 ===\n")

    # Gemini API 直接调用
    print("测试方法 6: 直接调用 Gemini API")
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GOOGLE_API_KEY
        }
        data = {
            "contents": [{
                "parts": [{
                    "text": "Explain how AI works in one paragraph"
                }]
            }]
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        if 'candidates' in result:
            text = result['candidates'][0]['content']['parts'][0]['text']
            print("✅ 成功! 响应:", text[:100], "...\n")
        else:
            print("❌ 响应格式不正确:", result, "\n")

    except Exception as e:
        print("❌ 失败:", str(e), "\n")

    # Gemini 2.0 API 直接调用
    print("测试方法 7: 直接调用 Gemini 2.0 API")
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GOOGLE_API_KEY
        }
        data = {
            "contents": [{
                "parts": [{
                    "text": "Explain how AI works in one paragraph"
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1000
            }
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        if 'candidates' in result:
            text = result['candidates'][0]['content']['parts'][0]['text']
            print("✅ 成功! 响应:", text[:100], "...\n")
        else:
            print("❌ 响应格式不正确:", result, "\n")

    except Exception as e:
        print("❌ 失败:", str(e), "\n")


if __name__ == "__main__":
    print("开始 Gemini API 测试...")

    # 运行异步测试
    asyncio.run(test_all_methods())

    # 运行历史记录测试
    test_with_history()

    # 运行流式响应测试
    test_streaming()

    # 运行直接 API 测试
    test_direct_api()
