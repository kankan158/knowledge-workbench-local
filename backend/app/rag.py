from __future__ import annotations

import os
import re
import math
from typing import Any, Dict, List, Optional

import requests


class DeepSeekRAG:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").strip()
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_answer(self, question: str, context_documents: List[Dict[str, object]]) -> str:
        if not self.is_configured():
            return self._fallback_answer(question, context_documents)

        context_text = self._format_context(context_documents)
        prompt = self._build_prompt(question, context_text)

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant. Answer questions based on the provided context. If the context doesn't contain relevant information, say so clearly."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
                timeout=30,
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return self._fallback_answer(question, context_documents)

    def _format_context(self, documents: List[Dict[str, object]]) -> str:
        if not documents:
            return "No relevant documents found."

        lines = ["Based on the following sources:\n"]
        for index, doc in enumerate(documents[:5], 1):
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:300]
            source = doc.get("source", "unknown")
            lines.append(f"\n[{index}] {title}")
            lines.append(f"Source: {source}")
            lines.append(f"Content: {content}...")
        return "\n".join(lines)

    def _build_prompt(self, question: str, context: str) -> str:
        return f"""{context}

---

Question: {question}

Based on the sources above, provide a concise answer. If the sources don't contain relevant information, say so."""

    def _fallback_answer(self, question: str, documents: List[Dict[str, object]]) -> str:
        if not documents:
            return "No relevant documents were found. Please add documents to your knowledge base first."

        # Sentence-level extraction using simple token-overlap scoring.
        def tokenize(text: str) -> List[str]:
            return [t for t in re.findall(r"[\w\u4e00-\u9fff]+", text.lower())]

        query_tokens = set(tokenize(question))
        ranked: list[tuple[float, str, str]] = []  # (score, title, formatted_sentence_source)

        for doc in documents:
            title = doc.get("title", "Untitled")
            source = doc.get("source", "unknown")
            content = doc.get("content", "") or ""
            # Split into sentences by punctuation and newlines
            sentences = re.split(r"(?<=[。.!?\n])\s*", content)
            for sent in sentences:
                s = sent.strip()
                if not s:
                    continue
                tokens = tokenize(s)
                if not tokens:
                    continue
                overlap = query_tokens.intersection(tokens)
                score = len(overlap) / math.sqrt(len(tokens) * max(1, len(query_tokens)))
                # Boost short exact matches modestly
                if len(overlap) >= max(1, len(query_tokens) // 2):
                    score += 0.2
                if score > 0:
                    snippet = s.replace("\n", " ")
                    if len(snippet) > 300:
                        snippet = snippet[:300].rstrip() + "..."
                    formatted = f"{snippet} — {source}"
                    ranked.append((score, title, formatted))

        if not ranked:
            # fallback to short excerpt per document (previous behavior)
            top_docs = documents[:5]
            lines: list[str] = ["Found the following excerpts (no clear sentence-level matches):"]
            for idx, doc in enumerate(top_docs, start=1):
                title = doc.get("title", "Untitled")
                source = doc.get("source", "unknown")
                content = (doc.get("content", "") or "").replace("\n", " ")[:300]
                if len(doc.get("content", "")) > 300:
                    content = content.rstrip() + "..."
                lines.append(f"\n[{idx}] {title} — {source}\n\"{content}\"")
            lines.append("\nEnable DEEPSEEK_API_KEY for synthesized answers.")
            return "\n".join(lines)

        # sort and return top few unique title+snippet entries
        ranked.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        out_lines: list[str] = ["Most relevant sentences found:"]
        for score, title, formatted in ranked:
            if formatted in seen:
                continue
            seen.add(formatted)
            out_lines.append(f"\n{title}: \"{formatted}\"")
            if len(out_lines) >= 6:
                break

        out_lines.append("\nFor a single synthesized answer, set DEEPSEEK_API_KEY to enable model synthesis.")
        return "\n".join(out_lines)
