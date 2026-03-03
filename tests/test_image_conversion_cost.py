"""Tests for image conversion cost estimation in wyby.render_warnings."""

from __future__ import annotations

import logging

import pytest

from wyby.render_warnings import (
    IMAGE_HEAVY_PIXEL_LIMIT,
    IMAGE_LIGHT_PIXEL_LIMIT,
    IMAGE_MODERATE_PIXEL_LIMIT,
    ImageConversionCost,
    check_image_conversion_warning,
    estimate_image_conversion_cost,
    log_image_conversion_cost,
)


# ---------------------------------------------------------------------------
# ImageConversionCost enum
# ---------------------------------------------------------------------------


class TestImageConversionCost:
    """Tests for the ImageConversionCost enum ordering and comparison."""

    def test_ordering(self) -> None:
        assert ImageConversionCost.LIGHT < ImageConversionCost.MODERATE
        assert ImageConversionCost.MODERATE < ImageConversionCost.HEAVY
        assert ImageConversionCost.HEAVY < ImageConversionCost.EXTREME

    def test_ge(self) -> None:
        assert ImageConversionCost.HEAVY >= ImageConversionCost.MODERATE
        assert ImageConversionCost.HEAVY >= ImageConversionCost.HEAVY
        assert not (ImageConversionCost.LIGHT >= ImageConversionCost.MODERATE)

    def test_le(self) -> None:
        assert ImageConversionCost.LIGHT <= ImageConversionCost.MODERATE
        assert ImageConversionCost.LIGHT <= ImageConversionCost.LIGHT
        assert not (ImageConversionCost.HEAVY <= ImageConversionCost.MODERATE)

    def test_gt(self) -> None:
        assert ImageConversionCost.EXTREME > ImageConversionCost.HEAVY
        assert not (ImageConversionCost.LIGHT > ImageConversionCost.LIGHT)

    def test_lt(self) -> None:
        assert ImageConversionCost.LIGHT < ImageConversionCost.HEAVY
        assert not (ImageConversionCost.HEAVY < ImageConversionCost.HEAVY)

    def test_comparison_with_non_enum_returns_not_implemented(self) -> None:
        assert ImageConversionCost.LIGHT.__ge__(42) is NotImplemented
        assert ImageConversionCost.LIGHT.__gt__(42) is NotImplemented
        assert ImageConversionCost.LIGHT.__le__(42) is NotImplemented
        assert ImageConversionCost.LIGHT.__lt__(42) is NotImplemented

    def test_values(self) -> None:
        assert ImageConversionCost.LIGHT.value == 0
        assert ImageConversionCost.MODERATE.value == 1
        assert ImageConversionCost.HEAVY.value == 2
        assert ImageConversionCost.EXTREME.value == 3


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------


class TestImageThresholdConstants:
    """Tests for image conversion threshold constants."""

    def test_thresholds_are_positive(self) -> None:
        assert IMAGE_LIGHT_PIXEL_LIMIT > 0
        assert IMAGE_MODERATE_PIXEL_LIMIT > 0
        assert IMAGE_HEAVY_PIXEL_LIMIT > 0

    def test_thresholds_are_ordered(self) -> None:
        assert (
            IMAGE_LIGHT_PIXEL_LIMIT
            < IMAGE_MODERATE_PIXEL_LIMIT
            < IMAGE_HEAVY_PIXEL_LIMIT
        )


# ---------------------------------------------------------------------------
# estimate_image_conversion_cost
# ---------------------------------------------------------------------------


