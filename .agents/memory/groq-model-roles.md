---
name: Groq model roles
description: Distinguishes Groq classifier models from chat-capable models used by the agent graph.
---

Groq `meta-llama/*prompt-guard*` models are classifier-only models. Their response is a probability score, even when given a normal chat prompt, so they cannot be used for supervisor, writer, coder, or faithfulness calls.

**Why:** The writer accepted the classifier probability as `final_answer`, which made the UI display floating-point values instead of an answer.

**How to apply:** Keep `GROQ_MODEL` set to an account-accessible chat model and retain configuration validation that rejects model names containing `prompt-guard`.