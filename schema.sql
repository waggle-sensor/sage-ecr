CREATE DATABASE IF NOT EXISTS SageECR;

/* App Specification */
/* TODO: save commit hash to prevent changes */
CREATE TABLE IF NOT EXISTS SageECR.Apps (
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

CREATE TABLE IF NOT EXISTS SageECR.Sources (
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
    owner_id              VARCHAR(64) NOT NULL,
    description           TEXT,
    external_link         VARCHAR(256),
    PRIMARY KEY (namespace,name)
);


/* meta files (for things like images, markdown, etc) */
CREATE TABLE IF NOT EXISTS SageECR.MetaFiles (
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
    id                  VARCHAR(194) NOT NULL,
    build_name          VARCHAR(64),
    build_number        INT NOT NULL,
    architectures       VARCHAR(256),
    time_created        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id, build_name, build_number)
);

CREATE TABLE IF NOT EXISTS SageECR.Certifications (
    id                  VARCHAR(194) NOT NULL PRIMARY KEY,
    profile             VARCHAR(64),
    certifiedBy         VARCHAR(64),
    certifiedDate       TIMESTAMP
);

CREATE TABLE IF NOT EXISTS SageECR.Profiles (
    id                  VARCHAR(194) NOT NULL PRIMARY KEY,
    number              INT DEFAULT '-1',
    profile             VARCHAR(64),
    certifiedBy         VARCHAR(64),
    certifiedDate       TIMESTAMP
);






/* hardware requirements
    GPU , sensor,  etc..
*/
CREATE TABLE IF NOT EXISTS SageECR.Resources (
   id                  VARCHAR(194) NOT NULL,
    resource            VARCHAR(256),
    PRIMARY KEY(`id`, `resource`)
);


/* Token Cache */


CREATE TABLE IF NOT EXISTS SageECR.TokenCache (
    token               VARCHAR(256) NOT NULL,
    user                VARCHAR(256) NOT NULL,
    scopes              VARCHAR(512) NOT NULL,
    is_admin            BOOLEAN,
    expires             TIMESTAMP,  /* this is the cache expiration (1hour), not real token expiration (weeks) */
    PRIMARY KEY (token)
);


CREATE EVENT IF NOT EXISTS `SageECR`.`AuthNCacheEvent`
ON SCHEDULE
EVERY 1 HOUR
COMMENT 'TokenCleanup'
DO
DELETE FROM `SageECR`.`TokenCache` WHERE `expires` < NOW();
