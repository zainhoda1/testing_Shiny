import seaborn as sns
from faicons import icon_svg
from chatlas import ChatAnthropic
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import json
from pathlib import Path
import pyautogui

# Import data from shared.py
from shared import app_dir, df
from shiny import reactive
from shiny.express import input, render, ui
from shinywidgets import render_plotly

# ChatAnthropic() requires an API key from Anthropic.
# See the docs for more information on how to obtain one.
# https://posit-dev.github.io/chatlas/reference/ChatAnthropic.html
_ = load_dotenv()


# Get screen dimensions
screen_width, screen_height = pyautogui.size()

# Calculate right side region (capture right half of screen)
left = int(screen_width // 2)
top = int(screen_height * 0.2)
width = int(screen_width // 2)
height = int(screen_height * 0.8)

# Define the region to capture the right side
region = (left, top, width, height)

# Get the directory where this script is located
#here = Path(__file__).parent
folder_location = Path(__file__).parent
outside_folder = Path(__file__).parent.parent.parent.parent

image_file_name = "image_now_test.png"
image_file_path = outside_folder / image_file_name
summary_file = "summary.json"
summary_file_path = folder_location / summary_file



# Read the JSON file
with open(summary_file_path, 'r') as f:
    data_info = json.load(f)

chat_client = ChatAnthropic(
    system_prompt=f"""You are a helpful assistant for data analysis. 
    
    Dataset context:
    {json.dumps(data_info, indent=2)}
    
    When users ask for analysis or visualizations, provide Python code using:
    - use library seaborn for visualizations
    - The dataframe to use is df.

    
    Make an innovative visualization.
    Always provide simple executable code that works with the available data 
    but do not add show in the code. Show multiple options but each visualization in its own code block 
    """,
)




ui.page_opts(title="Visualization dashboard - 4", fillable=True)

# Initialize Shiny chat component
chat = ui.Chat(id="chat")

            
with ui.layout_columns():
    with ui.card():
        chat.ui(
        messages=["Hello! How can I help you today?"],
        width="100%",
    )
        
                
        # Add code input area
        ui.input_text_area(
            "custom_code",
            "Enter your visualization code:",
            value="""sns.histplot(
    data=df,
    x="body_mass_g",
    hue="species",
    multiple="stack"
)""",
            rows=6,
            width="70%"
        )
        
        ui.input_action_button("execute_code", "Execute Code", class_="btn-primary")



    with ui.card():
        
        @render.plot
        def custom_visualization():
            # Default plot if no custom code is executed
            if input.execute_code() == 0:
                return sns.lineplot(
                    data=df,
                    x="bill_length_mm",
                    y="bill_depth_mm",
                    hue="species",
                )
            
            try:
                # Create a safe environment for code execution
                safe_globals = {
                    'sns': sns,
                    'plt': plt,
                    'pd': pd,
                    'df': df,  # Use the full dataset
                }
                
                # Execute the user's code
                code = input.custom_code()
                
                # Clear any existing plots
                plt.clf()
                
                # Execute the code and capture the result
                exec(code, safe_globals)
                
                # Return the current figure
                return plt.gcf()
                
            except Exception as e:
                # If there's an error, show an error plot
                fig, ax = plt.subplots()
                ax.text(0.5, 0.5, f"Error in code:\n{str(e)}", 
                       ha='center', va='center', transform=ax.transAxes,
                       fontsize=12, color='red', 
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow"))
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                ax.axis('off')
                return fig


        ui.input_action_button("analyze_image", "Analyze Image", class_="btn-primary")

# Generate a response when the user submits a message
@chat.on_user_submit
async def handle_user_input(user_input: str):
    response = await chat_client.stream_async(user_input)
    await chat.append_message_stream(response)



# Handle the analyze image button
@reactive.Effect
@reactive.event(input.analyze_image)
async def analyze_chart():
    image12 = pyautogui.screenshot(region=region)
    image12.save(image_file_path)

    from chatlas import content_image_file
    image_path = image_file_path
    
    if image_path.exists():
        response = await chat_client.stream_async(
            content_image_file(str(image_path), resize='high'),
            "Please analyze this data visualization. Describe what you see, identify any patterns or trends, and provide insights about the data shown."
        )
        await chat.append_message_stream(response)
    else:
        await chat.append_message("Image file not found. Please make sure 'newplot.png' exists in the www/ directory.")