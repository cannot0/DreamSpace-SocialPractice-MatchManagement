"""寒暑假返家乡活动推荐模块。"""

import os
import sys


VENDOR_DIR = os.path.join(os.path.dirname(__file__), ".vendor")
if os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

