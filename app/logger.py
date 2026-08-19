import logging


def setup_logger() -> None:
    """
    Set up the logger configuration for the application.

    This function configures logging for container-friendly stdout output
    and sets the log level for specific loggers.

    Logs are written only to the console (stream handler).

    The log level for the "aiogram.event" and "httpx" loggers is set to CRITICAL.

    :return: None
    """
    # Set up basic logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # noqa
        handlers=[
            # Add a stream handler to log to the console
            logging.StreamHandler(),
        ]
    )
    # Set the log level for aiogram.event and httpx logger to CRITICAL
    aiogram_logger = logging.getLogger("aiogram.event")
    aiogram_logger.setLevel(logging.CRITICAL)
