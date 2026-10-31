import math

from app.core.config import (
    AI_COST_PER_PHOTO_INR,
    PHOTO_REVIEW_FEE_MULTIPLIER,
    PHOTO_REVIEW_FEE_MAX,
    PHOTO_REVIEW_FEE_MIN,
)


def calculate_review_fee(photo_count: int) -> float:
    """
    Fee the renter pays to have the AI check rejected photos: a multiple of the
    estimated AI cost, rounded up to the next 5 INR, kept between a minimum and
    a maximum. The multiple is what discourages false rejections.
    """
    ai_cost = photo_count * AI_COST_PER_PHOTO_INR
    raw_fee = ai_cost * PHOTO_REVIEW_FEE_MULTIPLIER
    rounded_up = math.ceil(raw_fee / 5) * 5
    return float(min(PHOTO_REVIEW_FEE_MAX, max(PHOTO_REVIEW_FEE_MIN, rounded_up)))
