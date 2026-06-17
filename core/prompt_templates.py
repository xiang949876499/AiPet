def render_washing_reminder(
    customer_name: str,
    pet_name: str,
    pet_type: str,
    last_service_days: int,
    available_time: str = "",
    promotion: str = "",
    note: str = "",
) -> str:
    return f"""你是宠物门店的私域运营助手。请根据以下信息，为店员生成一条适合微信发送的洗护预约提醒话术。
要求：
- 语气自然、温和、不过度推销
- 不超过 100 字
- 包含宠物名称
- 提醒客户上次洗护已经过去一段时间
- 给出轻柔预约引导
- 不要制造焦虑
- 不要涉及医疗诊断
- 不要建议用药

客户称呼：{customer_name}
宠物名称：{pet_name}
宠物类型：{pet_type}
上次服务距今：{last_service_days} 天
可预约时间：{available_time}
门店活动：{promotion}
备注：{note}

请输出 3 个版本：简短版、温和版、促销版。"""


def fallback_message(task_type: str, customer_name: str, pet_name: str) -> str:
    if task_type == "洗护提醒":
        return f"{customer_name}，{pet_name}上次洗护已经有一段时间啦。这周如果方便，可以帮您预留一个洗护预约时间。"
    if task_type == "老客唤醒":
        return f"{customer_name}，好久没见{pet_name}啦。店里给老朋友准备了小福利，有空可以带它回来看看。"
    return f"{customer_name}，想和您跟进一下{pet_name}的情况，方便时回复我就好。"
