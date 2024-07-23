# Inspired by https://gist.github.com/valferon/4d6ebfa8a7f3d4e84085183609d10f14
#
#

import os
import argparse
import configparser
import logging
import subprocess

import psycopg2
import sys
from datetime import datetime

BACKUP_PATH = './backups/'

def initLoggers() -> None:
    # STDOUT logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    stdoutHandler = logging.StreamHandler(sys.stdout)
    stdoutHandler.setLevel(logging.DEBUG)
    stdoutFormatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] - %(message)s - [%(module)s/%(filename)s::%(funcName)s:%(lineno)d]')
    stdoutHandler.setFormatter(stdoutFormatter)

    root.addHandler(stdoutHandler)


def createDatabseUser(host: str, port: int, user: str, password: str, newUser: str, newUserPassword: str, verbose: bool):
    """
    Create a new database user.
    """
    logging.info('Creating user "{}"...'.format(newUser))
    connection = psycopg2.connect(host=host, port=port, user=user, password=password, dbname='postgres')
    connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    with connection.cursor() as cursor:
        cursor.execute('CREATE USER "{}" WITH PASSWORD \'{}\';'.format(newUser, newUserPassword))

def createDatabase(host: str, port: int, user: str, password: str, newUser: str, databaseName: str, verbose: bool):
    """
    Create a new database.
    """
    logging.info('Creating database "{}"...'.format(databaseName))
    connection = psycopg2.connect(host=host, port=port, user=user, password=password, dbname='postgres')
    connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    with connection.cursor() as cursor:
        cursor.execute('CREATE DATABASE "{}";'.format(databaseName))
        cursor.execute('REVOKE CONNECT ON DATABASE "{}" FROM PUBLIC;'.format(databaseName))
        cursor.execute('GRANT ALL PRIVILEGES ON DATABASE "{}" TO "{}";'.format(databaseName, newUser))

def backupPostgresDb(host: str, database_name: str, port: int, user: str, password: str, dest_file: str, verbose: bool) -> bytes:
    """
    Backup postgres database to a file.
    """

    logging.info('Backing up database "{}"...'.format(database_name))
    os.environ["PGPASSWORD"] = password

    if verbose:
        args = [
            'pg_dump',
            f'--dbname={database_name}',
            f'--host={host}',
            f'--port={port}',
            f'--username={user}',
            '-Fc',
            '-f', dest_file,
            '-v'
        ]
    else:
        args = [
            'pg_dump',
            f'--dbname={database_name}',
            f'--host={host}',
            f'--port={port}',
            f'--username={user}',
            '-Fc',
            '-f', dest_file
        ]

    process = subprocess.Popen(args, stdout=subprocess.PIPE)
    output = process.communicate()[0]
    os.environ["PGPASSWORD"] = ""

    if int(process.returncode) != 0:
        print('Command failed. Return code : {}'.format(process.returncode))
        exit(1)

    return output

def restorePostgresDb(db_host, db, port, user, password, backup_file, verbose):
    """
    Restore postgres db from a file.
    """

    logging.info('Restoring database "{}"...'.format(db))
    os.environ["PGPASSWORD"] = password

    if verbose:
        args = [
            'pg_restore',
            '--no-owner',
            f'--dbname={db}',
            f'--host={db_host}',
            f'--port={port}',
            f'--username={user}',
            '-v',
            backup_file
        ]
    else:
        args = [
            'pg_restore',
            '--no-owner',
            f'--dbname={db}',
            f'--host={db_host}',
            f'--port={port}',
            f'--username={user}',
            backup_file
        ]

    process = subprocess.Popen(args, stdout=subprocess.PIPE)
    output = process.communicate()[0]
    os.environ["PGPASSWORD"] = ""

    if int(process.returncode) != 0:
        print('Command failed. Return code : {}'.format(process.returncode))
        # TODO: raise exception or something like that

    return output

def fixDatabaseOwner(db_host, db_port, user_name, user_password, db_name):
    """
    Fix database owner.
    """
    logging.info('Fixing database objects owner...')
    connection = None
    try:
        connection = psycopg2.connect(host=db_host, port=db_port, user=user_name, password=user_password, dbname=db_name)
        connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with connection.cursor() as cursor:
            cursor.execute('SELECT \'ALTER TABLE \'|| schemaname || \'."\' || tablename ||\'" OWNER TO "{}";\' FROM pg_tables WHERE NOT schemaname IN (\'pg_catalog\', \'information_schema\') ORDER BY schemaname, tablename;'.format(db_name))
            for row in cursor.fetchall():
                cursor.execute(row[0])

            cursor.execute('SELECT \'ALTER SEQUENCE \'|| sequence_schema || \'."\' || sequence_name ||\'" OWNER TO "{}";\' FROM information_schema.sequences WHERE NOT sequence_schema IN (\'pg_catalog\', \'information_schema\') ORDER BY sequence_schema, sequence_name;'.format(db_name))
            for row in cursor.fetchall():
                cursor.execute(row[0])

            cursor.execute('SELECT \'ALTER VIEW \'|| table_schema || \'."\' || table_name ||\'" OWNER TO "{}";\' FROM information_schema.views WHERE NOT table_schema IN (\'pg_catalog\', \'information_schema\') ORDER BY table_schema, table_name;'.format(db_name))
            for row in cursor.fetchall():
                cursor.execute(row[0])

            cursor.execute('SELECT \'ALTER TABLE \'|| oid::regclass::text ||\' OWNER TO "{}";\' FROM pg_class WHERE relkind = \'m\' ORDER BY oid;'.format(db_name))
            for row in cursor.fetchall():
                cursor.execute(row[0])

    except Exception as exception:
        logging.exception(exception)
        exit(1)

