from databricks import sql
from databricks.sdk.core import Config
from config import HTTP_PATH

_cfg = None


def _get_config():
    global _cfg
    if _cfg is None:
        _cfg = Config()
    return _cfg


def get_connection():
    cfg = _get_config()
    return sql.connect(
        server_hostname=cfg.host,
        http_path=HTTP_PATH,
        credentials_provider=lambda: cfg.authenticate,
    )
