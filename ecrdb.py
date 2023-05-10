import sys
import time

import MySQLdb

# from config import *
import config
import json
from error_response import *
from datetime import datetime, timedelta
import re
import logging
import base64
import bleach

logger = logging.getLogger(__name__)


class EcrDB:
    def __init__(self, retries=60):
        if not config.mysql_host:
            raise Exception("mysql_host is not defined")

        count = 0
        while True:
            try:
                self.db = MySQLdb.connect(
                    host=config.mysql_host,
                    user=config.mysql_user,
                    passwd=config.mysql_password,
                    db=config.mysql_db,
                )
            except Exception as e:  # pragma: no cover
                if count > retries:
                    raise
                print(
                    f"Could not connect to database, error={e}, retry in 2 seconds",
                    file=sys.stderr,
                )
                time.sleep(2)
                count += 1
                continue
            break

        self.cur = self.db.cursor()
        return

    def execute(self, query, values=None):
        self.cur.execute(query, values)

    def initdb(self):
        # TODO(sean) This should eventually be replaced with an actual database migration. Otherwise, we
        # will have to manually run any table alterations out of band to sync up to the tables below.

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Apps (
    id                  VARCHAR(194) UNIQUE NOT NULL,
    namespace           VARCHAR(64),
    name                VARCHAR(64),
    version             VARCHAR(64),
    frozen              BOOLEAN DEFAULT FALSE,
    description         TEXT,
    authors             TEXT,
    collaborators       TEXT,
    keywords            TEXT,
    homepage            TEXT,
    funding             TEXT,
    license             VARCHAR(256),
    depends_on          VARCHAR(128),
    baseCommand         VARCHAR(64),
    arguments           VARCHAR(256),
    inputs              TEXT,
    metadata            TEXT,
    testing             VARCHAR(256),
    schema_version      VARCHAR(64),
    time_created        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    owner               VARCHAR(64) NOT NULL,
    INDEX(id, namespace, name, version)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Sources (
    id                  VARCHAR(194) NOT NULL,
    architectures       VARCHAR(256),
    url                 VARCHAR(256) NOT NULL,
    branch              VARCHAR(64),
    tag                 VARCHAR(64),
    git_commit          VARCHAR(40), /* Typicall not set by user, but could be in the future */
    directory           VARCHAR(256),
    dockerfile          VARCHAR(256),
    build_args          VARCHAR(256),
    PRIMARY KEY (id)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Namespaces (
    id                  VARCHAR(32) NOT NULL,
    owner_id            VARCHAR(64) NOT NULL,
    PRIMARY KEY (id)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Repositories (
    namespace             VARCHAR(32) NOT NULL,
    name                  VARCHAR(256) NOT NULL,
    owner_id              VARCHAR(64) NOT NULL,
    description           TEXT,
    external_link         VARCHAR(256),
    PRIMARY KEY (namespace,name)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS MetaFiles (
    app_id                VARCHAR(194) NOT NULL,
    namespace             VARCHAR(64),
    name                  VARCHAR(64),
    version               VARCHAR(64),
    file_name             VARCHAR(256),
    file                  MEDIUMBLOB,
    kind                  ENUM('thumb', 'image', 'science_description'),
    description           TEXT,  /* maybe useful for alt text, but not currently used */
    PRIMARY KEY (app_id, file_name),
    INDEX(app_id, namespace, name, version)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Permissions (
    resourceType        VARCHAR(64),
    resourceName        VARCHAR(64),
    granteeType         ENUM('USER', 'GROUP'),
    grantee             VARCHAR(64),
    permission          ENUM('READ', 'WRITE', 'READ_ACP', 'WRITE_ACP', 'FULL_CONTROL'),
    PRIMARY KEY (resourceType, resourceName, granteeType, grantee, permission)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Builds (
    id                  VARCHAR(194) NOT NULL,
    build_name          VARCHAR(64),
    build_number        INT NOT NULL,
    architectures       VARCHAR(256),
    time_created        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id, build_name, build_number)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Certifications (
    id                  VARCHAR(194) NOT NULL PRIMARY KEY,
    profile             VARCHAR(64),
    certifiedBy         VARCHAR(64),
    certifiedDate       TIMESTAMP
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Profiles (
    id                  VARCHAR(194) NOT NULL PRIMARY KEY,
    number              INT DEFAULT '-1',
    profile             VARCHAR(64),
    certifiedBy         VARCHAR(64),
    certifiedDate       TIMESTAMP
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS Resources (
   id                  VARCHAR(194) NOT NULL,
    resource            VARCHAR(256),
    PRIMARY KEY(`id`, `resource`)
);
"""
        )

        self.cur.execute(
            """
CREATE TABLE IF NOT EXISTS TokenCache (
    token               VARCHAR(256) NOT NULL,
    user                VARCHAR(256) NOT NULL,
    scopes              VARCHAR(512) NOT NULL,
    is_admin            BOOLEAN,
    expires             TIMESTAMP,  /* this is the cache expiration (1hour), not real token expiration (weeks) */
    PRIMARY KEY (token)
);
"""
        )

        self.cur.execute(
            """
CREATE EVENT IF NOT EXISTS AuthNCacheEvent
ON SCHEDULE
EVERY 1 HOUR
COMMENT 'TokenCleanup'
DO
DELETE FROM `SageECR`.`TokenCache` WHERE `expires` < NOW();
"""
        )

    def deleteAllData(self):
        tables = [
            "Apps",
            "Sources",
            "Namespaces",
            "Repositories",
            "MetaFiles",
            "Permissions",
            "Builds",
            "Certifications",
            "Profiles",
            "Resources",
            "TokenCache",
        ]

        for table in tables:
            self.cur.execute(f"TRUNCATE TABLE {table}")

    # returns true if user has the permissions
    # TODO if resourceType  = repository, also check namespace
    def hasPermission(
        self, resourceType, resourceName, granteeType, grantee, permission
    ):
        if not grantee:
            raise Exception("grantee undefined")

        permissions = [permission]

        if permission != "FULL_CONTROL":
            if permission == "READ":
                permissions = [permission, "WRITE", "FULL_CONTROL"]
            elif permission == "READ_ACP":
                permissions = [permission, "WRITE_ACP", "FULL_CONTROL"]
            else:
                permissions = [permission, "FULL_CONTROL"]

        permissionIN = "permission IN (%s" + " , %s" * (len(permissions) - 1) + ")"

        permissionsPublicRead = "FALSE"
        if permission == "READ" and not (
            granteeType == "GROUP" and grantee == "Allusers"
        ):
            permissionsPublicRead = '(granteeType="GROUP" AND grantee="Allusers")'

        stmt = f"SELECT * FROM Permissions WHERE resourceType = %s AND resourceName = %s AND ((  granteeType = %s AND grantee = %s AND ({permissionIN}) ) OR {permissionsPublicRead}  )"

        debug_stmt = stmt

        debug_stmt = debug_stmt.replace("%s", resourceType, 1)
        debug_stmt = debug_stmt.replace("%s", resourceName, 1)
        debug_stmt = debug_stmt.replace("%s", granteeType, 1)
        debug_stmt = debug_stmt.replace("%s", grantee, 1)
        for p in permissions:
            debug_stmt = debug_stmt.replace("%s", p, 1)

        self.execute(
            stmt, (resourceType, resourceName, granteeType, grantee, *permissions)
        )
        row = self.cur.fetchone()
        if row == None:
            return False

        if len(row) > 0:
            return True

        return False

    def insertApp(
        self, col_names_str, values, variables_str, sources_values, resourcesArray
    ):
        stmt = f"REPLACE INTO Sources ( id, architectures , url, branch, tag, git_commit, directory, dockerfile, build_args ) VALUES (%s , %s, %s, %s, %s, %s, %s, %s, %s)"
        self.execute(stmt, sources_values)

        id_str = sources_values[0]
        for res in resourcesArray:
            res_str = json.dumps(res)
            stmt = f"REPLACE INTO Resources ( id, resource) VALUES (%s , %s)"
            self.execute(
                stmt,
                (
                    id_str,
                    res_str,
                ),
            )

        stmt = f"REPLACE INTO Apps ( {col_names_str}) VALUES ({variables_str})"
        self.execute(stmt, values)

        self.db.commit()

        return

    def deleteApp(self, user, isAdmin, namespace, repository, version, force=False):
        app, ok = self.listApps(
            user=user,
            isAdmin=isAdmin,
            namespace=namespace,
            repository=repository,
            version=version,
        )

        if not ok:
            raise Exception("App not found")

        app_id = app.get("id", "")
        if not app_id:
            raise Exception("App id empty " + json.dumps(app))

        frozen = app.get("frozen", False)
        if frozen and (not force):
            raise Exception("App {app_id} is frozen, it cannot be deleted")

        for table in ["Apps", "Sources", "Certifications", "Profiles"]:
            stmt_apps = f"DELETE FROM {table} WHERE `id` = %s"
            self.execute(stmt_apps, (app_id,))

        # also cleanup metafiles
        stmt_apps = f"DELETE FROM MetaFiles WHERE `app_id` = %s"
        self.execute(stmt_apps, (app_id,))

        self.db.commit()

        return 1

    def getAppField(self, app_id, field):
        stmt = f"SELECT  id, {field} FROM Apps WHERE `id` = %s"
        self.execute(stmt, (app_id,))

        returnFields = ["id", field]
        returnObj = {}
        row = self.cur.fetchone()
        i = 0
        if row == None:
            raise ErrorResponse(
                f"App {app_id} not found", status_code=HTTPStatus.INTERNAL_SERVER_ERROR
            )
        for value in row:
            returnObj[returnFields[i]] = value
            i += 1

        # decode embedded json
        if field in ["inputs", "metadata"]:
            if field in returnObj and returnObj[field] != "":
                try:
                    returnObj[field] = json.loads(returnObj[field])
                except json.JSONDecodeError:
                    returnObj[field] = {"error": "could not parse json"}

        return returnObj[field]

    def setAppField(self, namespace, repository, version, field, value):
        # convert bool to int for stupid mysql
        if isinstance(value, bool):
            value = int(value)

        values = (value, namespace, repository, version)
        stmt = f"UPDATE Apps SET {field} = %s WHERE namespace = %s AND name = %s AND version = %s"
        debug_stmt = stmt
        for key in values:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        logger.debug(f"(setAppField) debug_stmt: {debug_stmt}")

        self.execute(stmt, values)
        self.db.commit()
        return int(self.cur.rowcount)

    # counts all apps, independent of permissions
    def countApps(self, namespace, repository):
        stmt = f"SELECT COUNT(id) FROM Apps WHERE namespace=%s AND name=%s"

        debug_stmt = stmt
        for key in [namespace, repository]:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        logger.debug(f"(countApps) debug stmt: {debug_stmt}")

        self.execute(
            stmt,
            (
                namespace,
                repository,
            ),
        )
        result = self.cur.fetchone()

        return result[0]

    def countRepositories(self, namespace):
        stmt = f"SELECT COUNT(name) FROM Apps WHERE namespace=%s"

        debug_stmt = stmt
        for key in [namespace]:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        logger.debug(f"(countApps) debug stmt: {debug_stmt}")

        self.execute(stmt, (namespace,))
        result = self.cur.fetchone()

        return result[0]

    # in case of a single app (namespace, repository and version specified), this does not return a list
    # filter supports "public" , "owner", "shared" (owner and shared have no overlap)
    def listApps(
        self,
        user="",
        app_id="",
        namespace="",
        repository="",
        version="",
        limit=None,
        continuationToken=None,
        isAdmin=False,
        filter={},
        view="",
    ):
        for key in filter:
            if not key in ["public", "owner", "shared"]:
                raise Exception(f"Unknown filter option {key}")

        query_data = []

        include_public = True

        owner_condition = ""
        if filter.get("shared", False):
            # only show apps shared with user + exclude own apps
            include_public = False
            owner_condition = " AND Apps.owner != %s "
            query_data.append(user)

        if filter.get("owner", False):
            include_public = False
            owner_condition = " AND Apps.owner = %s "
            query_data.append(user)

        appID_condition = ""
        if app_id != "":
            appID_condition = " AND id = %s"
            query_data.append(app_id)

        namespace_condition = ""
        if namespace:
            namespace_condition = " AND Apps.namespace=%s"
            query_data.append(namespace)

        repo_condition = ""
        if repository:
            if not namespace:
                raise Exception("Repository specified without namespace")

            repo_condition = " AND Apps.name=%s"
            query_data.append(repository)

        version_condition = ""
        if version:
            if not namespace:
                raise Exception("namespace required")
            if not repository:
                raise Exception("repository required")

            version_condition = " AND Apps.version=%s"
            query_data.append(version)

        user_condition = "FALSE"
        if isAdmin:
            user_condition = "TRUE"
        else:
            if user != "" and (not filter.get("public", False)):
                # without this, api returns only public apps
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
        sub_stmt = '( Permissions.resourceType="repository" AND Permissions.resourceName=CONCAT(Apps.namespace , "/", Apps.name )  OR (Permissions.resourceType="namespace" AND Permissions.resourceName=Apps.namespace) )'

        # dbAppsFields_str  = ",".join(config.mysql_Apps_fields.keys())
        # this adds prefix "Apps." and create a single string
        dbAppsFields_str = ",".join(
            ["Apps." + item for item in config.mysql_Apps_fields.keys()]
        )

        dbSourcesFields_str = ",".join(
            ["s." + item for item in config.mysql_Sources_fields.keys()]
        )

        if include_public:
            public_stmt = '(granteeType="GROUP" AND grantee="AllUsers")'
        else:
            public_stmt = "FALSE"

        # a) all apps
        # b) only public
        # c) user is owner
        # d) shared with user

        # this makes sure only apps for which user has permission are returned
        permissions_stmt = f'( ({user_condition}) OR {public_stmt} ) AND ( permission in ("READ", "WRITE", "FULL_CONTROL") )'

        # AND (NOT (Permissions.resourceType="namespace" AND granteeType="GROUP" AND grantee="AllUsers"))
        # this above is to make sure that a public namespace does not imply public repo

        # INNER JOIN Permissions : makes sure App disappear if the user does not have any permission
        stmt = f'SELECT DISTINCT {dbAppsFields_str},{dbSourcesFields_str} FROM Apps LEFT JOIN Sources s ON s.id = Apps.id INNER JOIN Permissions ON {sub_stmt} {owner_condition} {appID_condition} {namespace_condition} {repo_condition} {version_condition} AND {permissions_stmt} {token_stmt} AND (NOT (Permissions.resourceType="namespace" AND granteeType="GROUP" AND grantee="AllUsers")) ORDER BY `namespace`, `name`, `version` ASC {limit_stmt}'

        debug_stmt = stmt
        for key in query_data:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        logger.debug(f"(listApps) debug stmt: {debug_stmt}")

        self.execute(stmt, query_data)

        # self.cur.rowcount

        rows = self.cur.fetchall()

        app_list = []

        for row in rows:
            app_obj = {}
            app_obj["source"] = {}

            ref_hash = config.mysql_Apps_fields
            target = app_obj
            count = len(config.mysql_Apps_fields)
            table = "Apps"
            for pos, field in enumerate(
                list(config.mysql_Apps_fields.keys())
                + list(config.mysql_Sources_fields.keys())
            ):
                if pos == count:
                    table = "Sources"
                    ref_hash = config.mysql_Sources_fields
                    target = app_obj["source"]

                if view == "app" and table == "Apps":
                    if field not in config.app_view_fields:
                        continue

                if not field in ref_hash:
                    raise Exception(
                        f"Type not found for field {field} in table {table}"
                    )
                if ref_hash[field] == "datetime":
                    target[field] = row[pos].isoformat() + "Z"
                elif ref_hash[field] == "json":
                    if row[pos] != None and row[pos] != "":
                        try:
                            target[field] = json.loads(row[pos])
                        except json.JSONDecodeError:
                            target[field] = {"error": "could not parse json"}

                elif ref_hash[field] == "bool":
                    target[field] = row[pos] == "1"
                else:
                    target[field] = row[pos]

            app_list.append(app_obj)
            # app_list.append({"id": row[0], "namespace": row[1], "name": row[2], "version":row[3], "time_created":row[4].isoformat() + 'Z'})

        if app_id or (namespace and repository and version):
            # only single app was requested, return object, not list
            if len(app_list) == 0:
                return None, False
            if len(app_list) > 1:
                raise Exception("More than one app found, but only one expected.")

            return app_list[0], True

        # if no apps, we are done
        if not app_list:
            return app_list

        # quote app_id list for queries
        app_ids = [f"{app['id']}" for app in app_list]
        format_strings = ",".join(["%s"] * len(app_ids))

        # get thumbnails  # todo(nc): write as join without subqueries?
        stmt = f'SELECT app_id, namespace, name, version, file_name FROM MetaFiles WHERE kind = "thumb" AND app_id IN ({format_strings});'
        self.execute(stmt, tuple(app_ids))
        thumbs = self.cur.fetchall()

        # images
        stmt = f'SELECT app_id, namespace, name, version, file_name FROM MetaFiles WHERE kind = "image" AND app_id IN ({format_strings});'
        self.execute(stmt, tuple(app_ids))
        images = self.cur.fetchall()

        # science markdown
        stmt = f'SELECT app_id, namespace, name, version, file_name FROM MetaFiles WHERE kind = "science_description" AND app_id IN ({format_strings});'
        self.execute(stmt, tuple(app_ids))
        sci_descripts = self.cur.fetchall()

        # (hacky) joining of the meta paths
        for app in app_list:
            thumb_paths = [
                f"{thumb[1]}/{thumb[2]}/{thumb[3]}/{thumb[4]}"
                for thumb in thumbs
                if thumb[0] == app["id"]
            ]
            image_paths = [
                f"{img[1]}/{img[2]}/{img[3]}/{img[4]}"
                for img in images
                if img[0] == app["id"]
            ]
            sci_paths = [
                f"{sci_d[1]}/{sci_d[2]}/{sci_d[3]}/{sci_d[4]}"
                for sci_d in sci_descripts
                if sci_d[0] == app["id"]
            ]

            app.update(
                {
                    "thumbnail": thumb_paths[0] if len(thumb_paths) > 0 else None,
                    "images": image_paths if image_paths else None,
                    "science_description": sci_paths[0] if len(sci_paths) > 0 else None,
                }
            )

        return app_list

    def listNamespaces(self, user=""):
        query_data = []

        user_condition = "FALSE"
        if user != "":
            user_condition = '(granteeType="USER" AND grantee=%s)'
            query_data.append(user)

        stmt = f'SELECT DISTINCT id , owner_id FROM Namespaces INNER JOIN Permissions  ON Permissions.resourceType="namespace" AND Permissions.resourceName=Namespaces.id  AND ( ({user_condition}) OR (granteeType="GROUP" AND grantee="AllUsers")) AND (permission in ("READ", "WRITE", "FULL_CONTROL"))'
        self.execute(stmt, query_data)

        rows = self.cur.fetchall()

        app_list = []

        for row in rows:
            app_list.append({"id": row[0], "owner_id": row[1], "type": "namespace"})

        return app_list

    # filter supports "public" , "owner", "shared" (owner and shared have no overlap)
    def listRepositories(self, user="", namespace="", isAdmin=None, filter={}):
        query_data = []

        include_public = True

        for key in filter:
            if not key in ["public", "owner", "shared", "nopublic"]:
                raise Exception(f"Unknown filter option {key}")

        if filter.get("nopublic", False):
            include_public = False

        owner_condition = ""
        if filter.get("shared", False):
            # only show apps shared with user + exclude own apps
            include_public = False
            owner_condition = " AND Repositories.owner_id != %s "
            query_data.append(user)

        if filter.get("owner", False):
            include_public = False
            owner_condition = " AND Repositories.owner_id = %s "
            query_data.append(user)

        namespace_condition = ""
        if namespace:
            namespace_condition = "AND Repositories.namespace=%s"
            query_data.append(namespace)

        user_condition = "FALSE"
        if isAdmin:
            user_condition = "TRUE"
        else:
            if user != "" and (not filter.get("public", False)):
                # without this, api returns only public apps
                user_condition = '(granteeType="USER" AND grantee=%s)'
                query_data.append(user)

        if include_public:
            public_stmt = '(granteeType="GROUP" AND grantee="AllUsers")'
        else:
            public_stmt = "FALSE"

        sub_stmt = '( Permissions.resourceType="repository" AND Permissions.resourceName=CONCAT(Repositories.namespace , "/", Repositories.name )  OR (Permissions.resourceType="namespace" AND Permissions.resourceName=Repositories.namespace) )'

        # this makes sure only apps for which user has permission are returned
        permissions_stmt = f'( ({user_condition}) OR {public_stmt} ) AND ( permission in ("READ", "WRITE", "FULL_CONTROL") )'

        # not needed ?  --->    AND ( Permissions.resourceName LIKE CONCAT(Repositories.namespace, \"%%\") )

        fields = ["namespace", "name", "owner_id", "description", "external_link"]
        fields_str = ",".join(fields)
        stmt = f"""SELECT DISTINCT {fields_str} FROM Repositories INNER JOIN Permissions ON {sub_stmt} {owner_condition} {namespace_condition} AND {permissions_stmt}"""

        debug_stmt = stmt
        for key in query_data:
            debug_stmt = debug_stmt.replace("%s", key, 1)

        logger.debug(f"(listRepositories) debug stmt: {debug_stmt}")
        self.execute(stmt, query_data)
        # self.execute(stmt , (namespace, user))
        # self.execute(debug_stmt )

        rows = self.cur.fetchall()

        rep_list = []
        logger.debug(f"len(rows): {len(rows)}")
        for row in rows:
            obj = {}

            # obj = dict(zip(fields, row))
            obj["type"] = "repository"
            for pos, field in enumerate(fields):
                if row[pos]:
                    obj[field] = row[pos]
                else:
                    obj[field] = ""
            rep_list.append(obj)
            # rep_list.append({"type": "repository", "namespace": row[0], "name": row[1], "owner_id": row[2]})

        return rep_list

    def getPermissions(self, resourceType, resourceName):
        stmt = f"SELECT  resourceType, resourceName, granteeType , grantee, permission FROM Permissions WHERE resourceType = %s AND resourceName = %s"
        self.execute(stmt, (resourceType, resourceName))

        rows = self.cur.fetchall()

        perm_list = []

        for row in rows:
            perm_list.append(
                {
                    "resourceType": row[0],
                    "resourceName": row[1],
                    "granteeType": row[2],
                    "grantee": row[3],
                    "permission": row[4],
                }
            )

        return perm_list

    # this will return all permissions of repos that are owned by owner_id
    # permissions grnated to owner_id itself are ignored
    def getRepoPermissionsByOwner(self, owner_id):
        if not owner_id:
            raise Exception("This function requires are user.")

        fields_str = "namespace, name, owner_id, Permissions.resourceType,Permissions.resourceName,Permissions.granteeType,Permissions.grantee,Permissions.permission"
        fields = [x.strip() for x in fields_str.split(",")]

        # TODO this is risky, ignoring grantee works, but may ignore a group of same name (did not find a nice solution. maybe use CONCAT)

        stmt = f'SELECT {fields_str}  FROM Repositories INNER JOIN Permissions ON ( Permissions.resourceType="repository" AND Permissions.resourceName=CONCAT(Repositories.namespace , "/", Repositories.name )  OR (Permissions.resourceType="namespace" AND Permissions.resourceName=Repositories.namespace) )  WHERE (owner_id = %s OR (granteeType="GROUP" and grantee="AllUsers")) AND grantee != %s  ORDER BY namespace, name, resourceType, resourceName;'
        debug_stmt = stmt
        for key in [owner_id, owner_id]:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        logger.debug(f"getRepoPermissionsByOwner: {debug_stmt}")

        self.execute(
            stmt,
            (
                owner_id,
                owner_id,
            ),
        )

        rows = self.cur.fetchall()

        perm_list = []

        for row in rows:
            obj = {}
            for pos, field in enumerate(fields):
                obj[field] = row[pos]

            perm_list.append(obj)

        return perm_list

    def addPermission(
        self, resourceType, resourceName, granteeType, grantee, permission
    ):
        if granteeType == "GROUP" and grantee == "AllUsers" and permission != "READ":
            raise ErrorResponse(
                f"AllUsers can only get READ permission.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        stmt = f"INSERT IGNORE INTO Permissions ( resourceType, resourceName, granteeType , grantee, permission) VALUES (%s , %s , %s,  %s, %s)"

        debug_stmt = stmt

        for key in [resourceType, resourceName, granteeType, grantee, permission]:
            debug_stmt = debug_stmt.replace("%s", f'"{key}"', 1)

        self.execute(
            stmt, (resourceType, resourceName, granteeType, grantee, permission)
        )

        self.db.commit()

        return int(self.cur.rowcount)

    # deletes all permissions unless limited by any of optional parameters
    # permissions for owner will be excluded
    def deletePermissions(
        self,
        owner,
        resourceType,
        resourceName,
        granteeType=None,
        grantee=None,
        permission=None,
    ):
        # owner = self.getAppField(app_id, "owner")

        if not owner:
            raise ErrorResponse(
                "Owner not found", status_code=HTTPStatus.INTERNAL_SERVER_ERROR
            )

        stmt_delete_permissions = (
            f"DELETE FROM Permissions WHERE resourceType = %s AND resourceName =%s"
        )
        params = [resourceType, resourceName]
        if granteeType:
            stmt_delete_permissions += " AND granteeType=%s"
            params.append(granteeType)

        if grantee:
            stmt_delete_permissions += " AND grantee=%s"
            params.append(grantee)

        if permission:
            stmt_delete_permissions += " AND permission=%s"
            params.append(permission)

        # make sure owner does not take his own permissions away

        stmt_delete_permissions += (
            ' AND NOT (granteeType="USER" AND grantee=%s AND permission="FULL_CONTROL")'
        )
        params.append(owner)

        self.execute(stmt_delete_permissions, params)
        self.db.commit()

        return int(self.cur.rowcount)

    def getBuildInfo(self, app_id, name):
        stmt = f"SELECT  id, build_number , architectures FROM Builds WHERE id = %s AND build_name=%s ORDER BY time_created DESC LIMIT 1"
        self.execute(stmt, (app_id, name))

        row = self.cur.fetchone()
        if row == None:
            raise Exception("No build id found in database")

        number = row[1]
        architectures = json.loads(row[2])

        return (number, architectures)

    def SaveBuildInfo(self, app_id, build_name, build_number, architectures):
        architectures_str = json.dumps(architectures)

        stmt = "REPLACE INTO Builds ( id, build_name, build_number, architectures)  VALUES (%s , %s,  %s, %s) "

        self.execute(stmt, (app_id, build_name, build_number, architectures_str))

        self.db.commit()

        return

    # return user id if token found, empty string otherwise
    def getTokenInfo(self, token):
        stmt = (
            "SELECT user, scopes, is_admin FROM TokenCache WHERE SHA2(%s, 512) = token"
        )
        self.execute(stmt, (token,))

        row = self.cur.fetchone()
        i = 0
        if row == None:
            return "", "", False

        if len(row) != 3:
            return "", "", False

        return row[0], row[1], row[2]

    def setTokenInfo(self, token, user_id, scopes, is_admin):
        # ignore should be ok, scopes should not change for a given token

        stmt = "INSERT IGNORE INTO TokenCache (token, user, scopes, is_admin, expires) VALUES (SHA2(%s, 512), %s, %s, %s, %s)"

        expires = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

        self.execute(stmt, (token, user_id, scopes, is_admin, expires))

        self.db.commit()

        return

    # returns owner, otherwise empty string
    def getNamespace(self, name):
        stmt = "SELECT id, owner_id FROM Namespaces WHERE id = %s"
        self.execute(stmt, (name,))

        row = self.cur.fetchone()

        if row == None:
            return {}, False

        if len(row) != 2:
            raise Exception("wrong number of columns")

        returnObj = {}
        returnObj["id"] = row[0]
        returnObj["owner_id"] = row[1]
        return returnObj, True

    def deleteNamespace(self, namespace):
        stmt = f"DELETE FROM Namespaces WHERE id = %s"
        debug_stmt = stmt
        debug_stmt = debug_stmt.replace("%s", f'"{namespace}"', 1)
        self.execute(stmt, (namespace,))

        self.db.commit()

        return 1

    def addNamespace(self, name, owner_id):
        # name restriction from https://docs.docker.com/docker-id/
        # "... can only contain numbers and lowercase letters."

        p = re.compile(f"[a-z0-9]+", re.ASCII)
        if not p.fullmatch(name):
            raise Exception("Namespace can only contain numbers and lowercase letters")

        if len(name) < 4 or len(name) > 30:
            raise Exception("Namespace must be between 4 and 30 characters long")

        stmt = "INSERT INTO Namespaces (id, owner_id) VALUES (%s, %s)"
        self.execute(stmt, (name, owner_id))

        stmt = "REPLACE INTO Permissions (resourceType, resourceName, granteeType, grantee, permission) VALUES (%s, %s, %s, %s, %s)"
        self.execute(stmt, ("namespace", name, "USER", owner_id, "FULL_CONTROL"))

        self.db.commit()

        result, ok = self.getNamespace(name)
        if not ok:
            raise Exception("namespace creation failed")

        return result

    # returns owner, otherwise empty string
    def getRepository(self, namespace, name):
        # full_name = f'{namespace}/{name}'

        stmt = "SELECT namespace, name, owner_id FROM Repositories WHERE namespace = %s AND name = %s"
        self.execute(stmt, (namespace, name))

        row = self.cur.fetchone()

        if row == None:
            return {}, False

        if len(row) != 3:
            raise Exception("Number of columns wrong")

        returnObj = {}
        returnObj["namespace"] = row[0]
        returnObj["name"] = row[1]
        returnObj["owner_id"] = row[2]
        return returnObj, True

    def deleteRepository(self, namespace, name):
        stmt = f"DELETE FROM Repositories WHERE namespace = %s AND name = %s"
        self.execute(stmt, (namespace, name))

        resourceName = f"{namespace}/{name}"
        stmt = f'DELETE FROM Permissions WHERE resourceType = "repository" AND resourceName =%s'
        self.execute(stmt, (resourceName,))

        self.db.commit()
        return 1

    def addRepository(self, namespace, name, owner_id):
        # name restriction from https://docs.docker.com/docker-hub/repos/
        # "The repository name needs to be unique in that namespace, can be two to 255 characters, and can only contain lowercase letters, numbers or - and _."

        p = re.compile(f"[a-z0-9_-]+", re.ASCII)
        if not p.fullmatch(name):
            raise Exception("Repository can only contain numbers and lowercase letters")

        if len(name) < 2 or len(name) > 255:
            raise Exception("Repository must be between 2 and 255 characters long")

        stmt = (
            "INSERT INTO Repositories (namespace, name, owner_id) VALUES (%s, %s, %s)"
        )
        self.execute(stmt, (namespace, name, owner_id))

        full_name = f"{namespace}/{name}"
        stmt = "INSERT INTO Permissions (resourceType, resourceName, granteeType, grantee, permission) VALUES (%s, %s, %s, %s, %s)"
        self.execute(stmt, ("repository", full_name, "USER", owner_id, "FULL_CONTROL"))

        self.db.commit()
        return 1

    def addMetaFile(self, namespace, name, version, file_name, blob, kind):
        app_id = f"{namespace}/{name}:{version}"
        stmt = "INSERT INTO MetaFiles (app_id, namespace, name, version, file_name, file, kind) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        self.execute(stmt, (app_id, namespace, name, version, file_name, [blob], kind))
        self.db.commit()
        return 1

    def getMetaFile(self, namespace, name, version, file_name):
        app_id = f"{namespace}/{name}:{version}"
        stmt = "SELECT file, kind FROM MetaFiles where app_id = %s AND file_name = %s"
        self.execute(stmt, (app_id, file_name))
        content, kind = self.cur.fetchone()
        if kind == "science_description":
            content = bleach.clean(content.decode("utf-8"))
        return content
