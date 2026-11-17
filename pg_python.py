#!/usr/bin/env python3
"""
pg_data.py
----------
What this script does, in order:
  1. Connects to a locally hosted PostgreSQL database.
  2. Runs a SELECT query that JOINs two tables together.
  3. Stores the joined rows in a Python variable (a list of dictionaries).
  4. Converts that variable to JSON and sends it to an API endpoint
     with an HTTP POST request.

Install the required libraries first (run in your terminal):
    pip install psycopg2-binary requests

  - psycopg2-binary : the library that lets Python talk to PostgreSQL
  - requests        : the library that makes HTTP calls (GET, POST, etc.)
"""

# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------

import os                       # Built-in. Lets us read environment variables (safer place for passwords).
import sys                      # Built-in. Lets us exit the script with an error code if something fails.
import json                     # Built-in. Converts Python dictionaries/lists into JSON text.
import decimal                  # Built-in. Postgres NUMERIC columns come back as Decimal objects.
import datetime                 # Built-in. Postgres date/timestamp columns come back as datetime objects.

import psycopg2                 # Third-party. The PostgreSQL driver.
import psycopg2.extras          # Part of psycopg2. Gives us RealDictCursor (rows as dictionaries).
import requests                 # Third-party. Used to send the POST request to the API.


# ---------------------------------------------------------------------------
# CONFIGURATION  (the section you will edit most often)
# ---------------------------------------------------------------------------

# os.getenv("NAME", "default") means: "use the environment variable NAME if it
# exists, otherwise use the default value after the comma".
# For quick testing you can just replace the defaults with your real values.
# For anything long-term, set environment variables instead so passwords
# are not saved inside your code.

DB_CONFIG = {
    "host":     os.getenv("PGHOST", "localhost"),      # Where Postgres runs. "localhost" = this computer.
    "port":     os.getenv("PGPORT", "5432"),           # Postgres default port is 5432.
    "dbname":   os.getenv("PGDATABASE", "mydatabase"), # <-- CHANGE: the name of your database.
    "user":     os.getenv("PGUSER", "postgres"),       # <-- CHANGE: your Postgres username.
    "password": os.getenv("PGPASSWORD", "your_password"),  # <-- CHANGE: your Postgres password.
}

# The API endpoint that will receive the data.
API_URL = os.getenv("API_URL", "https://example.com/api/orders")  # <-- CHANGE: your real endpoint.

# Optional: many APIs require a token. Leave as "" if yours does not.
API_TOKEN = os.getenv("API_TOKEN", "")

# ---------------------------------------------------------------------------
# THE SQL QUERY  (the section you will edit second most often)
# ---------------------------------------------------------------------------
# This is a multi-line Python string (triple quotes). Lines starting with
# "--" are SQL comments: Postgres ignores them, they are only for you.
#
# EXAMPLE SCENARIO: two tables
#   customers(id, name, email)
#   orders(id, customer_id, order_date, total)
# Rename the tables and columns below to match YOUR database.

SQL_QUERY = """
    SELECT
        -- SELECT lists the columns you want back. "c" and "o" are short
        -- nicknames (aliases) for the tables, defined in FROM/JOIN below.
        -- Format is: alias.column_name

        c.id          AS customer_id,   -- "AS customer_id" renames the column in the output.
                                        -- This becomes the JSON key, so name it how the API expects.
        c.name        AS customer_name, -- Column "name" from the customers table.
        c.email       AS customer_email,-- Column "email" from the customers table.
        o.id          AS order_id,      -- Column "id" from the orders table. We rename it
                                        -- because c.id and o.id would otherwise clash.
        o.order_date  AS order_date,    -- Column "order_date" from the orders table.
        o.total       AS order_total    -- Last column: NO trailing comma here, or SQL errors out.

    FROM customers AS c
        -- FROM names the main (left) table. "AS c" gives it the nickname "c".

    INNER JOIN orders AS o
        -- JOIN pulls in the second (right) table, nicknamed "o".
        -- INNER JOIN = only rows that have a match in BOTH tables.
        -- Change to LEFT JOIN to keep ALL customers, even those with no orders
        -- (the order columns will be NULL / None for those).

        ON o.customer_id = c.id
        -- ON is the matching rule: the orders.customer_id column must equal
        -- customers.id. This is the link between the two tables
        -- (the foreign key). If you get this wrong you get wrong/duplicated data.

    WHERE o.order_date >= %s
        -- WHERE filters rows. "%s" is a PLACEHOLDER: the real value is passed
        -- separately in Python (see QUERY_PARAMS). NEVER paste values directly
        -- into the SQL text with f-strings; placeholders prevent SQL injection.
        -- Delete this whole WHERE block if you want every row.

    ORDER BY o.order_date DESC
        -- ORDER BY sorts results. DESC = newest first. Use ASC for oldest first.

    LIMIT 100;
        -- LIMIT caps how many rows come back. Remove it to get everything.
"""

# The values that replace the %s placeholders, IN ORDER, as a tuple.
# We have one %s above, so we have one value. A one-item tuple needs the
# trailing comma: ("2024-01-01",)  <- that comma is required by Python.
# If you add a second %s to the query, add a second value here.
QUERY_PARAMS = ("2024-01-01",)  # <-- CHANGE: only orders on/after this date.


