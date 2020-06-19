
import sys
import time

import MySQLdb

#from config import *
import config
import json
from error_response import *

class EcrDB():
    def __init__ ( self , retries=60) :
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

    # returns true if user has any of the permissions 
    def hasPermission(self, app_id, granteeType, grantee, permissions):

        permissionIN = "permission IN (%s"+ " , %s" * (len(permissions) -1) + ")"
        #permissionOR = "permission = %s" + " OR permission = %s" * (len(permissions) -1)
      

        permissionsPublicRead = 'FALSE'
        if 'READ' in permissions and not (granteeType == 'GROUP' and grantee == "Allusers"):
            permissionsPublicRead='(granteeType="GROUP" AND grantee="Allusers")'

        stmt = f'SELECT BIN_TO_UUID(id) FROM AppPermissions WHERE BIN_TO_UUID(id) = %s AND (( granteeType = %s AND grantee = %s AND ({permissionIN}) ) OR {permissionsPublicRead}  )'
        print(f'stmt: {stmt} app_id={app_id} granteeType={granteeType} grantee={grantee} permissions={json.dumps(permissions)}', file=sys.stderr)
    
        self.cur.execute(stmt, (app_id, granteeType, grantee,  *permissions ))
        row = self.cur.fetchone()
        if row == None:
            return False

        if len(row) > 0:
            return True

        return False

       


    def deleteApp(self, app_id):
        stmt_apps = f'DELETE FROM Apps WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt_apps} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt_apps, (app_id, ))


        stmt_permissions = f'DELETE FROM AppPermissions WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt_permissions} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt_permissions, (app_id, ))

        self.db.commit()

        return



    def getApp(self, app_id):
        stmt = f'SELECT  BIN_TO_UUID(id), {config.dbFields_str} FROM Apps WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))

        returnFields = ["id"] + config.dbFields
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
        for field in ["inputs", "metadata"]:
            value = returnObj.get(field, None)
            if value:
                try:
                    returnObj[field] = json.loads(value)
                except Exception as e:
                    raise Exception(f'Error in reading json in field {field}, got "{value}" and error {str(e)}')
        
        stmt = f'SELECT  BIN_TO_UUID(id), resource FROM Resources WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))
        resources = []
        rows = self.cur.fetchall()
        for row in rows:
            row_obj = json.loads(row[1])
            resources.append(row_obj)

        if len(resources) > 0:
            returnObj["resources"] = resources


        stmt = f'SELECT  BIN_TO_UUID(id), name, architectures , url, branch, directory, dockerfile FROM Sources WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))
        sources_array = []
        rows = self.cur.fetchall()
        for row in rows:

            source_obj = {}
            source_obj["name"] = row[1]
            source_obj["architectures"] = json.loads(row[2])
            source_obj["url"] = row[3]
            source_obj["branch"] = row[4]
            source_obj["directory"] = row[5]
            source_obj["dockerfile"] = row[6]


            sources_array.append(source_obj)


        returnObj["sources"] = sources_array

        return returnObj
    
    def getAppField(self, app_id, field):
        stmt = f'SELECT  BIN_TO_UUID(id), {field} FROM Apps WHERE BIN_TO_UUID(id) = %s'
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


    def listApps(self, user="", app_id=""):

        query_data = []

        appID_condition = 'TRUE'
        if app_id != "":
            appID_condition = f'id = %s'
            query_data.append(app_id)
 
        user_condition = 'FALSE'
        if user != "" :
            user_condition = '(granteeType="USER" AND grantee=%s)'
            query_data.append(user)



        stmt = f'SELECT  BIN_TO_UUID(id), name, version, owner FROM Apps INNER JOIN AppPermissions  USING (id) WHERE {appID_condition} AND ( ({user_condition}) OR (granteeType="GROUP" AND grantee="AllUsers")) AND (permission="READ" OR permission="FULL_CONTROL")'
        print(f'stmt: {stmt}', file=sys.stderr)
        self.cur.execute(stmt , query_data)

        #if user == "":
        #    # only public apps
        #    stmt = f'SELECT  BIN_TO_UUID(id), name, version, owner FROM Apps INNER JOIN AppPermissions  USING (id) WHERE  granteeType="GROUP" AND grantee="AllUsers" AND (permission="READ" OR permission="FULL_CONTROL")'
        #    print(f'stmt: {stmt}', file=sys.stderr)
        #    self.cur.execute(stmt)
        #else :
    #
        #    stmt = f'SELECT  BIN_TO_UUID(id), name, version, owner FROM Apps INNER JOIN AppPermissions  USING (id) WHERE ( (granteeType="USER" AND grantee=%s) OR (granteeType="GROUP" AND grantee="AllUsers")) AND (permission="READ" OR permission="FULL_CONTROL")'
        #    print(f'stmt: {stmt}', file=sys.stderr)
        #    self.cur.execute(stmt , (user,))

        
        rows = self.cur.fetchall()

        app_list = []

        for row in rows:
            print(f'row: {row}', file=sys.stderr)

            app_list.append({"id": row[0], "name": row[1], "version":row[2], "owner":row[3]})
        
        return app_list

    def getPermissions(self, app_id):
        stmt = f'SELECT  BIN_TO_UUID(id), granteeType , grantee, permission FROM AppPermissions WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))

        rows = self.cur.fetchall()

        perm_list = []

        for row in rows:
            #print(f'row: {row}', file=sys.stderr)

            perm_list.append({"id": row[0], "granteeType": row[1], "grantee":row[2], "permission":row[3]})

        return perm_list

    # TODO ignore Duplicate entry 
    def addPermission(self, app_id, granteeType , grantee , permission):

        if granteeType=="GROUP" and grantee=="AllUsers" and permission != "READ":
            raise ErrorResponse(f'AllUsers can only get READ permission.', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        stmt = f'INSERT INTO AppPermissions ( id, granteeType , grantee, permission) VALUES (UUID_TO_BIN(%s) , %s,  %s, %s)'
        self.cur.execute(stmt, (app_id, granteeType, grantee , permission))

        self.db.commit()

        return 1

    # deletes all permissions unless limited by any of optional parameters
    def deletePermissions(self, app_id, granteeType=None , grantee=None , permission=None):

        
        
        owner = self.getAppField(app_id, "owner")

        
        if not owner:
            raise ErrorResponse('Owner not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        

        stmt_delete_permissions = f'DELETE FROM AppPermissions WHERE BIN_TO_UUID(id) = %s'
        params = [app_id]
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
    
       

        stmt = f'SELECT  BIN_TO_UUID(id), build_number , architectures FROM Builds WHERE BIN_TO_UUID(id) = %s AND build_name=%s ORDER BY time_created DESC LIMIT 1'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, name))

        row = self.cur.fetchone()
        if row == None:
            raise Exception("No build id found in database")

       
        number = row[1]
        architectures = json.loads(row[2])


        return (number, architectures)

    def SaveBuildInfo(self, app_id, source_name, build_number, architectures):

        architectures_str = json.dumps(architectures)


        stmt = 'INSERT INTO Builds ( id, build_name, build_number, architectures)  VALUES (UUID_TO_BIN(%s) , %s,  %s, %s) '


        self.cur.execute(stmt, (app_id, source_name, build_number, architectures_str))

        self.db.commit()

        return
        


    # def setLastBuildID(self, app_id, source_name, queue_item_number, number):
        
        
    #     try:
                
    #         stmt = 'UPDATE Builds SET last_queue_id=%s, number=%s WHERE BIN_TO_UUID(id) = %s'

    #         self.cur.execute(stmt, (queue_item_number, number, app_id))

    #         self.db.commit()
    #     except Exception as e:
    #         raise ErrorResponse(f'error updating build info: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        
