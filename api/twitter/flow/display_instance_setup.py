from Cookie import CookieError
import json
import logging
from bottle import template, request, redirect, response
from api.config import Configuration
from api.core.utility import parseString
from api.twitter.feed import TwitterAuthentication
from api.twitter.flow.display import LocationsMapPage, getHomeLink
from api.twitter.flow.display_core import Display
from api.web.twitter_instance import TwitterInstance
from api.web.web_core import WebApplicationTwitter

logger = logging.getLogger(__name__)



class GateInstance(Display):
    """ Overall instance management page.

        If no instance is running on this users account then display page to setup a new one.
        If one is already running then display page to manage that instance. """
    link_info = Display.LinkInfo(lambda link: lambda: link, '/gate_instance')

    def __init__(self, application):
        Display.__init__(self, application, pageRoute=('/gate_instance', None), webSocketManagers=None)
        assert isinstance(application, WebApplicationTwitter)

    @property
    def page_html_function(self):
        def func(templateArguments):
            oauth_token = request.GET.oauth_token
            oauth_secret = request.GET.oauth_secret
            templateArguments.update({'oauth_token': oauth_token,
                                      'oauth_secret': oauth_secret})

            oauth = TwitterInstance.makeAuthTuple(oauth_token, oauth_secret)
            if not self.application.twitter_instances.isAuthInUse(oauth):
                return self.start_instance_get(templateArguments)
            else:
                return self.manage_instance_get(templateArguments, oauth)

        return func

    def start_instance_get(self, template_arguments):
        template_arguments.update({'post_address': StartInstancePost.link_info.getPageLink()})

        keywords = request.GET.keywords
        regions = parseString(request.GET.regions,default='{}')
        instanceSetupCode = parseString(request.GET.instance_setup_code,default='')

        template_arguments.update({'home_link' : getHomeLink(Configuration.PROJECT_NAME),
                                   'keywords' : keywords,
                                   'regions' : regions,
                                   'instance_setup_code' : instanceSetupCode,
                                   'max_geographical_filters' : Configuration.TWITTER_MAX_GEO_FILTERS})

        error = request.GET.error
        if len(error) > 0:
            template_arguments.update({'error' : error})

        return template('instance-start.tpl', template_arguments)

    def manage_instance_get(self, template_arguments, oauth):
        # Cannot have tuple as key in json.
        oauthStr = unicode(oauth)

        instance = self.application.twitter_instances.getInstanceByAuth(oauth)
        if instance is None:
            return self.start_instance_get(template_arguments)

        try:
            instancesByName = json.loads(request.get_cookie('_instancesByName','{}'))
            instancesByAuth = json.loads(request.get_cookie('_instancesByAuth','{}'))
        except CookieError as e:
            # There seems to be a bug in Python cookie module (which bottle uses) causing it to fail when certain cookie keys
            # are present (even if we don't directly look them up). In repo see file documents/cookie-bug.png,
            # this try/catch prevents the bug from causing a serious issue.
            logger.warn('Cookie error while decoding _instancesByName or _instancesByAuth from user, deleting pre-existing cookies: %s' % e.message)
            instancesByName = dict()
            instancesByAuth = dict()

        # Delete old data in case auth used with different instance name previously.
        oldInstanceName = instancesByAuth.get(oauthStr, None)
        if oldInstanceName is not None:
            logger.info('Cleaning up old cookie data, association between account and instance')
            try:
                del instancesByAuth[oauthStr]
            except KeyError:
                pass

            try:
                del instancesByName[oldInstanceName]
            except KeyError:
                pass

        instancesByName[instance.instance_key] = oauth
        instancesByAuth[oauthStr] = instance.instance_key
        response.set_cookie('_instancesByName', json.dumps(instancesByName), path='/')
        response.set_cookie('_instancesByAuth', json.dumps(instancesByAuth), path='/')

        return redirect(LocationsMapPage.link_info.getPageLink(instance.instance_key))

