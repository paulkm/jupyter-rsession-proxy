import os
import json
import logging
import subprocess as sp

from tornado import web

from notebook.utils import url_path_join as ujoin
from notebook.base.handlers import IPythonHandler

logger = logging.getLogger('nbrsessionproxy')

class RSessionProxyHandler(IPythonHandler):

    rsession_port = 8005
    rsession_path = '/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/sbin:/sbin:/bin'
    rsession_ld_lib_path = '/usr/lib/R/lib:/lib:/usr/lib/x86_64-linux-gnu:/usr/lib/jvm/java-7-openjdk-amd64/jre/lib/amd64/server'

    rsession_env = {
        'R_DOC_DIR':'/usr/share/R/doc', 
        'R_HOME':'/usr/lib/R', 
        'R_INCLUDE_DIR':'/usr/share/R/include', 
        'R_SHARE_DIR':'/usr/share/R/share', 
        'RSTUDIO_DEFAULT_R_VERSION':'3.3.0', 
        'RSTUDIO_DEFAULT_R_VERSION_HOME':'/usr/lib/R', 
        'RSTUDIO_LIMIT_RPC_CLIENT_UID':'998', 
        'RSTUDIO_MINIMUM_USER_ID':'500', 
    }
    rsession_cmd = [
        '/usr/lib/rstudio-server/bin/rsession',
        '--standalone=1',
        '--program-mode=server',
        '--log-stderr=1',
        '--www-port={}'.format(rsession_port),
        '--user-identity={}'.format(os.environ['USER']),
    ]

    proc = None

    @web.authenticated
    def post(self):
        logger.info('%s request to %s', self.request.method, self.request.uri)

        server_env = os.environ.copy()

        # Seed RStudio's R and RSTUDIO variables
        server_env.update(self.rsession_env)

        # Prepend RStudio's PATH and LD_LIBRARY_PATH
        server_env['PATH'] = self.rsession_path + ':' + server_env['PATH']
        server_env['LD_LIBRARY_PATH'] = \
            self.rsession_ld_lib_path + ':' + server_env['LD_LIBRARY_PATH']

        # Runs rsession in background since we do not need stdout/stderr
        self.proc = sp.Popen(self.rsession_cmd, env=server_env)

        if self.proc.poll() == 0:
            raise web.HTTPError(reason='rsession terminated', status_code=500)
            self.finish()

        response = {
            'pid':self.proc.pid,
            'url':'{}proxy/{}/'.format(self.base_url, self.rsession_port),
        }

        self.finish(json.dumps(response))

    @web.authenticated
    def get(self):
        if not self.proc:
            self.set_status(500)
            self.write('rsession not yet started')
            self.finish()
        self.finish(self.proc.poll())
 
    def delete(self):
        logger.info('%s request to %s', self.request.method, self.request.uri)
        self.proc.kill()
        self.finish(self.proc.poll())

def setup_handlers(web_app):
    host_pattern = '.*$'
    route_pattern = ujoin(web_app.settings['base_url'], '/rsessionproxy/?')
    web_app.add_handlers(host_pattern, [
        (route_pattern, RSessionProxyHandler)
    ])
    logger.info('Added handler for route %s', route_pattern)

# vim: set et ts=4 sw=4: