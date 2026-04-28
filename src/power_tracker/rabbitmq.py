import os
import socket

import pika
from pika.exceptions import AMQPConnectionError


def build_connection(heartbeat: int | None = None) -> pika.BlockingConnection:
    """Create and return an authenticated RabbitMQ BlockingConnection.

    Connection parameters are read from environment variables:
      RABBITMQ_HOST     (default: localhost)
      RABBITMQ_PORT     (default: 5672)
      RABBITMQ_USER     (default: guest)
      RABBITMQ_PASSWORD (default: guest)
      RABBITMQ_VHOST    (default: /)

    Args:
        heartbeat: Optional AMQP heartbeat interval in seconds.
                   When None the pika default is used.

    Raises:
        ConnectionError: If the host is not reachable or AMQP auth fails.
    """
    host = os.environ.get("RABBITMQ_HOST", "localhost")
    port = int(os.environ.get("RABBITMQ_PORT", 5672))
    user = os.environ.get("RABBITMQ_USER", "guest")
    password = os.environ.get("RABBITMQ_PASSWORD", "guest")
    vhost = os.environ.get("RABBITMQ_VHOST", "/")

    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        raise ConnectionError(
            f"RabbitMQ host {host}:{port} is not reachable. "
            "Check host/IP, firewall, and broker listener settings."
        ) from exc

    credentials = pika.PlainCredentials(
        username=user,
        password=password,
    )
    params_kwargs: dict = {
        "host": host,
        "port": port,
        "credentials": credentials,
        "virtual_host": vhost,
        "connection_attempts": 3,
        "retry_delay": 2,
        "socket_timeout": 5,
    }
    if heartbeat is not None:
        params_kwargs["heartbeat"] = heartbeat

    params = pika.ConnectionParameters(**params_kwargs)
    try:
        return pika.BlockingConnection(params)
    except AMQPConnectionError as exc:
        raise ConnectionError(
            f"AMQP connection failed for {user}@{host}:{port} vhost={vhost!r}. "
            "Verify credentials, vhost permissions, and broker auth settings."
        ) from exc
