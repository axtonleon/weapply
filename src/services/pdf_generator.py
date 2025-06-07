# src/job_app/services/pdf_generator.py

import logging
from io import BytesIO
from xhtml2pdf import pisa


import markdown  # <-- Import the new library


logger = logging.getLogger(__name__)

def create_pdf_from_text(text_content: str) -> bytes:
    """
    Creates a PDF document from a markdown-formatted string of text.

    This method first converts the markdown text to HTML, then uses xhtml2pdf
    to render the resulting HTML into a polished PDF document.

    Args:
        text_content: The markdown-formatted string to be written to the PDF.

    Returns:
        The content of the generated PDF as a bytes object, or an empty
        bytes object if an error occurs.
    """
    result_file = BytesIO()
    
    try:
        # --- 1. CONVERT MARKDOWN TO HTML ---
        # The 'fenced_code' extension allows for code blocks like ```python ... ```
        # 'tables' allows for markdown tables.
        # 'nl2br' converts single newlines into <br> tags, which is good for address blocks or poems.
        html_content = markdown.markdown(
            text_content, extensions=['fenced_code', 'tables', 'nl2br']
        )

        # --- 2. CREATE THE FULL HTML DOCUMENT WITH CSS ---
        # This CSS provides some basic, professional styling for common markdown elements.
        source_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: a4 portrait;
                    margin: 2cm; /* Set margins for the whole page */
                }}
                body {{
                    font-family: "Helvetica", "Arial", sans-serif;
                    font-size: 11pt;
                    line-height: 1.5;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    font-family: "Times New Roman", serif;
                    line-height: 1.2;
                    margin-bottom: 0.5em;
                }}
                h1 {{ font-size: 22pt; }}
                h2 {{ font-size: 18pt; }}
                h3 {{ font-size: 14pt; }}
                p, ul, ol {{
                    margin-bottom: 1em;
                }}
                ul, ol {{
                    padding-left: 20px;
                }}
                li {{
                    margin-bottom: 0.3em;
                }}
                strong {{
                    font-weight: bold;
                }}
                em {{
                    font-style: italic;
                }}
                pre {{
                    background-color: #f0f0f0;
                    padding: 10px;
                    border: 1px solid #ccc;
                    white-space: pre-wrap; /* Allow code to wrap */
                    word-wrap: break-word;
                }}
                code {{
                    font-family: "Courier New", monospace;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 1em;
                }}
                th, td {{
                    border: 1px solid #999;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # --- 3. GENERATE THE PDF ---
        pisa_status = pisa.CreatePDF(
            src=source_html,
            dest=result_file
        )

        # --- 4. CHECK FOR ERRORS AND RETURN ---
        if pisa_status.err:
            logger.error(f"Failed to generate PDF. Error from xhtml2pdf: {pisa_status.err}")
            return b""
        
        pdf_bytes = result_file.getvalue()
        logger.info(f"Successfully generated a markdown-aware PDF of size {len(pdf_bytes)} bytes.")
        return pdf_bytes

    except Exception as e:
        logger.error(f"An unexpected error occurred during PDF generation: {e}", exc_info=True)
        return b""
    finally:
        result_file.close()