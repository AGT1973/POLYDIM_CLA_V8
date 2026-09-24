#!/usr/bin/env python3
"""
openrouter_cerebras_router.py
Router Inteligente de Inferencia y Monitoreo de Cuotas (POLYDIM V772)
- Monitorea el balance de OpenRouter vía Credits API
- Conmuta a Cerebras WSE (gpt-oss-120b) o AI Studio (Gemini) ante HTTP 402/403 o saldo <= 0
"""

import os
import json
import urllib.request
import urllib.error

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "")

def check_openrouter_balance(api_key: str = None) -> dict:
    key = api_key or OPENROUTER_API_KEY
    if not key:
        return {"status": "NO_KEY", "action": "USE_CEREBRAS_DIRECT"}

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {key}", "User-Agent": "POLYDIM_Router/7.72"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            credits_data = data.get("data", {})
            total_credits = credits_data.get("total_credits", 0.0)
            total_usage = credits_data.get("total_usage", 0.0)
            remaining = total_credits - total_usage
            return {
                "status": "POSITIVO" if remaining > 0 else "SALDO_AGOTADO",
                "remaining_usd": remaining,
                "total_credits": total_credits,
                "total_usage": total_usage,
                "action": "NORMAL" if remaining > 0 else "ACTIVAR_CEREBRAS_FALLBACK"
            }
    except urllib.error.HTTPError as e:
        if e.code in (402, 403):
            return {"status": "SALDO_AGOTADO_O_FORBIDDEN", "http_code": e.code, "action": "ACTIVAR_CEREBRAS_FALLBACK"}
        return {"status": "ERROR_HTTP", "http_code": e.code, "action": "ACTIVAR_CEREBRAS_FALLBACK"}
    except Exception as ex:
        return {"status": "ERROR_CONEXION", "error": str(ex), "action": "ACTIVAR_CEREBRAS_FALLBACK"}

def get_active_inference_endpoint(openrouter_key: str = None) -> dict:
    balance_info = check_openrouter_balance(openrouter_key)
    if balance_info.get("action") == "NORMAL":
        return {
            "provider": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "deepseek/deepseek-r1",
            "balance_info": balance_info
        }
    else:
        return {
            "provider": "Cerebras_WSE",
            "base_url": "https://api.cerebras.ai/v1",
            "model": "gpt-oss-120b",
            "reason": balance_info.get("status"),
            "speed_tok_s": 3000
        }

if __name__ == "__main__":
    endpoint = get_active_inference_endpoint()
    print("=== POLYDIM V772 INFERENCE ROUTING STATUS ===")
    print(json.dumps(endpoint, indent=2))
