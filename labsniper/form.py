FORM_DEFAULTS = {
    "name": "仪器使用预约",  # 主题
    "description": "",  # 备注
    "project": "0",  # 关联项目（填写从1开始的非空的选项序号，0表示不选）
    "fund_card_no": "0",  # 经费卡号（填写从1开始的非空的选项序号，0表示不选）
    "count": "1",  # 样品数量
}
FORM_BASE = {
    "_ajax": "1",
    "_object": "component_form",
    "_event": "submit",
    "submit": "save",
    "component_id": "0",
}


class Form:
    def __init__(self, form: dict | None = None) -> None:
        if form is None:
            form = {}
        if not isinstance(form, dict):
            msg = "Invalid parameter. Detail:\n"
            mas += "参数无效，表单数据必须为字典类型"
            raise TypeError(msg)
        self.data = {**FORM_DEFAULTS, **form, **FORM_BASE}

    # TODO 从预约表单获取表单的其它必填项，并自动填入
