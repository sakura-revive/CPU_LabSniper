import re
from abc import ABC, abstractmethod
from enum import auto, Enum

import requests

from .utils import normalize_string


class CredentialType(Enum):
    """Enum for credential types."""

    LOCAL = auto()
    SSO = auto()
    MANUAL = auto()

    def __str__(self):
        return self.name


class Credential(ABC):
    def __init__(self, credential_type: CredentialType):
        self.credential_type = credential_type

    def get_credential_type(self) -> CredentialType:
        return self.credential_type

    @abstractmethod
    def login(self) -> dict:
        """Abstract method for logging in."""
        pass


class LocalCredential(Credential):
    def __init__(self, username: str, password: str):
        """Initialize local credential with username and password."""
        super().__init__(credential_type=CredentialType.LOCAL)

        self.username = normalize_string(username, param_name="用户名")
        self.password = normalize_string(password, param_name="密码")

    def login(self) -> dict:
        session = requests.Session()

        login_url = "https://dygx1.cpu.edu.cn/lims/login"
        headers = {
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
        }
        data = {
            "token": self.username,
            "password": self.password,
            "submit": "登录",
        }
        # Login
        try:
            response = session.post(url=login_url, headers=headers, data=data)
        except Exception as e:
            msg = f"Failed to login ({type(e).__name__}). Detail:\n"
            msg += "网络异常，无法连接至服务器，本地登录失败。"
            raise RuntimeError(msg) from e

        if response.status_code == 401:  # Unauthorized
            msg = "Failed to login (401 Unauthorized). Detail:\n"
            pattern = r'<div class="message message_error"><p>(.*)</p></div>'
            re_msg = re.search(pattern, response.text)
            if re_msg:
                msg += f"{re_msg.group(1)}"
            else:
                msg += "本地登录失败，请检查用户名和密码是否正确。"
            raise RuntimeError(msg)

        cookies = session.cookies.get_dict()
        return cookies


class SSOCredential(Credential):
    def __init__(self, username: str, password: str) -> None:
        """Initialize SSO credential with username and password."""
        super().__init__(credential_type=CredentialType.SSO)

        self.username = normalize_string(username, param_name="用户名")
        self.password = normalize_string(password, param_name="密码")

    def encode(self, string: str) -> str:
        from base64 import b64encode

        # Base64 encode a string twice
        return b64encode(b64encode(str(string).encode("utf-8"))).decode("utf-8")

    def login(self) -> dict:
        session = requests.Session()  # Start a login session

        login_url = "https://id.cpu.edu.cn/sso/login"
        service = "https://dygx1.cpu.edu.cn/gateway/login?from=cpu&redirect=http%3A%2F%2Fdygx1.cpu.edu.cn%2Flims%2F%21people%2Fcpu%2Flogin"
        params = {"service": service}

        headers = {
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
        }
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
            "username": self.encode(self.username),
            "password": self.encode(self.password),
            "rememberpwd": "on",
        }
        try:
            # To the login page
            session.get(login_url, params=params, headers=headers)
            # Login
            response = session.post(login_url, params=params, data=data)
        except Exception as e:
            msg = f"Failed to login via SSO ({type(e).__name__}). Detail:\n"
            msg += "网络异常，无法连接至服务器，统一身份认证登录失败。"
            raise RuntimeError(msg) from e

        if response.status_code == 401:  # Unauthorized
            msg = "Failed to login via SSO (401 Unauthorized). Detail:\n"
            pattern = r'<div class="tips"><span>(.*)</span></div>'
            re_msg = re.search(pattern, response.text)
            if re_msg:
                msg += f"{re_msg.group(1)}"
            else:
                msg += "统一身份认证登录失败，请检查用户名和密码是否正确。"
            raise RuntimeError(msg)

        cookies = session.cookies.get_dict()
        return cookies


class ManualCredential(Credential):
    def __init__(self, cookies: dict) -> None:
        """Initialize manual credential with username and password."""
        super().__init__(credential_type=CredentialType.MANUAL)

        if not isinstance(cookies, dict):
            msg = f"Invalid parameter. Detail:\nCookies必须为字典类型，而不是{type(cookies)}."
            raise TypeError(msg)
        self.cookies = cookies

    def login(self) -> dict:
        return self.cookies
