# FileName: Database.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


""" The module only supports SQLite, PostgreSQL, MariaDB, MySQL, SQL Server, Oracle. Based on SQLAlchemy."""
from liberrpa.Logging import Log

from sqlalchemy import create_engine, text, Connection, URL
from types import TracebackType
from typing import Any, Literal
from collections.abc import Mapping, Sequence

type TypeOfDatabase = Literal["SQLite", "PostgreSQL", "MariaDB", "MySQL", "SQL Server", "Oracle"]
type TypeOfDbOptions = Mapping[str, Sequence[str] | str]

_SUPPORTED_DATABASE_TYPES = ["SQLite", "PostgreSQL", "MariaDB", "MySQL", "SQL Server", "Oracle"]


class DatabaseConnection:
    """
    A short-lived context manager for database connections, based on SQLAlchemy.

    You can either provide a full connection string or provide separate parameters
    such as dbType, username, password, host, port, database, and options.

    The connection is opened when entering the context, and a transaction is started.
    When exiting the context, the transaction is committed if no exception occurred;
    otherwise, it is rolled back. The connection is then closed and the engine is disposed.

    Supported database types: SQLite, PostgreSQL, MariaDB, MySQL, SQL Server, Oracle.

    Example connection strings:
        SQLite: "sqlite:///<path_to_db>"
        PostgreSQL: "postgresql+psycopg2://<username>:<password>@<host>:<port>/<database>"
        MariaDB/MySQL: "mysql+pymysql://<username>:<password>@<host>:<port>/<database>"
        SQL Server: "mssql+pymssql://<username>:<password>@<host>:<port>/<database>"
        Oracle: "oracle+oracledb://<username>:<password>@<host>:<port>/<service_name>"

    Parameters:
        connectString: A full connection string. If it is provided, all other connection arguments are ignored.
        dbType: One of ["SQLite", "PostgreSQL", "MariaDB", "MySQL", "SQL Server", "Oracle"]. Used only when connectString is not provided.
        username: Username for the database. Ignored for SQLite.
        password: Password for the database. Ignored for SQLite.
        host: Database host. Ignored for SQLite.
        port: Port for the database connection. Ignored for SQLite.
        database: Database name or SQLite database file path.
        options: Additional connection options, such as charset, sslmode, or service_name.

    Example usage:
    ```
    with DatabaseConnection(
        dbType="PostgreSQL",
        username="postgres",
        password="password",
        host="localhost",
        port=5432,
        database="mydb",
        options={"sslmode": "require"}
    ) as connObj:
        temp = execute(
            connObj=connObj,
            query='''INSERT INTO public.categories (category_name, parent_category_id) VALUES (:category_name, :parent_category_id)''',
            params=[
                {"category_name": "Smartphones", "parent_category_id": 1},
                {"category_name": "Tablets", "parent_category_id": 1},
            ],
        )
        print(temp)

    with DatabaseConnection(
        dbType="SQLite",
        database=r"./test.db",
    ) as connObj:
        print(fetch_all(connObj=connObj, query="SELECT * FROM users;", params=None, returnDict=False))
    ```
    """

    def __init__(
        self,
        connectString: str | None = None,
        dbType: TypeOfDatabase | None = None,
        username: str | None = None,
        password: str | None = None,
        host: str | None = "localhost",
        port: int | None = None,
        database: str = "",
        options: TypeOfDbOptions | None = None,
    ) -> None:
        self.connection: Connection
        self.queryOptions: dict[str, Sequence[str] | str] = {} if options is None else dict(options)

        if connectString:
            self.engine = create_engine(connectString, echo=False)
            return None

        else:
            match dbType:
                case "SQLite":
                    drivername = "sqlite"
                    # SQLite URLs should not include username, password, host, or port.
                    username = None
                    password = None
                    host = None
                    port = None
                case "PostgreSQL":
                    drivername = "postgresql+psycopg2"
                case "MariaDB":
                    drivername = "mysql+pymysql"
                case "MySQL":
                    drivername = "mysql+pymysql"
                case "SQL Server":
                    drivername = "mssql+pymssql"
                case "Oracle":
                    drivername = "oracle+oracledb"
                case _:
                    raise ValueError(f"The argument 'dbType' should be one of {_SUPPORTED_DATABASE_TYPES}")

            url = URL.create(
                drivername=drivername,
                username=username,
                password=password,
                host=host,
                port=port,
                database=database,
                query=self.queryOptions,
            )
            # echo=True for debugging
            self.engine = create_engine(url, echo=False)

    def __enter__(self) -> Connection:
        Log.verbose("Opening database connection...")

        try:
            self.connection = self.engine.connect()
            self.transaction = self.connection.begin()
        except Exception:
            self.engine.dispose()
            raise

        return self.connection

    def __exit__(
        self,
        excType: type[BaseException] | None,
        excValue: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        try:
            if excType:
                Log.error(f"Error occurred: {excValue}, rolling back changes...")
                self.transaction.rollback()
            else:
                Log.verbose("Committing changes before disconnection...")
                self.transaction.commit()
        finally:
            Log.verbose("Closing database connection...")
            self.connection.close()
            self.engine.dispose()


@Log.trace()
def fetch_one(
    connObj: Connection,
    query: str,
    params: dict[str, Any] | None = None,
    returnDict: bool = True,
) -> dict[str, Any] | list[Any] | None:
    """
    Execute a query and fetch a single row.

    Parameters:
        connObj: The active database connection.
        query: The SQL query to be executed.

            Example: "SELECT * FROM employees WHERE employee_id = :id"
        params: The parameters to bind to the query.

            This should be a dictionary where the keys correspond to the placeholders in the SQL query (e.g., ":id"). Example: {"id": 1}.

            If no parameters are required, pass None.
        returnDict: Whether to return the result as a dictionary (True) or list (False).

    Returns:
        dict[str, Any] | list[Any] | None: The fetched row as a dictionary or list, or None if no row is found.
    """
    result = connObj.execute(text(query), params)
    row = result.fetchone()
    if row is None:
        return None
    if returnDict:
        return row._asdict()
    else:
        return list(row)


@Log.trace()
def fetch_all(
    connObj: Connection,
    query: str,
    params: dict[str, Any] | None = None,
    returnDict: bool = True,
) -> list[dict[str, Any]] | list[list[Any]]:
    """
    Execute a query and fetch all rows.

    Parameters:
        connObj: The active database connection.
        query: The SQL query to be executed.

            Example: "SELECT * FROM employees WHERE salary > :salary"
        params: The parameters to bind to the query.

            This should be a dictionary where the keys correspond to the placeholders in the SQL query (e.g., ":salary").

            Example: {"salary": 50000}.

            If no parameters are required, pass None.
        returnDict: Whether to return the results as dictionaries (True) or lists (False).

    Returns:
        list[dict[str, Any]] | list[list[Any]]: A list of rows, where each row is a dictionary or list.
    """
    result = connObj.execute(text(query), params)
    if returnDict:
        return [row._asdict() for row in result.fetchall()]
    else:
        return [list(row) for row in result.fetchall()]


@Log.trace()
def execute(connObj: Connection, query: str, params: list[dict[str, Any]] | dict[str, Any] | None = None) -> int:
    """
    Execute an SQL query and return the number of affected rows.

    Parameters:
        connObj: The active database connection.
        query: The SQL query to be executed.

            Example: "UPDATE employees SET salary = :salary WHERE employee_id = :id"
        params: The parameters to bind to the query.

            This can be a single dictionary or a list of dictionaries for bulk operations.

            Example for single operation: {"salary": 55000, "id": 1}.

            Example for bulk operation: [{"salary": 55000, "id": 1}, {"salary": 62000, "id": 2}].

            If no parameters are required, pass None.

    Returns:
        int: The number of rows affected by the query.
    """
    result = connObj.execute(text(query), params)
    return result.rowcount or 0


if __name__ == "__main__":
    ...
    # from liberrpa._TempInfo import *

    # Test SQL Server
    """ with DatabaseConnection(
        dbType="SQL Server",
        username="sa",
        password=strPassword,
        host=strHost,
        port=1433,
        options={},  # Use service_name instead of database
    ) as connObj:
        print(
            fetch_all(
                connObj=connObj,
                query="SELECT * FROM TestTable;",
            )
        ) """
    """ with DatabaseConnection(connectString=f"mssql+pymssql://sa:{strPassword}@{strHost}:1433/") as connObj:
        print(
            fetch_all(
                connObj=connObj,
                query="SELECT * FROM TestTable;",
            )
        ) """

    # Test Oracle
    """ with DatabaseConnection(
        dbType="Oracle",
        username="system",
        password=strPassword,
        host=strHost,
        port=1521,
        options={"service_name": "XE"},  # Use service_name instead of database
    ) as connObj:
        print(fetch_all(connObj=connObj, query="SELECT user FROM dual"))
        # print(execute(connObj=connObj, query="SELECT * FROM test_table;")) """
    """ with DatabaseConnection(
        connectString=f"oracle+oracledb://system:{strPassword}@{strHost}:1521/?service_name=XE"
    ) as connObj:
        print(fetch_all(connObj=connObj, query="SELECT user FROM dual")) """

    # Test PostgreSQL
    """ with DatabaseConnection(
        dbType="PostgreSQL",
        username="postgres",
        password=strPassword,
        host="localhost",
        port=5432,
        database="postgres",
        options={"sslmode": "disable"},
    ) as connObj:
        print(fetch_all(connObj=connObj, query="SELECT * FROM public.employees", params=None, returnDict=False)) """
    """ with DatabaseConnection(
        connectString=f"postgresql+psycopg2://postgres:{strPassword}@localhost:5432/postgres?sslmode=disable"
    ) as connObj:
        print(fetch_all(connObj=connObj, query="SELECT * FROM public.employees", params=None, returnDict=False)) """

    # Test SQLite
    """ with DatabaseConnection(
        dbType="SQLite",
        username=None,
        password=None,
        host=None,
        port=None,
        database=strSqlitePath,
        options={},
    ) as connObj:
        print(fetch_all(connObj=connObj, query="SELECT * FROM users;", params=None, returnDict=False)) """
    """ with DatabaseConnection(connectString=f"sqlite:///{strSqlitePath}") as connObj:
        print(fetch_all(connObj=connObj, query="SELECT * FROM users;", params=None, returnDict=False)) """

    # Test MySQL/MariaDB
    """ with DatabaseConnection(
        dbType="MySQL",
        username="root",
        password=strPassword,
        host=strHost,
        port=3306,
        database="testDb",
        options={},
    ) as connObj:
        print(fetch_all(connObj=connObj, query="SELECT * FROM users;")) """
    """ with DatabaseConnection(connectString=f"mysql+pymysql://root:{strPassword}@{strHost}:3306/testDb") as connObj:
        print(fetch_all(connObj=connObj, query="SELECT * FROM users;")) """
