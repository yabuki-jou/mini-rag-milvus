"""定义企业行政 Agent 在节点之间传递的可持久化状态。"""

from typing import Any, NotRequired

from langgraph.graph import MessagesState


class AdminAgentState(MessagesState):
    """保存对话消息、授权范围和后续人工确认动作。

    Attributes:
        messages: LangGraph 自动追加和归并的对话消息。
        user_id: 应用服务注入的当前用户 UUID 字符串。
        kb_id: 应用服务注入的会话知识库 UUID 字符串。
        pending_action: 后续人工确认阶段使用的可序列化动作草稿；
            A-05 暂不读写该字段。

    Graph State 只保存能够写入 Checkpoint 的数据。数据库 Session、
    Engine、模型和 Milvus 客户端都由节点运行时获取，不能放进这里。
    """

    user_id: NotRequired[str]
    kb_id: NotRequired[str]
    pending_action: NotRequired[dict[str, Any] | None]