class ManageInstancePost(Display):
    """ Post operation on manage instance means terminate that instance. """
    link_info = Display.LinkInfo(lambda link: lambda: link, '/manage_instance')

    def __init__(self, application):
        Display.__init__(self, application, pageRoute=('/manage_instance', ['POST']), webSocketManagers=None)
        assert isinstance(application, WebApplicationTwitter)


    @property
    def page_html_function(self):
        def func(templateArguments):
            oauth_token = request.forms.get('oauth_token')
            oauth_secret = request.forms.get('oauth_secret')

            oauth = TwitterInstance.makeAuthTuple(oauth_token, oauth_secret)
            removedInstance = self.application.twitter_instances.removeTwitterInstanceByAuth(oauth)

            if removedInstance is not None:
                assert isinstance(removedInstance, TwitterInstance)

                logger.info('Cleaned up twitter instance with oauth: %s' % unicode(oauth))

                try:
                    keywords = ','.join(removedInstance.twitter_thread.twitter_feed.keywords)
                except TypeError:
                    keywords = ''

                regions = removedInstance.geographic_setup_string
                instanceSetupCode = removedInstance.instance_setup_code
            else:
                keywords = None
                regions = None
                instanceSetupCode = None

            return redirect(Display.addArgumentsToLink(GateInstance.link_info.getPageLink(),
                                                       oauth_token=oauth_token,
                                                       oauth_secret=oauth_secret,
                                                       keywords=keywords,
                                                       regions=regions,
                                                       instance_setup_code=instanceSetupCode))

        return func


class StartInstancePost(Display):
    """ Post operation to start a new instance. """
    link_info = Display.LinkInfo(lambda link: lambda: link, '/start_instance')

    def __init__(self, application, consumerToken, consumerSecret, initialData=None):
        Display.__init__(self, application, pageRoute=('/start_instance', ['POST']), webSocketManagers=None)
        assert isinstance(application, WebApplicationTwitter)

        self.consumer_token = consumerToken
        self.consumer_secret = consumerSecret
        self.initial_data = initialData

    @property
    def page_html_function(self):
        def func(templateArguments):
            form = request.forms.decode('UTF-8')

            oauth_token = form.get('oauth_token')
            oauth_secret = form.get('oauth_secret')
            keywords = form.get('keywords')
            geographical_setup_string = unicode(form.get('regions')) # includes all geographical information including influence and twitter feed areas.
            instance_setup_code = form.get('instance_setup_code')

            keywordsList = None
            if keywords is not None:
                if len(keywords) > 0:
                    assert isinstance(keywords, basestring)
                    keywordsList = keywords.split(',')

            def redirectError(errorMessage):
                return redirect(Display.addArgumentsToLink(GateInstance.link_info.getPageLink(),
                                                           oauth_token=oauth_token,
                                                           oauth_secret=oauth_secret,
                                                           keywords=keywords,
                                                           regions=geographical_setup_string,
                                                           instance_setup_code=instance_setup_code,
                                                           error=errorMessage))



            if not oauth_token or not oauth_secret:
                return redirectError('Twitter login credentials are missing')

            oauth = TwitterInstance.makeAuthTuple(oauth_token, oauth_secret)
            if self.application.twitter_instances.isAuthInUse(oauth):
                # Do nothing, we will be redirected to the gate instance which will hopefully
                # correct this mistake.
                pass
            else:
                try:
                    twitterInstance = self.application.twitter_instances.createInstance(TwitterAuthentication(Configuration.CONSUMER_TOKEN, Configuration.CONSUMER_SECRET, oauth_token, oauth_secret),
                                                                                        geographical_setup_string,
                                                                                        keywordsList,
                                                                                        instance_setup_code)
                except ValueError as e:
                    return redirectError('Failed to setup instance, reason: %s' % e.message)

                error = twitterInstance.setup_error
                if error is not None:
                    return redirectError(error)

            return redirect(Display.addArgumentsToLink(GateInstance.link_info.getPageLink(), oauth_token=oauth_token, oauth_secret=oauth_secret))

        return func