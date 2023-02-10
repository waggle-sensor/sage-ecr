class TokenNotFound(Exception):
    pass


class StaticAuthenticator:

    def __init__(self, items):
        self.items = items

    def get_token_info(self, token):
        try:
            info = self.items[token]
        except KeyError:
            raise TokenNotFound()

        user_id = info["id"]
        return {
            "user": user_id,
            "is_admin": info.get("is_admin", False),
            "is_approved": info.get("is_approved", False),
            "scopes": info.get("scopes", ""),
        }


class SageAuthenticator:

    def get_token_info(self, token):
        raise TokenNotFound()
        # # ask sage token introspection
        # headers = {"Accept":"application/json; indent=4", "Authorization": f"Basic {config.tokenInfoPassword}" , "Content-Type":"application/x-www-form-urlencoded"}
        # data=f"token={token}"
        # r = requests.post(config.tokenInfoEndpoint, data = data, headers=headers, timeout=5)
        # result_obj = r.json()
        # if not "active" in result_obj:
        #     #res = Response(f'Authorization failed (broken response) {result_obj}', mimetype= 'text/plain', status=500)
        #     res= ErrorWResponse(f'Authorization failed (broken response) {result_obj}', status_code=HTTPStatus.UNAUTHORIZED)
        #     return res(environ, start_response)

        # is_active = result_obj.get("active", False)
        # if not is_active:
        #     #res = Response(f'Authorization failed (token not active)', mimetype= 'text/plain', status=401)
        #     res= ErrorWResponse(f'Authorization failed (token not active)', status_code=HTTPStatus.UNAUTHORIZED)
        #     return res(environ, start_response)

        # user_id = result_obj.get("username")