class TestEstimateImageConversionCost:
    """Tests for estimate_image_conversion_cost()."""

    def test_small_sprite_is_light(self) -> None:
        """A 8x8 sprite (64 pixels) should be LIGHT."""
        assert (
            estimate_image_conversion_cost(8, 8)
            == ImageConversionCost.LIGHT
        )

    def test_16x16_is_moderate(self) -> None:
        """16x16 = 256 pixels, at the MODERATE boundary."""
        assert (
            estimate_image_conversion_cost(16, 16)
            == ImageConversionCost.MODERATE
        )

    def test_moderate_range(self) -> None:
        """A 20x20 sprite (400 pixels) is MODERATE."""
        assert (
            estimate_image_conversion_cost(20, 20)
            == ImageConversionCost.MODERATE
        )

    def test_32x32_is_heavy(self) -> None:
        """32x32 = 1024 pixels, at the HEAVY boundary."""
        assert (
            estimate_image_conversion_cost(32, 32)
            == ImageConversionCost.HEAVY
        )

    def test_heavy_range(self) -> None:
        """A 50x50 image (2500 pixels) is HEAVY."""
        assert (
            estimate_image_conversion_cost(50, 50)
            == ImageConversionCost.HEAVY
        )

    def test_64x64_is_extreme(self) -> None:
        """64x64 = 4096 pixels, at the EXTREME boundary."""
        assert (
            estimate_image_conversion_cost(64, 64)
            == ImageConversionCost.EXTREME
        )

    def test_large_image_is_extreme(self) -> None:
        """100x100 = 10000 pixels, clearly EXTREME."""
        assert (
            estimate_image_conversion_cost(100, 100)
            == ImageConversionCost.EXTREME
        )

    def test_1x1_is_light(self) -> None:
        """Minimum image is LIGHT."""
        assert (
            estimate_image_conversion_cost(1, 1)
            == ImageConversionCost.LIGHT
        )

    def test_alpha_coverage_reduces_effective_pixels(self) -> None:
        """With has_alpha and low coverage, cost should drop."""
        # 64x64 = 4096 pixels = EXTREME without alpha.
        # With 5% coverage: 204 effective pixels = LIGHT.
        assert (
            estimate_image_conversion_cost(
                64, 64, has_alpha=True, alpha_coverage=0.05
            )
            == ImageConversionCost.LIGHT
        )

    def test_alpha_coverage_ignored_without_has_alpha(self) -> None:
        """alpha_coverage should be ignored when has_alpha is False."""
        # 64x64 = 4096 pixels = EXTREME regardless of alpha_coverage.
        assert (
            estimate_image_conversion_cost(
                64, 64, has_alpha=False, alpha_coverage=0.01
            )
            == ImageConversionCost.EXTREME
        )

    def test_has_alpha_full_coverage_same_as_no_alpha(self) -> None:
        """has_alpha with 100% coverage is same cost as no alpha."""
        no_alpha = estimate_image_conversion_cost(40, 20)
        with_alpha = estimate_image_conversion_cost(
            40, 20, has_alpha=True, alpha_coverage=1.0
        )
        assert no_alpha == with_alpha

    def test_rejects_zero_width(self) -> None:
        with pytest.raises(ValueError, match="width must be >= 1"):
            estimate_image_conversion_cost(0, 10)

    def test_rejects_zero_height(self) -> None:
        with pytest.raises(ValueError, match="height must be >= 1"):
            estimate_image_conversion_cost(10, 0)

    def test_rejects_negative_width(self) -> None:
        with pytest.raises(ValueError, match="width must be >= 1"):
            estimate_image_conversion_cost(-5, 10)

    def test_rejects_negative_height(self) -> None:
        with pytest.raises(ValueError, match="height must be >= 1"):
            estimate_image_conversion_cost(10, -5)

    def test_rejects_alpha_coverage_below_zero(self) -> None:
        with pytest.raises(ValueError, match="alpha_coverage"):
            estimate_image_conversion_cost(
                10, 10, has_alpha=True, alpha_coverage=-0.1
            )

    def test_rejects_alpha_coverage_above_one(self) -> None:
        with pytest.raises(ValueError, match="alpha_coverage"):
            estimate_image_conversion_cost(
                10, 10, has_alpha=True, alpha_coverage=1.1
            )

    def test_alpha_coverage_boundary_zero(self) -> None:
        """alpha_coverage=0.0 should be accepted."""
        estimate_image_conversion_cost(
            10, 10, has_alpha=True, alpha_coverage=0.0
        )

    def test_alpha_coverage_boundary_one(self) -> None:
        """alpha_coverage=1.0 should be accepted."""
        estimate_image_conversion_cost(
            10, 10, has_alpha=True, alpha_coverage=1.0
        )


# ---------------------------------------------------------------------------
# check_image_conversion_warning
# ---------------------------------------------------------------------------


