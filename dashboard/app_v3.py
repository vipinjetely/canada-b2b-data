import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv


load_dotenv()


st.set_page_config(
    page_title="Canada B2B Data — V3",
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
            COUNT(*) AS total_locations,

            COUNT(*) FILTER (
                WHERE phone IS NOT NULL
                  AND phone <> ''
            ) AS with_phone,

            COUNT(*) FILTER (
                WHERE email IS NOT NULL
                  AND email <> ''
            ) AS with_email,

            COUNT(*) FILTER (
                WHERE website IS NOT NULL
                  AND website <> ''
            ) AS with_website,

            COUNT(*) FILTER (
                WHERE record_readiness = 'SALES_READY'
            ) AS sales_ready,

            COUNT(*) FILTER (
                WHERE employee_count_type = 'VERIFIED'
            ) AS verified_employee,

            COUNT(*) FILTER (
                WHERE source_confidence_band = 'HIGH'
            ) AS high_confidence,

            ROUND(
                AVG(quality_score),
                2
            ) AS average_quality,

            COUNT(
                DISTINCT province
            ) AS provinces

        FROM v3_business_locations;
        """
    )


@st.cache_data(ttl=300)
def get_provinces():
    df = run_query(
        """
        SELECT DISTINCT province
        FROM v3_business_locations
        WHERE province IS NOT NULL
          AND province <> ''
        ORDER BY province;
        """
    )

    return df["province"].tolist()


@st.cache_data(ttl=300)
def get_categories():
    df = run_query(
        """
        SELECT
            basic_category,
            COUNT(*) AS records

        FROM v3_business_locations

        WHERE basic_category IS NOT NULL
          AND basic_category <> ''

        GROUP BY basic_category

        ORDER BY records DESC

        LIMIT 500;
        """
    )

    return df["basic_category"].tolist()


@st.cache_data(ttl=300)
def get_province_summary():
    return run_query(
        """
        SELECT
            province,

            COUNT(*) AS locations,

            COUNT(*) FILTER (
                WHERE record_readiness = 'SALES_READY'
            ) AS sales_ready,

            COUNT(*) FILTER (
                WHERE phone IS NOT NULL
                  AND phone <> ''
            ) AS with_phone,

            COUNT(*) FILTER (
                WHERE email IS NOT NULL
                  AND email <> ''
            ) AS with_email,

            COUNT(*) FILTER (
                WHERE employee_count_type = 'VERIFIED'
            ) AS verified_employee,

            ROUND(
                AVG(quality_score),
                2
            ) AS avg_quality

        FROM v3_business_locations

        WHERE province IS NOT NULL
          AND province <> ''

        GROUP BY province

        ORDER BY locations DESC;
        """
    )


@st.cache_data(ttl=300)
def get_readiness_summary():
    return run_query(
        """
        SELECT
            record_readiness,
            COUNT(*) AS records,

            ROUND(
                COUNT(*) * 100.0
                / SUM(COUNT(*)) OVER (),
                2
            ) AS percentage

        FROM v3_business_locations

        GROUP BY record_readiness

        ORDER BY records DESC;
        """
    )


@st.cache_data(ttl=300)
def get_employee_summary():
    return run_query(
        """
        SELECT
            COALESCE(
                employee_size_bucket,
                'Unknown'
            ) AS employee_size_bucket,

            COUNT(*) AS locations

        FROM v3_business_locations

        WHERE employee_count_type = 'VERIFIED'

        GROUP BY employee_size_bucket

        ORDER BY locations DESC;
        """
    )


@st.cache_data(ttl=300)
def get_change_summary():
    return run_query(
        """
        SELECT
            change_type,
            COUNT(*) AS history_events,
            MAX(detected_at) AS latest_detection

        FROM v3_location_change_history

        GROUP BY change_type

        ORDER BY history_events DESC;
        """
    )


def search_businesses(
    search_text,
    province,
    category,
    readiness,
    confidence_band,
    contact_filter,
    employee_filter,
    min_quality,
    limit,
):
    conditions = []
    params = []

    if search_text:
        conditions.append(
            """
            (
                business_name ILIKE %s
                OR city ILIKE %s
                OR postal_code ILIKE %s
                OR phone ILIKE %s
                OR email ILIKE %s
                OR website ILIKE %s
                OR location_id ILIKE %s
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
                pattern,
            ]
        )

    if province != "All":
        conditions.append(
            "province = %s"
        )
        params.append(province)

    if category != "All":
        conditions.append(
            "basic_category = %s"
        )
        params.append(category)

    if readiness != "All":
        conditions.append(
            "record_readiness = %s"
        )
        params.append(readiness)

    if confidence_band != "All":
        conditions.append(
            "source_confidence_band = %s"
        )
        params.append(confidence_band)

    if contact_filter == "Has phone":
        conditions.append(
            """
            phone IS NOT NULL
            AND phone <> ''
            """
        )

    elif contact_filter == "Has email":
        conditions.append(
            """
            email IS NOT NULL
            AND email <> ''
            """
        )

    elif contact_filter == "Has website":
        conditions.append(
            """
            website IS NOT NULL
            AND website <> ''
            """
        )

    elif contact_filter == "Has phone and email":
        conditions.append(
            """
            phone IS NOT NULL
            AND phone <> ''
            AND email IS NOT NULL
            AND email <> ''
            """
        )

    elif contact_filter == "Has phone, email and website":
        conditions.append(
            """
            phone IS NOT NULL
            AND phone <> ''
            AND email IS NOT NULL
            AND email <> ''
            AND website IS NOT NULL
            AND website <> ''
            """
        )

    if employee_filter == "Verified employee data":
        conditions.append(
            "employee_count_type = 'VERIFIED'"
        )

    elif employee_filter == "Unknown employee data":
        conditions.append(
            "employee_count_type = 'UNKNOWN'"
        )

    conditions.append(
        "COALESCE(quality_score, 0) >= %s"
    )
    params.append(min_quality)

    where_clause = ""

    if conditions:
        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )

    query = f"""
        SELECT
            location_id,
            business_name,
            city,
            province,
            postal_code,
            basic_category,

            phone,
            email,
            website,

            employee_count,
            employee_size_bucket,
            employee_count_type,
            employee_evidence_source,

            quality_score,
            record_readiness,
            source_confidence_band,
            source_confidence,

            operating_status,
            resolution_method

        FROM v3_business_locations

        {where_clause}

        ORDER BY
            quality_score DESC NULLS LAST,
            business_name NULLS LAST

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
    "V3 operating-location data layer with contact coverage, "
    "evidence-based employee enrichment, conservative identity "
    "resolution, record-quality scoring and daily change detection."
)


summary = get_summary().iloc[0]

total_locations = int(
    summary["total_locations"]
)

with_phone = int(
    summary["with_phone"]
)

with_email = int(
    summary["with_email"]
)

with_website = int(
    summary["with_website"]
)

sales_ready = int(
    summary["sales_ready"]
)

verified_employee = int(
    summary["verified_employee"]
)

high_confidence = int(
    summary["high_confidence"]
)

average_quality = float(
    summary["average_quality"]
)

provinces = int(
    summary["provinces"]
)


metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "Business / Location Candidates",
    f"{total_locations:,}",
)

metric2.metric(
    "Sales-Ready Records",
    f"{sales_ready:,}",
)

metric3.metric(
    "Average Record Quality",
    f"{average_quality:.2f} / 100",
)


metric4, metric5, metric6 = st.columns(3)

metric4.metric(
    "With Phone",
    f"{with_phone:,}",
)

metric5.metric(
    "With Email",
    f"{with_email:,}",
)

metric6.metric(
    "With Website",
    f"{with_website:,}",
)


metric7, metric8, metric9 = st.columns(3)

metric7.metric(
    "Verified Employee Evidence",
    f"{verified_employee:,}",
)

metric8.metric(
    "High Source Confidence",
    f"{high_confidence:,}",
)

metric9.metric(
    "Province / Territory Values",
    f"{provinces:,}",
)


st.info(
    "Sales-ready is a record-completeness/readiness classification, "
    "not a claim that every business or every field has been "
    "independently verified. Employee counts remain UNKNOWN unless "
    "supported by business/location-specific evidence."
)


st.divider()

st.subheader("Business Search & Export")


row1_col1, row1_col2, row1_col3 = st.columns(3)

with row1_col1:
    search_text = st.text_input(
        "Search",
        placeholder=(
            "Business, city, postal code, "
            "phone, email, website or location ID..."
        ),
    )

with row1_col2:
    province = st.selectbox(
        "Province / Territory",
        ["All"] + get_provinces(),
    )

with row1_col3:
    category = st.selectbox(
        "Business Category",
        ["All"] + get_categories(),
    )


row2_col1, row2_col2, row2_col3 = st.columns(3)

with row2_col1:
    readiness = st.selectbox(
        "Record Readiness",
        [
            "All",
            "SALES_READY",
            "PARTIAL",
            "INCOMPLETE",
        ],
    )

with row2_col2:
    confidence_band = st.selectbox(
        "Source Confidence",
        [
            "All",
            "HIGH",
            "MEDIUM",
            "LOW",
        ],
    )

with row2_col3:
    employee_filter = st.selectbox(
        "Employee Evidence",
        [
            "All",
            "Verified employee data",
            "Unknown employee data",
        ],
    )


row3_col1, row3_col2, row3_col3 = st.columns(3)

with row3_col1:
    contact_filter = st.selectbox(
        "Contact Availability",
        [
            "All",
            "Has phone",
            "Has email",
            "Has website",
            "Has phone and email",
            "Has phone, email and website",
        ],
    )

with row3_col2:
    min_quality = st.slider(
        "Minimum Record Quality",
        min_value=0,
        max_value=100,
        value=0,
        step=5,
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
    province=province,
    category=category,
    readiness=readiness,
    confidence_band=confidence_band,
    contact_filter=contact_filter,
    employee_filter=employee_filter,
    min_quality=min_quality,
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
    file_name="canada_b2b_v3_filtered_results.csv",
    mime="text/csv",
)


st.divider()

st.subheader("Record Readiness")

readiness_summary = get_readiness_summary()

st.dataframe(
    readiness_summary,
    use_container_width=True,
    hide_index=True,
)


st.divider()

st.subheader("Coverage by Province / Territory")

province_summary = get_province_summary()

st.dataframe(
    province_summary,
    use_container_width=True,
    hide_index=True,
)


st.divider()

st.subheader("Verified Employee-Size Coverage")

employee_summary = get_employee_summary()

if employee_summary.empty:
    st.caption(
        "No verified employee-size evidence is currently available."
    )
else:
    st.dataframe(
        employee_summary,
        use_container_width=True,
        hide_index=True,
    )


st.divider()

st.subheader("Daily Change History")

change_summary = get_change_summary()

if change_summary.empty:
    st.caption(
        "No NEW, CHANGED or REMOVED events have been recorded yet. "
        "The current PostgreSQL snapshot matches the latest V3 "
        "processed snapshot."
    )
else:
    st.dataframe(
        change_summary,
        use_container_width=True,
        hide_index=True,
    )


st.divider()

st.subheader("Data Quality & Methodology")

st.markdown(
    """
