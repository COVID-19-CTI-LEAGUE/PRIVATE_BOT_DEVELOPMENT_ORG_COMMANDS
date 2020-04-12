import time

def verify_signature(request, timestamp, signature):
    # Verify the request signature of the request sent from Slack
    # Generate a new hash using the app's signing secret and request data

    # Compare the generated hash and incoming request signature
    # Python 2.7.6 doesn't support compare_digest
    # It's recommended to use Python 2.7.7+
    # noqa See https://docs.python.org/2/whatsnew/2.7.html#pep-466-network-security-enhancements-for-python-2-7

    if abs(time() - int(timestamp)) > 60 * 5:
        return False

    if hasattr(hmac, "compare_digest"):
        req = str.encode('v0:' + str(timestamp) + ':') + request.get_data()
        request_hash = 'v0=' + hmac.new(
            str.encode(self.signing_secret),
            req, hashlib.sha256
        ).hexdigest()
        # Compare byte strings for Python 2
        if (sys.version_info[0] == 2):
            return hmac.compare_digest(bytes(request_hash), bytes(signature))
        else:
            return hmac.compare_digest(request_hash, signature)
    else:
        # So, we'll compare the signatures explicitly
        req = str.encode('v0:' + str(timestamp) + ':') + request.get_data()
        request_hash = 'v0=' + hmac.new(
            str.encode(self.signing_secret),
            req, hashlib.sha256
        ).hexdigest()

        if len(request_hash) != len(signature):
            return False
        result = 0
        if isinstance(request_hash, bytes) and isinstance(signature, bytes):
            for x, y in zip(request_hash, signature):
                result |= x ^ y
        else:
            for x, y in zip(request_hash, signature):
                result |= ord(x) ^ ord(y)
        return result == 0


def build_response(message):
    resp = { "response_type" : "ephemeral",
            "text" : message,
            "type" : "mrkdwn"
            }
    return resp

def get_slack_profile(user_id):
    contact_info = {}
    try:
        resp=slack.users_profile_get(user=user_id)
        if resp['ok']:
            contact_info= {
                'full_name' :   resp['profile']['real_name'],
                'display_name' :  resp['profile']['display_name'],
                'title' :  resp['profile']['title']
                }
        return contact_info
    except:
        pass
    return None
