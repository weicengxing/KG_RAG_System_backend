#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import textwrap
from typing import List, Optional, Tuple, Any, Dict

import requests

URL = "https://qidianai.xyz/api/user/chat/send"

CONFIG = {
   # 重点：大概率必须填。填你 DevTools 里请求头 satoken: 那串
   "satoken": "8d200f5a-6861-4d1a-9578-d8658bf0132f",
   "print_final": False,

   "payload": {
       "modelId": 32,
       "content": "你擅长什么",
       "sessionId": "f21d3a83-6b7f-4dad-b7f4-1ee749e6d81a",
       "attachments": [],
   },

   "wrap_width": 88,
   "print_stream": True,
   "timeout_sec": 300,

   # 出错时最多打印多少响应文本
   "max_error_body_chars": 3000,
}


def format_output(text: str, width: int) -> str:
   text = (text or "").strip()
   if not text:
       return ""
   return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def sse_event_blocks(resp):
   block: List[str] = []
   for raw in resp.iter_lines(decode_unicode=True):
       if raw is None:
           continue
       line = raw.rstrip("\r")
       if line == "":
           if block:
               yield block
               block = []
           continue
       block.append(line)
   if block:
       yield block


def parse_sse_block(lines: List[str]) -> Tuple[Optional[str], str]:
   event_type = None
   data_lines: List[str] = []
   for line in lines:
       if line.startswith("event:"):
           event_type = line.split(":", 1)[1].strip()
       elif line.startswith("data:"):
           data_lines.append(line.split(":", 1)[1].lstrip())
   return event_type, "\n".join(data_lines)


def _extract_text_from_json(obj: Any) -> Optional[str]:
   if obj is None:
       return None
   if isinstance(obj, str):
       return obj
   if isinstance(obj, (int, float, bool)):
       return str(obj)

   if isinstance(obj, dict):
       for key in ("content", "message", "text", "delta", "answer", "data"):
           if key in obj:
               val = obj[key]
               if isinstance(val, (dict, list)):
                   extracted = _extract_text_from_json(val)
                   if extracted:
                       return extracted
               elif val is not None:
                   return str(val)

       if "choices" in obj and isinstance(obj["choices"], list) and obj["choices"]:
           return _extract_text_from_json(obj["choices"][0])

   if isinstance(obj, list):
       parts: List[str] = []
       for item in obj:
           t = _extract_text_from_json(item)
           if t:
               parts.append(t)
       if parts:
           return "".join(parts)

   return None


def decode_data_text(data: str) -> str:
   s = (data or "").strip()
   if not s:
       return ""
   if s in ("[DONE]", "DONE"):
       return s

   if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
       try:
           obj = json.loads(s)
           extracted = _extract_text_from_json(obj)
           return extracted if extracted is not None else s
       except Exception:
           return data

   return data


def dump_http_error(resp: requests.Response) -> None:
   print(f"HTTP {resp.status_code} {resp.reason}", flush=True)
   ct = resp.headers.get("content-type", "")
   print(f"content-type: {ct}", flush=True)

   body = resp.text or ""
   body = body[: CONFIG["max_error_body_chars"]]
   if body.strip():
       print("---- response body (truncated) ----", flush=True)
       print(body, flush=True)
       print("---- end ----", flush=True)


def main() -> int:
   payload: Dict[str, Any] = CONFIG["payload"]
   if not payload.get("content"):
       raise SystemExit("ERROR: CONFIG['payload']['content'] 不能为空")
   if not payload.get("sessionId"):
       raise SystemExit("ERROR: CONFIG['payload']['sessionId'] 不能为空")

   satoken = (CONFIG.get("satoken") or "").strip()

   headers = {
       "Accept": "text/event-stream",
       "Content-Type": "application/json",
       "Origin": "https://qidianai.xyz",
       "Referer": "https://qidianai.xyz/desktop/chat",
       "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
       "Cache-Control": "no-cache",
       "Pragma": "no-cache",
   }

   # 关键：通常必须带鉴权
   if satoken:
       headers["satoken"] = satoken
       headers["Cookie"] = f"satoken={satoken}"

   chunks: List[str] = []

   try:
       with requests.post(
           URL,
           headers=headers,
           json=payload,
           stream=True,
           timeout=CONFIG["timeout_sec"],
       ) as resp:
           if resp.status_code >= 400:
               dump_http_error(resp)
               resp.raise_for_status()

           for block in sse_event_blocks(resp):
               event_type, data = parse_sse_block(block)
               text = decode_data_text(data)

               if (text or "").strip() in ("[DONE]", "DONE"):
                   break

               if event_type in (None, "message", "start"):
                   if event_type == "start":
                       continue
                   if text:
                       chunks.append(text)
                       if CONFIG["print_stream"]:
                           print(text, end="", flush=True)

   except requests.RequestException as e:
       raise SystemExit(f"Request failed: {e}")

   full = "".join(chunks)

    # A：只流式输出，不再最终重复打印
   if not CONFIG["print_stream"]:
       print(format_output(full, CONFIG["wrap_width"]))

   return 0



if __name__ == "__main__":
   raise SystemExit(main())
