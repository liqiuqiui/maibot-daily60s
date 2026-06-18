"""daily60s 插件测试的本地 pytest 配置。"""

from __future__ import annotations

import sys
from pathlib import Path


# 插件测试迁到插件目录后，不再经过仓库根下的 pytests/conftest.py。
# 这里补上相同的路径注入，确保依旧能直接导入项目与 src 模块。
project_root = Path(__file__).resolve().parents[3]
src_root = project_root / "src"

if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))
if str(project_root) not in sys.path:
    sys.path.insert(1, str(project_root))
