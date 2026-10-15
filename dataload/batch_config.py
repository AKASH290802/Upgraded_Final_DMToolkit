"""
Batch Configuration Dialog for DataLoader
Handles batch size and parallel processing settings
"""
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox


def select_batch_and_parallel_settings(total_records):
    """
    Select batch size and parallel processing settings
    
    Args:
        total_records (int): Total number of records to process
        
    Returns:
        dict: Configuration settings with keys:
            - batch_size (int): Records per batch
            - parallel_batches (int): Number of parallel batches
            - cancelled (bool): Whether user cancelled the dialog
    """
    settings = {'batch_size': 10000, 'parallel_batches': 1, 'cancelled': False}
    
    def on_select():
        """Handle Select button - confirm the configuration"""
        try:
            # Get batch size
            batch = int(batch_entry.get())
            if batch <= 0:
                tk.messagebox.showerror("Invalid Input", "Batch size must be greater than 0")
                return
            
            # Get parallel batches
            parallel = int(parallel_entry.get())
            if parallel <= 0:
                tk.messagebox.showerror("Invalid Input", "Parallel batches must be greater than 0")
                return
            if parallel > 10:
                result = tk.messagebox.askyesno("Warning", 
                    "More than 10 parallel batches may cause API rate limiting issues.\n\nDo you want to continue?")
                if not result:
                    return
            
            settings['batch_size'] = batch
            settings['parallel_batches'] = parallel
            settings['cancelled'] = False
            settings_win.destroy()
            
        except ValueError:
            tk.messagebox.showerror("Invalid Input", "Please enter valid numbers")
    
    def on_cancel():
        """Handle Cancel button - abort configuration"""
        settings['cancelled'] = True
        settings_win.destroy()
    
    def on_window_close():
        """Handle window close button (X) - just close dialog, don't terminate program"""
        settings['cancelled'] = True
        settings_win.destroy()
    
    def on_parallel_change(*args):
        """Update recommendation based on parallel selection"""
        try:
            parallel = int(parallel_var.get())
            batch_size_val = int(batch_entry.get())
            total_batches = (total_records + batch_size_val - 1) // batch_size_val
            
            if parallel > 1:
                estimated_time_reduction = f"~{parallel}x faster"
                recommendation.config(text=f"Will process {total_batches} batches in groups of {parallel}\n"
                                           f"Estimated speedup: {estimated_time_reduction}")
            else:
                recommendation.config(text="Sequential processing (traditional method)")
        except:
            recommendation.config(text="Enter valid numbers to see recommendations")
    
    def on_batch_change(*args):
        """Update recommendation when batch size changes"""
        on_parallel_change()
    
    root = tk.Tk()
    root.withdraw()
    
    settings_win = tk.Toplevel()
    settings_win.title("Batch Processing Configuration")
    settings_win.geometry("700x600")  # Increased height for better button visibility
    settings_win.grab_set()
    settings_win.protocol("WM_DELETE_WINDOW", on_window_close)  # Handle X button
    settings_win.resizable(False, False)
    settings_win.configure(bg="#f8f9fa")  # Light background color
    
    # Header
    header_frame = tk.Frame(settings_win)
    header_frame.pack(pady=15, padx=20, fill=tk.X)
    tk.Label(header_frame, text="Batch Processing Configuration", 
             font=("Arial", 14, "bold")).pack()
    tk.Label(header_frame, text=f"Total Records: {total_records:,}", 
             font=("Arial", 11)).pack()
    
    # Main content frame
    content_frame = tk.Frame(settings_win)
    content_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Batch Size Setting
    batch_frame = tk.Frame(content_frame)
    batch_frame.pack(pady=10, fill=tk.X)
    tk.Label(batch_frame, text="Records per batch:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
    
    batch_var = tk.StringVar()
    batch_entry = tk.Entry(batch_frame, width=15, font=("Arial", 10), textvariable=batch_var)
    batch_entry.insert(0, "10000")
    batch_entry.pack(anchor=tk.W, pady=5)
    batch_var.trace('w', on_batch_change)
    
    tk.Label(batch_frame, text="Recommended: 5,000 - 10,000 records per batch", 
             font=("Arial", 9), fg="gray").pack(anchor=tk.W)
    
    # Parallel Processing Setting
    parallel_frame = tk.Frame(content_frame)
    parallel_frame.pack(pady=10, fill=tk.X)
    tk.Label(parallel_frame, text="Parallel batches (simultaneous processing):", 
             font=("Arial", 10, "bold")).pack(anchor=tk.W)
    
    parallel_var = tk.StringVar()
    parallel_entry = tk.Entry(parallel_frame, width=15, font=("Arial", 10), textvariable=parallel_var)
    parallel_entry.insert(0, "3")
    parallel_entry.pack(anchor=tk.W, pady=5)
    parallel_var.trace('w', on_parallel_change)
    
    tk.Label(parallel_frame, text="Recommended: 3-5 for large datasets, 1 for sequential processing", 
             font=("Arial", 9), fg="gray").pack(anchor=tk.W)
    
    # Recommendation
    recommendation_frame = tk.Frame(content_frame)
    recommendation_frame.pack(pady=10, fill=tk.X)
    tk.Label(recommendation_frame, text="Processing Plan:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
    recommendation = tk.Label(recommendation_frame, text="", 
                             font=("Arial", 9), fg="blue", justify=tk.LEFT, wraplength=600)
    recommendation.pack(anchor=tk.W, pady=5)
    
    # Performance Info
    info_frame = tk.Frame(content_frame)
    info_frame.pack(pady=10, fill=tk.X)
    tk.Label(info_frame, text="Performance Benefits of Parallel Processing:", 
             font=("Arial", 10, "bold")).pack(anchor=tk.W)
    
    benefits = [
        "• 3x parallel: ~3x faster processing for large datasets",
        "• Better resource utilization and reduced total processing time",
        "• Automatic error handling per batch",
        "• Individual batch files for detailed tracking"
    ]
    
    for benefit in benefits:
        tk.Label(info_frame, text=benefit, font=("Arial", 9)).pack(anchor=tk.W)
    
    tk.Label(info_frame, text="• Note: May hit API rate limits with >5 parallel batches", 
             font=("Arial", 9), fg="orange").pack(anchor=tk.W)
    
    # Initial recommendation
    on_parallel_change()
    
    # Buttons frame - positioned at bottom with proper spacing
    button_frame = tk.Frame(settings_win, bg="#f0f0f0")
    button_frame.pack(pady=15, padx=20, side=tk.BOTTOM, fill=tk.X)
    
    # Create inner frame for button centering
    inner_button_frame = tk.Frame(button_frame, bg="#f0f0f0")
    inner_button_frame.pack(pady=10)
    
    # Select button (green) - Make it more prominent
    select_btn = tk.Button(inner_button_frame, text="✓ Select Configuration", command=on_select, 
                          bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), 
                          width=20, height=2, relief=tk.RAISED, bd=3)
    select_btn.pack(side=tk.LEFT, padx=15)
    
    # Cancel button (red)
    cancel_btn = tk.Button(inner_button_frame, text="✗ Cancel", command=on_cancel, 
                          bg="#f44336", fg="white", font=("Arial", 12, "bold"), 
                          width=15, height=2, relief=tk.RAISED, bd=3)
    cancel_btn.pack(side=tk.LEFT, padx=15)
    
    # Center the window
    settings_win.update_idletasks()
    x = (settings_win.winfo_screenwidth() // 2) - (settings_win.winfo_width() // 2)
    y = (settings_win.winfo_screenheight() // 2) - (settings_win.winfo_height() // 2)
    settings_win.geometry(f"+{x}+{y}")
    
    # Focus on the first entry
    batch_entry.focus_set()
    batch_entry.select_range(0, tk.END)
    
    settings_win.wait_window()
    root.destroy()
    
    return settings


def simple_batch_size_dialog(total_records):
    """
    Simple batch size selection dialog for backward compatibility
    
    Args:
        total_records (int): Total number of records
        
    Returns:
        int or None: Selected batch size
    """
    selected = {'value': None}
    
    def on_select():
        try:
            size = int(entry.get())
            if size > 0:
                selected['value'] = size
                win.destroy()
            else:
                tk.messagebox.showerror("Invalid Input", "Batch size must be greater than 0")
        except ValueError:
            tk.messagebox.showerror("Invalid Input", "Please enter a valid number")
    
    def on_cancel():
        selected['value'] = None
        win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Select Batch Size")
    win.geometry("450x300")  # Increased size for better button visibility
    win.grab_set()
    win.configure(bg="#f8f9fa")  # Light background color
    
    tk.Label(win, text=f"You have {total_records:,} records.", 
             font=("Arial", 11, "bold")).pack(pady=10)
    tk.Label(win, text="Enter batch size for processing:", 
             font=("Arial", 10)).pack(pady=5)
    
    entry = tk.Entry(win, width=20, font=("Arial", 10))
    entry.insert(0, "10000")  # Default value
    entry.pack(pady=10)
    entry.focus_set()
    entry.select_range(0, tk.END)
    
    # Button frame with better visibility
    button_frame = tk.Frame(win, bg="#f0f0f0")
    button_frame.pack(pady=15, fill=tk.X)
    
    # Create inner frame for centering
    inner_frame = tk.Frame(button_frame, bg="#f0f0f0")
    inner_frame.pack()
    
    # Select button with icon and prominence
    tk.Button(inner_frame, text="✓ Select Batch Size", command=on_select, 
             bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), 
             width=18, height=2, relief=tk.RAISED, bd=3).pack(side=tk.LEFT, padx=10)
    
    # Cancel button
    tk.Button(inner_frame, text="✗ Cancel", command=on_cancel, 
             bg="#f44336", fg="white", font=("Arial", 11, "bold"), 
             width=12, height=2, relief=tk.RAISED, bd=3).pack(side=tk.LEFT, padx=10)
    
    win.wait_window()
    root.destroy()
    return selected['value']


def test_dialogs():
    """Test function to verify the dialogs work correctly"""
    print("Testing Advanced Batch Configuration Dialog...")
    result1 = select_batch_and_parallel_settings(15000)
    print(f"Advanced dialog result: {result1}")
    
    print("\nTesting Simple Batch Size Dialog...")
    result2 = simple_batch_size_dialog(8000)
    print(f"Simple dialog result: {result2}")

if __name__ == "__main__":
    test_dialogs()
