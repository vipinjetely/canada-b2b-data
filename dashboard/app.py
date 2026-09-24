import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

st.set_page_config(
    page_title="Canada B2B Business Data",
    page_icon="🇨🇦",
    layout="wide",
)


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def run_query(query, params=None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or ())
            columns = [
                description.name
                for description in cursor.description
            ]
            rows = cursor.fetchall()

    return pd.DataFrame(rows, columns=columns)


@st.cache_data(ttl=300)
def get_summary():
    return run_query(
        """
        SELECT
            COUNT(*) AS total_businesses,
            COUNT(*) FILTER (
                WHERE odbus_matched = TRUE
            ) AS enriched_businesses,
            COUNT(DISTINCT province) AS provinces_territories
        FROM businesses;
        """
    )


@st.cache_data(ttl=300)
def get_provinces():
    df = run_query(
        """
        SELECT DISTINCT province
        FROM businesses
        WHERE province IS NOT NULL
          AND province <> ''
        ORDER BY province;
        """
    )

    return df["province"].tolist()


@st.cache_data(ttl=300)
def get_statuses():
    df = run_query(
        """
        SELECT DISTINCT status
        FROM businesses
        WHERE status IS NOT NULL
          AND status <> ''
        ORDER BY status;
        """
    )

    return df["status"].tolist()


def search_businesses(
    search_text,
    province,
    status,
    enriched_only,
    limit,
):
    conditions = []
    params = []

    if search_text:
        conditions.append(
            """
            (
                business_name ILIKE %s
                OR corporation_number ILIKE %s
                OR business_number ILIKE %s
            )
            """
        )

        pattern = f"%{search_text}%"
        params.extend([pattern, pattern, pattern])

    if province != "All":
        conditions.append("province = %s")
        params.append(province)

    if status != "All":
        conditions.append("status = %s")
        params.append(status)

    if enriched_only:
        conditions.append("odbus_matched = TRUE")

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            corporation_number,
            business_number,
            business_name,
            city,
            province,
            postal_code,
            status,
            odbus_derived_naics,
            odbus_naics_description,
            odbus_business_sector,
            odbus_matched
        FROM businesses
        {where_clause}
        ORDER BY business_name
        LIMIT %s;
    """

    params.append(limit)

    return run_query(query, params)


st.title("🇨🇦 Canada B2B Business Data Automation System")

st.caption(
    "Production-oriented business data pipeline using "
    "official Canadian public datasets, PostgreSQL and Python."
)

summary = get_summary().iloc[0]

total_businesses = int(summary["total_businesses"])
enriched_businesses = int(summary["enriched_businesses"])
provinces_territories = int(summary["provinces_territories"])

match_rate = (
    enriched_businesses / total_businesses * 100
    if total_businesses
    else 0
)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Federal Business Records",
    f"{total_businesses:,}",
)

col2.metric(
    "ODBus Enriched",
    f"{enriched_businesses:,}",
)

col3.metric(
    "Enrichment Rate",
    f"{match_rate:.2f}%",
)

col4.metric(
    "Province / Territory Values",
    f"{provinces_territories:,}",
)

st.divider()

st.subheader("Business Search")

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    search_text = st.text_input(
        "Business name / Corporation number / BN",
        placeholder="Search businesses...",
    )

with filter_col2:
    province = st.selectbox(
        "Province / Territory",
        ["All"] + get_provinces(),
    )

with filter_col3:
    status = st.selectbox(
        "Corporation Status",
        ["All"] + get_statuses(),
    )

option_col1, option_col2 = st.columns(2)

with option_col1:
    enriched_only = st.checkbox(
        "Show only ODBus-enriched records"
    )

with option_col2:
    limit = st.selectbox(
        "Maximum results",
        [25, 50, 100, 250, 500],
        index=1,
    )

results = search_businesses(
    search_text=search_text.strip(),
    province=province,
    status=status,
    enriched_only=enriched_only,
    limit=limit,
)

st.write(f"Showing **{len(results):,}** records")

st.dataframe(
    results,
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Data Provenance & Matching")

st.markdown(
    """
**Primary dataset:** Corporations Canada federal corporation
open data.

**Supplemental enrichment:** Statistics Canada Open Database
of Businesses (ODBus).

**Matching strategy:** Conservative automatic matching using
normalized business name and province. ODBus records are used
automatically only when the matching key uniquely identifies a
single ODBus record.

**Important limitation:** The federal Corporations Canada
dataset does not represent every business operating in Canada,
and the ODBus enrichment dataset is supplemental rather than a
current authoritative national business master.
"""
)