# Error Analyzer: an AI-assisted qualitative error analysis application.

## Tag, compare, and learn faster.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17075450.svg)](https://doi.org/10.5281/zenodo.17075450)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Website](https://img.shields.io/badge/Website-erroranalyzer.com-blue)](https://erroranalyzer.com)
[![Download](https://img.shields.io/badge/Download-Windows%20Installer-blue)](https://github.com/SidahmedKhettab/error-analyzer/releases/latest/download/Error-Analyzer-Setup.exe)

> Copyright © 2025 [**Sid Ahmed KHETTAB**](https://scholar.google.com/citations?user=ABvaWHoAAAAJ&hl=en)  
> Developed during doctoral research at the [**University of Oran 2 Mohamed Ben Ahmed**](https://www.univ-oran2.dz/), under the supervision of [**Prof. Fatima Zohra HARIG BENMOSTEFA**](https://scholar.google.fr/citations?user=MULc2x4AAAAJ&)  
> Licensed under the [**GNU AGPL v3**](https://www.gnu.org/licenses/agpl-3.0)

Error Analyzer is an open-source, advanced web-based platform for qualitative error analysis, annotation, and text correction. Developed within the fields of linguistics, discourse analysis, and semiotics, it is designed to support rigorous academic research. The platform enables researchers to conduct systematic investigations by comparing 'wrong' and 'corrected' texts, applying qualitative coding procedures, categorizing errors, and identifying recurrent linguistic patterns. Assisted by Google’s Natural Language Processing (NLP) and Gemini AI, Error Analyzer integrates computational methods with established analytical frameworks, producing detailed reports that enhance both empirical studies and pedagogical practice. It is intended for linguists, educators, and scholars who seek not only correction but also structured analysis, theoretical insight, and reproducible research outcomes.

## ✨ Features

-   **Intelligent Text Comparison:** Side-by-side comparison of original and corrected texts with a dynamic diff viewer to highlight changes.
-   **Advanced NLP Insights:** Utilize Google NLP to analyze Part-of-Speech (POS) tags, dependencies, entities, tense, number, and surface edits, providing quantitative linguistic insights.
-   **Gemini AI Integration:** Engage with an AI chat assistant for deeper analysis, context-aware explanations, and automated tagging suggestions.
-   **Flexible Tagging & Annotation:** Manually tag and annotate specific errors or linguistic phenomena within texts.
-   **Comprehensive Notes Management:** Create and manage detailed notes associated with text pairs for qualitative analysis.
-   **Dynamic Tag Reporting:** Generate visual reports and charts (e.g., bar charts, pie charts, volcano plots) based on your tags and NLP data, offering actionable insights into error patterns.
-   **Project Management:** Easily create, edit, delete, import, and export projects, maintaining a structured workflow for your analysis tasks.
-   **Multi-language Support:** Seamlessly switch between English and French interfaces for broader accessibility.
-   **Secure User Authentication:** Protect your projects with robust user login and project access control.

## 🚀 Installation

> ⚠️ **Note:**  
> - If you’re on Windows and don’t have experience with Python or development environments, it’s preferable to use the compiled standalone **Windows Installer** available [here](https://github.com/SidahmedKhettab/error-analyzer/releases/latest/download/Error-Analyzer-Setup.exe).  
> - On Linux or macOS, or if you’re an advanced Windows user, follow the steps below to build from source. These instructions are intended for users who are comfortable working with code.

To get Error Analyzer up and running on your local machine, follow these steps:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/SidahmedKhettab/error-analyzer.git
    cd error-analyzer
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Google API Key:**
    Error Analyzer utilizes Google NLP and Gemini AI. You'll need a Google Cloud API Key with access to these services.
    -   Obtain your API Key from the Google Cloud Console.
    -   During the application's setup, you will be prompted to configure this key within the application's settings.

## 💡 Usage

1.  **Run the Application:**
    ```bash
    python main.py
    ```
    The application will typically run on `http://127.0.0.1:5000/`.

2.  **Access in Browser:**
    Open your web browser and navigate to the address provided in the console (e.g., `http://127.0.0.1:5000/`).

3.  **Create or Import a Project:**
    -   Register a new account or log in.
    -   Create a new project and upload your CSV data containing "wrong" and "corrected" text pairs.
    -   Alternatively, import an existing project.

4.  **Perform NLP Analysis:**
    -   Navigate to your project.
    -   Initiate NLP analysis to generate linguistic insights for your text pairs.

5.  **Explore & Analyze:**
    -   Use the intuitive interface to compare texts, apply tags, manage notes, and interact with the AI chat for deeper understanding.
    -   Generate comprehensive Tag Reports to visualize error patterns and linguistic shifts.

## 🤝 Contributing

Contributions are welcome! If you have suggestions for improvements, bug reports, or want to contribute code, please feel free to:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/YourFeature`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'feat: Add new feature'`).
5.  Push to the branch (`git push origin feature/YourFeature`).
6.  Open a Pull Request.

## 📄 License

Licensed under **AGPL-3.0**. See the [LICENSE](LICENSE) file for the complete terms.  

*Summary (not a substitute for the license):*  
You may use and modify this software. If you modify or host it for others to use, you must also make your source code available under the same license.

## 📚 Citation

If you use Error Analyzer in research, please cite:

KHETTAB, S. A. (2025). Error Analyzer (v1.0.0). Zenodo. https://doi.org/10.5281/zenodo.17075450

## 📧 Contact

For inquiries, support, or collaboration regarding Error Analyzer, please feel free to reach out:

ktbsidahmed@gmail.com  
khettab.sidahmed@univ-oran2.dz
