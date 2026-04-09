import logging
import os

from sqlalchemy.orm import Session

from app.models.db import RuleModel
from app.models.schemas import CATEGORIES

logger = logging.getLogger(__name__)


class CategorizationEngine:
    """Categorizes transaction descriptions using rules first, LLM fallback second."""

    def categorize(self, description: str, db: Session) -> str:
        # 1. Query rules ordered by priority DESC, return first match
        rules = db.query(RuleModel).order_by(RuleModel.priority.desc()).all()
        for rule in rules:
            if rule.pattern.lower() in description.lower():
                return rule.category

        # 2. No rule matched — try LLM fallback
        return self._llm_fallback(description)

    def _llm_fallback(self, description: str) -> str:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            categories_str = ", ".join(CATEGORIES)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a personal finance categorization assistant. "
                            f"Classify the transaction description into exactly one of these categories: {categories_str}. "
                            f"Reply with only the category name, nothing else."
                        ),
                    },
                    {"role": "user", "content": description},
                ],
                max_tokens=20,
                temperature=0,
            )
            category = response.choices[0].message.content.strip()
            if category in CATEGORIES:
                return category
            logger.warning("LLM returned invalid category %r for %r, defaulting to Other", category, description)
            return "Other"
        except Exception as exc:
            logger.warning("LLM fallback failed for %r: %s", description, exc)
            return "Other"
