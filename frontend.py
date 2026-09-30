import streamlit as st
import pandas as pd

from pathlib import Path
from io import BytesIO

from bulk_cleanup import (
    create_run_directory,
    standardize_dataset,
    validate_dataset,
    detect_duplicates,
    calculate_quality_metrics,
    calculate_quality_health,
    export_results,
)


# ========================================
# PAGE CONFIGURATION
# ========================================

st.set_page_config(
    page_title="CRM Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ========================================
# PROJECT PATHS
# ========================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ========================================
# CUSTOM STYLING
# ========================================

st.markdown(
    """
    <style>

    /* ====================================
       DESIGN SYSTEM
       ==================================== */

    :root {
        --crm-green: #0F6B4F;
        --crm-green-hover: #0B5A42;
        --crm-green-soft: #EAF5F0;

        --crm-black: #111111;
        --crm-white: #FFFFFF;

        --crm-border: #E5E7EB;
        --crm-muted: #6B7280;
        --crm-surface: #FFFFFF;

        --crm-shadow: rgba(0, 0, 0, 0.045);
    }


    /* ====================================
       GLOBAL
       ==================================== */

    .stApp {
        background: var(--crm-white);
    }

    .main {
        padding-top: 1rem;
    }

    .block-container {
        max-width: 1240px;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
        padding-bottom: 4rem;
    }


    /* ====================================
       GENERAL TYPOGRAPHY
       ==================================== */

    h1,
    h2,
    h3,
    h4,
    h5,
    h6 {
        color: var(--crm-black);
    }

    p,
    label {
        color: var(--crm-black);
    }


    /* ====================================
       SECTION TITLES
       ==================================== */

    .section-title {
        margin-top: 2rem;
        margin-bottom: 1rem;
        color: var(--crm-black);
        font-size: 1.08rem;
        font-weight: 750;
        letter-spacing: -0.015em;
    }

    .section-number {
        color: var(--crm-green);
        font-weight: 800;
        margin-right: 0.45rem;
        font-size: 0.82rem;
    }


    /* ====================================
       METRIC CARDS
       ==================================== */

    div[data-testid="stMetric"] {
        background: var(--crm-surface);
        border: 1px solid var(--crm-border);
        border-radius: 16px;
        padding: 1.15rem 1.25rem;
        box-shadow: 0 5px 18px var(--crm-shadow);

        transition:
            transform 0.18s ease,
            box-shadow 0.18s ease,
            border-color 0.18s ease;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: var(--crm-green);
        box-shadow: 0 10px 26px rgba(0, 0, 0, 0.07);
    }

    div[data-testid="stMetricLabel"] {
        color: var(--crm-muted) !important;
        font-size: 0.76rem !important;
        font-weight: 600 !important;
    }

    div[data-testid="stMetricValue"] {
        color: var(--crm-black) !important;
        font-size: 1.8rem !important;
        font-weight: 800 !important;
    }


    /* ====================================
       INPUTS
       ==================================== */

    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div {
        border-radius: 12px;
        border: 1px solid var(--crm-border);
        background: var(--crm-surface);

        transition:
            border-color 0.18s ease,
            box-shadow 0.18s ease;
    }

    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: var(--crm-green);
        box-shadow:
            0 0 0 3px rgba(15, 107, 79, 0.12);
    }

    input,
    textarea {
        color: var(--crm-black) !important;
    }


    /* ====================================
       FILE UPLOADER
       ==================================== */

    [data-testid="stFileUploader"] {
        background: var(--crm-surface);
        border: 1px dashed var(--crm-green);
        border-radius: 16px;
        padding: 0.5rem;

        transition:
            background 0.18s ease,
            border-color 0.18s ease;
    }

    [data-testid="stFileUploader"]:hover {
        background: var(--crm-green-soft);
        border-color: var(--crm-green-hover);
    }

    [data-testid="stFileUploaderDropzone"] {
        background: transparent !important;
        border: none !important;
    }


    /* ====================================
       BUTTONS
       ==================================== */

    .stButton > button {
        min-height: 2.8rem;
        border-radius: 11px;
        border: 1px solid var(--crm-border);
        background: var(--crm-white);
        color: var(--crm-black);
        font-weight: 650;

        transition:
            transform 0.16s ease,
            box-shadow 0.16s ease,
            border-color 0.16s ease,
            background 0.16s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        border-color: var(--crm-green);
        color: var(--crm-green);
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06);
    }

    .stButton > button[kind="primary"] {
        background: var(--crm-green);
        border-color: var(--crm-green);
        color: #FFFFFF;
        font-weight: 750;
        box-shadow:
            0 8px 20px rgba(15, 107, 79, 0.18);
    }

    .stButton > button[kind="primary"]:hover {
        background: var(--crm-green-hover);
        border-color: var(--crm-green-hover);
        color: #FFFFFF;
        box-shadow:
            0 10px 24px rgba(15, 107, 79, 0.24);
    }


    /* ====================================
       DOWNLOAD BUTTONS
       ==================================== */

    [data-testid="stDownloadButton"] button {
        border-radius: 11px;
        border: 1px solid var(--crm-border);
        background: var(--crm-white);
        color: var(--crm-black);
        font-weight: 650;

        transition:
            transform 0.16s ease,
            border-color 0.16s ease,
            color 0.16s ease;
    }

    [data-testid="stDownloadButton"] button:hover {
        transform: translateY(-1px);
        border-color: var(--crm-green);
        color: var(--crm-green);
    }


    /* ====================================
       ALERTS
       ==================================== */

    [data-testid="stAlert"] {
        border-radius: 13px;
    }

    .success-box {
        padding: 1rem 1.15rem;
        margin: 0.5rem 0 1.25rem;
        border-radius: 13px;

        background: var(--crm-green-soft);
        border: 1px solid rgba(15, 107, 79, 0.22);
        color: var(--crm-green);

        line-height: 1.6;
    }

    .warning-box {
        padding: 1rem 1.15rem;
        margin: 0.5rem 0 1.25rem;
        border-radius: 13px;

        background: var(--crm-surface);
        border: 1px solid var(--crm-border);
        color: var(--crm-black);

        line-height: 1.6;
    }


    /* ====================================
       DATAFRAME
       ==================================== */

    [data-testid="stDataFrame"] {
        border: 1px solid var(--crm-border);
        border-radius: 14px;
        overflow: hidden;
    }


    /* ====================================
       EXPANDER
       ==================================== */

    [data-testid="stExpander"] {
        border: 1px solid var(--crm-border);
        border-radius: 14px;
        background: var(--crm-surface);
        overflow: hidden;
    }


    /* ====================================
       STATUS
       ==================================== */

    [data-testid="stStatusWidget"] {
        border-radius: 14px;
        border: 1px solid var(--crm-border);
    }


    /* ====================================
       CODE BLOCK
       ==================================== */

    [data-testid="stCode"] {
        border-radius: 12px;
    }


    /* ====================================
       SIDEBAR
       ==================================== */

    [data-testid="stSidebar"] {
        border-right: 1px solid var(--crm-border);
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: var(--crm-black);
    }

    .sidebar-brand {
        padding: 0.5rem 0 1rem;
    }

    .sidebar-logo {
        display: inline-flex;
        align-items: center;
        justify-content: center;

        width: 34px;
        height: 34px;
        margin-bottom: 0.7rem;

        border-radius: 10px;

        background: var(--crm-green);
        color: #FFFFFF;

        font-weight: 800;
    }

    .sidebar-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: var(--crm-black);
    }

    .sidebar-description {
        margin-top: 0.45rem;
        color: var(--crm-muted);
        font-size: 0.85rem;
        line-height: 1.6;
    }

    .sidebar-footer {
        margin-top: 1.5rem;
        padding-top: 1rem;

        border-top: 1px solid var(--crm-border);

        color: var(--crm-muted);
        font-size: 0.75rem;
        line-height: 1.5;
    }


    /* ====================================
       FOOTER
       ==================================== */

    .footer {
        padding: 1.5rem 0 0;
        color: var(--crm-muted);
        font-size: 0.78rem;
        text-align: center;
    }


    /* ====================================
       DARK MODE
       ==================================== */

    @media (prefers-color-scheme: dark) {

        :root {
            --crm-green: #2A8F6B;
            --crm-green-hover: #36A77E;
            --crm-green-soft: #102A21;

            --crm-black: #F5F7F6;
            --crm-white: #0D0F0E;

            --crm-border: #29312D;
            --crm-muted: #9AA5A0;
            --crm-surface: #151917;

            --crm-shadow: rgba(0, 0, 0, 0.22);
        }

        .stApp {
            background: #0D0F0E;
        }

        div[data-testid="stMetric"] {
            background: #151917;
            border-color: #29312D;
        }

        div[data-testid="stMetricLabel"] {
            color: #9AA5A0 !important;
        }

        div[data-testid="stMetricValue"] {
            color: #F5F7F6 !important;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            background: #151917;
            border-color: #29312D;
        }

        input,
        textarea {
            color: #F5F7F6 !important;
        }

        .stButton > button {
            background: #151917;
            border-color: #29312D;
            color: #F5F7F6;
        }

        .stButton > button:hover {
            background: #1A201D;
            color: #6ED1A8;
            border-color: #2A8F6B;
        }

        [data-testid="stDownloadButton"] button {
            background: #151917;
            border-color: #29312D;
            color: #F5F7F6;
        }

        [data-testid="stDownloadButton"] button:hover {
            background: #1A201D;
            color: #6ED1A8;
            border-color: #2A8F6B;
        }

        [data-testid="stFileUploader"] {
            background: #151917;
            border-color: #2A8F6B;
        }

        [data-testid="stFileUploader"]:hover {
            background: #102A21;
        }

        [data-testid="stExpander"],
        [data-testid="stStatusWidget"] {
            background: #151917;
            border-color: #29312D;
        }

        [data-testid="stSidebar"] {
            background: #0D0F0E;
            border-color: #29312D;
        }

        .sidebar-title {
            color: #F5F7F6;
        }

        .sidebar-description {
            color: #9AA5A0;
        }

        .sidebar-footer {
            color: #7F8984;
            border-color: #29312D;
        }

        .section-title {
            color: #F5F7F6;
        }

        .success-box {
            background: #102A21;
            border-color: rgba(42, 143, 107, 0.35);
            color: #6ED1A8;
        }

        .warning-box {
            background: #151917;
            border-color: #29312D;
            color: #F5F7F6;
        }

        [data-testid="stDataFrame"] {
            border-color: #29312D;
        }

        .footer {
            color: #7F8984;
        }
    }


    /* ====================================
       MOBILE
       ==================================== */

    @media (max-width: 768px) {

        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .section-title {
            margin-top: 1.5rem;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ========================================
# SESSION STATE
# ========================================

if "result" not in st.session_state:
    st.session_state.result = None

if "run_directory" not in st.session_state:
    st.session_state.run_directory = None

if "uploaded_file_bytes" not in st.session_state:
    st.session_state.uploaded_file_bytes = None

if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None


# ========================================
# HERO
# ========================================

st.html(
    """
    <style>

    .crm-hero {
        position: relative;
        overflow: hidden;

        padding: 44px 48px;
        margin: 0 0 40px 0;

        border-radius: 24px;

        background: #111111;
        border: 1px solid #111111;

        box-shadow:
            0 18px 45px rgba(0, 0, 0, 0.09);
    }

    .crm-hero-content {
        position: relative;
        z-index: 2;
        max-width: 760px;
    }

    .crm-hero-eyebrow {
        display: inline-block;

        margin-bottom: 16px;
        padding: 6px 11px;

        border-radius: 999px;

        background: rgba(15, 107, 79, 0.18);
        color: #72C9A8;

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        font-size: 11px;
        font-weight: 700;

        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .crm-hero-title {
        margin: 0;

        color: #FFFFFF;

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        font-size: 44px;
        line-height: 1.04;

        letter-spacing: -0.045em;
        font-weight: 800;
    }

    .crm-hero-description {
        margin: 18px 0 0 0;

        max-width: 650px;

        color: #D1D5DB;

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        font-size: 17px;
        line-height: 1.65;
    }

    .crm-hero-orbit {
        position: absolute;

        width: 270px;
        height: 270px;

        right: -95px;
        top: -115px;

        border-radius: 50%;

        border: 1px solid rgba(15, 107, 79, 0.45);

        box-shadow:
            0 0 0 35px rgba(15, 107, 79, 0.08),
            0 0 0 70px rgba(15, 107, 79, 0.04);
    }

    .crm-hero-orbit::after {
        content: "";

        position: absolute;

        width: 8px;
        height: 8px;

        right: 55px;
        bottom: 42px;

        border-radius: 50%;

        background: #2A8F6B;

        box-shadow:
            0 0 0 7px rgba(42, 143, 107, 0.12),
            0 0 24px rgba(42, 143, 107, 0.5);
    }


    /* ====================================
       DARK MODE HERO
       ==================================== */

    @media (prefers-color-scheme: dark) {

        .crm-hero {
            background: #151917;
            border-color: #29312D;

            box-shadow:
                0 18px 45px rgba(0, 0, 0, 0.28);
        }

        .crm-hero-title {
            color: #F5F7F6;
        }

        .crm-hero-description {
            color: #AEB8B3;
        }

        .crm-hero-eyebrow {
            color: #6ED1A8;
            background: rgba(42, 143, 107, 0.16);
        }

        .crm-hero-orbit {
            border-color: rgba(42, 143, 107, 0.42);

            box-shadow:
                0 0 0 35px rgba(42, 143, 107, 0.08),
                0 0 0 70px rgba(42, 143, 107, 0.04);
        }

        .crm-hero-orbit::after {
            background: #36A77E;
        }
    }


    /* ====================================
       MOBILE HERO
       ==================================== */

    @media (max-width: 768px) {

        .crm-hero {
            padding: 32px 24px;
            border-radius: 19px;
        }

        .crm-hero-title {
            font-size: 34px;
        }

        .crm-hero-description {
            font-size: 15px;
            line-height: 1.6;
        }

        .crm-hero-orbit {
            width: 190px;
            height: 190px;

            right: -85px;
            top: -80px;
        }
    }

    </style>

    <div class="crm-hero">

        <div class="crm-hero-content">

            <div class="crm-hero-eyebrow">
                CRM Data Intelligence
            </div>

            <div class="crm-hero-title">
                Turn messy CRM data<br>
                into trusted data.
            </div>

            <div class="crm-hero-description">
                Clean, validate, deduplicate and analyze your CRM data
                before it enters your workflow.
            </div>

        </div>

        <div class="crm-hero-orbit"></div>

    </div>
    """
)


# ========================================
# SIDEBAR
# ========================================

with st.sidebar:

    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-logo">◆</div>

            <div class="sidebar-title">
                CRM Intelligence
            </div>

            <div class="sidebar-description">
                Clean and prepare customer data
                for reliable CRM operations.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        """
        <div class="sidebar-description">
            Your dataset passes through the existing
            cleanup, validation, duplicate detection,
            CRM and intelligence engine.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="sidebar-footer">
            Data processing is handled by your
            existing CRM automation pipeline.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ========================================
# CLIENT INPUT
# ========================================

st.markdown(
    """
    <div class="section-title">
        <span class="section-number">01</span>
        Client information
    </div>
    """,
    unsafe_allow_html=True,
)

client_col, dataset_col = st.columns(2)

with client_col:

    client_name = st.text_input(
        "Client name",
        placeholder="e.g. ABC Company",
    )

with dataset_col:

    dataset_name = st.text_input(
        "Dataset name",
        placeholder="e.g. September Leads",
    )


# ========================================
# FILE UPLOAD
# ========================================

st.markdown(
    """
    <div class="section-title">
        <span class="section-number">02</span>
        Upload CRM dataset
    </div>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Upload a CSV file",
    type=["csv"],
    key="crm_csv_uploader",
    help="Upload a CSV containing your CRM or customer records.",
)


# ========================================
# STORE UPLOADED FILE
# ========================================

if uploaded_file is not None:

    try:

        file_bytes = uploaded_file.getvalue()

        st.session_state.uploaded_file_bytes = file_bytes
        st.session_state.uploaded_filename = uploaded_file.name

    except Exception as error:

        st.session_state.uploaded_file_bytes = None
        st.session_state.uploaded_filename = None

        st.error(
            f"Unable to store the uploaded CSV: {error}"
        )


# ========================================
# RESTORE DATASET FROM SESSION STATE
# ========================================

dataframe = None

source_filename = (
    st.session_state.uploaded_filename
)


if st.session_state.uploaded_file_bytes is not None:

    try:

        dataframe = pd.read_csv(
            BytesIO(
                st.session_state.uploaded_file_bytes
            ),
            dtype={"phone": str},
        )

    except Exception as error:

        st.session_state.uploaded_file_bytes = None
        st.session_state.uploaded_filename = None

        st.error(
            f"Unable to read the uploaded CSV: {error}"
        )

        dataframe = None


# ========================================
# DATASET PREVIEW
# ========================================

if dataframe is not None:

    st.success(
        f"CSV loaded successfully — "
        f"{len(dataframe)} records, "
        f"{len(dataframe.columns)} columns."
    )

    with st.expander(
        "Preview uploaded dataset",
        expanded=True,
    ):

        st.dataframe(
            dataframe.head(10),
            use_container_width=True,
        )


# ========================================
# RUN CLEANUP
# ========================================

st.markdown(
    """
    <div class="section-title">
        <span class="section-number">03</span>
        Run CRM intelligence
    </div>
    """,
    unsafe_allow_html=True,
)

run_cleanup = st.button(
    "Run CRM Cleanup",
    type="primary",
    use_container_width=True,
)


if run_cleanup:

    # ------------------------------------
    # VALIDATE CLIENT NAME
    # ------------------------------------

    if not client_name.strip():

        st.error(
            "Please enter a client name."
        )

        st.stop()


    # ------------------------------------
    # VALIDATE DATASET NAME
    # ------------------------------------

    if not dataset_name.strip():

        st.error(
            "Please enter a dataset name."
        )

        st.stop()


    # ------------------------------------
    # VALIDATE CSV
    # ------------------------------------

    if (
        dataframe is None
        or st.session_state.uploaded_file_bytes is None
    ):

        st.error(
            "Please upload a CSV file."
        )

        st.stop()


    # ------------------------------------
    # VALIDATE FILENAME
    # ------------------------------------

    if not source_filename:

        st.error(
            "The uploaded CSV filename could not be detected."
        )

        st.stop()


    # ------------------------------------
    # PROCESS DATASET
    # ------------------------------------

    try:

        with st.status(
            "Processing CRM dataset...",
            expanded=True,
        ) as status:

            st.write(
                "Creating cleanup run..."
            )

            run_directory = create_run_directory(
                client_name
            )


            st.write(
                "Standardizing CRM fields..."
            )

            standardized_dataframe = (
                standardize_dataset(
                    dataframe
                )
            )


            st.write(
                "Validating records..."
            )

            validated_dataframe = (
                validate_dataset(
                    standardized_dataframe
                )
            )


            st.write(
                "Detecting duplicate records..."
            )

            duplicate_dataframe = (
                detect_duplicates(
                    validated_dataframe
                )
            )


            st.write(
                "Calculating data quality..."
            )

            metrics = calculate_quality_metrics(
                duplicate_dataframe
            )

            health = calculate_quality_health(
                duplicate_dataframe
            )


            st.write(
                "Saving CRM records and generating reports..."
            )

            result = export_results(
                duplicate_dataframe,
                client_name,
                dataset_name,
                run_directory,
                source_filename,
            )


            status.update(
                label="CRM processing completed.",
                state="complete",
                expanded=False,
            )


        # --------------------------------
        # SAVE RESULTS TO SESSION
        # --------------------------------

        st.session_state.result = {
            "result": result,
            "dataframe": duplicate_dataframe,
            "metrics": metrics,
            "health": health,
            "run_directory": run_directory,
            "client_name": client_name,
            "dataset_name": dataset_name,
            "source_file": source_filename,
        }

        st.session_state.run_directory = (
            run_directory
        )


        st.success(
            "CRM cleanup and intelligence processing completed."
        )


    except Exception as error:

        st.error(
            f"CRM processing failed: {error}"
        )

        st.stop()


# ========================================
# DISPLAY RESULTS
# ========================================

session_result = st.session_state.result


if session_result is not None:

    result = session_result["result"]

    metrics = session_result["metrics"]

    health = session_result["health"]


    st.divider()


    st.markdown(
        """
        <div class="section-title">
            CRM intelligence results
        </div>
        """,
        unsafe_allow_html=True,
    )


    # ====================================
    # KPI METRICS
    # ====================================

    col1, col2, col3, col4 = st.columns(4)


    with col1:

        st.metric(
            "Total Leads",
            metrics["total_records"],
        )


    with col2:

        st.metric(
            "Clean Records",
            metrics["clean_records"],
        )


    with col3:

        st.metric(
            "Duplicate Records",
            metrics["duplicate_records"],
        )


    with col4:

        st.metric(
            "Review Required",
            metrics["possible_duplicate_records"],
        )


    # ====================================
    # QUALITY HEALTH
    # ====================================

    st.markdown(
        """
        <div class="section-title">
            Data quality health
        </div>
        """,
        unsafe_allow_html=True,
    )


    quality_col1, quality_col2, quality_col3 = (
        st.columns(3)
    )


    with quality_col1:

        st.metric(
            "Overall Health",
            f"{health['overall_health_score']:.1f}%",
        )


    with quality_col2:

        st.metric(
            "Validity",
            f"{health['validity_score']:.1f}%",
        )


    with quality_col3:

        st.metric(
            "Completeness",
            f"{health['completeness_score']:.1f}%",
        )


    # ====================================
    # HEALTH MESSAGE
    # ====================================

    if health["health_status"] == "EXCELLENT":

        st.markdown(
            """
            <div class="success-box">
                <strong>Health status: EXCELLENT</strong><br>
                The dataset passed the current CRM quality checks.
            </div>
            """,
            unsafe_allow_html=True,
        )


    elif health["health_status"] in [
        "GOOD",
        "FAIR",
    ]:

        st.info(
            f"Health status: {health['health_status']}"
        )


    else:

        st.markdown(
            f"""
            <div class="warning-box">
                <strong>
                    Health status: {health['health_status']}
                </strong><br>
                Some records require additional attention.
            </div>
            """,
            unsafe_allow_html=True,
        )


    # ====================================
    # RECORD BREAKDOWN
    # ====================================

    st.markdown(
        """
        <div class="section-title">
            Record breakdown
        </div>
        """,
        unsafe_allow_html=True,
    )


    breakdown_col1, breakdown_col2 = (
        st.columns(2)
    )


    with breakdown_col1:

        st.write("**Validation**")

        st.write(
            f"Clean: {metrics['clean_records']}"
        )

        st.write(
            f"Validation review: {metrics['review_records']}"
        )


    with breakdown_col2:

        st.write("**Duplicate detection**")

        st.write(
            f"Unique: {metrics['unique_records']}"
        )

        st.write(
            f"Confirmed duplicates: "
            f"{metrics['duplicate_records']}"
        )

        st.write(
            f"Review required: "
            f"{metrics['possible_duplicate_records']}"
        )


    # ====================================
    # AI RESULT
    # ====================================

    ai_result = result.get(
        "ai_analysis",
        {},
    )


    st.markdown(
        """
        <div class="section-title">
            AI analysis
        </div>
        """,
        unsafe_allow_html=True,
    )


    ai_col1, ai_col2, ai_col3 = (
        st.columns(3)
    )


    with ai_col1:

        st.metric(
            "AI Attempted",
            ai_result.get("total", 0),
        )


    with ai_col2:

        st.metric(
            "AI Completed",
            ai_result.get("analyzed", 0),
        )


    with ai_col3:

        st.metric(
            "AI Failed",
            ai_result.get("failed", 0),
        )


    if ai_result.get("failed", 0) > 0:

        st.warning(
            "Some AI analyses failed. "
            "The affected CRM leads remain stored safely "
            "and can be analyzed again later."
        )


    # ====================================
    # DELIVERY PACKAGE
    # ====================================

    delivery_package = result.get(
        "client_delivery"
    )


    if delivery_package:

        st.markdown(
            """
            <div class="section-title">
                Client delivery
            </div>
            """,
            unsafe_allow_html=True,
        )


        st.success(
            "Client delivery package generated successfully."
        )


        delivery_directory = Path(
            delivery_package["directory"]
        )


        st.code(
            str(delivery_directory),
            language="text",
        )


        # --------------------------------
        # DOWNLOAD PATHS
        # --------------------------------

        html_path = delivery_package.get(
            "html_report"
        )

        txt_path = delivery_package.get(
            "txt_report"
        )

        cleaned_path = delivery_package.get(
            "cleaned_dataset"
        )

        summary_path = delivery_package.get(
            "delivery_summary"
        )


        # --------------------------------
        # DOWNLOAD BUTTONS
        # --------------------------------

        download_col1, download_col2 = (
            st.columns(2)
        )


        with download_col1:

            if (
                html_path
                and Path(html_path).exists()
            ):

                with open(
                    html_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download HTML Report",
                        data=file.read(),
                        file_name="CRM Intelligence Report.html",
                        mime="text/html",
                        use_container_width=True,
                    )


            if (
                cleaned_path
                and Path(cleaned_path).exists()
            ):

                with open(
                    cleaned_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download Cleaned Dataset",
                        data=file.read(),
                        file_name="Cleaned Dataset.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )


        with download_col2:

            if (
                txt_path
                and Path(txt_path).exists()
            ):

                with open(
                    txt_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download TXT Report",
                        data=file.read(),
                        file_name="CRM Intelligence Report.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )


            if (
                summary_path
                and Path(summary_path).exists()
            ):

                with open(
                    summary_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download Delivery Summary",
                        data=file.read(),
                        file_name="Delivery Summary.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )


    # ====================================
    # RUN INFORMATION
    # ====================================

    st.markdown(
        """
        <div class="section-title">
            Run information
        </div>
        """,
        unsafe_allow_html=True,
    )


    st.write(
        f"**Client:** "
        f"{session_result['client_name']}"
    )


    st.write(
        f"**Dataset:** "
        f"{session_result['dataset_name']}"
    )


    st.write(
        f"**Source file:** "
        f"{session_result['source_file']}"
    )


    st.write(
        f"**Run directory:** "
        f"{session_result['run_directory']}"
    )


# ========================================
# FOOTER
# ========================================

st.divider()


st.markdown(
    """
    <div class="footer">
        CRM Intelligence · Data cleaning · Validation ·
        Duplicate detection · AI analysis · Reporting
    </div>
    """,
    unsafe_allow_html=True,
)