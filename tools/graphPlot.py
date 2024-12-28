import tempfile
import traceback
import subprocess
import os

class PlotHandler:
    """
    Handles Plotly graph generation from Python code.
    """

    @staticmethod
    def generate_plot(code, conn_string):
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as temp_file:
                safe_code = f"""
                                import pandas as pd
                                import plotly.express as px
                                from sqlalchemy import create_engine

                                conn = create_engine('{conn_string}')

                                {code}
                                """
                temp_file.write(safe_code)
                temp_file_path = temp_file.name

            result = subprocess.run(["python", temp_file_path], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Graph generation error: {result.stderr}")

        except Exception as e:
            traceback.print_exc()
            
            raise Exception(f"\033[91mError in graph_plot: {e} \033[0m")

        finally:
            # Clean up the temporary file
            try:
                if 'temp_file_path' in locals():
                    os.remove(temp_file_path)
            except Exception as cleanup_error:
                print("\033[91mError cleaning up temporary file:\033[0m", cleanup_error)