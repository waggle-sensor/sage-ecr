


/* App Specification */
/* TODO: save commit hash to prevent changes */
CREATE TABLE IF NOT EXISTS SageECR.Apps (
    id                  BINARY(16) NOT NULL PRIMARY KEY,
    namespace           VARCHAR(64),
    name                VARCHAR(64),
    version             VARCHAR(64),
    frozen              BOOLEAN DEFAULT FALSE,
    description         TEXT,
    depends_on          VARCHAR(128),
    baseCommand         VARCHAR(64),
    arguments           VARCHAR(256),
    inputs              VARCHAR(256),
    metadata            TEXT,
    schema_version      VARCHAR(64),
    time_created        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    owner               VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS SageECR.Sources (
    id                  BINARY(16) NOT NULL,
    architectures       VARCHAR(256),
    url                 VARCHAR(256) NOT NULL,
    branch              VARCHAR(64),
    directory           VARCHAR(256),
    dockerfile          VARCHAR(256),
    build_args          VARCHAR(256),
    PRIMARY KEY (id)
);



/*  namespace   */
CREATE TABLE IF NOT EXISTS SageECR.Namespaces (
    id                  VARCHAR(32) NOT NULL,
    owner_id            VARCHAR(64) NOT NULL,
    PRIMARY KEY (id)
);



/*  repository (id format: namespace/repository )  */
CREATE TABLE IF NOT EXISTS SageECR.Repositories (
    namespace             VARCHAR(32) NOT NULL,
    name                  VARCHAR(256) NOT NULL,
    owner_id            VARCHAR(64) NOT NULL,
    PRIMARY KEY (namespace,name)
);



/* Owner of repositories is the namespace owner  */

CREATE TABLE IF NOT EXISTS SageECR.Permissions ( # /* formerly SageECR.AppPermissions */
    resourceType        VARCHAR(64),  /* namespace or repository */
    resourceName        VARCHAR(64),  /* e.g. "username" in case of namespace, or "simple-plugin" in case of repository  */
    granteeType         ENUM('USER', 'GROUP'),
    grantee             VARCHAR(64), 
    permission          ENUM('READ', 'WRITE', 'READ_ACP', 'WRITE_ACP', 'FULL_CONTROL'),
    PRIMARY KEY (resourceType, resourceName, granteeType, grantee, permission)
);
# permissions similar to https://docs.aws.amazon.com/AmazonS3/latest/dev/acl-overview.html

/* Continous Integration related */
CREATE TABLE IF NOT EXISTS SageECR.Builds (
    id                  BINARY(16) NOT NULL,
    build_name          VARCHAR(64),
    build_number        INT NOT NULL,
    architectures       VARCHAR(256),
    time_created        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id, build_name, build_number)
);

CREATE TABLE IF NOT EXISTS SageECR.Certifications (
    id                  BINARY(16) NOT NULL PRIMARY KEY,
    profile             VARCHAR(64),
    certifiedBy         VARCHAR(64),
    certifiedDate       TIMESTAMP
);

CREATE TABLE IF NOT EXISTS SageECR.Profiles (
    id                  BINARY(16) NOT NULL PRIMARY KEY,
    number              INT DEFAULT '-1',
    profile             VARCHAR(64),
    certifiedBy         VARCHAR(64),
    certifiedDate       TIMESTAMP
);






/* hardware requirements
    GPU , sensor,  etc..
*/
CREATE TABLE IF NOT EXISTS SageECR.Resources (
   id                  BINARY(16) NOT NULL,
    resource            VARCHAR(256),
    PRIMARY KEY(`id`, `resource`)
);


/* Token Cache */

CREATE EVENT IF NOT EXISTS `SageECR`.`AuthNCacheEvent`
ON SCHEDULE
EVERY 1 HOUR
COMMENT 'Description'
DO
DELETE FROM `SageECR`.`TokenCache` WHERE `expires` < NOW();




CREATE TABLE IF NOT EXISTS SageECR.TokenCache (
    token               VARCHAR(256) NOT NULL,
    user                VARCHAR(256) NOT NULL,
    scopes              VARCHAR(512) NOT NULL,
    is_admin            BOOLEAN,
    expires             TIMESTAMP,
    PRIMARY KEY (token)
);