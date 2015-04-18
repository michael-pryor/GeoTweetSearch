from api.config import Configuration
from api.core.utility import getModulePath
from api.web.web_socket import WebSocket

MODULE_PATH = getModulePath(__file__)
STATIC_PATH = MODULE_PATH + '/static'
TEMPLATE_PATH = MODULE_PATH + '/views'

WEBSITE_ROOT_HTTP = 'http://' + Configuration.WEBSITE_ROOT
WEBSITE_ROOT_WEBSOCKET = 'ws://' + Configuration.WEBSITE_ROOT

PROBLEM_ROUTE = '/problem'
PROBLEM_ROUTE_HTTP = WEBSITE_ROOT_HTTP + PROBLEM_ROUTE

""" Arguments accessible by all templates """
DEFAULT_TEMPLATE_ARGS = {'socket_ops': WebSocket.OP.__dict__,
                         'cloud_key' : Configuration.CLOUD_MADE_API_KEY,
                         'static_root' : WEBSITE_ROOT_HTTP + Configuration.WEB_STATIC_ROUTE,
                         'problem_route' : PROBLEM_ROUTE_HTTP,
                         'project_name' : Configuration.PROJECT_NAME,
                         'website_root' : WEBSITE_ROOT_HTTP}

