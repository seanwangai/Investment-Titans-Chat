import requests
import logging
import streamlit as st

logger = logging.getLogger(__name__)


def generate_gemini_response(prompt, model_name, max_tokens=1000):
    """使用 Gemini API 生成回复"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": st.secrets["GOOGLE_API_KEY"]
        }
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_tokens
            }
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        if 'candidates' in result:
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            raise Exception(f"API 错误: {result}")
    except Exception as e:
        logger.error(f"Gemini API 错误: {str(e)}")
        raise
