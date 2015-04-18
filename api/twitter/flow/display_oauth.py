import logging
from urlparse import parse_qs
from bottle import request, redirect
from requests_oauthlib import OAuth1
import requests
from api.config import Configuration
from api.twitter.flow.display_core import Display
from api.web.web_core import WebApplicationTwitter, redirect_problem

__author__ = 'Michael'

logger = logging.getLogger(__name__)

class OAuthSignIn(Display):
    """ Initial oauth sign in page. First leg of 3 legged oauth. """
    link_info = Display.LinkInfo(lambda link: lambda: link, '/oauth/sign_in')

    def __init__(self, application, consumerToken, consumerSecret):
        Display.__init__(self, application, pageRoute=('/oauth/sign_in', None), webSocketManagers=None)
        assert isinstance(application, WebApplicationTwitter)
        self.consumer_token = consumerToken
        self.consumer_secret = consumerSecret


    @property
    def page_html_function(self):
        def func(templateArguments):
            oauth = OAuth1(self.consumer_token, client_secret=self.consumer_secret)
            response = requests.post('https://api.twitter.com/oauth/request_token',
                params={'oauth_callback': OAuthCallback.link_info.page_link}, auth=oauth)
            if not response.ok:
                return redirect_problem('Failed to retrieve oauth_token from twitter: %s' % response.text)

            qs = parse_qs(response.text)
            oauth_token = qs['oauth_token'][0]

            return redirect('https://api.twitter.com/oauth/authenticate?oauth_token=%s' % oauth_token)

        return func

class OAuthCallback(Display):
    """ Final stage of authorisation, twitter redirects here. """
    link_info = Display.LinkInfo(lambda link: lambda: link, '/oauth/callback')

    def __init__(self, application, consumerToken, consumerSecret, callbackLink):
        Display.__init__(self, application, pageRoute=('/oauth/callback', None), webSocketManagers=None)
        assert isinstance(application, WebApplicationTwitter)
        self.consumer_token = consumerToken
        self.consumer_secret = consumerSecret
        self.callback_link = callbackLink


    @property
    def page_html_function(self):
        def func(templateArguments):
            oauth_token = request.GET.oauth_token
            oauth_secret = request.GET.oauth_token_secret
            oauth_verifier = request.GET.oauth_verifier

            oauth = OAuth1(self.consumer_token, client_secret=self.consumer_secret, resource_owner_key=oauth_token, resource_owner_secret=oauth_secret, verifier=oauth_verifier)
            response = requests.post('https://api.twitter.com/oauth/access_token', auth=oauth)
            if not response.ok:
                return redirect_problem('Failed to retrieve oauth_secret from twitter')

            response = parse_qs(response.content)
            final_token = response['oauth_token'][0]
            final_token_secret = response['oauth_token_secret'][0]

            logger.info('oauth_token: %s, oauth_secret: %s received' % (final_token, final_token_secret))

            return redirect(Display.addArgumentsToLink(self.callback_link, oauth_token=final_token, oauth_secret=final_token_secret))

        return func

