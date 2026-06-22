from databricks import sql
from databricks.sdk.core import Config
from config import HTTP_PATH

cfg = Config()


def get_connection():
    return sql.connect(
        server_hostname=cfg.host,
        http_path=HTTP_PATH,
        credentials_provider=lambda: cfg.authenticate,
    )
