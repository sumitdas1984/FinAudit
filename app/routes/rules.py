from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import Rule
from app.services.rule_service import create_rule, delete_rule, list_rules

router = APIRouter()


class RuleCreate(BaseModel):
    pattern: str
    category: str
    priority: int


@router.get("/rules")
def get_rules(db: Session = Depends(get_db)):
    rules = list_rules(db)
    return [
        Rule(
            id=r.id,
            pattern=r.pattern,
            category=r.category,
            priority=r.priority,
            created_at=r.created_at,
        ).model_dump()
        for r in rules
    ]


@router.post("/rules", status_code=201)
def post_rule(body: RuleCreate, db: Session = Depends(get_db)):
    rule = create_rule(body.pattern, body.category, body.priority, db)
    return Rule(
        id=rule.id,
        pattern=rule.pattern,
        category=rule.category,
        priority=rule.priority,
        created_at=rule.created_at,
    ).model_dump()


@router.delete("/rules/{rule_id}", status_code=204)
def remove_rule(rule_id: int, db: Session = Depends(get_db)):
    found = delete_rule(rule_id, db)
    if not found:
        return JSONResponse(
            status_code=404,
            content={"error": "rule_not_found", "id": rule_id},
        )
    return Response(status_code=204)
