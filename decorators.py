

from flask import request

#from ecrdb import *
import ecrdb

from error_response import ErrorResponse

from http import HTTPStatus


def login_required(func):
    def wrapper2(self, **kwargs):
        authenticated = request.environ['authenticated']
        if not authenticated:
            raise ErrorResponse('Not authenticated', status_code=HTTPStatus.UNAUTHORIZED)

        #if len(args) == 0:
        #    return func(self)
        

        return func(self, **kwargs)
    
    return wrapper2



def has_permission(*permissions):
    def real_decorator(func):
        def wrapper(self, app_id):
                

            authenticated = request.environ['authenticated']

            ecr_db = ecrdb.EcrDB()


            if not authenticated:
                if not (ecr_db.hasPermission(app_id, "GROUP", "AllUsers" , permissions)):
                    raise ErrorResponse(f'Not authorized.', status_code=HTTPStatus.UNAUTHORIZED)

            requestUser = request.environ.get('user', "")
            isAdmin = request.environ.get('admin', False)


            if (isAdmin or ecr_db.hasPermission(app_id, "USER", requestUser ,permissions)):
                return func(self, app_id)

            raise ErrorResponse(f'Not authorized.', status_code=HTTPStatus.UNAUTHORIZED)


        
       
        return wrapper
    return real_decorator


