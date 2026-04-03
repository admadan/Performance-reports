import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

st.set_page_config(layout="wide")
st.title("🚢 Vessel Performance Dashboard")

# =========================
# PATHS (GITHUB SAFE)
# =========================
DATA_DIR = "data"
OUTPUT_DIR = "outputs"
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

# =========================
# UPLOAD FILE
# =========================
file = st.file_uploader("Upload Excel File", type=["xlsx"])

if file:

    excel_path = os.path.join(DATA_DIR, "input.xlsx")
    csv_path = os.path.join(DATA_DIR, "processed.csv")

    # Save Excel
    with open(excel_path, "wb") as f:
        f.write(file.getbuffer())

    # =========================
    # CONVERT TO CSV (FAST LOAD)
    # =========================
    if not os.path.exists(csv_path):
        df = pd.read_excel(excel_path)
        df.to_csv(csv_path, index=False)
        st.success("✅ Converted Excel → CSV")

    # =========================
    # LOAD CSV (FAST)
    # =========================
    @st.cache_data
    def load_data(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()

        df['Date'] = pd.to_datetime(df['Time'])
        df['Month'] = df['Date'].dt.strftime('%b-%y')

        # Smart weather classification
        df['Weather_Class'] = np.where(df['Wind speed Abs'] <= 10, "Good", "Bad")

        # Condition
        df['Condition'] = np.where(df['Sea/Port']=="Port","Port",
                           np.where(df['Ballast/Laden']=="Ballast","Ballast","Laden"))

        return df

    df = load_data(csv_path)

    # =========================
    # FILTERS
    # =========================
    st.sidebar.header("Filters")

    sea_port = st.sidebar.multiselect("Sea/Port", df['Sea/Port'].unique(), df['Sea/Port'].unique())
    bl = st.sidebar.multiselect("Ballast/Laden", df['Ballast/Laden'].unique(), df['Ballast/Laden'].unique())
    weather = st.sidebar.multiselect("Weather", df['Weather_Class'].unique(), df['Weather_Class'].unique())

    filtered_df = df[
        df['Sea/Port'].isin(sea_port) &
        df['Ballast/Laden'].isin(bl) &
        df['Weather_Class'].isin(weather)
    ]

    # =========================
    # ANALYST INPUTS
    # =========================
    st.header("📝 Analyst Commentary")

    intro = st.text_area("Introduction")
    op = st.text_area("Operating Profile Insights")
    raw = st.text_area("Raw Data Insights")
    hull = st.text_area("Hull Performance Insights")

    # =========================
    # CHART FUNCTIONS
    # =========================
    def save_chart(fig, name):
        path = os.path.join(CHART_DIR, name)
        fig.savefig(path, bbox_inches='tight')
        return path

    # Operating Profile
    fig1, ax = plt.subplots()
    filtered_df['Condition'].value_counts().plot.pie(ax=ax, autopct='%1.0f%%')
    pie_path = save_chart(fig1, "pie.png")
    st.pyplot(fig1)

    # Speed vs Consumption
    fig2, ax1 = plt.subplots()
    m = filtered_df.groupby('Month').mean(numeric_only=True)

    ax1.bar(m.index, m['STW (knot)'])
    ax2 = ax1.twinx()
    ax2.plot(m.index, m['ME Total Eq FO Mass Flow (MT/day)'], marker='o')

    speed_path = save_chart(fig2, "speed.png")
    st.pyplot(fig2)

    # Hull Performance
    fig3, ax = plt.subplots()
    gw = filtered_df[(filtered_df['Weather_Class']=="Good") & (filtered_df['Sea/Port']=="Sea")]

    ax.scatter(gw['Date'], gw['Speed loss'])

    if len(gw) > 1:
        x = np.arange(len(gw))
        y = gw['Speed loss'].values
        m_fit, b = np.polyfit(x, y, 1)
        ax.plot(gw['Date'], m_fit*x + b)

    hull_path = save_chart(fig3, "hull.png")
    st.pyplot(fig3)

    # =========================
    # PDF GENERATION
    # =========================
    def generate_pdf():

        pdf_path = os.path.join(OUTPUT_DIR, "report.pdf")

        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()

        story = []

        story.append(Paragraph("Vessel Performance Report", styles['Title']))

        story.append(Paragraph("1. Introduction", styles['Heading2']))
        story.append(Paragraph(intro, styles['BodyText']))

        story.append(Paragraph("2. Operating Profile", styles['Heading2']))
        story.append(Image(pie_path, width=400, height=250))
        story.append(Paragraph(op, styles['BodyText']))

        story.append(PageBreak())

        story.append(Paragraph("3. Raw Data Analysis", styles['Heading2']))
        story.append(Image(speed_path, width=400, height=250))
        story.append(Paragraph(raw, styles['BodyText']))

        story.append(PageBreak())

        story.append(Paragraph("4. Hull Performance", styles['Heading2']))
        story.append(Image(hull_path, width=400, height=250))
        story.append(Paragraph(hull, styles['BodyText']))

        doc.build(story)

        return pdf_path

    # =========================
    # GENERATE BUTTON
    # =========================
    if st.button("📄 Generate Report"):

        with st.spinner("Generating PDF..."):
            pdf_file = generate_pdf()

        st.success("✅ Report saved in /outputs folder")

        # Download button
        with open(pdf_file, "rb") as f:
            st.download_button(
                "⬇️ Download Report",
                f,
                file_name="Vessel_Report.pdf",
                mime="application/pdf"
            )
