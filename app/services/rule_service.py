from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.db import RuleModel


def create_rule(pattern: str, category: str, priority: int, db: Session) -> RuleModel:
    rule = RuleModel(
        pattern=pattern,
        category=category,
        priority=priority,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session) -> list[RuleModel]:
    return db.query(RuleModel).order_by(RuleModel.priority.desc()).all()


def delete_rule(rule_id: int, db: Session) -> bool:
    rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def upsert_rule_for_correction(description: str, category: str, db: Session) -> RuleModel:
    """Create or update a rule mapping description → category (used by correction endpoint)."""
    existing = db.query(RuleModel).filter(RuleModel.pattern == description).first()
    if existing:
        existing.category = category
        existing.created_at = datetime.now(timezone.utc).isoformat()
        db.commit()
        db.refresh(existing)
        return existing
    return create_rule(pattern=description, category=category, priority=0, db=db)
