"""按文件名顺序执行全部迁移。

用法（在 backend 目录）:
  python -m migrations.run
"""

from importlib import import_module
from pathlib import Path


def upgrade() -> None:
    here = Path(__file__).resolve().parent
    modules = [p.stem for p in sorted(here.glob("0*.py"))]
    if not modules:
        raise SystemExit("没有找到迁移脚本")
    for name in modules:
        print(f"==> migrations.{name}")
        module = import_module(f"migrations.{name}")
        module.upgrade()


if __name__ == "__main__":
    upgrade()
