"""Tests for wallet scoring algorithm."""
import pytest
from src.wallet.scoring import (
    calculate_win_rate,
    confidence_factor,
    compute_smart_score,
    classify_tier,
    should_unfollow,
)


class TestWinRate:
    def test_basic(self):
        assert calculate_win_rate(7, 10) == 70.0

    def test_zero_trades(self):
        assert calculate_win_rate(0, 0) == 0.0

    def test_perfect(self):
        assert calculate_win_rate(50, 50) == 100.0


class TestConfidenceFactor:
    def test_many_trades(self):
        assert confidence_factor(100, 20) == 1.0

    def test_few_trades(self):
        cf = confidence_factor(10, 20)
        assert 0 < cf < 1.0

    def test_zero(self):
        assert confidence_factor(0, 20) == 0.0


class TestSmartScore:
    def test_elite_wallet(self):
        result = compute_smart_score(
            wr_30d=90.0, wr_90d=85.0, total_trades=50, avg_roi_pct=15.0
        )
        assert result["smart_score"] >= 85

    def test_low_count_penalty(self):
        result_high = compute_smart_score(
            wr_30d=80.0, wr_90d=75.0, total_trades=100, avg_roi_pct=5.0
        )
        result_low = compute_smart_score(
            wr_30d=80.0, wr_90d=75.0, total_trades=10, avg_roi_pct=5.0
        )
        assert result_high["smart_score"] > result_low["smart_score"]

    def test_roi_cap(self):
        # Very high ROI should be capped
        result = compute_smart_score(
            wr_30d=70.0, wr_90d=65.0, total_trades=30, avg_roi_pct=500.0
        )
        assert result["roi_factor"] <= 1.3


class TestTierClassification:
    def test_elite(self):
        config = {"elite_threshold": 85, "smart_threshold": 70, "min_trades": 20}
        assert classify_tier(90, config) == "ELITE"
        assert classify_tier(85, config) == "ELITE"

    def test_smart(self):
        config = {"elite_threshold": 85, "smart_threshold": 70, "min_trades": 20}
        assert classify_tier(75, config) == "SMART"
        assert classify_tier(70, config) == "SMART"

    def test_watch(self):
        config = {"elite_threshold": 85, "smart_threshold": 70, "min_trades": 20}
        assert classify_tier(60, config) == "WATCH"


class TestUnfollow:
    def test_wr_drop(self):
        unfollow, reason = should_unfollow(
            current_wr=65, peak_wr=85, trailing_drop=15, consecutive_losses=0, max_consecutive=5
        )
        assert unfollow
        assert "dropped" in reason

    def test_consecutive_losses(self):
        unfollow, reason = should_unfollow(
            current_wr=80, peak_wr=85, trailing_drop=15, consecutive_losses=6, max_consecutive=5
        )
        assert unfollow

    def test_no_trigger(self):
        unfollow, _ = should_unfollow(
            current_wr=75, peak_wr=85, trailing_drop=15, consecutive_losses=2, max_consecutive=5
        )
        assert not unfollow
