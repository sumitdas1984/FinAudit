from sqlalchemy import Column, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TransactionModel(Base):
    __tablename__ = "transactions"

    id = Column(Text, primary_key=True)
    date = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(Text, nullable=False)
    is_reviewed = Column(Integer, nullable=False, default=0)


class RuleModel(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern = Column(Text, nullable=False, unique=True)
    category = Column(Text, nullable=False)
    priority = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False)
