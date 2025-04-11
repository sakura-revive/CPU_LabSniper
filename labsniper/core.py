import re
import json
import time
import requests
import socketio
import urllib.parse
from copy import deepcopy
from typing import List, Dict, Optional

INF = float("inf")
DELAY_SECONDS = -2
TICKET_ALIVE_SECONDS = 55


def get_timestamp(input_time: Optional[str] = None) -> Optional[int]:
    if input_time is None or input_time == "":
        return None

    from datetime import datetime

    time_format = "%Y-%m-%d %H:%M:%S"
    try:
        time_obj = datetime.strptime(input_time, time_format)  # Parse time
    except ValueError as e:
        raise ValueError(
            f'Invalid time format. Please use "YYYY-mm-dd HH:MM:SS", e.g. "2024-04-01 09:30:00".'
        ) from e
    try:
        timestamp = int(time_obj.timestamp())  # Convert datetime object to timestamp
    except OSError as e:
        raise RuntimeError(
            f'Failed to convert time "{datetime.strftime(time_obj, time_format)}" to timestamp. Is this time too far away?'
        ) from e
    return timestamp


class User:
    LOGIN_METHODS = ["oauth"]
    COOKIE_KEYS = ["session_lims2_cf_cpu"]

    def __init__(self) -> None:
        self.__credential = {}
        self.__login_method = self.LOGIN_METHODS[0]
        self.__tag = ""
        self.__cookies = {}

    def get_cur_credential(self) -> dict:
        return self.__credential

    def get_cur_login_method(self) -> str:
        return self.__login_method

    def get_cur_tag(self) -> str:
        return self.__tag

    def __oauth(self, service: str, credential: str, cookie_keys: List[str]) -> dict:
        def encode(string: str) -> str:
            from base64 import b64encode

            # Base64 encode a string twice
            return b64encode(b64encode(str(string).encode("utf-8"))).decode("utf-8")

        session = requests.Session()  # Start a login session
        headers = {
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        }

        params = {"service": service}
        # To the login page
        session.get("https://id.cpu.edu.cn/sso/login", params=params, headers=headers)

        data = {
            "lt": "${loginTicket}",
            "useVCode": "",
            "isUseVCode": "true",
            "sessionVcode": "",
            "errorCount": "",
            "execution": "e1s1",
            "service": service,
            "_eventId": "submit",
            "geolocation": "",
            "username": encode(credential["username"]),
            "password": encode(credential["password"]),
            "rememberpwd": "on",
        }
        # Login
        response = session.post(
            "https://id.cpu.edu.cn/sso/login", params=params, data=data
        )

        if response.status_code == 401:  # Unauthorized
            raise RuntimeError(
                "Failed to login via oauth. Please check your username and password."
            )

        cookies_complete = session.cookies.get_dict()
        cookies = {}
        for cookie_key in cookie_keys:
            if cookie_key in cookies_complete:
                cookies = {**cookies, cookie_key: cookies_complete[cookie_key]}
            else:
                raise RuntimeError(
                    f'Cookie key "{cookie_key}" not found. Complete cookies:\n{cookies_complete}'
                )
        return cookies

    def __login(self) -> None:
        if self.__login_method == "oauth":
            service = "https://dygx1.cpu.edu.cn/gateway/login?from=cpu&redirect=http%3A%2F%2Fdygx1.cpu.edu.cn%2Flims%2F%21people%2Fcpu%2Flogin"
            self.__cookies = deepcopy(
                self.__oauth(
                    service=service,
                    credential=self.__credential,
                    cookie_keys=self.COOKIE_KEYS,
                )
            )

    def set_credential(self, username: str = "", password: str = "") -> None:
        if not isinstance(username, str):
            raise ValueError(f"username must be a string, not {type(username)}.")
        if not isinstance(password, str):
            raise ValueError(f"password must be a string, not {type(password)}.")
        if username == "" or password == "":
            raise ValueError("username and password must not be empty.")
        self.__credential = {"username": username, "password": password}

    def set_login_method(self, login_method: str) -> None:
        if login_method.lower() not in self.LOGIN_METHODS:
            raise ValueError(f"Unsupported login method: {login_method}")
        self.__login_method = login_method

    def set_tag(self, tag: str) -> None:
        if not isinstance(tag, str):
            raise ValueError(f"tag must be a string, not {type(tag)}.")
        self.__tag = tag

    def set_cookies(self, cookies: Optional[Dict] = None) -> None:
        if not (cookies is None or isinstance(cookies, dict)):
            raise ValueError(f"cookies must be a dictionary, not {type(cookies)}.")
        if cookies is not None:
            self.__cookies = deepcopy(cookies)
        else:
            self.__login()

    def get_cookies(self) -> dict:
        if self.__cookies == {}:
            self.set_cookies()
        return self.__cookies


