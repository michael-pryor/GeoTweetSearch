from api.caching.caching_shared import getDatabase

__author__ = 'Michael Pryor'


if __name__ == '__main__':
    db = getDatabase()
    db.place.remove()
    db.geocode.remove()