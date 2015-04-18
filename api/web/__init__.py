__author__ = 'Michael Pryor'
from config import TEMPLATE_PATH, STATIC_PATH

import bottle
bottle.TEMPLATE_PATH.insert(0,TEMPLATE_PATH)