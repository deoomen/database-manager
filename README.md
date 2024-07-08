# Database manager

This repo is inspired by [valferion](https://gist.github.com/valferon) gist: [postgres_manager.py](https://gist.github.com/valferon/4d6ebfa8a7f3d4e84085183609d10f14).

## Overview of settings

### Script parameters

| Parameter | Default value | Description |
| --- | --- | --- |
| `--configfile` | - | The name of the configuration file. |
| `--action` | - | Action to be performed (may differ depending on the database type). |
| `--swap`/`--no-swap` | `--no-swap` | Relevant for `restore` action. Whether to rename the restored database to a new name at the end of the action or leave it temporary. |
| `--verbose`/`--no-verbose` | `--no-verbose` | Additional information in the logs. |

### Configuration file

Section `[backup]`:

- `host` - source database host address,
- `port` - source database port,
- `user` - user name with which the backup will be performed,
- `password` - password of the user,
- `db` - the name of the source database.

Section `[restore]`:

- `host` - host address of the target database,
- `port` - port of the target database,
- `user` - name of the user with which operations on the target database will be performed,
- `password` - password of the user,
- `user_new` - name of the new user in the target database,
- `password_new` - password of the new user,
- `db_new` - name of the new database.

## Run

### Running the script

Sometimes you don't want to install any additional dependencies. That's when `docker-compose.yml` comes to the rescue.

1. Start the environment: `docker compose up -d`.
2. Switch to the container: `docker exec -it database-manager_app_1 bash`.
3. Create `mysql.config` or `psql.config` file according to the example (`sample.*.config`).
4. Run the script depending on the type of database such as:
    - `python mysql-database-manager.py --configfile=mysql.config --action=restore --swap`,
    - `python postgres-database-manager.py --configfile=mysql.config --action=restore --swap`.

### Running through a GitLab Job

1. Choose the job `run_script:mysql` or `run_script:postgresql`.
2. Fill in the environment variables:
    - `ACTION`,
    - `SWAP`,
    - `VERBOSE`,
    - `BACKUP_HOST`,
    - `BACKUP_PORT`,
    - `BACKUP_USER`,
    - `BACKUP_PASSWORD`,
    - `BACKUP_DB`,
    - `RESTORE_HOST`,
    - `RESTORE_PORT`,
    - `RESTORE_USER`,
    - `RESTORE_PASSWORD`,
    - `RESTORE_USER_NEW`,
    - `RESTORE_PASSWORD_NEW`,
    - `RESTORE_DB_NEW`.
3. Run job.
