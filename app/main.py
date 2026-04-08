from fastapi import FastAPI

from app.models.database import engine
from app.models.db import Base
from app.routes import analytics, rules, transactions, upload

app = FastAPI(
    title="Personal Finance Audit",
    docs_url="/api/v1/docs",
    redoc_url=None,
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(upload.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
