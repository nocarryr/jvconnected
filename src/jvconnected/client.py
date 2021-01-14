from loguru import logger
import asyncio
import httpx
import httpcore

class ClientError(Exception):
    def __init__(self, msg, response_obj, data=None):
        self.msg = msg
        self.response_obj = response_obj
        self.data = data
    def __str__(self):
        return f'{self.msg}: {self.response_obj} - {self.data}'

class ClientAuthError(ClientError):
    pass

class ClientNetworkError(ClientError):
    pass

class Client(object):
    """Http client wrapper

    Arguments:
        hostaddr (str): The network host address
        auth_user (str): Api username
        auth_pass (str): Api password

    """
    AUTH_URI = '/api.php'
    CMD_URI = '/cgi-bin/api.cgi'
    def __init__(self, hostaddr: str, auth_user: str, auth_pass: str, hostport: int = 80):
        if hostaddr.endswith('/'):
            hostaddr = hostaddr.rstrip('/')
        if not hostaddr.startswith('http'):
            hostaddr = f'http://{hostaddr}'
        self.hostaddr = hostaddr
        self.hostport = hostport
        self._client = None
        if auth_user is None:
            auth_user = ''
        if auth_pass is None:
            auth_pass = ''
        self.auth = httpx.DigestAuth(auth_user, auth_pass)
        self._authenticated = False
        self._error = False

    @property
    def netloc(self):
        return f'{self.hostaddr}:{self.hostport}'

    def _build_uri(self, path: str):
        path = path.lstrip('/')
        return f'{self.netloc}/{path}'

    async def _authenticate(self):
        """Authenticate with the host using digest auth
        """
        if self._authenticated:
            return
        if self._error:
            return
        uri = self._build_uri(self.AUTH_URI)
        resp = await self._client.get(uri)
        try:
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(exc)
            self._error = True
            if resp.status_code == 401:
                raise ClientAuthError(f'Unauthorized for "{uri}"', resp)
        self._authenticated = True

    async def open(self):
        """Open the Http client session and authenticate
        """
        if self._client is None:
            self._authenticated = False
            self._error = False
            try:
                self._client = httpx.AsyncClient(auth=self.auth)
                await self._authenticate()
            except (httpcore.NetworkError, httpcore.TimeoutException,
                    httpx.NetworkError, httpx.TimeoutException) as exc:
                logger.warning(repr(exc))
                self._error = True
                raise ClientNetworkError(str(exc), exc)

    async def close(self):
        """Close the client session
        """
        if self._client is not None:
            c = self._client
            self._client = None
            await c.aclose()

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def request(self, command: str, params=None):
        """Make an api request

        Arguments:
            command (str): The api command name
            params (dict, optional): Data parameters for the command (if needed)

        Returns:
            dict:
                The response data
        """
        if self._error:
            return
        payload = {'Request':{'Command':command}}
        if params is not None:
            payload['Request']['Params'] = params
        uri = self._build_uri(self.CMD_URI)
        try:
            resp = await self._client.post(uri, json=payload)
        except (httpcore.NetworkError, httpcore.TimeoutException, httpcore.ProtocolError,
                httpx.NetworkError, httpx.TimeoutException, httpx.ProtocolError) as exc:
            logger.warning(repr(exc))
            self._error = True
            raise ClientNetworkError(str(exc), exc)
        try:
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(exc)
            self._error = True
            raise
        data = resp.json()
        # logger.debug(f'Response: {data}')
        resp_data = self._check_response_data(command, resp, data)
        return resp_data

    @logger.catch
    def _check_response_data(self, command, resp, data):
        """Validate an api response from the host
        """
        resp_data = data.get('Response', {})
        if resp_data.get('Result') != 'Success':
            raise ClientError('Result failure', resp, data)
        elif resp_data.get('Requested') != command:
            raise ClientError('Response does not match request', resp, data)
        return resp_data

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'
    def __str__(self):
        return self.hostaddr
