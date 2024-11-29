from typing import List, Dict
import docx
import os
import re


class DocxLoader:
    """Handles loading a DOCX file and extracting its content along with metadata."""

    def __init__(self, file_path: str):
        if not os.path.isfile(file_path) or not file_path.endswith(".docx"):
            raise ValueError("Invalid file path or file is not a DOCX.")
        self.file_path = file_path
        self.doc = docx.Document(file_path)  # Load the DOCX file
        self.data = []  # Store extracted data

    def load_content(self) -> List[Dict[str, str]]:
        """
        Load a DOCX file and extract its content into a list of dictionaries.
        
        Each dictionary contains:
        - "content": The text content of a "page".
        - "metadata": Metadata information such as the page number.
        
        Page breaks in the document are used to determine page boundaries.
        
        Args:
            file_path (str): The path to the DOCX file.
        
        Returns:
            List[Dict[str, str]]: A list of dictionaries with text content and metadata.
        """
        page_no = 1  # Initialize page number
        content_lines = []  # Collect content for each page
        for para in self.doc.paragraphs:
            if para.contains_page_break: # If a page break is detected
                if content_lines: # if the page contains any text
                    self._add_page_content(content_lines, page_no)
                    content_lines = []  # Reset content for the next page
                    page_no += 1  # Increment the page number
                else: # otherwise ignore that page
                    page_no+=1


            if para.text.strip():  # Skip empty paragraphs
                #pre-process paragraph text
                # pre_processed_text_stage_1 = re.sub(r'\s+', ' ', para.text)  # Replace multiple spaces with one space
                # final_pre_processed_text = re.sub(r'\n', ' ', pre_processed_text_stage_1)   # Remove line breaks
                content_lines.append(para.text)

        # Add the last page's content if any
        if content_lines:
            self._add_page_content(content_lines, page_no)

        return self.data

    def _add_page_content(self, content_lines: List[str], page_no: int) -> None:
        """Helper method to append page content to the data list."""
        self.data.append({
            "content": "\n".join(content_lines).strip(),
            "metadata": {"page":page_no,"source":str(os.path.join(os.getcwd(),self.file_path))}
            })