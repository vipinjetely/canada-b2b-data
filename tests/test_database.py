import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def test_database_connection():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()

    assert result[0] == 1


def test_business_table_not_empty():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM businesses;"
            )
            count = cursor.fetchone()[0]

    assert count > 0


def test_corporation_number_unique_in_database():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT corporation_number
                    FROM businesses
                    GROUP BY corporation_number
                    HAVING COUNT(*) > 1
                ) duplicates;
                """
            )

            duplicate_count = cursor.fetchone()[0]

    assert duplicate_count == 0