import tkinter as tk
from tkinter import ttk

def select_object(sf):
    # Get object names (custom + 'Account')
    objects = [
        obj['name'] for obj in sf.describe()['sobjects']
        if obj['name'].endswith('__c') or obj['name'].lower() == 'account'
    ]
    selected_object = {'value': None}

    def on_select(event):
        selected_object['value'] = combo.get()
        root.destroy()

    root = tk.Tk()
    root.title("Select Salesforce Object")
    root.geometry("400x120")

    label = ttk.Label(root, text="Choose a Salesforce object:")
    label.pack(pady=10)

    combo = ttk.Combobox(root, values=objects, state="readonly", width=50)
    combo.pack(pady=5)
    combo.bind("<<ComboboxSelected>>", on_select)

    root.mainloop()
    return selected_object['value']
