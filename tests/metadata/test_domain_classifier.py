"""Tests for DomainClassifier in the metadata knowledge graph system."""

import pytest

from src.metadata.domain_classifier import DomainClassifier


class TestDomainClassifier:
    """Test cases for DomainClassifier."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = DomainClassifier()

    def test_classify_plate_table(self):
        """Test classification of plate-related table."""
        result = self.classifier.classify("cloud_fixed_plate")

        assert result == "车辆"

    def test_classify_parking_table(self):
        """Test classification of parking-related table."""
        result = self.classifier.classify("parking_lot_info")

        assert result == "停车"

    def test_classify_user_table(self):
        """Test classification of user-related table."""
        result = self.classifier.classify("user_account")

        assert result == "用户"

    def test_classify_order_table(self):
        """Test classification of order-related table."""
        result = self.classifier.classify("order_details")

        assert result == "订单"

    def test_classify_device_table(self):
        """Test classification of device-related table."""
        result = self.classifier.classify("device_info")

        assert result == "设备"

    def test_classify_unknown_table(self):
        """Test classification of unknown table returns '其他'."""
        result = self.classifier.classify("unknown_table_xyz")

        assert result == "其他"

    def test_classify_with_comment(self):
        """Test classification using table comment."""
        result = self.classifier.classify(
            table_name="custom_table",
            comment="车辆信息表"
        )

        assert result == "车辆"

    def test_classify_comment_overrides_table_name(self):
        """Test that comment can override table name matching."""
        # Table name doesn't match, but comment does
        result = self.classifier.classify(
            table_name="abc_xyz",
            comment="会员用户信息"
        )

        assert result == "用户"

    def test_classify_priority_ordering(self):
        """Test that priority ordering works correctly when multiple domains match."""
        # Table matches both 车辆 and 停车
        # DOMAIN_PRIORITY = ["车辆", "停车", ...]
        result = self.classifier.classify("vehicle_parking_info")

        # 车辆 has higher priority
        assert result == "车辆"

    def test_classify_multi_returns_multiple_domains(self):
        """Test classify_multi returns multiple matching domains."""
        result = self.classifier.classify_multi("car_parking_access")

        assert len(result) > 1
        assert "车辆" in result
        assert "停车" in result

    def test_classify_multi_returns_sorted_by_priority(self):
        """Test classify_multi returns domains sorted by priority."""
        result = self.classifier.classify_multi("access_device_camera")

        # Check that result is sorted according to DOMAIN_PRIORITY
        priority = self.classifier.DOMAIN_PRIORITY
        for i in range(len(result) - 1):
            current_idx = priority.index(result[i]) if result[i] in priority else len(priority)
            next_idx = priority.index(result[i + 1]) if result[i + 1] in priority else len(priority)
            assert current_idx <= next_idx

    def test_classify_multi_unknown_returns_default(self):
        """Test classify_multi returns ['其他'] for unknown tables."""
        result = self.classifier.classify_multi("xyz_random_table")

        assert result == ["其他"]

    def test_classify_multi_with_comment(self):
        """Test classify_multi with comment."""
        result = self.classifier.classify_multi(
            table_name="table_a",
            comment="财务支付账单"
        )

        # Should match 财务 domain
        assert "财务" in result

    def test_classify_case_insensitive(self):
        """Test classification is case insensitive."""
        result1 = self.classifier.classify("USER_INFO")
        result2 = self.classifier.classify("user_info")
        result3 = self.classifier.classify("User_Info")

        assert result1 == result2 == result3 == "用户"

    def test_classify_chinese_keywords(self):
        """Test classification with Chinese keywords."""
        result = self.classifier.classify("车辆信息表")

        assert result == "车辆"

    def test_classify_mixed_keywords(self):
        """Test classification with mixed English and Chinese keywords."""
        result = self.classifier.classify("car_车辆_plate_车牌")

        assert result == "车辆"

    def test_get_matching_domains_returns_all_matches(self):
        """Test _get_matching_domains returns all matching domains."""
        result = self.classifier._get_matching_domains("car_plate_stock")

        # Should match 车辆 and 库存
        assert "车辆" in result
        assert "库存" in result

    def test_get_matching_domains_empty_comment(self):
        """Test _get_matching_domains with empty comment."""
        result = self.classifier._get_matching_domains("user_info", comment="")

        assert "用户" in result

    def test_sort_by_priority_correct_order(self):
        """Test _sort_by_priority returns correct order."""
        domains = ["库存", "车辆", "用户", "订单"]
        expected_priority = ["车辆", "订单", "用户", "库存"]

        result = self.classifier._sort_by_priority(domains)

        # Check that 车辆 comes first (highest priority)
        assert result[0] == "车辆"

    def test_sort_by_priority_unknown_domain(self):
        """Test _sort_by_priority handles unknown domains."""
        domains = ["车辆", "未知领域"]

        result = self.classifier._sort_by_priority(domains)

        # Unknown domains should come after known ones
        assert result[0] == "车辆"
        assert result[1] == "未知领域"

    def test_classify_stock_table(self):
        """Test classification of stock/inventory table."""
        result = self.classifier.classify("inventory_stock")

        assert result == "库存"

    def test_classify_finance_table(self):
        """Test classification of finance table."""
        result = self.classifier.classify("payment_record")

        assert result == "财务"

    def test_classify_access_table(self):
        """Test classification of access table."""
        result = self.classifier.classify("entry_exit_record")

        assert result == "通行"

    def test_classify_member_table(self):
        """Test classification of member table."""
        result = self.classifier.classify("member_info")

        assert result == "用户"