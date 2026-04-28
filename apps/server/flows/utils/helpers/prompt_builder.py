"""
Prompt 构建工具

用于构建标准化的系统提示词
"""


def create_system_prompt(
    task_description: str,
    output_format: str,
    examples: list[dict[str, str]] | None = None,
    constraints: list[str] | None = None,
    role: str = "你是一个专业的网络小说读者，MBTI是INFJ，在做文本处理时绝对客观，不会使用总结性结尾。"
) -> str:
    """
    创建标准化的系统提示词

    Args:
        task_description: 任务描述
        output_format: 输出格式说明
        examples: 示例列表，每个示例包含 'input' 和 'output' 键
        constraints: 约束条件列表
        role: 角色描述

    Returns:
        完整的系统提示词
    """
    prompt_parts = [
        role,
        "",
        "## 任务描述",
        task_description,
        "",
        "## 输出格式",
        output_format,
    ]

    if constraints:
        prompt_parts.extend([
            "",
            "## 约束条件",
            *[f"- {constraint}" for constraint in constraints]
        ])

    if examples:
        prompt_parts.extend([
            "",
            "## 示例"
        ])
        for i, example in enumerate(examples, 1):
            prompt_parts.extend([
                f"### 示例 {i}",
                f"**输入**: {example.get('input', '')}",
                f"**输出**: {example.get('output', '')}",
                ""
            ])

    prompt_parts.extend([
        "",
        "严格按照上述格式要求输出结果。"
    ])

    return "\n".join(prompt_parts)



