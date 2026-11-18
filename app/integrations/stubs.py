"""Stubs for partner APIs that require a commercial contract.

Responses follow the public response shape of each real API so the stub can be
swapped for a real client without touching callers. Every payload carries
``"simulated": True``.
"""

from __future__ import annotations

from typing import Any


def sim_swap_retrieve_date(phone_number: str) -> dict[str, Any]:
    """CAMARA SIM Swap ``retrieve-date`` (GSMA Open Gateway)."""
    return {
        "simulated": True,
        "api": "CAMARA sim-swap/v1/retrieve-date",
        "phoneNumber": phone_number,
        "latestSimChange": "2026-11-17T14:02:00Z",
    }


def account_balance() -> dict[str, Any]:
    """Open Finance Brasil ``accounts/{id}/balances`` plus recent transactions."""
    return {
        "simulated": True,
        "api": "open-banking/accounts/v2/accounts/{accountId}/balances",
        "data": {"availableAmount": {"amount": "2318.40", "currency": "BRL"}},
        "transactions": [
            {"name": "Aposentadoria", "date": "25/10", "amount": 1621.00},
            {"name": "Farmácia", "date": "17/11", "amount": -48.90},
            {"name": "Conta de luz", "date": "10/11", "amount": -132.10},
        ],
    }
