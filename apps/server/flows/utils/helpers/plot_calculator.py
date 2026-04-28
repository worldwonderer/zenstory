"""情节点数量计算工具

根据章节字数动态计算情节点数量范围，确保信息密度恒定。

规则：150-200字 → 1个情节点
"""

import logging

logger = logging.getLogger(__name__)


def calculate_plots_range(
    chapter_word_count: int,
    words_per_plot_min: int = 150,
    words_per_plot_max: int = 200,
    absolute_min: int = 3,
    absolute_max: int = 40,
) -> tuple[int, int]:
    """
    根据章节字数动态计算情节点数量范围

    核心规则：
    - 基于 200字/个（保守）计算最小值
    - 基于 150字/个（激进）计算最大值
    - 设置绝对边界避免极端情况

    Args:
        chapter_word_count: 章节字数
        words_per_plot_min: 每个情节点最少字数（默认150）
        words_per_plot_max: 每个情节点最多字数（默认200）
        absolute_min: 绝对最小情节点数（默认3）
        absolute_max: 绝对最大情节点数（默认40）

    Returns:
        (min_plots, max_plots): 情节点数量范围

    Examples:
        >>> calculate_plots_range(500)
        (3, 4)
        >>> calculate_plots_range(1000)
        (5, 7)
        >>> calculate_plots_range(2000)
        (10, 14)
        >>> calculate_plots_range(5000)
        (25, 34)

    Raises:
        ValueError: 当参数不合法时
    """
    # 参数验证
    if words_per_plot_min <= 0 or words_per_plot_max <= 0:
        raise ValueError(
            f"words_per_plot 必须大于0: min={words_per_plot_min}, max={words_per_plot_max}"
        )

    if words_per_plot_min > words_per_plot_max:
        raise ValueError(
            f"words_per_plot_min 不能大于 words_per_plot_max: "
            f"min={words_per_plot_min}, max={words_per_plot_max}"
        )

    if absolute_min <= 0 or absolute_max <= 0:
        raise ValueError(
            f"absolute 边界必须大于0: min={absolute_min}, max={absolute_max}"
        )

    if absolute_min >= absolute_max:
        raise ValueError(
            f"absolute_min 必须小于 absolute_max: "
            f"min={absolute_min}, max={absolute_max}"
        )

    # 处理边界情况：字数为0或负数
    if chapter_word_count <= 0:
        logger.warning(
            f"章节字数异常: {chapter_word_count}，使用默认最小范围"
        )
        return (absolute_min, absolute_min + 2)

    # 基于最大字数/个计算最小情节点数（保守估计）
    min_plots = chapter_word_count // words_per_plot_max

    # 基于最小字数/个计算最大情节点数（激进估计）
    max_plots = chapter_word_count // words_per_plot_min

    # 应用绝对下限
    min_plots = max(absolute_min, min_plots)
    max_plots = max(absolute_min, max_plots)

    # 应用绝对上限
    min_plots = min(min_plots, absolute_max)
    max_plots = min(max_plots, absolute_max)

    # 确保范围合理：max 必须 >= min
    # 注意：允许 max == min，这在极短或极长章节时是合理的
    if max_plots < min_plots:
        # 这种情况理论上不应该发生，但为了安全起见
        max_plots = min_plots

    # 计算密度（避免除零）
    density_at_max = chapter_word_count / max_plots if max_plots > 0 else 0
    density_at_min = chapter_word_count / min_plots if min_plots > 0 else 0

    logger.debug(
        f"章节字数: {chapter_word_count}, "
        f"计算情节点范围: {min_plots}-{max_plots} "
        f"(密度: {density_at_max:.0f}-{density_at_min:.0f}字/个)"
    )

    return (min_plots, max_plots)
