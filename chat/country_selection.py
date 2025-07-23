"""
Gradio Country Selection App - Standalone
Features: Country selection interface that can be embedded in Django
"""
import gradio as gr
import sys
import os
import uuid
from dotenv import load_dotenv

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, 'envs', '1.env')
load_dotenv(env_path)

# Add the project root to the path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import COUNTRY_CHOICES from the utils module
try:
    from growbal_django.accounts.utils import COUNTRY_CHOICES
    print("✅ Successfully imported country choices from utils module")
except ImportError as e:
    print(f"⚠️ Warning: Could not import country choices from utils: {e}")
    # Fallback to a minimal list if import fails
    COUNTRY_CHOICES = [
        ('USA', 'USA'), ('UK', 'UK'), ('Canada', 'Canada'), 
        ('Australia', 'Australia'), ('Germany', 'Germany')
    ]


def create_country_selection_app():
    """Create country selection interface with same design as main app"""
    
    # Read the logo file
    logo_path = os.path.join(os.path.dirname(__file__), "growbal_logoheader.svg")
    logo_html = ""
    if os.path.exists(logo_path):
        with open(logo_path, 'r') as f:
            logo_content = f.read()
            logo_html = f"""
            <div style="display: flex; justify-content: center; align-items: center; padding: 10px 0; background: #ffffff; margin-bottom: 10px; border-radius: 15px; box-shadow: 0 8px 32px rgba(43, 85, 86, 0.15);">
                <div style="max-width: 200px; height: auto;">
                    {logo_content}
                </div>
            </div>
            """
    
    # Same CSS as main app
    css = """
    /* Global Container Styling */
    .gradio-container {
        max-width: 1400px !important;
        margin: 0 auto !important;
        background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%) !important;
        padding: 20px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 50px rgba(25, 132, 132, 0.1) !important;
    }
    
    /* Button Styling */
    .btn-primary {
        background: linear-gradient(135deg, #198484 0%, #16a6a6 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 12px 24px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(25, 132, 132, 0.2) !important;
    }
    
    .btn-primary:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(25, 132, 132, 0.3) !important;
        background: linear-gradient(135deg, #16a6a6 0%, #198484 100%) !important;
    }
    
    /* Header Styling */
    .app-header {
        text-align: center !important;
        padding: 10px 0 !important;
        background: linear-gradient(135deg, #2b5556 0%, #21908f 100%) !important;
        border-radius: 15px !important;
        margin-bottom: 20px !important;
        box-shadow: 0 8px 32px rgba(25, 132, 132, 0.15) !important;
    }
    
    .app-title {
        color: #ffffff !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        margin-bottom: 4px !important;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.1) !important;
    }
    
    .app-description {
        color: #f8fffe !important;
        font-size: 0.9rem !important;
        font-weight: 400 !important;
        max-width: 600px !important;
        margin: 0 auto !important;
    }
    
    /* Country selection specific */
    .country-section {
        max-width: 600px !important;
        margin: 40px auto !important;
        text-align: center !important;
        padding: 40px !important;
        background: white !important;
        border-radius: 15px !important;
        box-shadow: 0 8px 32px rgba(25, 132, 132, 0.08) !important;
    }

    /* Dropdown Styling */
    .dropdown select {
        border: 2px solid rgba(25, 132, 132, 0.2) !important;
        border-radius: 10px !important;
        padding: 12px !important;
        font-size: 15px !important;
        transition: all 0.3s ease !important;
        background: #ffffff !important;
    }
    
    .dropdown select:focus {
        border-color: #198484 !important;
        box-shadow: 0 0 0 3px rgba(25, 132, 132, 0.1) !important;
        outline: none !important;
    }
    """
    
    # Create custom theme with same colors
    custom_theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.emerald,
        secondary_hue=gr.themes.colors.teal,
        neutral_hue=gr.themes.colors.gray,
        font=[gr.themes.GoogleFont("Inter"), "Arial", "sans-serif"]
    )
    
    with gr.Blocks(title="Growbal Intelligence - Country Selection", theme=custom_theme, css=css, fill_height=True) as interface:
        # Header (same as main app)
        gr.HTML(f"{logo_html}<div class='app-header'><h1 class='app-title'>Growbal Intelligence</h1><p class='app-description'>AI-powered service provider search</p></div>")
        
        # Country selection section
        with gr.Column(elem_classes="country-section"):
            gr.Markdown("## 🌍 Please select a country to begin")
            gr.Markdown("Choose your target country for service provider search")
            
            country_dropdown = gr.Dropdown(
                choices=[choice[1] for choice in COUNTRY_CHOICES],
                label="Select Country",
                info="Choose a country to search for service providers",
                container=True,
                elem_classes="dropdown"
            )
            
            continue_btn = gr.Button(
                "Continue to Search", 
                variant="primary", 
                visible=False,
                size="lg"
            )
            
            status = gr.Markdown("")
            
            # Output component for JavaScript redirect
            redirect_output = gr.HTML(visible=False)
        
        def show_continue(country):
            """Show continue button when country is selected"""
            if country:
                return gr.Button(visible=True), gr.Markdown(f"**Selected:** {country}")
            return gr.Button(visible=False), gr.Markdown("")
        
        def proceed_to_chat(country):
            """Handle proceeding to chat interface"""
            if not country:
                return gr.HTML("Please select a country first.")
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # JavaScript to send message to parent Django window
            redirect_js = f"""
            <script>
                console.log('Sending redirect message to parent');
                
                // Try to send message to parent window (Django)
                if (window.parent && window.parent !== window) {{
                    window.parent.postMessage({{
                        type: 'redirect',
                        url: '/chat/{session_id}/{country}/'
                    }}, '*');
                }}
                
                // For standalone testing, redirect directly
                if (window.parent === window) {{
                    window.location.href = '/chat/{session_id}/{country}/';
                }}
            </script>
            <div style="text-align: center; padding: 20px; color: #198484;">
                <h3>🚀 Redirecting to chat interface...</h3>
                <p><strong>Session:</strong> {session_id}</p>
                <p><strong>Country:</strong> {country}</p>
                <p><em>If redirect doesn't work, you can manually navigate to the chat interface.</em></p>
            </div>
            """
            
            return gr.HTML(redirect_js, visible=True)
        
        # Event handlers
        country_dropdown.change(
            show_continue, 
            inputs=[country_dropdown], 
            outputs=[continue_btn, status]
        )
        
        continue_btn.click(
            proceed_to_chat, 
            inputs=[country_dropdown], 
            outputs=[redirect_output]
        )
        
    return interface


def main():
    """Main function to launch the country selection app"""
    interface = create_country_selection_app()
    
    # Parse command line arguments
    port = 7860
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number, using default 7860")
    
    launch_config = {
        "server_port": port,
        "share": False,
        "debug": True,
        "inbrowser": not ('--no-browser' in sys.argv),
        "quiet": False,
        "favicon_path": None
    }
    
    print(f"🚀 Launching Country Selection App on port {port}")
    interface.launch(**launch_config)


if __name__ == "__main__":
    main()