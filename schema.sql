


/* App Specification */
CREATE TABLE IF NOT EXISTS SageECR.Apps (
    id                  BINARY(16) NOT NULL PRIMARY KEY,
    name                VARCHAR(64),
    description         VARCHAR(128),
    version             VARCHAR(64),
    source              VARCHAR(128),
    depends_on          VARCHAR(128),
    architecture        VARCHAR(64),
    baseCommand         VARCHAR(64),
    arguments           VARCHAR(128),
    inputs              VARCHAR(64),
    metadata            VARCHAR(64),
    schema_version      VARCHAR(64),
    time_created        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    owner               VARCHAR(64) NOT NULL
);

/* Continous Integration related */
CREATE TABLE IF NOT EXISTS SageECR.CI (
    id                  BINARY(16) NOT NULL PRIMARY KEY,
    build               VARCHAR(64),
    profile             VARCHAR(64),
    certifiedBy         VARCHAR(64),
    certifiedDate       TIMESTAMP
);


/* hardware requirements
    GPU , sensor,  etc..
*/
CREATE TABLE IF NOT EXISTS SageECR.Requirements (
    id                  BINARY(16) NOT NULL PRIMARY KEY,
    requirement         VARCHAR(64),
   PRIMARY KEY(`id`, `requirement`)
);