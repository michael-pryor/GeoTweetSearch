import logging
from bottle import   static_file, Bottle, redirect, request, template
from api.config import Configuration
from api.web.twitter_instance import TwitterInstances, TwitterInstancesPruner
from config import STATIC_PATH, DEFAULT_TEMPLATE_ARGS, PROBLEM_ROUTE

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

def redirect_problem(errorDescription):
    return redirect(Configuration.WEBSITE_ROOT + PROBLEM_ROUTE + '?error=%s' % errorDescription)

class WebApplication(object):
    def __init__(self):
        super(WebApplication, self).__init__()
        self.bottle_app = Bottle()
        self.bottle_app.route(Configuration.WEB_STATIC_ROUTE + '/<file:path>', callback=self.static)
        self.bottle_app.route(PROBLEM_ROUTE, callback=self.problem_callback)

    def static(self, file):
        return static_file(file, root=STATIC_PATH)

    def problem_callback(self):
        error = request.GET.error
        args = {'ERROR': error}
        args.update(DEFAULT_TEMPLATE_ARGS)
        return template('problem.tpl', args)


class WebApplicationTwitter(WebApplication):
    def __init__(self, tweetQueue, maxInstanceInactiveTime, dataCollection):
        super(WebApplicationTwitter,self).__init__()

        self.twitter_instances = TwitterInstances(dataCollection, tweetQueue)
        self.twitter_instances_pruner = TwitterInstancesPruner(maxInstanceInactiveTime,
                                                               Configuration.MAX_INSTANCE_TOTAL_AGE_MS,
                                                               self.twitter_instances)
        self.twitter_instances_pruner.start()

    @property
    def tweet_queue(self):
        return self.twitter_instances.tweet_provider

    @tweet_queue.setter
    def tweet_queue(self, tweetQueue):
        self.twitter_instances.tweet_provider = tweetQueue

from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketHandler
def startServer(ip, port, bottle_app):
    """ Start running server.

        Browsers should point to http://IP:port.

        @param ip IP to host server on.
        @param port Port to host server on."""
    try:
        server = WSGIServer((ip, port), bottle_app, handler_class=WebSocketHandler)
        server.serve_forever()
    except Exception as e:
        logger.error('Server terminating ungracefully: %s' % e.message)
    else:
        logger.error('Server terminating gracefully')