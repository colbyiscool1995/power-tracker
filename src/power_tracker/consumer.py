import json
import os
import socket

import pika
from pika.exceptions import AMQPConnectionError
from dotenv import load_dotenv

from power_tracker.database import init_db, insert_wattage_reading

load_dotenv()


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
        heartbeat=60,
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


def _on_message(channel, method, properties, body):
    try:
        payload = json.loads(body)
        source = payload["source"]
        watts = float(payload["watts"])
        system_name = payload.get("system_name", "")
        local_ip = payload.get("local_ip", "")
        insert_wattage_reading(source, watts, system_name, local_ip)
        print(f"Inserted: [{system_name}] {source} = {watts:.3f} W")
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        print(f"Failed to process message due to invalid payload: {e} — nacking without requeue")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"Failed to process message due to transient error: {e} — nacking for retry")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def run_consumer():
    init_db()
    queue = os.environ.get("RABBITMQ_QUEUE", "wattage_readings")
    connection = _build_connection()
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue=queue, on_message_callback=_on_message)
    print(f"Consuming from queue '{queue}'. Ctrl+C to stop.")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    run_consumer()
