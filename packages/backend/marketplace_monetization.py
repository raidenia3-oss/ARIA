"""Marketplace monetization for AURA."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Transaction:
    transaction_id: str
    app_id: str
    developer_id: str
    amount: float
    currency: str = "USD"
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)


class CommissionPolicy:
    """Política de comisiones."""

    def __init__(self, base_rate: float = 0.30, min_payout: float = 50.0) -> None:
        self.base_rate = base_rate
        self.min_payout = min_payout

    def calculate(self, amount: float) -> Dict[str, Any]:
        commission = round(amount * self.base_rate, 2)
        net = round(amount - commission, 2)
        return {
            "gross": amount,
            "commission_rate": self.base_rate,
            "commission": commission,
            "net": net,
            "currency": "USD",
        }


class PayoutManager:
    """Gestión de pagos a desarrolladores."""

    def __init__(self, policy: CommissionPolicy) -> None:
        self.policy = policy
        self.transactions: List[Transaction] = []
        self.balances: Dict[str, float] = {}

    def record_transaction(self, transaction: Transaction) -> Transaction:
        self.transactions.append(transaction)
        self.balances[transaction.developer_id] = round(self.balances.get(transaction.developer_id, 0.0) + transaction.amount, 2)
        return transaction

    def calculate_payout(self, developer_id: str) -> Dict[str, Any]:
        balance = self.balances.get(developer_id, 0.0)
        eligible = balance >= self.policy.min_payout
        return {
            "developer_id": developer_id,
            "balance": balance,
            "min_payout": self.policy.min_payout,
            "eligible": eligible,
            "currency": "USD",
        }

    def get_transactions(self, developer_id: str, limit: int = 50) -> List[Transaction]:
        return [t for t in self.transactions if t.developer_id == developer_id][-limit:]


class MarketplaceMonetization:
    """Orquestador de monetización."""

    def __init__(self) -> None:
        self.policy = CommissionPolicy()
        self.payouts = PayoutManager(self.policy)
        self.earnings: Dict[str, float] = {}

    def record_sale(self, app_id: str, developer_id: str, amount: float, metadata: Optional[Dict[str, Any]] = None) -> Transaction:
        tx = Transaction(
            transaction_id=f"tx-{int(time.time() * 1000)}",
            app_id=app_id,
            developer_id=developer_id,
            amount=amount,
            metadata=metadata or {},
        )
        tx.status = "completed"
        self.payouts.record_transaction(tx)
        self.earnings[app_id] = round(self.earnings.get(app_id, 0.0) + amount, 2)
        return tx

    def commission_estimate(self, amount: float) -> Dict[str, Any]:
        return self.policy.calculate(amount)

    def payout_status(self, developer_id: str) -> Dict[str, Any]:
        return self.payouts.calculate_payout(developer_id)

    def transaction_history(self, developer_id: str, limit: int = 50) -> Dict[str, Any]:
        txs = self.payouts.get_transactions(developer_id, limit=limit)
        return {
            "developer_id": developer_id,
            "count": len(txs),
            "transactions": [
                {
                    "transaction_id": tx.transaction_id,
                    "app_id": tx.app_id,
                    "amount": tx.amount,
                    "status": tx.status,
                    "created_at": tx.created_at,
                }
                for tx in txs
            ],
        }
