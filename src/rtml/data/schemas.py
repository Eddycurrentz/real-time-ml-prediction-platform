"""Validated contracts for transaction events and labelled training rows."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

MerchantCategory = Literal[
    "grocery", "travel", "electronics", "dining", "utilities", "gambling", "other"
]
TransactionType = Literal["purchase", "withdrawal", "transfer", "refund"]
PaymentMethod = Literal["card", "bank_transfer", "wallet"]
DeviceType = Literal["mobile", "desktop", "pos", "atm"]


class TransactionEvent(BaseModel):
    """Online transaction contract; labelled fields are deliberately forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: UUID4
    timestamp: datetime
    customer_id: str = Field(..., min_length=1, max_length=128)
    amount: float = Field(..., gt=0, allow_inf_nan=False)
    merchant_category: MerchantCategory
    transaction_type: TransactionType
    payment_method: PaymentMethod
    customer_age: int | None = Field(default=None, ge=18, le=100)
    account_age_days: int = Field(..., ge=0)
    transaction_count_24h: int = Field(..., ge=0)
    average_transaction_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    location: str | None = Field(default=None, min_length=1, max_length=64)
    device_type: DeviceType | None = None
    previous_failed_transactions: int = Field(..., ge=0)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("timestamp must include a UTC timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def timestamp_must_not_be_far_in_future(self) -> "TransactionEvent":
        if self.timestamp > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("timestamp is more than five minutes in the future")
        return self


class TrainingRecord(TransactionEvent):
    """Offline row with a label; never accepted by the online event contract."""

    is_anomaly: bool
