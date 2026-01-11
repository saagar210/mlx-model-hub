# Finance Projects
# Category for finance dashboard and budgeting tools

## Context
This folder contains projects related to personal finance tracking, budgeting, and investment analysis.

## Primary Project: Personal Finance Dashboard
A comprehensive finance tracker with:
- Transaction import (CSV from multiple banks)
- ML-powered categorization
- Investment tracking
- Monthly/yearly reports and insights

## Tech Stack (Planned)
- Backend: FastAPI + PostgreSQL
- Frontend: React
- ML: scikit-learn/XGBoost for categorization
- Infrastructure: Docker, managed PostgreSQL

## Data Sources
- Chase, Bank of America, Fidelity, Capital One
- ~10 credit cards, ~5 investment accounts

## Project-Specific Rules
- Security first: Never log sensitive financial data
- All amounts should use Decimal, not float
- Comprehensive test coverage required for transaction handling
- Use .env for all credentials (never commit secrets)
