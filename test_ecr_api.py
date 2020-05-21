#!/usr/bin/env python3

import os
import tempfile

import pytest

from ecr_api import app

# from https://flask.palletsprojects.com/en/1.1.x/testing/
@pytest.fixture
def client():
    db_fd, app.config['DATABASE'] = tempfile.mkstemp()
    app.config['TESTING'] = True

    with app.test_client() as client:
        #with app.app_context():
        #    init_db()
        yield client

    os.close(db_fd)
    os.unlink(app.config['DATABASE'])


def test_connect(client):
    """Start with a blank database."""

    rv = client.get('/')
    assert b'SAGE Edge Code Repository' in rv.data