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
    page_icon="📊",
    layout="wide",
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

    .main {
        padding-top: 2rem;
    }

    .block-container {
        max-width: 1200px;
        padding-left: 3rem;
        padding-right: 3rem;
    }

    .hero {
        padding: 2rem;
        border-radius: 18px;
        background: linear-gradient(
            135deg,
            #111827,
            #1f2937
        );
        color: white;
        margin-bottom: 2rem;
    }

    .hero h1 {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }

    .hero p {
        font-size: 1.05rem;
        color: #d1d5db;
    }

    .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }

    .metric-card {
        padding: 1.2rem;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
        background: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    .metric-label {
        font-size: 0.85rem;
        color: #6b7280;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #111827;
    }

    .success-box {
        padding: 1rem;
        border-radius: 12px;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #065f46;
    }

    .warning-box {
        padding: 1rem;
        border-radius: 12px;
        background: #fffbeb;
        border: 1px solid #fde68a;
        color: #92400e;
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

st.markdown(
    """
    <div class="hero">
        <h1>CRM Intelligence</h1>
        <p>
            Clean, validate, deduplicate and analyze your CRM data
            before it enters your workflow.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ========================================
# SIDEBAR
# ========================================

with st.sidebar:

    st.header("CRM Cleanup")

    st.write(
        "Upload a customer or lead dataset "
        "to begin the cleanup process."
    )

    st.divider()

    st.caption(
        "Your CRM data is processed through "
        "the existing cleanup and intelligence engine."
    )


# ========================================
# CLIENT INPUT
# ========================================

st.markdown(
    '<div class="section-title">1. Client information</div>',
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
    '<div class="section-title">2. Upload CRM dataset</div>',
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
    '<div class="section-title">3. Run CRM intelligence</div>',
    unsafe_allow_html=True,
)

run_cleanup = st.button(
    "🚀 Run CRM Cleanup",
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

            # ----------------------------
            # CREATE RUN DIRECTORY
            # ----------------------------

            st.write(
                "Creating cleanup run..."
            )

            run_directory = create_run_directory(
                client_name
            )


            # ----------------------------
            # STANDARDIZE
            # ----------------------------

            st.write(
                "Standardizing CRM fields..."
            )

            standardized_dataframe = (
                standardize_dataset(
                    dataframe
                )
            )


            # ----------------------------
            # VALIDATE
            # ----------------------------

            st.write(
                "Validating records..."
            )

            validated_dataframe = (
                validate_dataset(
                    standardized_dataframe
                )
            )


            # ----------------------------
            # DUPLICATE DETECTION
            # ----------------------------

            st.write(
                "Detecting duplicate records..."
            )

            duplicate_dataframe = (
                detect_duplicates(
                    validated_dataframe
                )
            )


            # ----------------------------
            # QUALITY METRICS
            # ----------------------------

            st.write(
                "Calculating data quality..."
            )

            metrics = calculate_quality_metrics(
                duplicate_dataframe
            )

            health = calculate_quality_health(
                duplicate_dataframe
            )


            # ----------------------------
            # EXPORT + CRM + AI + REPORT
            # ----------------------------

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


            # ----------------------------
            # COMPLETE
            # ----------------------------

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
        '<div class="section-title">CRM intelligence results</div>',
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
        '<div class="section-title">Data quality health</div>',
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
        '<div class="section-title">Record breakdown</div>',
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
        '<div class="section-title">AI analysis</div>',
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
            '<div class="section-title">Client delivery</div>',
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
                        "📊 Download HTML Report",
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
                        "📁 Download Cleaned Dataset",
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
                        "📄 Download TXT Report",
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
                        "📋 Download Delivery Summary",
                        data=file.read(),
                        file_name="Delivery Summary.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )


    # ====================================
    # RUN INFORMATION
    # ====================================

    st.markdown(
        '<div class="section-title">Run information</div>',
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


st.caption(
    "CRM Intelligence • Data cleaning • Validation • "
    "Duplicate detection • AI analysis • Reporting"
)