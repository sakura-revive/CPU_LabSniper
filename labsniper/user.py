from .credential import Credential

COOKIE_KEYS = ["session_lims2_cf_cpu"]


class User:
    def __init__(self, credential: Credential, tag: str = "默认用户") -> None:
        """
        Initializes the User object with a tag.

        Args:
            tag (str): The tag for the user. Default is "默认用户".
        """
        if not isinstance(credential, Credential):
            msg = f"Invalid parameter. Detail:\n给定的凭证的类型不正确，不能是{type(credential)}."
            raise TypeError(msg)
        self.tag = tag
        self.credentials = credential
        self.cookies: dict[str:str] = {}

    def is_cookie_valid(self) -> bool:
        return all(key in self.cookies for key in COOKIE_KEYS)

    def get_cookies(self) -> dict:
        if not self.is_cookie_valid():
            cookies = self.credentials.login()
            self.cookies = {
                key: cookies[key] for key in cookies.keys() if key in COOKIE_KEYS
            }
            if not self.is_cookie_valid():
                msg = (
                    "Invalid cookie. Detail:\nCookie不完整，可能是登录失败或凭证错误。"
                )
                raise RuntimeError(msg)
        return self.cookies
