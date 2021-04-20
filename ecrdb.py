
import sys
import time

import MySQLdb

#from config import *
import config
import json
from error_response import *
from datetime import datetime , timedelta
import re
import logging
import base64

#logger = logging.getLogger('gunicorn.error')
#logger = logging.getLogger('__name__')
logger=None

class EcrDB():
    def __init__ ( self , retries=60) :

        if not config.mysql_host:
            raise Exception("mysql_host is not defined")

        count = 0
        while True:
            try:
                self.db=MySQLdb.connect(host=config.mysql_host,user=config.mysql_user,
                  passwd=config.mysql_password,db=config.mysql_db)
            except Exception as e: # pragma: no cover
                if count > retries:
                    raise
                print(f'Could not connnect to database, error={e}, retry in 2 seconds', file=sys.stderr)
                time.sleep(2)
                count += 1
                continue
            break

        self.cur=self.db.cursor()
        return

    # returns true if user has the permissions
    # TODO if resourceType  = repository, also check namespace
    def hasPermission(self, resourceType, resourceName, granteeType, grantee, permission):

        if not grantee:
            raise Exception("grantee undefined")

        permissions = [permission]

        if permission != "FULL_CONTROL":

            if permission == "READ":
                permissions = [permission, "WRITE", "FULL_CONTROL" ]
            elif permission == "READ_ACP":
                permissions = [permission, "WRITE_ACP", "FULL_CONTROL" ]
            else:
                permissions = [permission, "FULL_CONTROL" ]



        permissionIN = "permission IN (%s"+ " , %s" * (len(permissions) -1) + ")"


        permissionsPublicRead = 'FALSE'
        if permission == 'READ'  and not (granteeType == 'GROUP' and grantee == "Allusers"):
            permissionsPublicRead='(granteeType="GROUP" AND grantee="Allusers")'

        stmt = f'SELECT * FROM Permissions WHERE resourceType = %s AND resourceName = %s AND ((  granteeType = %s AND grantee = %s AND ({permissionIN}) ) OR {permissionsPublicRead}  )'
        #print(f'stmt: {stmt}  resourceType={resourceType} resourceName={resourceName} granteeType={granteeType} grantee={grantee} permissions={json.dumps(permissions)}', file=sys.stderr)

        debug_stmt = stmt


        debug_stmt = debug_stmt.replace("%s", resourceType, 1)
        debug_stmt = debug_stmt.replace("%s", resourceName, 1)
        debug_stmt = debug_stmt.replace("%s", granteeType, 1)
        debug_stmt = debug_stmt.replace("%s", grantee, 1)
        for p in permissions:
            debug_stmt = debug_stmt.replace("%s", p, 1)


        print(f'(hasPermission) debug stmt: {debug_stmt}', file=sys.stderr)


        self.cur.execute(stmt, (resourceType, resourceName, granteeType, grantee,  *permissions ))
        row = self.cur.fetchone()
        if row == None:
            return False

        if len(row) > 0:
            return True

        return False



    def deleteApp(self, namespace, repository, version, force=False):


        app, ok = self.getApp(namespace=namespace, name=repository, version=version)

        if not ok:
            raise Exception("App not found")

        app_id = app.get("id", "")
        if not app_id:
            raise Exception("App id empty")

        frozen = app.get("frozen", False)
        if frozen and (not force):
            raise Exception("App {app_id} is frozen, it cannot be deleted")


        #namespace = app["namespace"]
        #name = app["name"]
        #version = app["version"]

        for table in ["Apps", "Sources", "Certifications", "Profiles"]:

            stmt_apps = f'DELETE FROM {table} WHERE `id` = %s'
            print(f'stmt: {stmt_apps} app_id={app_id}', file=sys.stderr)
            self.cur.execute(stmt_apps, (app_id, ))

        self.db.commit()

        return 1

    # TODO listApps may be the better function to use
    def getApp(self, app_id=None, namespace=None, name=None, version=None):

        #current_identifier = ""
        if app_id:
            #current_identifier = app_id
            stmt = f'SELECT  id, {config.dbFields_str} FROM Apps WHERE `id` = %s'
            print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
            self.cur.execute(stmt, (app_id, ))
        else:
            #current_identifier = f'{namespace}/{name}:{version}'
            stmt = f'SELECT id, {config.dbFields_str} FROM Apps WHERE namespace = %s AND name = %s AND version = %s'
            print(f'stmt: {stmt} id={namespace}/{name}:{version}', file=sys.stderr)
            self.cur.execute(stmt, (namespace, name, version ))

        returnFields = ["id"] + config.dbFields
        returnObj={}
        row = self.cur.fetchone()
        i = 0
        if row == None:
            return {}, False
        for value in row:
            print(f'value: {value}', file=sys.stderr)
            returnObj[returnFields[i]] = value
            i+=1


        if not app_id:
            app_id = row[0]


        #decode embedded json
        for field in ["inputs", "metadata"]:
            value = returnObj.get(field, None)
            if value:
                try:
                    returnObj[field] = json.loads(value)
                except Exception as e:
                    raise Exception(f'Error in reading json in field {field}, got "{value}" and error {str(e)}')

        stmt = f'SELECT id, resource FROM Resources WHERE `id` = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))
        resources = []
        rows = self.cur.fetchall()
        for row in rows:
            row_obj = json.loads(row[1])
            resources.append(row_obj)

        if len(resources) > 0:
            returnObj["resources"] = resources


        stmt = f'SELECT  `id`, architectures , url, branch, directory, dockerfile, build_args FROM Sources WHERE `id` = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))
        #sources_array = []
        rows = self.cur.fetchall()

        row = rows[0]


        source_obj = {}

        source_obj["architectures"] = json.loads(row[1])
        source_obj["url"] = row[2]
        source_obj["branch"] = row[3]
        source_obj["directory"] = row[4]
        source_obj["dockerfile"] = row[5]
        source_obj["build_args"] = json.loads(row[6])

        #sources_array.append(source_obj)


        returnObj["source"] = source_obj

        return returnObj, True

    def getAppField(self, app_id, field):
        stmt = f'SELECT  id, {field} FROM Apps WHERE `id` = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))

        returnFields = ["id", field]
        returnObj={}
        row = self.cur.fetchone()
        i = 0
        if row == None:
            raise ErrorResponse(f'App {app_id} not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        for value in row:
            print(f'value: {value}', file=sys.stderr)
            returnObj[returnFields[i]] = value
            i+=1

        #decode embedded json
        if field in ["inputs", "metadata"]:
            if field in returnObj:
                returnObj[field] = json.loads(returnObj[field])

        return returnObj[field]


    def listApps(self, user="", app_id="", namespace="", repository="", limit=None, continuationToken=None, isAdmin=False):

        query_data = []

        appID_condition = ''
        if app_id != "":
            appID_condition = ' AND id = %s'
            query_data.append(app_id)


        repo_condition= ''
        if repository:
            if not namespace:
                raise Exception("Repository specified without namespace")

            repo_condition = ' AND Apps.name=%s'
            query_data.append(repository)

        namespace_condition= ''
        if namespace:
            namespace_condition = ' AND Apps.namespace=%s'
            query_data.append(namespace)

        user_condition = 'FALSE'
        if isAdmin:
            user_condition = 'TRUE'
        else:
            if user != "" :
                user_condition = '(granteeType="USER" AND grantee=%s)'
                query_data.append(user)

        limit_stmt = ""

        if limit:
            if not isinstance(limit, int):
                raise Exception("limit has to be of type int")

            limit_stmt = f" LIMIT {limit}"

        token_stmt = ""
        if continuationToken:
            continuationToken = base64.b64decode(str.encode(continuationToken)).decode()
            token_stmt = f" WHERE id > %s "
            query_data.append(continuationToken)

        # this line matches the correct app row with the correct permissions rows
        sub_stmt =  '( Permissions.resourceType="repository" AND Permissions.resourceName=CONCAT(Apps.namespace , "/", Apps.name )  OR (Permissions.resourceType="namespace" AND Permissions.resourceName=Apps.namespace) )'

        stmt = f'SELECT DISTINCT id, namespace, name, version, time_created FROM Apps INNER JOIN Permissions  ON {sub_stmt} {appID_condition} {repo_condition} {namespace_condition} AND ( ({user_condition}) OR (granteeType="GROUP" AND grantee="AllUsers")) AND (permission in ("READ", "WRITE", "FULL_CONTROL")) {token_stmt}  ORDER BY `namespace`, `name`, `version` ASC  {limit_stmt}'

        debug_stmt = stmt
        for key in query_data:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        logger.debug(f'(listApps) debug stmt: {debug_stmt}')


        #print(f'stmt: {stmt}', file=sys.stderr)
        self.cur.execute(stmt , query_data)

        #self.cur.rowcount


        rows = self.cur.fetchall()

        app_list = []

        for row in rows:
            print(f'row: {row}', file=sys.stderr)

            app_list.append({"id": row[0], "namespace": row[1], "name": row[2], "version":row[3], "time_created":row[4]})

        return app_list

    def listNamespaces(self, user=""):

        query_data = []

        user_condition = 'FALSE'
        if user != "" :
            user_condition = '(granteeType="USER" AND grantee=%s)'
            query_data.append(user)



        stmt = f'SELECT DISTINCT id , owner_id FROM Namespaces INNER JOIN Permissions  ON Permissions.resourceType="namespace" AND Permissions.resourceName=Namespaces.id  AND ( ({user_condition}) OR (granteeType="GROUP" AND grantee="AllUsers")) AND (permission in ("READ", "WRITE", "FULL_CONTROL"))'


        print(f'stmt: {stmt}', file=sys.stderr)

        debug_stmt = stmt
        if user != "" :
            debug_stmt = debug_stmt.replace("%s", f'"{user}"', 1)
        print(f'(listNamespaces) debug stmt: {debug_stmt}', file=sys.stderr)

        self.cur.execute(stmt , query_data)



        rows = self.cur.fetchall()

        app_list = []

        for row in rows:
            print(f'row: {row}', file=sys.stderr)

            app_list.append({"id": row[0], "owner_id": row[1], "type": "namespace"})

        return app_list


    def listRepositories(self, user="", namespace=""):

        query_data = []


        namespace_condition=''
        if namespace:
            namespace_condition='AND Repositories.namespace=%s'
            query_data.append(namespace)


        user_condition = 'FALSE'
        if user != "" :
            user_condition = '(granteeType="USER" AND grantee=%s)'
            query_data.append(user)


        sub_stmt =  '( Permissions.resourceType="repository" AND Permissions.resourceName=CONCAT(Repositories.namespace , "/", Repositories.name )  OR (Permissions.resourceType="namespace" AND Permissions.resourceName=Repositories.namespace) )'

            # not needed ?  --->    AND ( Permissions.resourceName LIKE CONCAT(Repositories.namespace, \"%%\") )

        stmt = f'''SELECT DISTINCT namespace , name , owner_id FROM Repositories INNER JOIN Permissions ON {sub_stmt} {namespace_condition}    AND ( ({user_condition}) OR (granteeType="GROUP" AND grantee="AllUsers")) AND (permission in ("READ", "WRITE", "FULL_CONTROL"))'''



        debug_stmt = stmt
        for key in query_data:
            debug_stmt = debug_stmt.replace("%s", key, 1)




        print(f'(listRepositories) debug stmt: {debug_stmt}', file=sys.stderr)
        #print(f'stmt: {stmt}', file=sys.stderr)
        #print(f'query_data: {query_data}', file=sys.stderr)
        self.cur.execute(stmt , query_data)
        #self.cur.execute(stmt , (namespace, user))
        #self.cur.execute(debug_stmt )


        rows = self.cur.fetchall()

        rep_list = []
        print(f'len(rows): {len(rows)}', file=sys.stderr)
        for row in rows:
            print(f'row: {row}', file=sys.stderr)

            rep_list.append({"type": "repository", "namespace": row[0], "name": row[1], "owner_id": row[2]})

        return rep_list


    def getPermissions(self, resourceType, resourceName):
        stmt = f'SELECT  resourceType, resourceName, granteeType , grantee, permission FROM Permissions WHERE resourceType = %s AND resourceName = %s'
        print(f'stmt: {stmt} resourceType={resourceType}, resourceName={resourceName}', file=sys.stderr)
        self.cur.execute(stmt, (resourceType, resourceName ))

        rows = self.cur.fetchall()

        perm_list = []

        for row in rows:
            #print(f'row: {row}', file=sys.stderr)

            perm_list.append({"resourceType": row[0], "resourceName": row[1], "granteeType": row[2], "grantee":row[3], "permission":row[4]})

        return perm_list


    def addPermission(self, resourceType, resourceName, granteeType , grantee , permission):

        if granteeType=="GROUP" and grantee=="AllUsers" and permission != "READ":
            raise ErrorResponse(f'AllUsers can only get READ permission.', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        stmt = f'INSERT IGNORE INTO Permissions ( resourceType, resourceName, granteeType , grantee, permission) VALUES (%s , %s , %s,  %s, %s)'

        debug_stmt = stmt

        for key in [resourceType, resourceName, granteeType , grantee , permission]:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        print(f'(addPermission) debug stmt: {debug_stmt}', file=sys.stderr)


        self.cur.execute(stmt, (resourceType, resourceName, granteeType, grantee , permission))

        self.db.commit()

        return int(self.cur.rowcount)

    # deletes all permissions unless limited by any of optional parameters
    # permissions for owner will be excluded
    def deletePermissions(self, owner, resourceType, resourceName, granteeType=None , grantee=None , permission=None):

        #owner = self.getAppField(app_id, "owner")

        if not owner:
            raise ErrorResponse('Owner not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        stmt_delete_permissions = f'DELETE FROM Permissions WHERE resourceType = %s AND resourceName =%s'
        params = [resourceType, resourceName]
        if granteeType:
            stmt_delete_permissions += ' AND granteeType=%s'
            params.append(granteeType)

        if grantee:
            stmt_delete_permissions += ' AND grantee=%s'
            params.append(grantee)

        if permission:
            stmt_delete_permissions += ' AND permission=%s'
            params.append(permission)

        # make sure owner does not take his own permissions away

        stmt_delete_permissions +=  ' AND NOT (granteeType="USER" AND grantee=%s AND permission="FULL_CONTROL")'
        params.append(owner)

        print(f'delete stmt: {stmt_delete_permissions} params='+json.dumps(params), file=sys.stderr)
        self.cur.execute(stmt_delete_permissions, params)
        self.db.commit()


        return int(self.cur.rowcount)


    def getBuildInfo(self, app_id, name):



        stmt = f'SELECT  id, build_number , architectures FROM Builds WHERE id = %s AND build_name=%s ORDER BY time_created DESC LIMIT 1'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, name))

        row = self.cur.fetchone()
        if row == None:
            raise Exception("No build id found in database")


        number = row[1]
        architectures = json.loads(row[2])


        return (number, architectures)

    def SaveBuildInfo(self, app_id, build_name, build_number, architectures):

        architectures_str = json.dumps(architectures)


        stmt = 'REPLACE INTO Builds ( id, build_name, build_number, architectures)  VALUES (%s , %s,  %s, %s) '


        self.cur.execute(stmt, (app_id, build_name, build_number, architectures_str))

        self.db.commit()


        return


    # return user id if token found, empty string otherwise
    def getTokenInfo(self, token):
        stmt = 'SELECT user, scopes, is_admin FROM TokenCache WHERE SHA2(%s, 512) = token'
        print(f'stmt: {stmt} token={token[:4]}...', file=sys.stderr)

        self.cur.execute(stmt, (token,))


        row = self.cur.fetchone()
        i = 0
        if row == None:
            return "", "", False

        if len(row) != 3 :
            return "", "", False

        return row[0], row[1] , row[2]

    def setTokenInfo(self, token, user_id, scopes, is_admin):

        # ignore should be ok, scopes should not change for a given token

        stmt = 'INSERT IGNORE INTO TokenCache (token, user, scopes, is_admin, expires) VALUES (SHA2(%s, 512), %s, %s, %s, %s)'

        expires = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

        self.cur.execute(stmt, (token, user_id, scopes, is_admin, expires))

        self.db.commit()

        return

    # returns owner, otherwise empty string
    def getNamespace(self, name):
        stmt = 'SELECT id, owner_id FROM Namespaces WHERE id = %s'
        print(f'stmt: {stmt} id=name', file=sys.stderr)

        self.cur.execute(stmt, (name,))


        row = self.cur.fetchone()

        if row == None:
            return {}, False

        if len(row) != 2 :
            raise Exception("wrong number of columns")

        returnObj = {}
        returnObj["id"] = row[0]
        returnObj["owner_id"] = row[1]
        return returnObj, True

    def deleteNamespace(self, namespace):

        stmt = f'DELETE FROM Namespaces WHERE id = %s'
        debug_stmt = stmt
        debug_stmt = debug_stmt.replace("%s", f'"{namespace}"', 1)

        print(f'debug_stmt: {debug_stmt}', file=sys.stderr)

        self.cur.execute(stmt, (namespace,))


        self.db.commit()

        return 1

    def addNamespace(self, name, owner_id, public=False):

        # name restriction from https://docs.docker.com/docker-id/
        # "... can only contain numbers and lowercase letters."

        p = re.compile(f'[a-z0-9]+', re.ASCII)
        if not p.match(name):
            raise Exception("Namespace can only contain numbers and lowercase letters")

        if len(name) < 4 or len(name) > 30 :
            raise Exception("Namespace must be between 4 and 30 characters long")

        stmt = 'INSERT INTO Namespaces (id, owner_id) VALUES (%s, %s)'
        print(f'stmt: {stmt} id=name', file=sys.stderr)

        self.cur.execute(stmt, (name, owner_id))


        stmt = 'REPLACE INTO Permissions (resourceType, resourceName, granteeType, grantee, permission) VALUES (%s, %s, %s, %s, %s)'
        print(f'stmt: {stmt} id={name}', file=sys.stderr)

        self.cur.execute(stmt, ("namespace", name, "USER", owner_id, "FULL_CONTROL"))

        if public:
            self.cur.execute(stmt, ("namespace", name, "GROUP", "AllUsers", "READ"))

        self.db.commit()


        result, ok = self.getNamespace(name)
        if not ok:
            raise Exception("namespace creation failed")


        return result

    # returns owner, otherwise empty string
    def getRepository(self, namespace, name):

        #full_name = f'{namespace}/{name}'

        stmt = 'SELECT namespace, name, owner_id FROM Repositories WHERE namespace = %s AND name = %s'
        print(f'stmt: {stmt} namespace={namespace} name={name}', file=sys.stderr)

        self.cur.execute(stmt, (namespace,name))


        row = self.cur.fetchone()

        if row == None:
            return {}, False

        if len(row) != 3 :
            raise Exception("Number of columns wrong")

        returnObj = {}
        returnObj["namespace"] = row[0]
        returnObj["name"] = row[1]
        returnObj["owner_id"] = row[2]
        return returnObj, True

    def deleteRepository(self, namespace, name):

        stmt = f'DELETE FROM Repositories WHERE namespace = %s AND name = %s'
        debug_stmt = stmt
        debug_stmt = debug_stmt.replace("%s", f'"{namespace}"', 1)
        debug_stmt = debug_stmt.replace("%s", f'"{name}"', 1)

        print(f'debug_stmt: {debug_stmt}', file=sys.stderr)

        self.cur.execute(stmt, (namespace, name))

        resourceName = f'{namespace}/{name}'
        stmt = f'DELETE FROM Permissions WHERE resourceType = "repository" AND resourceName =%s'
        debug_stmt = stmt
        debug_stmt = debug_stmt.replace("%s", f'"{resourceName}"', 1)
        print(f'debug_stmt: {debug_stmt}', file=sys.stderr)
        self.cur.execute(stmt, (resourceName,))

        self.db.commit()
        return 1


    def addRepository(self, namespace, name, owner_id):

        # name restriction from https://docs.docker.com/docker-hub/repos/
        # "The repository name needs to be unique in that namespace, can be two to 255 characters, and can only contain lowercase letters, numbers or - and _."

        p = re.compile(f'[a-z0-9_-]+', re.ASCII)
        if not p.match(name):
            raise Exception("Repository can only contain numbers and lowercase letters")

        if len(name) < 2 or len(name) > 255 :
            raise Exception("Repository must be between 2 and 255 characters long")



        stmt = 'INSERT INTO Repositories (namespace, name, owner_id) VALUES (%s, %s, %s)'
        print(f'stmt: {stmt} namespace={namespace} name={name}', file=sys.stderr)

        self.cur.execute(stmt, (namespace, name, owner_id))

        full_name = f'{namespace}/{name}'
        stmt = 'INSERT INTO Permissions (resourceType, resourceName, granteeType, grantee, permission) VALUES (%s, %s, %s, %s, %s)'
        print(f'stmt: {stmt} id={full_name}', file=sys.stderr)

        self.cur.execute(stmt, ("repository", full_name, "USER", owner_id, "FULL_CONTROL"))


        self.db.commit()
        return 1


