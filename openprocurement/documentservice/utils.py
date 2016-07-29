import os
from ConfigParser import ConfigParser
from datetime import datetime
from hashlib import sha512
from json import dumps
from logging import getLogger
from pyramid.security import Allow
from pyramid.httpexceptions import exception_response
from pytz import timezone
from webob.multidict import NestedMultiDict

LOGGER = getLogger(__name__)
TZ = timezone(os.environ['TZ'] if 'TZ' in os.environ else 'Europe/Kiev')
USERS = {}


def auth_check(username, password, request):
    if username in USERS and USERS[username]['password'] == sha512(password).hexdigest():
        return ['g:{}'.format(USERS[username]['group'])]


class Root(object):
    def __init__(self, request):
        pass

    __acl__ = [
        (Allow, 'g:uploaders', 'upload'),
        (Allow, 'g:api', 'upload'),
    ]


def read_users(filename):
    config = ConfigParser()
    config.read(filename)
    for i in config.sections():
        USERS.update(dict([
            (
                j,
                {
                    'password': k,
                    'group': i
                }
            )
            for j, k in config.items(i)
        ]))


def request_params(request):
    try:
        params = NestedMultiDict(request.GET, request.POST)
    except UnicodeDecodeError:
        response = exception_response(422)
        response.body = dumps(error_handler(request, response.code, {"location": "body", "name": "data", "description": "could not decode params"}))
        response.content_type = 'application/json'
        raise response
    except Exception, e:
        response = exception_response(422)
        response.body = dumps(error_handler(request, response.code, {"location": "body", "name": str(e.__class__.__name__), "description": str(e)}))
        response.content_type = 'application/json'
        raise response
    return params


def add_logging_context(event):
    request = event.request
    request.logging_context = params = {
        'API_KEY': request.registry.apikey,
        'DOC_KEY': request.registry.dockey,
        'TAGS': 'python,docs',
        'CURRENT_URL': request.url,
        'CURRENT_PATH': request.path_info,
        'REMOTE_ADDR': request.remote_addr or '',
        'USER_AGENT': request.user_agent or '',
        'REQUEST_ID': request.environ.get('REQUEST_ID', ''),
        'CLIENT_REQUEST_ID': request.headers.get('X-Client-Request-ID', ''),
    }
    if request.params:
        params['PARAMS'] = str(dict(request.params))
    if request.matchdict:
        for i, j in request.matchdict.items():
            params[i.upper()] = j


def update_logging_context(request, params):
    for x, j in params.items():
        request.logging_context[x.upper()] = j


def context_unpack(request, msg, params=None):
    if params:
        update_logging_context(request, params)
    logging_context = request.logging_context
    journal_context = msg
    for key, value in logging_context.items():
        journal_context["JOURNAL_" + key] = value
    journal_context['JOURNAL_TIMESTAMP'] = datetime.now(TZ).isoformat()
    return journal_context


def error_handler(request, status, error):
    params = {
        'ERROR_STATUS': status
    }
    for key, value in error.items():
        params['ERROR_{}'.format(key)] = value
    LOGGER.info('Error on processing request "{}"'.format(dumps(error)),
                extra=context_unpack(request, {'MESSAGE_ID': 'error_handler'}, params))
    request.response.status = status
    return {
        "status": "error",
        "errors": [error]
    }