**Operating-location layer:** V3 keeps business/location records
separate from the earlier legal/canonical entity layer. Repeated
brand names are not automatically treated as one company.

**Record readiness:** `SALES_READY`, `PARTIAL` and `INCOMPLETE`
describe record completeness and contactability. They are not
business-performance ratings and do not mean every field has been
independently verified.

**Source confidence:** The confidence band reflects the underlying
place/source confidence used by the V3 pipeline. It is separate from
record-quality scoring and does not prove employee or contact details.

**Employee evidence:** Employee counts and employee-size buckets are
only marked `VERIFIED` when supported by business/location-specific
evidence. Missing employee data remains `UNKNOWN`; aggregate Canadian
statistics are not assigned to individual businesses.

**Entity resolution:** Location identity uses conservative combinations
of normalized business name, postal code, phone and usable domain
signals. Shared/platform domains are not treated as strong identity
keys.

**Change detection:** Each refreshed processed snapshot is compared
with the current PostgreSQL snapshot before replacement. NEW, CHANGED
and REMOVED events can be retained in the change-history layer;
UNCHANGED rows are not written as history events.

**Coverage limitation:** V3 is a broad business/location discovery and
enrichment layer. A business/location candidate should not be described
as a uniquely verified Canadian legal entity merely because it appears
in this dataset.

**Contact limitation:** Phone, email and website coverage varies by
source. Decision-maker extraction remains evidence/review based and
unreviewed candidates are not automatically promoted to verified
production contacts.

**Compliance:** `do_not_call` is retained in the PostgreSQL model for
downstream compliance workflows. Any sales use must apply applicable
consent, suppression and do-not-call requirements.
"""
)