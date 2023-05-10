from http import HTTPStatus
import werkzeug
from werkzeug.wrappers import Response
import json

# from https://flask.palletsprojects.com/en/1.1.x/patterns/apierrors/
class ErrorResponse(werkzeug.exceptions.HTTPException):
    status_code = HTTPStatus.BAD_REQUEST

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
            self.code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


def ErrorWResponse(message, status_code=None, payload=None):
    return Response(json.dumps({"error":message}), mimetype="application/json", headers={"Access-Control-Allow-Origin": "*"},  status=status_code)

