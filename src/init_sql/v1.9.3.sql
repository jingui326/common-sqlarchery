ALTER TABLE sql_instance ADD awsSecretId varchar(100) DEFAULT '' COMMENT 'AWS SecretId';
ALTER TABLE sql_instance ADD is_ssl tinyint(1) DEFAULT 0  COMMENT '是否启用SSL';