class TestCheckImageConversionWarning:
    """Tests for check_image_conversion_warning()."""

    def test_returns_none_for_light(self) -> None:
        assert check_image_conversion_warning(8, 8) is None

    def test_returns_none_for_moderate(self) -> None:
        assert check_image_conversion_warning(20, 20) is None

    def test_returns_warning_for_heavy(self) -> None:
        warning = check_image_conversion_warning(50, 50)
        assert warning is not None
        assert "HEAVY" in warning

    def test_returns_warning_for_extreme(self) -> None:
        warning = check_image_conversion_warning(100, 100)
        assert warning is not None
        assert "EXTREME" in warning

    def test_heavy_warning_mentions_image_size(self) -> None:
        warning = check_image_conversion_warning(50, 50)
        assert warning is not None
        assert "50x50" in warning

    def test_heavy_warning_mentions_pixel_count(self) -> None:
        warning = check_image_conversion_warning(50, 50)
        assert warning is not None
        assert "2,500" in warning

    def test_extreme_warning_mentions_resize(self) -> None:
        warning = check_image_conversion_warning(100, 100)
        assert warning is not None
        assert "resize" in warning.lower()

    def test_extreme_warning_mentions_quantize(self) -> None:
        warning = check_image_conversion_warning(100, 100)
        assert warning is not None
        assert "quantize" in warning.lower()

    def test_alpha_can_reduce_to_none(self) -> None:
        """High alpha transparency on a large image should reduce warning."""
        # 100x100 = 10000 pixels, but only 1% opaque = 100 effective = LIGHT
        assert check_image_conversion_warning(
            100, 100, has_alpha=True, alpha_coverage=0.01
        ) is None


# ---------------------------------------------------------------------------
# log_image_conversion_cost
# ---------------------------------------------------------------------------


class TestLogImageConversionCost:
    """Tests for log_image_conversion_cost()."""

    def test_returns_cost_category(self) -> None:
        cost = log_image_conversion_cost(8, 8)
        assert cost == ImageConversionCost.LIGHT

    def test_logs_debug_for_light(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.render_warnings"):
            log_image_conversion_cost(8, 8)
        assert any("LIGHT" in r.message for r in caplog.records)

    def test_logs_debug_for_moderate(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="wyby.render_warnings"):
            log_image_conversion_cost(20, 20)
        assert any("MODERATE" in r.message for r in caplog.records)

    def test_logs_warning_for_heavy(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="wyby.render_warnings"):
            log_image_conversion_cost(50, 50)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert any("HEAVY" in r.message for r in caplog.records)

    def test_logs_warning_for_extreme(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="wyby.render_warnings"):
            log_image_conversion_cost(100, 100)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert any("EXTREME" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# from_image() integration — logs conversion cost
# ---------------------------------------------------------------------------


class TestFromImageLogsConversionCost:
    """Tests that from_image() logs conversion cost warnings."""

    def test_from_image_logs_debug_for_small_image(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Small images should log at DEBUG level."""
        from PIL import Image

        from wyby.sprite import from_image

        img = Image.new("RGB", (4, 4), color=(255, 0, 0))
        with caplog.at_level(logging.DEBUG, logger="wyby.render_warnings"):
            from_image(img)
        cost_messages = [
            r for r in caplog.records
            if "wyby.render_warnings" in r.name
            and "image conversion" in r.message.lower()
        ]
        assert len(cost_messages) >= 1

    def test_from_image_logs_warning_for_large_image(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Large images should trigger a WARNING log."""
        from PIL import Image

        from wyby.sprite import from_image

        img = Image.new("RGB", (100, 100), color=(0, 128, 255))
        with caplog.at_level(logging.WARNING, logger="wyby.render_warnings"):
            from_image(img)
        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "wyby.render_warnings" in r.name
        ]
        assert len(warnings) >= 1
        assert "EXTREME" in warnings[0].message


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


class TestImageConversionCostExports:
    """Tests that image conversion cost APIs are in the public package."""

    def test_image_conversion_cost_importable(self) -> None:
        from wyby import ImageConversionCost as ICC
        assert ICC is ImageConversionCost

    def test_estimate_importable(self) -> None:
        from wyby import estimate_image_conversion_cost as eicc
        assert eicc is estimate_image_conversion_cost

    def test_check_warning_importable(self) -> None:
        from wyby import check_image_conversion_warning as cicw
        assert cicw is check_image_conversion_warning

    def test_log_cost_importable(self) -> None:
        from wyby import log_image_conversion_cost as licc
        assert licc is log_image_conversion_cost

    def test_image_conversion_cost_in_all(self) -> None:
        import wyby
        assert "ImageConversionCost" in wyby.__all__

    def test_estimate_in_all(self) -> None:
        import wyby
        assert "estimate_image_conversion_cost" in wyby.__all__

    def test_check_warning_in_all(self) -> None:
        import wyby
        assert "check_image_conversion_warning" in wyby.__all__

    def test_log_cost_in_all(self) -> None:
        import wyby
        assert "log_image_conversion_cost" in wyby.__all__