def swapRestoreActive(db_host, restore_database, active_database, db_port, user_name, user_password):
    logging.info('Swapping active databases...')
    connection = None
    try:
        connection = psycopg2.connect(host=db_host, port=db_port, user=user_name, password=user_password, dbname='postgres')
        connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname = \'{}\';'.format(active_database))
            cursor.execute('DROP DATABASE "{}"'.format(active_database))
            cursor.execute('ALTER DATABASE "{}" RENAME TO "{}";'.format(restore_database, active_database))

    except Exception as exception:
        logging.exception(exception)
        exit(1)

def swapRestoreNew(db_host, restore_database, new_database, db_port, user_name, user_password):
    logging.info('Swapping new databases...')
    connection = None
    try:
        connection = psycopg2.connect(host=db_host, port=db_port, user=user_name, password=user_password, dbname='postgres')
        connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with connection.cursor() as cursor:
            cursor.execute('ALTER DATABASE "{}" RENAME TO "{}";'.format(restore_database, new_database))

    except Exception as exception:
        logging.exception(exception)
        exit(1)

def deleteDatabase(db_host, database, db_port, user_name, user_password):
    logging.info('Deleting database...')
    connection = None
    try:
        connection = psycopg2.connect(host=db_host, port=db_port, user=user_name, password=user_password, dbname='postgres')
        connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname = \'{}\';'.format(database))
            cursor.execute('DROP DATABASE IF EXISTS "{}"'.format(database))

    except Exception as exception:
        logging.exception(exception)
        exit(1)

def deleteUser(db_host, db_port, user_name, user_password, user_to_delete):
    logging.info('Deleting user...')
    connection = None
    try:
        connection = psycopg2.connect(host=db_host, port=db_port, user=user_name, password=user_password, dbname='postgres')
        connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with connection.cursor() as cursor:
            cursor.execute('DROP USER IF EXISTS "{}"'.format(user_to_delete))

    except Exception as exception:
        logging.exception(exception)
        exit(1)

def main():
    args_parser = argparse.ArgumentParser(description='Postgres database management')
    args_parser.add_argument("--configfile",
                             required=True,
                             help="Database configuration file")
    args_parser.add_argument("--action",
                             metavar="action",
                             choices=['restore', 'delete', 'create'],
                             help="Action to perform",
                             required=True)
    args_parser.add_argument("--swap",
                             metavar="swap",
                             default=False,
                             action=argparse.BooleanOptionalAction,
                             help="Swap active and new databases",
                             required=False)
    args_parser.add_argument("--verbose",
                             metavar="verbose",
                             default=False,
                             action=argparse.BooleanOptionalAction,
                             help="Berbose output",
                             required=False)
    args = args_parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.configfile)

    postgres_host_backup = config.get('backup', 'host')
    postgres_port_backup = config.get('backup', 'port')
    postgres_db_backup = config.get('backup', 'db')
    postgres_user_backup = config.get('backup', 'user')
    postgres_password_backup = config.get('backup', 'password')

    postgres_host_restore = config.get('restore', 'host')
    postgres_db_restore = "{}_restore".format(postgres_db_backup)
    postgres_port_restore = config.get('restore', 'port')
    postgres_user_restore = config.get('restore', 'user')
    postgres_password_restore = config.get('restore', 'password')
    postgres_new_user_restore = config.get('restore', 'user_new')
    postgres_new_password_restore = config.get('restore', 'password_new')

    if args.swap is False:
        postgres_db_restore = config.get('restore', 'db_new')

    if args.action == 'restore':
        timestr = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = 'backup-{}-{}.dump'.format(timestr, postgres_db_backup)
        local_file_path = '{}{}'.format(BACKUP_PATH, filename)

        backupPostgresDb(postgres_host_backup, postgres_db_backup, postgres_port_backup, postgres_user_backup, postgres_password_backup, local_file_path, args.verbose)
        createDatabseUser(postgres_host_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore, postgres_new_user_restore, postgres_new_password_restore, args.verbose)
        # createDatabase(postgres_host_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore, postgres_new_user_restore, postgres_new_user_restore, args.verbose)
        createDatabase(postgres_host_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore, postgres_new_user_restore, postgres_db_restore, args.verbose)
        restorePostgresDb(postgres_host_restore, postgres_db_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore, local_file_path, args.verbose)

        if args.swap is True:
            # swapRestoreActive(postgres_host_restore, postgres_db_restore, postgres_db_backup, postgres_port_restore, postgres_user_restore, postgres_password_restore)
            swapRestoreNew(postgres_host_restore, postgres_db_restore, postgres_new_user_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore)

        fixDatabaseOwner(postgres_host_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore, postgres_db_restore)
    elif args.action == 'delete':
        deleteDatabase(postgres_host_backup, postgres_db_restore, postgres_port_backup, postgres_user_backup, postgres_password_backup)
        deleteUser(postgres_host_backup, postgres_port_backup, postgres_user_backup, postgres_password_backup, postgres_new_user_restore)
    elif args.action == 'create':
        createDatabseUser(postgres_host_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore, postgres_new_user_restore, postgres_new_password_restore, args.verbose)
        createDatabase(postgres_host_restore, postgres_port_restore, postgres_user_restore, postgres_password_restore, postgres_new_user_restore, postgres_db_restore, args.verbose)

if __name__ == '__main__':
    try:
        startedAt = datetime.now()
        initLoggers()
        logging.info('Started at %s', startedAt.strftime('%Y-%m-%d %H:%M:%S'))
        main()
    except Exception as exception:
        logging.exception(exception)
        raise exception
    finally:
        endedAt = datetime.now()
        logging.info('Ended at %s', endedAt.strftime('%Y-%m-%d %H:%M:%S'))
        logging.info('Total time: %s', endedAt - startedAt)