class Reserve:
    FORM_BASE = {
        "_ajax": "1",
        "_object": "component_form",
        "_event": "submit",
        "submit": "save",
        "component_id": "0",
    }
    FORM_TEMPLATE = {
        "name": "仪器使用预约",  # 主题
        "description": "",  # 备注
        "project": "0",  # 关联项目（填写从1开始的非空的选项序号，0表示不选）
        "fund_card_no": "0",  # 经费卡号（填写从1开始的非空的选项序号，0表示不选）
        "count": "1",  # 样品数量
    }

    def __init__(self) -> None:
        self.__user = None
        self.__cookies = {}
        self.__equipment_info = {}
        self.__reserve_info = {}
        self.__intervene = None

    def get_cur_user(self) -> User:
        return self.__user

    def get_cur_cookies(self) -> dict:
        return self.__cookies

    def get_cur_equipment_info(self) -> dict:
        return self.__equipment_info

    def get_cur_reserve_info(self) -> dict:
        return self.__reserve_info

    def __get_equipment_info(self, equipment_id: str) -> dict:
        url = f"https://dygx1.cpu.edu.cn/lims/!equipments/equipment/index.{equipment_id}.reserv"

        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "dnt": "1",
            "referer": url,
            "sec-ch-ua": '"Microsoft Edge";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        }

        response = requests.get(url=url, cookies=self.__cookies, headers=headers)
        response.encoding = "utf-8"
        re_calendar_id = re.search("calendar_id=([0-9]*)\&", response.text)
        if re_calendar_id is None:  # Error handling
            error_msg = f"Failed to get equipment info for equipment {equipment_id}."
            if response.status_code == 401:  # Unauthorized
                raise RuntimeError(
                    f"{error_msg} Unauthorized. Are cookies still valid?"
                )
            elif response.status_code == 404:  # Not found
                raise RuntimeError(f"{error_msg} Equipment not found.")
            else:  # Other status codes
                raise RuntimeError(
                    f"{error_msg} Unexpected status code {response.status_code}."
                )

        calendar_id = re_calendar_id.group(1)
        equipment_info = {
            "equipment_id": equipment_id,
            "calendar_id": calendar_id,
        }
        return equipment_info

    def set_user(self, user: User) -> None:
        if not isinstance(user, User):
            raise ValueError(
                f"user must be an instance of class User, not {type(user)}."
            )
        self.__user = user

    def set_cookies(self, cookies: Optional[Dict] = None) -> None:
        if not (cookies is None or isinstance(cookies, dict)):
            raise ValueError(f"cookies must be a dictionary, not {type(cookies)}.")
        if cookies is not None:
            self.__cookies = deepcopy(cookies)
        else:
            if self.__user is not None:
                self.__cookies = deepcopy(self.__user.get_cookies())
            else:
                raise ValueError("No cookies are provided and no user is set.")

    def set_equipment_info(
        self, equipment_id: Optional[str] = None, equipment_info: Optional[dict] = None
    ) -> None:
        if not ((equipment_id is None) ^ (equipment_info is None)):  # xor
            raise ValueError(
                "exactly one of equipment_id and equipment_info should be provided."
            )

        if equipment_info is not None:
            if not isinstance(equipment_info, dict):
                raise ValueError(
                    f"equipment_info must be a dictionary, not {type(equipment_info)}."
                )
            self.__equipment_info = equipment_info
        else:  # elif equipment_id is not None:
            if not (isinstance(equipment_id, str) or isinstance(equipment_id, int)):
                raise ValueError(
                    f"equipment_id must be a string or an integer, not {type(equipment_id)}."
                )
            self.__equipment_info = self.__get_equipment_info(
                equipment_id=str(equipment_id)
            )

    def set_reserve_info(self, reserve_info: dict) -> None:
        if not isinstance(reserve_info, dict):
            raise ValueError(
                f"reserve_info must be a dictionary, not {type(reserve_info)}."
            )
        if not ("dtstart" in reserve_info and "dtend" in reserve_info):
            raise ValueError('reserve_info must contain "dtstart" and "dtend" keys.')
        dtstart = reserve_info["dtstart"]
        dtend = reserve_info["dtend"]
        if not (
            isinstance(dtstart, int) or (isinstance(dtstart, str) and dtstart.isdigit())
        ):
            raise ValueError(
                f"dtstart must be an integer or a number string, not {type(dtstart)}."
            )
        if not (isinstance(dtend, int) or (isinstance(dtend, str) and dtend.isdigit())):
            raise ValueError(
                f"dtend must be an integer or a number string, not {type(dtend)}."
            )
        self.__reserve_info = {
            **reserve_info,
            "dtstart": int(dtstart),
            "dtend": int(dtend),
        }

    def set_intervene(self, intervene: Optional[callable] = None) -> None:
        if not (intervene is None or callable(intervene)):
            raise ValueError("Intervene must be callable.")
        self.__intervene = intervene

    def __form_acquiry(self, hack: Optional[dict] = None) -> dict:
        url = f'https://dygx1.cpu.edu.cn/lims/!calendars/calendar/{self.__equipment_info["calendar_id"]}?equipment_id={self.__equipment_info["equipment_id"]}'
        cookies = self.__cookies

        headers = {
            "authority": "dygx1.cpu.edu.cn",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "dnt": "1",
            "origin": "https://dygx1.cpu.edu.cn",
            "pragma": "no-cache",
            "referer": f'https://dygx1.cpu.edu.cn/lims/!equipments/equipment/index.{self.__equipment_info["equipment_id"]}.reserv',
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "x-requested-with": "XMLHttpRequest",
        }
        data = {**self.FORM_TEMPLATE, **self.__reserve_info, **self.FORM_BASE}
        if hack is not None:
            data = {**data, **hack}
        response = requests.post(url=url, cookies=cookies, headers=headers, data=data)
        response.encoding = "utf-8"

        if (
            response.status_code == 200
            and "application/json" in response.headers["Content-Type"]
            and "dialog" in response.json()
            and "data" in response.json()["dialog"]
        ):
            re_form = re.search(
                'form: "(\\{.*?\\})", ticket: "(.*?)"',
                response.json()["dialog"]["data"],
            )
        else:
            re_form = None

        if re_form is None:  # Error handling
            error_msg = f"Failed to acquire form."
            if response.status_code == 401:  # Unauthorized
                raise RuntimeError(
                    f"{error_msg} Unauthorized. Are cookies still valid?"
                )
            elif (
                response.status_code == 200
            ):  # Status code is OK, but the form is invalid
                if "application/json" in response.headers["Content-Type"]:
                    response_json = response.json()
                    if (
                        "script" in response_json and "alert" in response_json["script"]
                    ):  # An alert is shown
                        alert = (
                            re.search('alert\\(\\"(.*)\\"\\)', response_json["script"])
                            .group(1)
                            .replace("\\n", "\n")
                            .replace("\\<br/\\>", "\n")
                        )
                        raise RuntimeError(f"{error_msg} Detail:\n{alert}")
                    elif (
                        "dialog" in response_json and "data" in response_json["dialog"]
                    ):  # An html dialog is shown
                        response_html: str = response_json["dialog"]["data"]
                        re_error_div = re.search(
                            '<div id="form_error_box"[\\s\\S]*?>([\\s\\S]*?)</div>',
                            response_html,
                        )
                        error_div = re_error_div.group(1)
                        error_li_list = re.findall("<li>([\\s\\S]*?)</li>", error_div)
                        error_detail = "\n".join(error_li_list).replace("<br/>", "\n")
                        raise RuntimeError(f"{error_msg} Detail:\n{error_detail}")
                    else:  # Other json response
                        raise RuntimeError(f"{error_msg} Unexpected response.")
                else:  # Not json
                    raise RuntimeError(
                        f"{error_msg} Unexpected response content type: {response.headers['Content-Type']}."
                    )

            else:  # Other status codes
                raise RuntimeError(
                    f"{error_msg} Unexpected status code {response.status_code}."
                )

        form_json = re_form.group(1)
        ticket = re_form.group(2)

        # Handle escape characters
        form = json.loads(form_json.replace("\\\\", "\\").replace('\\"', '"'))
        form["ticket"] = ticket
        return form

    def __submit_form(self, form: dict, hack: Optional[dict] = None) -> dict:
        params = {
            "userId": "",
            "ticket": form["ticket"],
            "ticketId": form["ticketId"],
        }
        form_submit = {**form, **self.__reserve_info}
        if hack is not None:
            form_submit = {**form_submit, **hack}

        message = {
            "form": json.dumps(form_submit),
            "ticket": form_submit["ticket"],
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
            if self.__intervene is not None:
                try:
                    self.__intervene()
                except Exception as e:
                    res["message"] = f"Intervene error:\n{str(e)}"
                    sio.disconnect()
                    return
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
        return res

    def reserve(
        self, hack_form: Optional[dict] = None, hack_submit: Optional[dict] = None
    ) -> None:
        if not isinstance(hack_form, dict):
            raise ValueError(f"hack_form must be a dictionary, not {type(hack_form)}.")
        if not isinstance(hack_submit, dict):
            raise ValueError(
                f"hack_submit must be a dictionary, not {type(hack_submit)}."
            )
        form = self.__form_acquiry(hack_form)
        res = self.__submit_form(form, hack_submit)
        if not res["success"]:
            raise RuntimeError(f"Failed to reserve. Detail:\n{res['message']}")
        else:
            return {"component_id": res["component_id"]}


def schedule(
    dtend: int,
    days_in_advance: int,
    delay_seconds: float = 0,
    ticket_alive_seconds: float = TICKET_ALIVE_SECONDS,
):
    dest_time = int(dtend)  # The end time of the reservation period
    seconds_per_day = 86400  # 24 * 60 * 60
    seconds_before_reserve = days_in_advance * seconds_per_day  # reserve ahead of time
    submit_time = (
        dest_time - seconds_before_reserve + delay_seconds
    )  # The time to submit the reservation

    def wrapper():
        print("Connection established.")
        line_break = ""
        while True:
            cur_time = time.time()
            time_left = submit_time - cur_time
            if time_left <= 0:
                break
            if time_left > ticket_alive_seconds:
                raise RuntimeError(
                    f"Ticket will expire before the scheduled submission. Submission is scheduled in {time_left:.4f} seconds, but ticket will expire in {ticket_alive_seconds} seconds."
                )
            print(
                f"\rTime left (s): {time_left:.4f}",
                end="",
            )
            line_break = "\n"
        print(f"{line_break}Submitting...\n")

    return wrapper


def single_reserve(
    credential: dict,
    dtstart: int,
    dtend: int,
    reserve_info: dict,
    equipment_id: Optional[str] = None,
    equipment_info: Optional[dict] = None,
    component_id: Optional[str] = None,
    intervene: Optional[callable] = None,
    hackstart: Optional[int] = None,
    hackend: Optional[int] = None,
    hackuser_id: Optional[str] = None,
) -> dict:
    if not isinstance(credential, dict):
        raise ValueError(f"credential must be a dictionary, not {type(credential)}.")

    user = User()
    # Set cookies for user
    if "cookies" in credential and isinstance(credential["cookies"], dict):
        user.set_cookies(cookies=credential["cookies"])
    elif "username" in credential and "password" in credential:
        user.set_credential(
            username=str(credential["username"]), password=str(credential["password"])
        )
        if "login_method" in credential:
            user.set_login_method(login_method=credential["login_method"])
        user.set_cookies()
    else:
        raise ValueError(
            "Invalid credential. Either provide username and password or provide cookies."
        )

    # Initialize reserve
    reserve = Reserve()
    reserve.set_user(user=user)
    reserve.set_cookies()
    reserve.set_equipment_info(equipment_id=equipment_id, equipment_info=equipment_info)

    if not isinstance(reserve_info, dict):
        raise ValueError(
            f"reserve_info must be a dictionary, not {type(reserve_info)}."
        )
    reserve_info_submit = {**reserve_info, "dtstart": int(dtstart), "dtend": int(dtend)}

    hack_form = {}
    # Fake reserve info, just for hacking
    if hackstart is not None:
        hack_form["dtstart"] = hackstart
    if hackend is not None:
        hack_form["dtend"] = hackend

    hack_submit = {}
    if component_id is not None and component_id != "":
        hack_submit["component_id"] = str(component_id)
    if hackuser_id is not None and hackuser_id != "":
        hack_submit["currentUserId"] = str(hackuser_id)

    reserve.set_reserve_info(reserve_info=reserve_info_submit)

    if intervene is not None and callable(intervene):
        reserve.set_intervene(intervene=intervene)

    res = reserve.reserve(hack_form=hack_form, hack_submit=hack_submit)
    return res
