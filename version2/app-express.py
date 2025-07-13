import asyncio
import numpy as np
import cv2
import pyautogui
import os
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import json
import time
from threading import Timer

from faicons import icon_svg
from chatlas import ChatAnthropic, content_image_file
from dotenv import load_dotenv
from pathlib import Path
from shiny import reactive
from shiny.express import input, render, ui

# Import data from shared.py
from shared import app_dir, df
from shiny import reactive
from shiny.express import input, render, ui
from shinywidgets import render_plotly

# Get the directory where this script is located
folder_location = Path(__file__).parent
outside_folder = Path(__file__).parent.parent.parent.parent

# ChatAnthropic() requires an API key from Anthropic.
_ = load_dotenv()

# Get current directory and create screenshots folder
current_dir = os.getcwd()

image_file_name = "image_now_test.png"
json_file_name = "app_settings1.json"

# Save directly to current working directory
#file_path = os.path.join(current_dir, sub_path, image_file_name)
image_file_path = outside_folder / image_file_name
#image_location = "image_now.png"

# Settings file path
settings_file = folder_location / json_file_name
#settings_file = os.path.join(current_dir, sub_path, json_file_name)

# Default settings
default_settings = {
    "mass": 6000,
    "species": ["Adelie", "Gentoo", "Chinstrap"]
}

# Global variables for debouncing
save_timer = None
app_initialized = False

def load_settings():
    """Load settings from file, or return defaults if file doesn't exist"""
    try:
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                loaded = json.load(f)
                print(f"Loaded settings: {loaded}")
                return loaded
    except Exception as e:
        print(f"Error loading settings: {e}")
    
    print(f"Using default settings: {default_settings}")
    return default_settings.copy()

def save_settings_to_file(mass_val, species_val):
    """Save current settings to file"""
    try:
        settings = {
            "mass": mass_val,
            "species": species_val
        }
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"Settings saved to file: {settings}")
    except Exception as e:
        print(f"Error saving settings: {e}")

def debounced_save(mass_val, species_val):
    """Save settings with debouncing to avoid too frequent saves"""
    global save_timer
    
    # Cancel previous timer if it exists
    if save_timer:
        save_timer.cancel()
    
    # Set new timer
    save_timer = Timer(2.0, save_settings_to_file, args=[mass_val, species_val])
    save_timer.start()

# Load initial settings
initial_settings = load_settings()

# Get screen dimensions
screen_width, screen_height = pyautogui.size()

# Calculate right side region (capture right half of screen)
left = int(screen_width // 2.5)
top = int(screen_height * 0.2)
width = int(screen_width // 1.67)
height = int(screen_height * 0.8)

# Define the region to capture the right side
region = (left, top, width, height)

chat_client = ChatAnthropic(
    system_prompt=f"""You are a helpful assistant for data analysis. 
        
    You will be provided an image, provide detailed descriptions of what you see in the visualization,
    including patterns, trends, and insights.""",
)

ui.page_opts(title="visualization dashboard - 2", fillable=True)

# Initialize Shiny chat component
chat = ui.Chat(id="chat")

with ui.sidebar(position="right", bg="#f8f8f8"):
    # Use initial settings loaded from file
    ui.input_slider("mass", "Mass", 2000, 6000, initial_settings["mass"])
    ui.input_checkbox_group(
        "species",
        "Species",
        ["Adelie", "Gentoo", "Chinstrap"],
        selected=initial_settings["species"],
    )
    #ui.input_action_button("save_screenshot", "Save Screenshot")
    ui.input_action_button("analyze_image", "Analyze This Chart", class_="btn-primary mt-2")
    
    # Add manual save button for testing
    #ui.input_action_button("save_settings", "Save Settings", class_="btn-success mt-2")

with ui.layout_columns():
    with ui.card():
        chat.ui(
            messages=["Hello! I can help you analyze data and discuss visualizations. You can ask me to analyze the chart shown on the right!"],
            width="100%",
        )
        
    with ui.card():
        ui.card_header("plotly plot")
        @render_plotly
        def scatterplot():
            color = "species"
            return px.scatter(
                filtered_df(),
                x="bill_length_mm",
                y="bill_depth_mm",
                color=None if color == "none" else color,
                trendline="lowess",
            )

# Initialize the app state
@reactive.Effect
def initialize_app():
    """Mark app as initialized after first render"""
    global app_initialized
    if not app_initialized:
        print("App initialized!")
        app_initialized = True

# Auto-save settings when inputs change (only after app is initialized)
@reactive.Effect
def auto_save_settings():
    """Auto-save settings when inputs change, but only after app initialization"""
    global app_initialized
    
    if not app_initialized:
        return
    
    try:
        mass_val = input.mass()
        species_val = input.species()
        
        # Check if values are actually different from initial settings
        if (mass_val != initial_settings["mass"] or 
            set(species_val) != set(initial_settings["species"])):
            print(f"Input changed - Mass: {mass_val}, Species: {species_val}")
            debounced_save(mass_val, species_val)
    except Exception as e:
        print(f"Error in auto_save_settings: {e}")

# Manual save button
@reactive.Effect
@reactive.event(input.save_settings)
def manual_save():
    """Manual save triggered by button"""
    try:
        mass_val = input.mass()
        species_val = input.species()
        save_settings_to_file(mass_val, species_val)
        print("Manual save completed!")
    except Exception as e:
        print(f"Error in manual save: {e}")


@reactive.calc
def filtered_df():
    filt_df = df[df["species"].isin(input.species())]
    filt_df = filt_df.loc[filt_df["body_mass_g"] < input.mass()]
    return filt_df

# Generate a response when the user submits a message
@chat.on_user_submit
async def handle_user_input(user_input: str):
    from chatlas import content_image_file
    
    # Check if user is asking about the image/chart
    image_keywords = ['chart', 'image', 'plot', 'visualization', 'graph', 'figure']
    if any(keyword in user_input.lower() for keyword in image_keywords):
        # Include the image in the message

        image_path = image_file_path
        if image_path.exists():
            response = await chat_client.stream_async(
                content_image_file(str(image_path), resize='high'),
                user_input
            )
        else:
            response = await chat_client.stream_async(f"{user_input}\n\nNote: The image file was not found at the expected location.")
    else:
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