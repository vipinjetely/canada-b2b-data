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

    return pd.DataFrame(
        rows,
        columns=columns,
    )


@st.cache_data(ttl=300)
def get_summary():
    return run_query(
        """
        SELECT
            COUNT(*) AS total_entities,

            COUNT(*) FILTER (
                WHERE phone IS NOT NULL
                  AND phone <> ''
            ) AS with_phone,

            COUNT(*) FILTER (
                WHERE email IS NOT NULL
                  AND email <> ''
            ) AS with_email,

            COUNT(*) FILTER (
                WHERE industry IS NOT NULL
                  AND industry <> ''
            ) AS with_industry,

            COUNT(*) FILTER (
                WHERE is_new_7d = TRUE
            ) AS new_7d,

            COUNT(*) FILTER (
                WHERE is_new_30d = TRUE
            ) AS new_30d,

            COUNT(
                DISTINCT registry_jurisdiction
            ) AS jurisdictions
        FROM business_entities;
        """
    )


@st.cache_data(ttl=300)
def get_jurisdictions():
    df = run_query(
        """
        SELECT DISTINCT registry_jurisdiction
        FROM business_entities
        WHERE registry_jurisdiction IS NOT NULL
          AND registry_jurisdiction <> ''
        ORDER BY registry_jurisdiction;
        """
    )

    return df[
        "registry_jurisdiction"
    ].tolist()


@st.cache_data(ttl=300)
def get_statuses():
    df = run_query(
        """
        SELECT DISTINCT status
        FROM business_entities
        WHERE status IS NOT NULL
          AND status <> ''
        ORDER BY status;
        """
    )

    return df["status"].tolist()


@st.cache_data(ttl=300)
def get_industries():
    df = run_query(
        """
        SELECT DISTINCT industry
        FROM business_entities
        WHERE industry IS NOT NULL
          AND industry <> ''
        ORDER BY industry
        LIMIT 500;
        """
    )

    return df["industry"].tolist()


@st.cache_data(ttl=300)
def get_jurisdiction_summary():
    return run_query(
        """
        SELECT
            registry_jurisdiction AS jurisdiction,
            COUNT(*) AS canonical_entities,

            COUNT(*) FILTER (
                WHERE phone IS NOT NULL
                  AND phone <> ''
            ) AS with_phone,

            COUNT(*) FILTER (
                WHERE email IS NOT NULL
                  AND email <> ''
            ) AS with_email,

            COUNT(*) FILTER (
                WHERE industry IS NOT NULL
                  AND industry <> ''
            ) AS with_industry,

            COUNT(*) FILTER (
                WHERE is_new_7d = TRUE
            ) AS new_7d,

            COUNT(*) FILTER (
                WHERE is_new_30d = TRUE
            ) AS new_30d

        FROM business_entities

        GROUP BY registry_jurisdiction

        ORDER BY canonical_entities DESC;
        """
    )


@st.cache_data(ttl=300)
def get_source_freshness():
    return run_query(
        """
        SELECT
            ds.source_name,
            ds.jurisdiction,
            ds.update_frequency,
            ds.last_source_update_at,
            ds.last_collected_at,
            COUNT(bsr.id) AS source_records,
            COUNT(
                DISTINCT bsr.business_id
            ) AS linked_entities

        FROM data_sources ds

        LEFT JOIN business_source_records bsr
            ON bsr.source_id = ds.id

        WHERE ds.is_active = TRUE

        GROUP BY
            ds.id,
            ds.source_name,
            ds.jurisdiction,
            ds.update_frequency,
            ds.last_source_update_at,
            ds.last_collected_at

        ORDER BY ds.id;
        """
    )


def search_businesses(
    search_text,
    jurisdiction,
    status,
    industry,
    contact_filter,
    freshness_filter,
    limit,
):
    conditions = []
    params = []

    if search_text:
        conditions.append(
            """
            (
                legal_name ILIKE %s
                OR operating_name ILIKE %s
                OR federal_corporation_number ILIKE %s
                OR business_number ILIKE %s
                OR province_registry_id ILIKE %s
                OR city ILIKE %s
            )
            """
        )

        pattern = f"%{search_text}%"

        params.extend(
            [
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
            ]
        )

    if jurisdiction != "All":
        conditions.append(
            "registry_jurisdiction = %s"
        )
        params.append(jurisdiction)

    if status != "All":
        conditions.append("status = %s")
        params.append(status)

    if industry != "All":
        conditions.append("industry = %s")
        params.append(industry)

    if contact_filter == "Has phone":
        conditions.append(
            "phone IS NOT NULL AND phone <> ''"
        )

    elif contact_filter == "Has email":
        conditions.append(
            "email IS NOT NULL AND email <> ''"
        )

    elif contact_filter == "Has phone or email":
        conditions.append(
            """
            (
                (phone IS NOT NULL AND phone <> '')
                OR
                (email IS NOT NULL AND email <> '')
            )
            """
        )

    elif contact_filter == "Has phone and email":
        conditions.append(
            """
            (
                phone IS NOT NULL
                AND phone <> ''
                AND email IS NOT NULL
                AND email <> ''
            )
            """
        )

    if freshness_filter == "New in last 7 days":
        conditions.append(
            "is_new_7d = TRUE"
        )

    elif freshness_filter == "New in last 30 days":
        conditions.append(
            "is_new_30d = TRUE"
        )

    where_clause = ""

    if conditions:
        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )

    query = f"""
        SELECT
            id,
            legal_name,
            operating_name,
            federal_corporation_number,
            business_number,
            province_registry_id,
            registry_jurisdiction,
            city,
            province,
            postal_code,
            phone,
            email,
            industry,
            naics_code,
            employee_size_bucket,
            status,
            last_verified_at,
            is_new_7d,
            is_new_30d,
            quality_score,
            confidence_score

        FROM business_entities

        {where_clause}

        ORDER BY legal_name NULLS LAST

        LIMIT %s;
    """

    params.append(limit)

    return run_query(
        query,
        params,
    )


