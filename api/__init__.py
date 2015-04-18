# We need to do this so that bottle can deal with multiple clients simultaneously and use web sockets.
# VERY IMPORTANT NOTE: always, always, always, make sure that this is called before all other code. If some
# things are not monkey patched you will see very weird unpredictable bugs.
from gevent import monkey
monkey.patch_all()