# ---------------------------------------------------------------------------
# HELPER: make Postgres data types JSON-friendly
# ---------------------------------------------------------------------------

def json_serializer(value):
    """
    json.dumps() does not know how to convert some types Postgres returns
    (dates, timestamps, Decimals). json.dumps calls this function whenever
    it hits a type it does not understand.
    """
    # datetime/date objects -> text like "2024-05-01T13:45:00"
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    # Decimal (used for NUMERIC/MONEY columns) -> normal float number
    if isinstance(value, decimal.Decimal):
        return float(value)
    # Anything else we did not plan for: raise an error so we notice it
    raise TypeError(f"Type {type(value)} is not JSON serializable")


# ---------------------------------------------------------------------------
# STEP 1 + 2 + 3: connect, query, and store the joined data in a variable
# ---------------------------------------------------------------------------

def fetch_joined_data():
    """Connects to Postgres, runs the JOIN query, returns a list of dicts."""

    connection = None  # Defined up front so the "finally" block can check it safely.
    try:
        # Open the connection. **DB_CONFIG "unpacks" the dictionary above into
        # keyword arguments: host=..., port=..., dbname=..., and so on.
        connection = psycopg2.connect(**DB_CONFIG)

        # A cursor is the object that actually runs SQL and holds the results.
        # RealDictCursor makes each row a dictionary like
        # {"customer_id": 1, "customer_name": "Ann"} instead of a plain tuple
        # (1, "Ann"). Dictionaries convert to JSON keys with no extra work.
        # "with ... as cursor" automatically closes the cursor when finished.
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:

            # Run the query. First argument = SQL text, second = values for the %s placeholders.
            cursor.execute(SQL_QUERY, QUERY_PARAMS)

            # fetchall() pulls every result row into memory as a list.
            # (For millions of rows, use fetchmany(n) in a loop instead.)
            rows = cursor.fetchall()

        # RealDictRow objects behave like dicts but are a special class;
        # dict(row) converts each to a plain dictionary. The result is the
        # "variable" holding your joined data: a list of dictionaries.
        joined_data = [dict(row) for row in rows]

        print(f"Fetched {len(joined_data)} rows from the database.")
        return joined_data

    finally:
        # "finally" always runs, even if an error happened above.
        # Always close the connection so you do not leak database connections.
        if connection is not None:
            connection.close()


# ---------------------------------------------------------------------------
# STEP 4: send the data to the API as JSON
# ---------------------------------------------------------------------------

def post_to_api(data):
    """Sends `data` (a list of dicts) to API_URL as a JSON POST request."""

    # Headers tell the API what we are sending.
    headers = {
        "Content-Type": "application/json",  # Says "the body is JSON".
    }
    # Only add the Authorization header if you set a token above.
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"  # Common token format. Some APIs use a different header (e.g. "X-API-Key").

    # Turn the Python list/dicts into a JSON string.
    # default=json_serializer handles dates and Decimals (see helper above).
    # If your API wants the list wrapped in an object, change `data` to
    # something like {"orders": data}.
    json_body = json.dumps(data, default=json_serializer)

    # Send the POST request.
    # data=json_body sends our pre-built JSON string as the request body.
    # timeout=30 means "give up after 30 seconds" so the script cannot hang forever.
    response = requests.post(API_URL, data=json_body, headers=headers, timeout=30)

    # raise_for_status() raises an error for HTTP codes 400-599
    # (e.g. 401 unauthorized, 404 not found, 500 server error).
    response.raise_for_status()

    print(f"API responded with status {response.status_code}")
    return response  # Returned in case you want to inspect response.json() or response.text.


# ---------------------------------------------------------------------------
# MAIN: runs the steps in sequence
# ---------------------------------------------------------------------------

def main():
    try:
        # Steps 1-3: query the database, get the joined data.
        joined_data = fetch_joined_data()

        # If the query returned nothing, there is no point calling the API.
        if not joined_data:
            print("No rows returned. Nothing to send.")
            return

        # Step 4: POST the data to the API.
        post_to_api(joined_data)

    except psycopg2.OperationalError as err:
        # Raised when we cannot connect: wrong host/port/user/password, server down, etc.
        print(f"Database connection problem: {err}")
        sys.exit(1)  # Exit code 1 = "something went wrong".
    except psycopg2.errors.UndefinedTable as err:
        # Raised when a table name in SQL_QUERY does not exist.
        print(f"Table not found. Check table names in SQL_QUERY: {err}")
        sys.exit(1)
    except psycopg2.errors.UndefinedColumn as err:
        # Raised when a column name in SQL_QUERY does not exist.
        print(f"Column not found. Check column names in SQL_QUERY: {err}")
        sys.exit(1)
    except psycopg2.Error as err:
        # Catch-all for any other database error (syntax errors, etc.).
        print(f"Database error: {err}")
        sys.exit(1)
    except requests.exceptions.RequestException as err:
        # Catch-all for API problems: no internet, bad URL, timeout, 4xx/5xx status.
        print(f"API request failed: {err}")
        sys.exit(1)


# This line means "only run main() if this file is executed directly"
# (python pg_data.py). If another script imports this file, main() will NOT
# run automatically, so you can reuse the functions elsewhere.
if __name__ == "__main__":
    main()
