

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
        

        return func(self, **kwargs)
    
    return wrapper2



def has_permission(*permission):
    def real_decorator(func):
        def wrapper(self, app_id):
                

            authenticated = request.environ['authenticated']

            ecr_db = ecrdb.EcrDB()


            if not authenticated:
                if not (ecr_db.hasPermission(app_id, "GROUP", "AllUsers" , permission)):
                    raise ErrorResponse(f'Not authorized.', status_code=HTTPStatus.UNAUTHORIZED)

            requestUser = request.environ.get('user', "")
            isAdmin = request.environ.get('admin', False)


            if (isAdmin or ecr_db.hasPermission(app_id, "USER", requestUser ,permission)):
                return func(self, app_id)

            raise ErrorResponse(f'Not authorized.', status_code=HTTPStatus.UNAUTHORIZED)


        
       
        return wrapper
    return real_decorator



def has_resource_permission(permission):
    def real_decorator(func):
        def wrapper2(self, namespace, repository=None, version=None):


            authenticated = request.environ['authenticated']


            resourceType = ""
            resourceName = ""
            if repository:
                resourceType="repository"    
                resourceName=f'{namespace}/{repository}'
            else:
                resourceType="namespace"    
                resourceName=namespace

            ecr_db = ecrdb.EcrDB()


            if not authenticated:
                if (ecr_db.hasPermission(resourceType, resourceName, "GROUP", "AllUsers" , permission)):
                    return func(self, namespace, repository, version)

                raise ErrorResponse(f'Not authorized.', status_code=HTTPStatus.UNAUTHORIZED)
                

            requestUser = request.environ.get('user', "")
            isAdmin = request.environ.get('admin', False)

            if not repository:
                # check namespace permission only

                if (isAdmin or ecr_db.hasPermission(resourceType, resourceName, "USER", requestUser ,permission)):
                    #return func(self, namespace, repository, version)
                    return func(self, namespace)
                    
                raise ErrorResponse(f'Not authorized. (User {requestUser} does not have permission {permission} for {resourceType} {resourceName})', status_code=HTTPStatus.UNAUTHORIZED)

            #
            # check repository permission and namespace-inherited permission
            hasNamespaceAccess = ecr_db.hasPermission("namespace", namespace, "USER", requestUser , permission)

            if (isAdmin or hasNamespaceAccess or ecr_db.hasPermission(resourceType, resourceName, "USER", requestUser ,permission)):
                return func(self, namespace, repository, version)

            raise ErrorResponse(f'Not authorized. (User {requestUser} does not have permission {permission} for {resourceType} {resourceName})', status_code=HTTPStatus.UNAUTHORIZED)


        
       
        return wrapper2
    return real_decorator

