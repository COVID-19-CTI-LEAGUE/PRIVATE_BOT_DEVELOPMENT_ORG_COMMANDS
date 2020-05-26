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

from ..shared_code import db, utils


def main(req: func.HttpRequest) -> func.HttpResponse:
    if not utils.is_request_authorized(req):
        return func.HttpResponse(
            'Unauthorized',
            status_code=403
        )
    
    response_url, trigger_id, user_id, params = utils.get_slack_command(req)

    args = params.split(' ')
    resp = {}

    if len(args) < 2:
        resp = utils.build_response('Missing parameter, please specif')
