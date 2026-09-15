import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

# Set before imports; prohibit metadata credential discovery.
for key, value in {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_DEFAULT_REGION": "eu-north-1",
    "AWS_REGION": "eu-north-1",
    "AWS_EC2_METADATA_DISABLED": "true",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "spill_test",
    "DB_USER": "test",
    "DB_PASS": "test",
    "IOT_ENDPOINT": "example.iot.eu-north-1.amazonaws.com",
    "SENDER": "sender@example.com",
    "RECIPIENTS": "recipient@example.com",
    "SES_FROM_EMAIL": "sender@example.com",
    "SES_TO_EMAILS": "recipient@example.com",
    "ALERT_FUNCTION_NAME": "test-alert",
}.items():
    os.environ[key] = value
ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), ROOT / "backend/lambda" / name / "lambda_function.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def loader():
    return load


@pytest.fixture
def ctx():
    return SimpleNamespace(aws_request_id="request-test")


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    import socket

    original = socket.socket.connect

    def guarded(sock, address):
        if isinstance(address, tuple) and address[0] not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            raise AssertionError("Tests must not access external services")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