st.title(
    "🇨🇦 Canada B2B Business Data Automation System"
)

st.caption(
    "V2 canonical business master built from "
    "multiple current Canadian public-data sources "
    "with conservative entity resolution and provenance."
)

summary = get_summary().iloc[0]

total_entities = int(
    summary["total_entities"]
)

with_phone = int(
    summary["with_phone"]
)

with_email = int(
    summary["with_email"]
)

new_7d = int(
    summary["new_7d"]
)

new_30d = int(
    summary["new_30d"]
)

jurisdictions = int(
    summary["jurisdictions"]
)


metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "Canonical Business Entities",
    f"{total_entities:,}",
)

metric2.metric(
    "Businesses With Phone",
    f"{with_phone:,}",
)

metric3.metric(
    "Businesses With Email",
    f"{with_email:,}",
)


metric4, metric5, metric6 = st.columns(3)

metric4.metric(
    "New / Recent Signal — 7 Days",
    f"{new_7d:,}",
)

metric5.metric(
    "New / Recent Signal — 30 Days",
    f"{new_30d:,}",
)

metric6.metric(
    "Registry Jurisdictions",
    f"{jurisdictions:,}",
)


st.caption(
    "Recent signals are source-specific. They may represent "
    "new licences, recent licence activity or other source "
    "dates and should not universally be interpreted as "
    "newly incorporated businesses."
)

st.divider()


st.subheader("Business Search")

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    search_text = st.text_input(
        "Search",
        placeholder=(
            "Business name, corporation number, "
            "BN, registry ID or city..."
        ),
    )

with row1_col2:
    jurisdiction = st.selectbox(
        "Registry Jurisdiction",
        ["All"] + get_jurisdictions(),
    )


row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    status = st.selectbox(
        "Status",
        ["All"] + get_statuses(),
    )

with row2_col2:
    industry = st.selectbox(
        "Industry / Licence Category",
        ["All"] + get_industries(),
    )


row3_col1, row3_col2, row3_col3 = st.columns(3)

with row3_col1:
    contact_filter = st.selectbox(
        "Contact Availability",
        [
            "All",
            "Has phone",
            "Has email",
            "Has phone or email",
            "Has phone and email",
        ],
    )

with row3_col2:
    freshness_filter = st.selectbox(
        "Freshness Signal",
        [
            "All",
            "New in last 7 days",
            "New in last 30 days",
        ],
    )

with row3_col3:
    limit = st.selectbox(
        "Maximum Results",
        [
            25,
            50,
            100,
            250,
            500,
            1000,
        ],
        index=2,
    )


results = search_businesses(
    search_text=search_text.strip(),
    jurisdiction=jurisdiction,
    status=status,
    industry=industry,
    contact_filter=contact_filter,
    freshness_filter=freshness_filter,
    limit=limit,
)


st.write(
    f"Showing **{len(results):,}** records"
)

st.dataframe(
    results,
    use_container_width=True,
    hide_index=True,
)


csv_data = results.to_csv(
    index=False,
).encode("utf-8")

st.download_button(
    label="Download Current Results as CSV",
    data=csv_data,
    file_name="canada_b2b_filtered_results.csv",
    mime="text/csv",
)


st.divider()

st.subheader(
    "Coverage by Registry Jurisdiction"
)

jurisdiction_summary = (
    get_jurisdiction_summary()
)

st.dataframe(
    jurisdiction_summary,
    use_container_width=True,
    hide_index=True,
)


st.divider()

st.subheader(
    "Source Freshness & Provenance"
)

source_freshness = (
    get_source_freshness()
)

st.dataframe(
    source_freshness,
    use_container_width=True,
    hide_index=True,
)


st.divider()

st.subheader(
    "Data Quality & Methodology"
)

st.markdown(
    """
**Canonical master:** Records are stored in a separate V2
`business_entities` layer rather than treating raw source rows
as unique businesses.

**Entity resolution:** Strong registry identifiers are preferred
where available. Cross-source automatic matching is deliberately
conservative to reduce false merges.

**Provenance:** Source records remain linked to canonical
business entities through `business_source_records`, allowing
the origin and verification history of source data to be
retained.

**Freshness:** Source collection and source-update timestamps
are tracked separately. A blank source-update timestamp means
the upstream dataset did not provide a reliable source-update
timestamp; it is not replaced with an invented value.

**Coverage limitation:** This system combines federal and
selected provincial/municipal public datasets. It should not be
described as a complete registry of every Canadian business.

**Contact limitation:** Phone, email, industry, employee-size
and other enrichment fields vary significantly by source.
Missing values are retained as missing rather than inferred.

**Recent-business limitation:** The 7-day and 30-day indicators
are source-specific activity signals. Depending on the source,
they may reflect licence issuance, licence activity or another
published source date rather than legal business formation.
"""
)