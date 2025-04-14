import json
import os
import re

import requests
import socketio
import urllib.parse

from .equipment import Equipment
from .form import Form
from .user import User
from .utils import get_timestamp, normalize_string

ENABLE_HACK = os.getenv("LABSNIPER_ENABLE_HACK", "") == "1"


class Reservation:
    def __init__(
        self,
        start: str,
        end: str,
        form: Form | None = None,
        component_id: str | None = None,
    ) -> None:
        self.dtstart = get_timestamp(start)
        self.dtend = get_timestamp(end)

        if form is None:
            form = Form()
        if not isinstance(form, Form):
            msg = "Invalid parameter. Detail:\n"
            msg += f"参数无效，给定的表单数据的类型不正确，不能为{type(form)}."
            raise TypeError(msg)
        self.form = form

        self.component_id = normalize_string(
            component_id,
            param_name="预约组件ID",
            allow_empty=True,
        )

    def get_request_creation_data(self) -> dict:
        return {**self.form.data, **{"dtstart": self.dtstart, "dtend": self.dtend}}

    def get_request_submission_data(self) -> dict:
        data = {}
        if self.component_id != "":
            data["component_id"] = self.component_id
        return data


class Hack:
    def __init__(
        self,
        start: str | None = None,
        end: str | None = None,
        current_user_id: str | None = None,
    ) -> None:
        self.dtstart = None
        self.dtend = None
        if not (start is None or start == ""):
            self.dtstart = get_timestamp(start)
        if not (end is None or end == ""):
            self.dtend = get_timestamp(end)

        self.current_user_id = normalize_string(
            current_user_id,
            param_name="操作者用户ID",
            allow_empty=True,
        )

    def get_request_creation_data(self) -> dict:
        if not ENABLE_HACK:
            return {}
        data = {}
        if self.dtstart is not None:
            data["dtstart"] = self.dtstart
        if self.dtend is not None:
            data["dtend"] = self.dtend
        return data

    def get_request_submission_data(self) -> dict:
        if not ENABLE_HACK:
            return {}
        data = {}
        if self.current_user_id != "":
            data["currentUserId"] = self.current_user_id
        return data


