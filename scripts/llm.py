"""
LLM-абстракция: ollama / openrouter / claude
Единая точка входа: ask(prompt, image_b64=None) -> str

Провайдер выбирается через LLM_PROVIDER (default: ollama).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).parent.parent / '.env')

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:4b')

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')


def ask(prompt: str, *, image_b64: str | None = None) -> str:
    provider = LLM_PROVIDER.lower()
    if provider == 'ollama':
        return _ask_ollama(prompt, image_b64=image_b64)
    elif provider == 'openrouter':
        return _ask_openrouter(prompt, image_b64=image_b64)
    elif provider == 'claude':
        return _ask_claude(prompt, image_b64=image_b64)
    else:
        raise ValueError(f'Unknown LLM_PROVIDER: {LLM_PROVIDER!r}. Use: ollama | openrouter | claude')


def _ask_ollama(prompt: str, *, image_b64: str | None = None) -> str:
    payload: dict = {
        'model': OLLAMA_MODEL,
        'prompt': prompt,
        'stream': False,
        'format': 'json',
    }
    if image_b64:
        payload['images'] = [image_b64]

    resp = requests.post(f'{OLLAMA_URL}/api/generate', json=payload, timeout=120)
    resp.encoding = 'utf-8'
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        raise RuntimeError(resp.text)

    return resp.json()['response']


def _ask_openrouter(prompt: str, *, image_b64: str | None = None) -> str:
    if image_b64:
        content = [
            {'type': 'text', 'text': prompt},
            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_b64}'}},
        ]
    else:
        content = prompt

    payload = {
        'model': OPENROUTER_MODEL,
        'messages': [{'role': 'user', 'content': content}],
        'response_format': {'type': 'json_object'},
    }

    resp = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        json=payload,
        headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
        timeout=120,
    )
    resp.encoding = 'utf-8'
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        raise RuntimeError(resp.text)

    return resp.json()['choices'][0]['message']['content']


def _ask_claude(prompt: str, *, image_b64: str | None = None) -> str:
    if image_b64:
        content = [
            {
                'type': 'image',
                'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': image_b64},
            },
            {'type': 'text', 'text': prompt},
        ]
    else:
        content = [{'type': 'text', 'text': prompt}]

    payload = {
        'model': ANTHROPIC_MODEL,
        'max_tokens': 1024,
        'messages': [{'role': 'user', 'content': content}],
    }

    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        json=payload,
        headers={
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
        },
        timeout=120,
    )
    resp.encoding = 'utf-8'
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        raise RuntimeError(resp.text)

    return resp.json()['content'][0]['text']
