"""文件树结构不变量的唯一权威实现。

这里集中放"父节点赋值是否合法"这类跨入口的规则。之所以要单独成模块：
REST 层（api/files.py）与 Agent 工具层（agent/tools/file_ops/crud.py）都要
做同一套校验，历史上各自写了一份，写法还不一致——Agent 那份漏了「parent
必须是 folder」，于是 AI 把章节挂到了普通文件下，而 GET /file-tree 只对
folder 递归子节点，导致刚写好的章节在文件树里彻底不可见。

放在 services/ 而不是 agent/ 下，是为了让 api/ 不必反向依赖 agent 包。
两个入口的差别只剩「异常怎么翻译」：本模块统一抛 ValueError，
REST 层捕获后转成带 error_code 的 APIException，Agent 工具层转成给模型看的
错误文本。规则本身只有这一份。
"""

from sqlmodel import Session

from models import File
from models.file_model import FILE_TYPE_FOLDER

__all__ = [
    "ParentNotFoundError",
    "is_descendant_of",
    "validate_parent_assignment",
]


class ParentNotFoundError(ValueError):
    """父节点不存在/跨项目/已删除。

    继承 ValueError，Agent 工具层沿用原有的 `except ValueError` 捕获即可；
    REST 层用它区分出 FILE_NOT_FOUND，其余不变量违例仍是 VALIDATION_ERROR，
    保持既有 REST 契约不变。
    """


def is_descendant_of(
    session: Session,
    file_id: str,
    candidate_parent_id: str | None,
) -> bool:
    """判断 candidate_parent_id 是否落在 file_id 的后代链上（含 candidate 就是 file_id 本身）。

    从候选父节点沿 parent_id 一路向上走，若途中撞见 file_id，说明把 file_id
    挂到候选父节点下会成环。visited 集合保证历史脏数据里已存在的环不会把
    这里打成死循环。
    """
    if not candidate_parent_id:
        return False

    visited: set[str] = set()
    current_id: str | None = candidate_parent_id

    while current_id:
        if current_id in visited:
            # 已有环：继续走下去也不会再遇到新节点
            return False
        if current_id == file_id:
            return True
        visited.add(current_id)

        current = session.get(File, current_id)
        if current is None:
            return False
        current_id = current.parent_id

    return False


def validate_parent_assignment(
    session: Session,
    project_id: str,
    parent_id: str | None,
    *,
    moving_file_id: str | None = None,
) -> str | None:
    """校验父节点赋值的全部不变量。

    - parent 必须存在、未删除、属于同一项目
    - parent 必须是 folder
    - 移动文件时不能把它挂到自己或自己的后代下（成环）

    Returns:
        校验通过的 parent_id（parent_id 为 None 时原样返回 None）。

    Raises:
        ValueError: 任一不变量不满足。第一项（不存在/跨项目/已删除）与后两项
            在 REST 层对应不同的 error_code，调用方靠 `not_found` 属性区分，
            见 ParentNotFoundError。
    """
    if parent_id is None:
        return None

    parent = session.get(File, parent_id)
    if not parent or parent.is_deleted or parent.project_id != project_id:
        raise ParentNotFoundError(
            f"Parent file {parent_id} not found in project {project_id}"
        )

    if parent.file_type != FILE_TYPE_FOLDER:
        raise ValueError(
            f"Parent file {parent_id} is not a folder "
            f"(file_type={parent.file_type}); 文件只能挂在文件夹下"
        )

    if moving_file_id and is_descendant_of(session, moving_file_id, parent_id):
        raise ValueError("不能把文件移动到它自己或它的子节点下")

    return parent_id
