"""
config.py — centralized environment configuration for the CAP agent.

All CAP credentials and endpoints come from environment variables so
that no secret ever needs to be hardcoded or committed to git. See
.env.example for the full list of variables this agent expects.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from croo import Config


@dataclass
class AppConfig:
    croo_config: Config
    sdk_key: str
    service_id: str | None  # only required by the requester / demo script


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(
            f"ERROR: missing required environment variable '{name}'. "
            f"Copy .env.example to .env, fill it in, then `export $(cat .env | xargs)` "
            f"(or use python-dotenv) before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    return val


def load_provider_config() -> AppConfig:
    return AppConfig(
        croo_config=Config(
            base_url=_require("CROO_API_URL"),
            ws_url=_require("CROO_WS_URL"),
            rpc_url=os.environ.get("BASE_RPC_URL", ""),
        ),
        sdk_key=_require("CROO_SDK_KEY"),
        service_id=None,
    )


def load_requester_config() -> AppConfig:
    return AppConfig(
        croo_config=Config(
            base_url=_require("CROO_API_URL"),
            ws_url=_require("CROO_WS_URL"),
            rpc_url=os.environ.get("BASE_RPC_URL", ""),
        ),
        sdk_key=_require("CROO_SDK_KEY"),
        service_id=_require("CROO_TARGET_SERVICE_ID"),
    )
