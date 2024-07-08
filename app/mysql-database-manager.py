# Inspired by https://gist.github.com/valferon/4d6ebfa8a7f3d4e84085183609d10f14
#
#

import argparse
import configparser
import logging
import subprocess

import pymysql
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
    connection = pymysql.connect(host=host, port=port, user=user, password=password, db='mysql')
    with connection.cursor() as cursor:
        cursor.execute('CREATE USER "{}";'.format(newUser))
        cursor.execute('ALTER USER "{0}" IDENTIFIED BY "{1}";'.format(newUser, newUserPassword))
        # cursor.execute('GRANT ALL PRIVILEGES ON *.* TO "{}";'.format(newUser))

def createDatabase(host: str, port: int, user: str, password: str, newUser: str, databaseName: str, verbose: bool):
    """
    Create a new database.
    """
    logging.info('Creating database "{}"...'.format(databaseName))
    connection = pymysql.connect(host=host, port=port, user=user, password=password, db='mysql')
    with connection.cursor() as cursor:
        cursor.execute('CREATE DATABASE {0} CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;'.format(databaseName))
        cursor.execute('GRANT ALL PRIVILEGES ON {0}.* TO \'{1}\'@\'%\';'.format(databaseName, newUser))

def backupMysqlDb(host: str, databaseName: str, port: int, user: str, password: str, destFile: str, verbose: bool) -> bytes:
    """
    Backup MySQL database to a file.
    """
    logging.info('Backing up database "{}"...'.format(databaseName))
    args = ['mysqldump',
            '--host={}'.format(host),
            '--port={}'.format(port),
            '--user={}'.format(user),
            '--password={}'.format(password),
            '--result-file={}'.format(destFile),
            '--routines',
            '--triggers',
            '--events',
            '--single-transaction',
            '--no-create-db',
            databaseName,
            ]

    if verbose:
        args.append('-v')

    process = subprocess.Popen(args, stdout=subprocess.PIPE)
    output = process.communicate()[0]

    if int(process.returncode) != 0:
        print('Command failed. Return code : {}'.format(process.returncode))
        exit(1)

    return output

def restoreMysqlDb(db_host, db, port, user, password, backup_file, verbose):
    """
    Restore postgres db from a file.
    """
    logging.info('Restoring database "{}"...'.format(db))
    args = ['mysql',
            '--host={}'.format(db_host),
            '--port={}'.format(port),
            '--user={}'.format(user),
            '--password={}'.format(password),
            '--database={}'.format(db),
        ]

    if verbose:
        args.append('-v')

    with open(backup_file, 'rb') as f:
        process = subprocess.Popen(args, stdin=f, stdout=subprocess.PIPE)
        output = process.communicate()[0]

    if int(process.returncode) != 0:
        print('Command failed. Return code : {}'.format(process.returncode))
        # TODO: raise exception or something like that

    return output

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

    host_backup = config.get('backup', 'host')
    port_backup = int(config.get('backup', 'port'))
    db_backup = config.get('backup', 'db')
    user_backup = config.get('backup', 'user')
    password_backup = config.get('backup', 'password')

    host_restore = config.get('restore', 'host')
    port_restore = int(config.get('restore', 'port'))
    user_restore = config.get('restore', 'user')
    password_restore = config.get('restore', 'password')
    new_user_restore = config.get('restore', 'user_new')
    new_password_restore = config.get('restore', 'password_new')

    if args.action == 'restore':
        timestr = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = 'backup-{}-{}.sql'.format(timestr, db_backup)
        local_file_path = '{}{}'.format(BACKUP_PATH, filename)

        backupMysqlDb(host_backup, db_backup, port_backup, user_backup, password_backup, filename, args.verbose)
        createDatabseUser(host_restore, port_restore, user_restore, password_restore, new_user_restore, new_password_restore, args.verbose)
        createDatabase(host_restore, port_restore, user_restore, password_restore, new_user_restore, new_user_restore, args.verbose)
        # createDatabase(host_restore, port_restore, user_restore, password_restore, new_user_restore, db_restore, args.verbose)
        restoreMysqlDb(host_restore, new_user_restore, port_restore, user_restore, password_restore, local_file_path, args.verbose)
        # swapRestoreActive(host_restore, db_restore, db_backup, port_restore, user_restore, password_restore)
        # swapRestoreNew(host_restore, db_restore, new_user_restore, port_restore, user_restore, password_restore)
        # fixDatabaseOwner(host_restore, port_restore, user_restore, password_restore, new_user_restore)
    elif args.action == 'create':
        createDatabseUser(host_restore, port_restore, user_restore, password_restore, new_user_restore, new_password_restore, args.verbose)
        createDatabase(host_restore, port_restore, user_restore, password_restore, new_user_restore, new_user_restore, args.verbose)

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
