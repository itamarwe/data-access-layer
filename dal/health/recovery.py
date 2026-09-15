"""Concrete recovery commands for the unified CLI."""

import shlex


def validate_command(root, path):
    return "dal validate"


def curate_command(kind, object_id):
    return "dal proposal create --help"
