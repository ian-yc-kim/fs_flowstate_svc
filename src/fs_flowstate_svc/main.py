import logging

import uvicorn

from fs_flowstate_svc.app import app
from fs_flowstate_svc.config import settings

# Set up logging for the application
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    uvicorn.run(app, host="0.0.0.0", port=settings.SERVICE_PORT)


if __name__ == "__main__":
    # Entry point for the application
    main()
