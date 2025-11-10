
import json, urllib.request

def lmstudio_describe(endpoint: str, model: str, path: str) -> str:
    prompt = "Give a concise 6-12 word description for this image filename. Avoid punctuation."
    body = {
        "model": model,
        "messages": [
            {"role":"system","content":"You are a precise captioning assistant."},
            {"role":"user","content": f"{prompt}\nImage path: {path}"}
        ],
        "temperature": 0.2,
        "max_tokens": 64
    }
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return "untitled"


import base64, os

def _b64_image(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""

def lmstudio_caption(endpoint: str, model: str, path: str, prompt: str, vision: bool=False) -> str:
    if vision:
        b64 = _b64_image(path)
        content = [{"type":"text","text":prompt}]
        if b64:
            content.append({"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64}})
        body = {"model": model, "messages":[{"role":"user","content": content}], "temperature":0.2, "max_tokens":128}
    else:
        body = {
            "model": model,
            "messages": [
                {"role":"system","content":"You produce dataset-quality image captions."},
                {"role":"user","content": f"{prompt}\nImage path: {path}"}
            ],
            "temperature": 0.2,
            "max_tokens": 128
        }
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""

def lmstudio_tags(endpoint: str, model: str, path: str, prompt: str, vision: bool=False) -> str:
    if vision:
        b64 = _b64_image(path)
        content = [{"type":"text","text":prompt}]
        if b64:
            content.append({"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64}})
        body = {"model": model, "messages":[{"role":"user","content": content}], "temperature":0.2, "max_tokens":128}
    else:
        body = {
            "model": model,
            "messages": [
                {"role":"system","content":"You output concise comma-separated tags only."},
                {"role":"user","content": f"{prompt}\nImage path: {path}"}
            ],
            "temperature": 0.2,
            "max_tokens": 64
        }
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""
