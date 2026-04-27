import json
import os
import socket
import time

import pika
from pika.exceptions import AMQPConnectionError
from dotenv import load_dotenv

from power_tracker.sensors import WattageSensor, get_sensor
from power_tracker.system_info import get_local_ip, get_system_name

load_dotenv()

_POLL_INTERVAL = int(os.environ.get("CLIENT_POLL_INTERVAL", 5))


def _build_connection() -> pika.BlockingConnection:
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
    params = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
        virtual_host=vhost,
        connection_attempts=3,
        retry_delay=2,
        socket_timeout=5,
    )
    try:
        return pika.BlockingConnection(params)
    except AMQPConnectionError as exc:
        raise ConnectionError(
            f"AMQP connection failed for {user}@{host}:{port} vhost={vhost!r}. "
            "Verify credentials, vhost permissions, and broker auth settings."
        ) from exc


def run_client(sensor: WattageSensor | None = None):
    if sensor is None:
        sensor = get_sensor()

    system_name = get_system_name()
    local_ip = get_local_ip()
    print(f"System: {system_name} ({local_ip})")

    queue = os.environ.get("RABBITMQ_QUEUE", "wattage_readings")
    connection = _build_connection()
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)

    print(f"Publishing to queue '{queue}' every {_POLL_INTERVAL}s.")

    try:
        while True:
            readings = sensor.get_wattage()
            for source, watts in readings.items():
                payload = json.dumps({
                    "source": source,
                    "watts": watts,
                    "system_name": system_name,
                    "local_ip": local_ip,
                })
                channel.basic_publish(
                    exchange="",
                    routing_key=queue,
                    body=payload,
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                print(f"  -> {source}: {watts:.3f} W")
            time.sleep(_POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        connection.close()


if __name__ == "__main__":
    run_client()
