import logging
import os
import sys
import json
import hmac
import hashlib
import re

import requests
import re
import os
import traceback

import azure.functions as func

from urllib.parse import parse_qs

from ..shared_code import db, utils


def main(req: func.HttpRequest) -> func.HttpResponse:
    if not utils.is_request_authorized(req):
        return func.HttpResponse(
            'Forbidden',
            status_code=403
        )
    
    response_url, trigger_id, user_id, org = utils.get_slack_command(req)
    resp = {}

    if len(org) == 0:
        resp = utils.build_response('Missing organization')
    else:
        resp = db.leave_org(user_id, org)

    return func.HttpResponse(
        json.dumps(resp),
        mimetype="application/json"
    )
