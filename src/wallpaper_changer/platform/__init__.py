# -*- coding: utf-8 -*-
"""Automatic selection of the operating-system backend."""

from __future__ import annotations

import sys

if sys.platform == "win32":  # pragma: no cover - depende do SO
    from .win import Platform
elif sys.platform == "darwin":  # pragma: no cover
    from .macos import Platform
else:  # pragma: no cover
    from .linux import Platform

platform = Platform()
