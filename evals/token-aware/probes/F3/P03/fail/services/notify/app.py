"""Routes for the notify service."""

from http import HTTPStatus


def send_email(request):
    return HTTPStatus.ACCEPTED, {"queued": True}


def send_webhook(request):
    return HTTPStatus.ACCEPTED, {"queued": True}


def health(request):
    return HTTPStatus.OK, "ok"


ROUTES = {
    ("POST", "/email"): send_email,
    ("POST", "/webhooks"): send_webhook,
    ("GET", "/health"): health,
}
