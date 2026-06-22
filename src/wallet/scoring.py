"""Smart Wallet Scoring Algorithm.

Computes a composite score for each wallet based on:
- Win rate (30d weighted 60%, 90d weighted 40%)
- Confidence adjustment (trade count normalization)
- ROI factor
- Consistency (streak detection)

Output: smart_score (0-100), tier (ELITE / SMART / WATCH)
"""
import math


def calculate_win_rate(wins: int, total: int) -> float:
    """Calculate win rate as percentage."""
    if total == 0:
        return 0.0
    return (wins / total) * 100


def confidence_factor(total_trades: int, min_trades: int = 20) -> float:
    """Linear confidence: 0 → 1.0, reaching 1.0 at 50 trades."""
    return min(total_trades / max(min_trades * 2.5, 50), 1.0)


def compute_smart_score(
    wr_30d: float,
    wr_90d: float,
    total_trades: int,
    avg_roi_pct: float = 0.0,
    wr_30d_weight: float = 0.6,
    wr_90d_weight: float = 0.4,
) -> dict:
    """
    Compute the Smart Wallet Score.

    Formula:
      weighted_wr = wr_30d * 0.6 + wr_90d * 0.4
      confidence = min(total_trades / 50, 1.0)
      roi_factor = 1.0 + (avg_roi_pct / 100)  (capped [0.8, 1.3])
      smart_score = weighted_wr * confidence * roi_factor
    """
    weighted_wr = wr_30d * wr_30d_weight + wr_90d * wr_90d_weight
    confidence = confidence_factor(total_trades)

    # ROI adjustment: cap between 0.8 and 1.3
    roi_factor = 1.0 + (avg_roi_pct / 100.0)
    roi_factor = max(0.8, min(1.3, roi_factor))

    raw_score = weighted_wr * confidence * roi_factor

    # Clamp to 0-100
    smart_score = max(0.0, min(100.0, raw_score))

    return {
        "weighted_wr": round(weighted_wr, 2),
        "confidence": round(confidence, 3),
        "roi_factor": round(roi_factor, 3),
        "smart_score": round(smart_score, 2),
    }


def classify_tier(smart_score: float, tier_config: dict) -> str:
    """Classify wallet into ELITE / SMART / WATCH based on score."""
    elite = tier_config.get("elite_threshold", 85)
    smart = tier_config.get("smart_threshold", 70)

    if smart_score >= elite:
        return "ELITE"
    elif smart_score >= smart:
        return "SMART"
    return "WATCH"


def should_unfollow(
    current_wr: float,
    peak_wr: float,
    trailing_drop: float = 15.0,
    consecutive_losses: int = 0,
    max_consecutive: int = 5,
) -> tuple[bool, str]:
    """Determine if a wallet should be auto-unfollowed."""
    if (peak_wr - current_wr) >= trailing_drop:
        return True, f"WR dropped {peak_wr - current_wr:.1f}% from peak {peak_wr:.1f}%"
    if consecutive_losses >= max_consecutive:
        return True, f"{consecutive_losses} consecutive losses"
    return False, ""
