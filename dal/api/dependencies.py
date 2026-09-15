from fastapi import Request

from .services import APIServices


def services(request: Request) -> APIServices:
    return request.app.state.services
