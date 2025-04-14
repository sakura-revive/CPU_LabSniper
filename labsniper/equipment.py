import re

import requests

from .user import User
from .utils import normalize_string


class Equipment:
    def __init__(
        self,
        equipment_id: str,
        user: User,
    ) -> None:
        if not isinstance(user, User):
            msg = f"Invalid parameter. Detail:\n给定的用户的类型不正确，不能是{type(user)}."
            raise TypeError(msg)

        self.equipment_id = normalize_string(equipment_id, param_name="仪器编号")
        self.user = user
        self.calendar_id = ""

    def get_calendar_id(self) -> str:
        if self.calendar_id != "":
            return self.calendar_id

        url = f"https://dygx1.cpu.edu.cn/lims/!equipments/equipment/index.{self.equipment_id}.reserv"
        headers = {
            "referer": url,
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
        }
        cookies = self.user.get_cookies()

        try:
            response = requests.get(url=url, cookies=cookies, headers=headers)
        except Exception as e:
            msg = f"Failed to get equipment info for equipment {self.equipment_id} "
            msg += f"({type(e).__name__}). Detail:\n"
            msg += "网络异常，无法连接至服务器，仪器信息获取失败。"
            raise RuntimeError(msg) from e

        pattern = r"calendar_id=([0-9]*)&"
        re_calendar_id = re.search(pattern, response.text)
        if re_calendar_id is None:  # Error handling
            msg = f"Failed to get equipment info for equipment {self.equipment_id} "
            if response.status_code == 401:  # Unauthorized
                msg += "(401 Unauthorized). Detail:\n"
                msg += "仪器信息获取失败，请检查登录状态或凭证是否正确。"
                raise RuntimeError(msg)
            elif response.status_code == 404:  # Not found
                msg += f"(404 Not Found). Detail:\n"
                msg += f"仪器信息获取失败，未找到编号为{self.equipment_id}的仪器。"
                raise RuntimeError(msg)
            elif response.status_code == 200:  # OK
                msg += "(200 OK). Detail:\n"
                msg += "仪器信息获取失败，可能是因为该仪器并未对当前用户开放预约。"
                raise RuntimeError(msg)
            else:  # Other status codes
                msg += f"({response.status_code}). Detail:\n"
                msg += f"仪器信息获取失败，出现意外的错误码{response.status_code}."
                raise RuntimeError(msg)

        calendar_id = re_calendar_id.group(1)
        self.calendar_id = calendar_id
        return calendar_id
