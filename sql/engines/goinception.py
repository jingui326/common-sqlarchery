# -*- coding: UTF-8 -*-
import logging
import re
import traceback
import MySQLdb
import os

from common.config import SysConfig
from sql.utils.sql_utils import get_syntax_type
from sql.utils.multi_thread import multi_thread
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult
from common.utils.get_logger import get_logger


class GoInceptionEngine(EngineBase):
    def __init__(self, instance=None):
        super().__init__(instance=instance)
        self.logger = get_logger()

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if hasattr(self, 'instance'):
            self.conn = MySQLdb.connect(host=self.host, port=self.port, charset=self.instance.charset or 'utf8mb4',
                                        connect_timeout=10)
            return self.conn
        archer_config = SysConfig()
        go_inception_host = archer_config.get('go_inception_host')
        go_inception_port = int(archer_config.get('go_inception_port', 4000))
        self.conn = MySQLdb.connect(host=go_inception_host, port=go_inception_port, charset='utf8mb4',
                                    connect_timeout=10)
        return self.conn

    def execute_check(self, db_name='', instance=None,  sql=''):
        """inception check"""
        check_result = ReviewSet(full_sql=sql)
        self.logger.debug("Debug db_name in goinception.execute_check {0}".format(db_name))
        self.logger.info('Debug before doing execute check:{0}'.format(check_result.to_dict()))
        self.logger.debug('Debug before doing execute check: {0}'.format(check_result.to_dict()))
        # inception 校验
        check_result.rows = []
        inception_sql = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};--port={instance.port};--check=1;*/
                            inception_magic_start;
                            use `{db_name}`;
                            {sql.rstrip(';')};
                            inception_magic_commit;"""
        inception_result = self.query(db_name=db_name, sql=inception_sql)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML 仅适用于MySQL，待调整
        for r in inception_result.rows:
            check_result.rows += [ReviewResult(inception_result=r)]
            if r[2] == 1:  # 警告
                check_result.warning_count += 1
            elif r[2] == 2:  # 错误
                check_result.error_count += 1
            # 没有找出DDL语句的才继续执行此判断
            if check_result.syntax_type == 2:
                if get_syntax_type(r[5], parser=False, db_type='mysql') == 'DDL':
                    check_result.syntax_type = 1
        check_result.column_list = inception_result.column_list
        check_result.checked = True
        check_result.error = inception_result.error
        check_result.warning = inception_result.warning
        self.logger.debug('Debug execute check {0}'.format(check_result.to_dict()))
        return check_result

    def execute(self, workflow=None):
        """执行上线单"""

        self.logger.debug("Entering goIncetion execute!")

        instance = workflow.instance
        db_names = workflow.db_names.split(',') if workflow.db_names else []

        self.logger.debug("Debug tenants {0}".format(db_names))

        global execute_res
        # execute_res = {}
        execute_res = []

        multi_thread(self.execute_sql, db_names, (instance, workflow))

        self.logger.debug("Debug execute result in goinception {0}".format(execute_res))

        return execute_res

    def execute_sql(self, db_name, instance, workflow):

        self.logger.debug("Start execute sql for {0} via goInception.".format(db_name))
        self.logger.info("Start execute sql for {0} via goInception.".format(db_name))

        execute_result = ReviewSet(full_sql=workflow.sqlworkflowcontent.sql_content)

        global execute_res

        if workflow.is_backup:
            str_backup = "--backup=1"
        else:
            str_backup = "--backup=0"
        # 提交inception执行
        sql_execute = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};--port={instance.port};--execute=1;--ignore-warnings=1;{str_backup};*/
                            inception_magic_start;
                            use `{db_name}`;
                            {workflow.sqlworkflowcontent.sql_content.rstrip(';')};
                            inception_magic_commit;"""
        inception_result = self.query(db_name=db_name, sql=sql_execute)

        # 执行报错，inception crash或者执行中连接异常的场景
        if inception_result.error and not execute_result.rows:
            execute_result.error = inception_result.error
            execute_result.rows = [ReviewResult(
                stage='Execute failed',
                errlevel=2,
                stagestatus='异常终止',
                errormessage=f'goInception Error: {inception_result.error}',
                sql=workflow.sqlworkflowcontent.sql_content)]

            # return execute_result

        # 把结果转换为ReviewSet
        for r in inception_result.rows:
            execute_result.rows += [ReviewResult(inception_result=r)]

        print("Debug execute result {0}".format(inception_result.rows))

        self.logger.debug('Debug goinception execute sql result {0}'.format(execute_result.to_dict()))
        self.logger.info('Debug goinception execute sql result {0}'.format(execute_result.to_dict()))

        # 如果发现任何一个行执行结果里有errLevel为1或2，并且状态列没有包含Execute Successfully，则最终执行结果为有异常.
        for r in execute_result.rows:
            if r.errlevel in (1, 2) and not re.search(r"Execute Successfully", r.stagestatus):
                execute_result.error = "Line {0} has error/warning: {1}".format(r.id, r.errormessage)
                break
        # return execute_result
        # execute_res[db_name] = execute_result
        execute_res.extend(execute_result.to_dict())

    def query(self, db_name='', sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """

        self.logger.debug("Debug db_name in goinception.query: {0}".format(db_name))
        if db_name:
            self.logger.debug("Starting flash sql for {0} in goInception.".format(db_name))
            self.logger.info("Starting flash sql for {0}".format(db_name))
        else:
            self.logger.debug("Query database: {0}".format(sql))

        result_set = ResultSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        try:
            cursor = conn.cursor()
            effect_row = cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = effect_row
        except Exception as e:
            self.logger.error(f'goInception语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}')
            result_set.error = str(e)
        finally:
            self.logger.info("goInception execute sql for {0} success!".format(db_name))
            self.logger.info("Debug goInception execute result: {0}".format(result_set.to_dict()))
        if close_conn:
            self.close()
        return result_set

    def get_variables(self, variables=None):
        """获取实例参数"""
        if variables:
            sql = f"inception get variables like '{variables[0]}';"
        else:
            sql = "inception get variables;"
        return self.query(sql=sql)

    def set_variable(self, variable_name, variable_value):
        """修改实例参数值"""
        sql = f"""inception set {variable_name}={variable_value};"""
        return self.query(sql=sql)

    def osc_control(self, **kwargs):
        """控制osc执行，获取进度、终止、暂停、恢复等"""
        sqlsha1 = kwargs.get('sqlsha1')
        command = kwargs.get('command')
        if command == 'get':
            sql = f"inception get osc_percent '{sqlsha1}';"
        else:
            sql = f"inception {command} osc '{sqlsha1}';"
        return self.query(sql=sql)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
