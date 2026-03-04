"""业务域分类器 - 基于关键词匹配推断表所属业务域"""

from typing import List


class DomainClassifier:
    """业务域分类器 - 基于关键词匹配推断表所属业务域

    该分类器通过表名和表注释中的关键词来推断表所属的业务域。
    支持单标签分类和多标签分类两种模式。

    Attributes:
        BUSINESS_KEYWORDS: 业务域关键词映射，键为业务域名称，值为该域的关键词列表
        DOMAIN_PRIORITY: 业务域优先级列表，用于多域匹配时的排序
    """

    BUSINESS_KEYWORDS = {
        "订单": ["order", "trade", "sale", "订单", "交易"],
        "用户": ["user", "customer", "member", "用户", "会员", "客户"],
        "库存": ["stock", "inventory", "warehouse", "库存", "仓库"],
        "财务": ["finance", "account", "payment", "财务", "支付", "账单"],
        "车辆": ["car", "vehicle", "plate", "车辆", "车牌"],
        "停车": ["park", "parking", "garage", "停车", "场库"],
        "通行": ["access", "entry", "exit", "通行", "出入"],
        "设备": ["device", "equipment", "camera", "设备", "摄像机"],
    }

    DOMAIN_PRIORITY = ["车辆", "停车", "通行", "订单", "用户", "库存", "财务", "设备"]

    def _get_matching_domains(self, table_name: str, comment: str = "") -> List[str]:
        """获取所有匹配的业务域

        Args:
            table_name: 表名
            comment: 表注释

        Returns:
            匹配的业务域名称列表
        """
        # 转换为小写进行不区分大小写的匹配
        table_name_lower = table_name.lower()
        comment_lower = comment.lower() if comment else ""

        matching_domains = []

        for domain, keywords in self.BUSINESS_KEYWORDS.items():
            # 先检查表名
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in table_name_lower:
                    matching_domains.append(domain)
                    break
            else:
                # 表名未匹配，检查表注释
                if comment_lower:
                    for keyword in keywords:
                        keyword_lower = keyword.lower()
                        if keyword_lower in comment_lower:
                            matching_domains.append(domain)
                            break

        return matching_domains

    def _sort_by_priority(self, domains: List[str]) -> List[str]:
        """按优先级排序业务域

        Args:
            domains: 待排序的业务域列表

        Returns:
            按优先级排序后的业务域列表
        """
        return sorted(
            domains,
            key=lambda d: self.DOMAIN_PRIORITY.index(d)
            if d in self.DOMAIN_PRIORITY
            else len(self.DOMAIN_PRIORITY),
        )

    def classify(self, table_name: str, comment: str = "") -> str:
        """推断业务域（单标签）

        根据表名和表注释中的关键词推断表所属的业务域。
        当多个业务域匹配时，返回优先级最高的业务域。

        Args:
            table_name: 表名
            comment: 表注释

        Returns:
            业务域名称，如 "车辆"、"停车" 等，未匹配返回 "其他"
        """
        matching_domains = self._get_matching_domains(table_name, comment)

        if not matching_domains:
            return "其他"

        # 按优先级排序并返回最高优先级的业务域
        sorted_domains = self._sort_by_priority(matching_domains)
        return sorted_domains[0]

    def classify_multi(self, table_name: str, comment: str = "") -> List[str]:
        """推断业务域（多标签）

        根据表名和表注释中的关键词推断表所属的所有业务域。

        Args:
            table_name: 表名
            comment: 表注释

        Returns:
            业务域名称列表，按优先级排序
        """
        matching_domains = self._get_matching_domains(table_name, comment)

        if not matching_domains:
            return ["其他"]

        # 去重并按优先级排序
        unique_domains = list(dict.fromkeys(matching_domains))
        return self._sort_by_priority(unique_domains)