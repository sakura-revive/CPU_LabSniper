import sys
import threading

from rich.console import Console, Group
from rich.box import ROUNDED
from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .utils import normalize_string, simple_exception_output

sys.excepthook = simple_exception_output


class ThreadMonitor:
    def __init__(
        self,
        main_title: str = "主程序",
        thread_title: str = "任务汇总",
        max_cols: int = 3,
    ) -> None:
        if not isinstance(max_cols, int):
            msg = "Invalid parameter. Detail:\n"
            msg += f"参数无效，最大列数必须为整数类型，而不是{type(max_cols)}."
            raise msg
        if max_cols <= 0:
            msg = f"Invalid parameter. Detail:\n"
            msg += f"参数无效，最大列数必须为正整数。"
        self.max_cols = max_cols

        self.main_title = normalize_string(
            main_title, param_name="主标题", allow_empty=True
        )
        self.thread_title = normalize_string(
            thread_title, param_name="线程标题", allow_empty=True
        )

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        self.main_thread_output = ""
        self.thread_name_mapping: dict[str, str] = {}
        self.thread_data: dict[str, str] = {}
        self.lock = threading.Lock()

        self.console = Console(file=self.original_stdout)
        self.live = Live(
            console=self.console,
            screen=False,
            auto_refresh=False,
            redirect_stdout=False,
            redirect_stderr=False,
            # vertical_overflow="visible",
        )
        self.live.start()

        sys.stdout = self
        sys.stderr = self

    def register_thread_as(self, target_thread_name: str) -> None:
        with self.lock:
            thread = threading.current_thread()
            self.thread_name_mapping[thread.name] = target_thread_name

    def __enter__(self) -> "ThreadMonitor":
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        self.stop()

    def __del__(self) -> None:
        self.stop()

    def stop(self) -> None:
        with self.lock:
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            try:
                self.live.stop()
            except Exception:
                pass

    def generate_renderable(self) -> Table:
        panels = []
        if self.main_thread_output != "":
            main_panel = Panel(
                Text(self.main_thread_output, style="white"),
                title=self.main_title,
                border_style="green",
                expand=True,
            )
            panels.append(main_panel)

        num_threads = len(self.thread_data)
        if num_threads == 0:
            table = Table(box=None, show_header=False, show_lines=False)
        else:
            num_cols = min(self.max_cols, num_threads)
            num_rows = -(num_threads // (-num_cols))  # 向上取整

            table = Table(
                box=ROUNDED,  # 圆角边框
                border_style=Style(color="cyan"),
                title=self.thread_title,
                show_header=False,
                show_lines=True,
                expand=True,
            )
            for _ in range(num_cols):
                table.add_column(
                    style=Style(color="white"),
                    justify="left",
                    vertical="top",
                    # min_width=20,
                )

            for i in range(num_rows):
                row_data = []
                for j in range(num_cols):
                    thread_idx = i * num_cols + j
                    if thread_idx < num_threads:
                        row_data.append(list(self.thread_data.values())[thread_idx])
                    else:
                        row_data.append("")
                table.add_row(*row_data)
        panels.append(table)

        return Group(*panels)

    def write(self, message: str) -> None:
        with self.lock:
            thread = threading.current_thread()
            target_thread_name = self.thread_name_mapping.get(thread.name, thread.name)
            if target_thread_name in self.thread_data:
                self.thread_data[target_thread_name] += message
            elif target_thread_name == "MainThread":
                self.main_thread_output += message
            else:
                self.thread_data[target_thread_name] = message
            grid = self.generate_renderable()
            self.live.update(grid, refresh=True)

    def flush(self) -> None:
        pass
