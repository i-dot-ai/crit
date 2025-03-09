import logging
import sys

logger = logging.getLogger("crit")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter(
    "%(created)f:%(levelname)s:%(name)s:%(module)s:%(message)s"
)
handler.setFormatter(formatter)

logger.addHandler(handler)