class ReservationService:
    @staticmethod
    def param_check(
        param,
        param_type: type,
        param_name: str,
        allow_none: bool = False,
    ) -> None:
        if param is None and allow_none:
            return
        if not isinstance(param, param_type):
            msg = "Invalid parameter. Detail:\n"
            msg += f"参数无效，给定的{param_name}的类型不正确，不能为{type(param)}."
            raise TypeError(msg)

    def __init__(
        self,
        user: User,
        equipment: Equipment,
        reservation: Reservation,
        hack: Hack | None = None,
    ) -> None:
        self.param_check(user, User, "用户数据")
        self.param_check(equipment, Equipment, "仪器数据")
        self.param_check(reservation, Reservation, "预约数据")
        self.param_check(hack, Hack, "特殊数据", allow_none=True)

        self.user = user
        self.equipment = equipment
        self.reservation = reservation
        self.hack = hack

    def create_request(self) -> None:
        equipment_id = self.equipment.equipment_id
        calendar_id = self.equipment.get_calendar_id()
        url = f"https://dygx1.cpu.edu.cn/lims/!calendars/calendar/{calendar_id}?equipment_id={equipment_id}"

        headers = {
            "authority": "dygx1.cpu.edu.cn",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "dnt": "1",
            "origin": "https://dygx1.cpu.edu.cn",
            "pragma": "no-cache",
            "referer": f"https://dygx1.cpu.edu.cn/lims/!equipments/equipment/index.{equipment_id}.reserv",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "x-requested-with": "XMLHttpRequest",
        }
        cookies = self.user.get_cookies()

        data = self.reservation.get_request_creation_data()
        if self.hack is not None:
            data = {**data, **self.hack.get_request_creation_data()}
        try:
            response = requests.post(
                url=url,
                cookies=cookies,
                headers=headers,
                data=data,
            )
            response.encoding = "utf-8"
        except Exception as e:
            msg = f"Failed to create a request ({type(e).__name__}). Detail:\n"
            msg += "网络异常，无法连接至服务器，预约请求创建失败。"
            raise RuntimeError(msg) from e

        if (
            response.status_code == 200
            and "application/json" in response.headers["Content-Type"]
            and "dialog" in response.json()
            and "data" in response.json()["dialog"]
        ):
            pattern = r'form: "(\{.*?\})", ticket: "(.*?)"'
            re_form = re.search(pattern, response.json()["dialog"]["data"])
        else:
            re_form = None

        if re_form is not None:
            form_json = re_form.group(1)
            ticket = re_form.group(2)

            # Handle escape characters
            form = json.loads(form_json.replace("\\\\", "\\").replace('\\"', '"'))

            self.request_data: dict = form
            self.ticket: str = ticket
            self.ticket_id: str = form["ticketId"]
            return

        # Error handling
        msg = f"Failed to create a request "
        if response.status_code == 401:
            # Unauthorized
            msg += "(401 Unauthorized). Detail:\n"
            msg += "预约请求创建失败，可能是用户未登录或登录状态已过期。"
            raise RuntimeError(msg)
        elif response.status_code == 200:
            # Status code is OK, but the request is invalid
            msg += "(200 OK). Detail:\n"
            if "application/json" not in response.headers["Content-Type"]:
                # Not json
                msg += "预约请求创建失败，且无法解析错误原因。"
                raise RuntimeError(msg)

            # json response
            response_json = response.json()
            if "script" in response_json and "alert" in response_json["script"]:
                # An alert is shown
                pattern = r"alert\(\"(.*)\"\)"
                alert = (
                    re.search(pattern, response_json["script"])
                    .group(1)
                    .replace("\\n", "\n")
                    .replace("\\<br/\\>", "\n")
                )
                msg += f"预约请求创建失败，以下是错误信息：\n{alert}"
                raise RuntimeError(msg)
            elif "dialog" in response_json and "data" in response_json["dialog"]:
                # An html dialog is shown
                response_html: str = response_json["dialog"]["data"]

                pattern1 = r'<div id="form_error_box"[\s\S]*?>([\s\S]*?)</div>'
                re_error_div = re.search(pattern1, response_html)
                error_div = re_error_div.group(1)

                pattern2 = r"<li>([\s\S]*?)</li>"
                error_li_list = re.findall(pattern2, error_div)
                error_detail = "\n".join(error_li_list).replace("<br/>", "\n")

                msg += f"预约请求创建失败，以下是错误信息：\n{error_detail}"
                raise RuntimeError(msg)
            else:
                # Other json response
                msg += "预约请求创建失败，且无法解析错误原因。"
                raise RuntimeError(msg)

        else:
            # Other status codes
            msg += f"({response.status_code}). Detail:\n"
            msg += f"预约请求创建失败，出现意外的状态码{response.status_code}."
            raise RuntimeError(msg)

    def submit_request(self) -> str:
        form_submit = {
            **self.request_data,
            **self.reservation.get_request_creation_data(),
            **self.reservation.get_request_submission_data(),
            "ticketId": self.ticket_id,  # make sure the ticketId is correct
        }
        if self.hack is not None:
            form_submit = {
                **form_submit,
                **self.hack.get_request_submission_data(),
            }

        params = {
            "userId": "",
            "ticket": self.ticket,
            "ticketId": self.ticket_id,
        }
        message = {
            "form": json.dumps(form_submit),
            "ticket": self.ticket,
        }
        host = "https://dygx1.cpu.edu.cn"
        path = "/socket.iov2"
        query = urllib.parse.urlencode(params)
        url = f"{host}{path}?{query}"

        # Ready to connect
        sio = socketio.Client()
        res = {
            "success": False,
            "component_id": "",
            "message": "",
        }

        @sio.on("yiqikong-reserv-reback")
        def on_message(data):
            # Received the message
            nonlocal res
            if "success" in data and data["success"] == 1:
                res["success"] = True
                res["component_id"] = str(data["component_id"])
            else:
                error_msg: str = data["error_msg"]
                res["message"] = error_msg.replace("<br/>", "\n").replace(", ", "\n")
            sio.disconnect()

        @sio.event
        def connect():
            # Connected
            sio.emit("yiqikong-reserv", message)

        @sio.event
        def connect_error(msg=None):
            nonlocal res
            res["message"] = f"Connection error: {msg}"
            sio.disconnect()

        @sio.event
        def error(msg=None):
            nonlocal res
            res["message"] = f"Unexpected error: {msg}"
            sio.disconnect()

        sio.connect(url, socketio_path=path)
        sio.wait()  # Until the result is obtained
        if not res["success"]:
            msg = f"Failed to submit request. Detail:\n"
            msg += f"预约请求提交失败，以下是错误信息：\n{res['message']}"
            raise RuntimeError(msg)

        component_id = res["component_id"]
        return component_id
