import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


def test_connection() -> None:
    connection = psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        version = cursor.fetchone()

    connection.close()

    print("DATABASE CONNECTION OK")
    print(version[0])


if __name__ == "__main__":
    test_connection()