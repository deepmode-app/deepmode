# app/ai_config.py

import os

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_EMAIL_ENABLED = os.getenv("AI_EMAIL_ENABLED", "true").lower() == "true"

# OpenAI API endpoint
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Model configuration
OPENAI_MODEL = "gpt-4o-mini"  # Light but strong model
OPENAI_TEMPERATURE = 0.7
OPENAI_MAX_TOKENS_WEEKLY = 1200
OPENAI_MAX_TOKENS_DAILY = 400

